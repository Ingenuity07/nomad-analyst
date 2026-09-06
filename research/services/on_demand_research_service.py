import logging
import time
from datetime import timedelta
from typing import Dict, Any, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from research.models import ResearchRun, ResearchReport
from research.schemas import StructuredResearchOutput
from research.prompts import NOMAD_RESEARCH_SYSTEM_PROMPT, build_research_user_prompt
from research.services.evidence_builder import ResearchEvidencePackageBuilder
from research.services.delta_service import ResearchDeltaService

from llm.router import IntelligentRouter, llm_service
from llm.contracts import LLMRequest, LLMResult
from llm.enums import LLMOperation, LLMComplexity
from market.models import Instrument

logger = logging.getLogger(__name__)

# Configurable caching and lock settings
INTRADAY_CACHE_MINUTES = 30
LONG_TERM_CACHE_MINUTES = 24 * 60 # 24 hours
LOCK_TIMEOUT_SECONDS = 60


class OnDemandResearchService:
    """
    Coordinates Phase 17E on-demand research:
    1. Strictly user-initiated (0 background calls).
    2. Reuses existing research when available (0 LLM calls).
    3. Exactly ONE LLM call when new research or explicit refresh is executed.
    4. Concurrency locking to prevent duplicate concurrent requests.
    5. Purely deterministic delta calculation.
    """

    def __init__(
        self,
        provider: Optional[IntelligentRouter] = None,
        evidence_builder: Optional[ResearchEvidencePackageBuilder] = None,
        delta_service: Optional[ResearchDeltaService] = None
    ):
        self.router = provider or llm_service
        self.evidence_builder = evidence_builder or ResearchEvidencePackageBuilder()
        self.delta_service = delta_service or ResearchDeltaService()

    def examine(
        self,
        symbol: str,
        mode: str = "INTRADAY",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point for user-initiated stock examination.
        Checks cache/persistence first; calls LLM exactly once if not cached or refreshed.
        """
        clean_symbol = symbol.strip().upper()
        mode_upper = mode.strip().upper()
        if mode_upper not in ("INTRADAY", "LONG_TERM", "GENERAL"):
            mode_upper = "INTRADAY"

        # 1. Check if reusable completed research exists
        if not force_refresh:
            existing_run = self.get_latest_research(clean_symbol, mode_upper)
            if existing_run and existing_run.status == "completed":
                cache_ttl = INTRADAY_CACHE_MINUTES if mode_upper == "INTRADAY" else LONG_TERM_CACHE_MINUTES
                age = timezone.now() - existing_run.started_at
                if age < timedelta(minutes=cache_ttl):
                    logger.info(f"Reusing existing research for {clean_symbol} [{mode_upper}] (id={existing_run.id}). Zero LLM calls.")
                    delta = self.delta_service.compute_delta(existing_run)
                    return {
                        "research_run": existing_run,
                        "reused": True,
                        "delta": delta,
                        "llm_calls_made": 0
                    }

        # 2. Acquire concurrency lock to avoid duplicate parallel executions
        lock_key = f"nomad:research_lock:{clean_symbol}:{mode_upper}"
        acquired = cache.add(lock_key, "locked", timeout=LOCK_TIMEOUT_SECONDS)
        if not acquired:
            # Check if there is a currently running research task
            running_run = ResearchRun.objects.filter(
                symbol__iexact=clean_symbol,
                research_mode=mode_upper,
                status="running"
            ).order_by('-started_at').first()
            if running_run:
                logger.info(f"Research currently running for {clean_symbol} [{mode_upper}] (id={running_run.id}).")
                return {
                    "research_run": running_run,
                    "reused": True,
                    "delta": None,
                    "llm_calls_made": 0
                }
            raise RuntimeError(f"A research request for {clean_symbol} [{mode_upper}] is already in progress.")

        try:
            # 3. Build deterministic evidence package
            start_time = time.time()
            evidence_package = self.evidence_builder.build_package(clean_symbol, mode=mode_upper)

            # Resolve instrument if available
            instrument = Instrument.objects.filter(symbol__iexact=clean_symbol).first()

            # Create initial ResearchRun record
            opp_info = evidence_package.get("opportunity", {})
            mkt_info = evidence_package.get("market_context", {})

            research_run = ResearchRun.objects.create(
                symbol=clean_symbol,
                research_mode=mode_upper,
                research_type="ON_DEMAND",
                instrument=instrument,
                status="running",
                query=f"Examine {clean_symbol} in {mode_upper} mode",
                evidence_snapshot=evidence_package,
                evidence_hash=evidence_package.get("evidence_hash", ""),
                opportunity_score_at_research=opp_info.get("score"),
                opportunity_state_at_research=opp_info.get("state", ""),
                market_context_snapshot=mkt_info,
            )

            # 4. Dispatch exactly ONE LLM call via IntelligentRouter
            prompt = build_research_user_prompt(clean_symbol, mode_upper, evidence_package)
            request = LLMRequest(
                operation=LLMOperation.GENERATE,
                complexity=LLMComplexity.COMPLEX,
                prompt=prompt,
                system_prompt=NOMAD_RESEARCH_SYSTEM_PROMPT,
                schema=StructuredResearchOutput
            )

            logger.info(f"Dispatching single LLM call for {clean_symbol} [{mode_upper}] (run_id={research_run.id})")
            llm_result: LLMResult = self.router.execute(request)

            duration_ms = int((time.time() - start_time) * 1000)

            if not llm_result.is_success() or not llm_result.output:
                error_msg = llm_result.error_message or "LLM generation failed or returned invalid schema."
                err_cat = str(llm_result.error_category or "UNKNOWN")
                logger.error(f"Research run failed for {clean_symbol}: {error_msg} (cat={err_cat})")

                research_run.status = "failed"
                research_run.error_message = error_msg
                research_run.error_category = err_cat
                research_run.duration_ms = duration_ms
                research_run.completed_at = timezone.now()
                research_run.save()

                return {
                    "research_run": research_run,
                    "reused": False,
                    "delta": None,
                    "error": error_msg,
                    "llm_calls_made": 1
                }

            # 5. Persist validated structured output
            structured_data = llm_result.output.model_dump() if hasattr(llm_result.output, "model_dump") else llm_result.output

            research_run.research_output = structured_data
            research_run.model_name = llm_result.model or ""
            research_run.provider = llm_result.provider or ""
            research_run.tokens_used = llm_result.usage.get("total_tokens", 0)
            research_run.duration_ms = duration_ms
            research_run.status = "completed"
            research_run.completed_at = timezone.now()
            research_run.save()

            # Create backward-compatible ResearchReport entry
            ResearchReport.objects.create(
                research_run=research_run,
                title=f"{clean_symbol} {mode_upper} Research Report",
                summary=structured_data.get("summary", ""),
                analysis=structured_data.get("analyst_interpretation", "")
            )

            # Compute initial delta
            delta = self.delta_service.compute_delta(research_run)

            return {
                "research_run": research_run,
                "reused": False,
                "delta": delta,
                "llm_calls_made": 1
            }

        finally:
            cache.delete(lock_key)

    def refresh(self, research_run_id: str) -> Dict[str, Any]:
        """
        Explicitly triggers a fresh research examination for a given run's symbol and mode.
        Guaranteed to execute exactly 1 new LLM call.
        """
        run = ResearchRun.objects.filter(id=research_run_id).first()
        if not run:
            raise ValueError(f"Research run '{research_run_id}' not found.")

        return self.examine(
            symbol=run.symbol,
            mode=run.research_mode,
            force_refresh=True
        )

    def get_latest_research(self, symbol: str, mode: str = "INTRADAY") -> Optional[ResearchRun]:
        """Returns the most recent completed research run for the symbol and mode."""
        return ResearchRun.objects.filter(
            symbol__iexact=symbol,
            research_mode=mode,
            status="completed"
        ).order_by('-started_at').first()

    def get_research_by_id(self, research_run_id: str) -> Optional[ResearchRun]:
        """Retrieves a research run by its UUID."""
        return ResearchRun.objects.filter(id=research_run_id).first()
