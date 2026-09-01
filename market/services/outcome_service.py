"""
outcome_service.py — Live recommendation outcome evaluation service.

Module 11: Backtesting Foundation

Responsibilities:
  - Find active/triggered recommendations needing evaluation.
  - Evaluate entry trigger and stop/target against new bars.
  - Persist RecommendationOutcome records.
  - Update StockRecommendation.status accordingly.
  - Enforce idempotency: same bar evaluated twice = same result, no duplicates.

CRITICAL DESIGN RULES:
  1. Never update a RecommendationOutcome that already exists for the
     same (recommendation, evaluation_version). Create new version if re-eval needed.
  2. Status updates to StockRecommendation only happen through this service
     (for outcome-driven transitions). Lifecycle is preserved.
  3. All ORM queries must use select_for_update() when writing to prevent
     race conditions across Celery workers.
  4. No network calls, no external APIs.
"""
from __future__ import annotations

import logging
import uuid as uuid_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from django.db import transaction
from django.utils import timezone as django_tz

from market.models import OHLCVBar, RecommendationOutcome, StockRecommendation
from market.services.cost_model import CostConfig
from market.services.outcome_engine import (
    EntryEvaluator,
    ExitEvaluator,
    MFEMAECalculator,
    PnLCalculator,
)

logger = logging.getLogger(__name__)

# Data quality warning constants
DQ_NO_BARS       = "NO_BARS_AVAILABLE"
DQ_STALE_BARS    = "STALE_BAR_DATA"
DQ_NO_STOP       = "MISSING_STOP_PRICE"
DQ_NO_TARGET     = "MISSING_TARGET_PRICE"
DQ_HIST_FUND     = "UNAVAILABLE_HISTORICAL: Fundamental data is current, not point-in-time."
DQ_HIST_NEWS     = "UNAVAILABLE_HISTORICAL: News data is current, not point-in-time."

# Evaluation version for current module
EVALUATION_VERSION = 1


class RecommendationOutcomeService:
    """
    Evaluates active and triggered recommendations against market bar data.

    Designed to be called periodically by a Celery task during market hours.
    All writes are idempotent.
    """

    def __init__(
        self,
        cost_config: Optional[CostConfig] = None,
        ambiguity_policy: str = "CONSERVATIVE",
        max_holding_bars: int = 200,
    ):
        self.cost_config = cost_config or CostConfig.no_cost()
        self.ambiguity_policy = ambiguity_policy
        self.max_holding_bars = max_holding_bars
        self._entry_eval = EntryEvaluator()
        self._exit_eval  = ExitEvaluator()
        self._mfe_mae    = MFEMAECalculator()
        self._pnl_calc   = PnLCalculator()

    # ── Public API ────────────────────────────────────────────────────────

    def evaluate_active_recommendations(
        self, as_of: Optional[datetime] = None
    ) -> dict:
        """
        Find all ACTIVE recommendations and evaluate them against available bars.

        Returns a summary dict: {evaluated, skipped, new_outcomes, errors}.
        Only creates outcomes when evaluation is complete (entry decided).
        """
        as_of = as_of or django_tz.now()
        recs = StockRecommendation.objects.filter(
            status="ACTIVE"
        ).select_related("instrument").order_by("generated_at")

        summary = {"evaluated": 0, "skipped": 0, "new_outcomes": 0, "errors": 0}

        for rec in recs:
            try:
                outcome = self._evaluate_one(rec, as_of)
                if outcome is not None:
                    summary["new_outcomes"] += 1
                summary["evaluated"] += 1
            except Exception as exc:
                logger.error(f"OutcomeService: error evaluating rec {rec.id}: {exc}")
                summary["errors"] += 1

        return summary

    def evaluate_single(
        self,
        rec: StockRecommendation,
        as_of: Optional[datetime] = None,
        bars: Optional[List[OHLCVBar]] = None,
    ) -> Optional[RecommendationOutcome]:
        """
        Evaluate a single recommendation. Returns the created outcome or None.

        Args:
            rec:   The recommendation to evaluate.
            as_of: Point-in-time ceiling for bar queries. Default: now().
            bars:  Optional pre-loaded bars (for testing). If None, queries DB.
        """
        as_of = as_of or django_tz.now()
        return self._evaluate_one(rec, as_of, bars=bars)

    # ── Core evaluation ───────────────────────────────────────────────────

    def _evaluate_one(
        self,
        rec: StockRecommendation,
        as_of: datetime,
        bars: Optional[List[OHLCVBar]] = None,
    ) -> Optional[RecommendationOutcome]:
        """Evaluate one recommendation. Creates an outcome record if decided."""
        # Idempotency: skip if outcome already exists for this version
        if RecommendationOutcome.objects.filter(
            recommendation=rec, evaluation_version=EVALUATION_VERSION
        ).exists():
            return None

        # Only evaluate BUY/SELL recs with an entry price
        if rec.signal not in ("BUY", "SELL"):
            return None
        if rec.entry_price is None:
            return None

        dq_warnings = []

        # Determine timeframe for bar queries
        timeframe = rec.timeframe or "1d"

        # Load bars AFTER the recommendation's as_of (PIT safe)
        if bars is None:
            bars = self._load_bars_after(rec, as_of, timeframe)

        if not bars:
            dq_warnings.append(DQ_NO_BARS)

        if rec.stop_price is None:
            dq_warnings.append(DQ_NO_STOP)
        if rec.target_price is None:
            dq_warnings.append(DQ_NO_TARGET)

        # Historical data limitations
        if rec.market_context:
            dq_warnings.append(DQ_HIST_FUND)
        dq_warnings.append(DQ_HIST_NEWS)

        # Evaluate entry
        entry_result = self._entry_eval.evaluate(rec, bars)

        if not entry_result.triggered:
            # Entry never triggered — only create outcome if rec is expired/finalised
            if self._is_recommendation_expired(rec, as_of):
                return self._persist_no_entry_outcome(rec, bars, dq_warnings)
            return None

        # Entry triggered — evaluate exit
        bars_after_entry = bars[entry_result.trigger_bar_index + 1:]
        exit_result = self._exit_eval.evaluate(
            rec, entry_result, bars_after_entry,
            ambiguity_policy=self.ambiguity_policy,
            max_holding_bars=self.max_holding_bars,
        )

        # Only finalise if exit is determined
        if not self._exit_is_final(exit_result):
            return None

        # MFE/MAE
        entry_to_exit_bars = bars[entry_result.trigger_bar_index:]
        mfe_mae = self._mfe_mae.calculate(
            rec.signal, entry_result.trigger_price, entry_to_exit_bars
        )

        # P&L (only when exit price is known)
        pnl = None
        if exit_result.exit_price is not None and entry_result.trigger_price is not None:
            pnl = self._pnl_calc.calculate(
                signal=rec.signal,
                actual_entry_price=entry_result.trigger_price,
                actual_exit_price=exit_result.exit_price,
                stop_price=float(rec.stop_price) if rec.stop_price else None,
                cost_config=self.cost_config,
            )

        # Holding duration
        hold_bars = None
        hold_secs = None
        if entry_result.trigger_bar_index is not None and exit_result.exit_bar_index is not None:
            hold_bars = exit_result.exit_bar_index - 0  # bars from entry to exit
            if entry_result.trigger_timestamp and exit_result.exit_timestamp:
                delta = exit_result.exit_timestamp - entry_result.trigger_timestamp
                hold_secs = int(delta.total_seconds())

        return self._persist_outcome(
            rec=rec,
            entry_result=entry_result,
            exit_result=exit_result,
            mfe_mae=mfe_mae,
            pnl=pnl,
            hold_bars=hold_bars,
            hold_secs=hold_secs,
            bars_evaluated=len(bars),
            dq_warnings=dq_warnings,
        )

    def _load_bars_after(
        self, rec: StockRecommendation, as_of: datetime, timeframe: str
    ) -> List[OHLCVBar]:
        """Load PIT-safe bars after the recommendation's as_of, up to as_of."""
        return list(
            OHLCVBar.objects.filter(
                instrument=rec.instrument,
                timeframe=timeframe,
                timestamp__gt=rec.as_of,
                timestamp__lte=as_of,
            ).order_by("timestamp")
        )

    def _is_recommendation_expired(
        self, rec: StockRecommendation, as_of: datetime
    ) -> bool:
        """True if this recommendation can no longer trigger (session/time expired)."""
        if rec.expires_at and as_of >= rec.expires_at:
            return True
        # Daily/delivery: consider expired after 30 days without trigger
        if rec.horizon != "INTRADAY":
            from datetime import timedelta
            if as_of >= rec.as_of + timedelta(days=30):
                return True
        return False

    def _exit_is_final(self, exit_result) -> bool:
        """True when the exit evaluation has reached a terminal state."""
        return exit_result.exit_reason in (
            "TARGET_HIT", "TARGET_2_HIT", "STOP_HIT",
            "EXPIRED_SESSION", "EXPIRED_MAX_DURATION",
            "AMBIGUOUS_INTRABAR", "CANCELLED",
        )

    # ── Persistence ───────────────────────────────────────────────────────

    @transaction.atomic
    def _persist_no_entry_outcome(
        self, rec, bars, dq_warnings: List[str]
    ) -> RecommendationOutcome:
        """Create an outcome record for a recommendation where entry never triggered."""
        outcome = RecommendationOutcome.objects.create(
            recommendation=rec,
            evaluation_version=EVALUATION_VERSION,
            entry_triggered=False,
            entry_timestamp=None,
            actual_entry_price=None,
            exit_reason="NO_ENTRY",
            exit_timestamp=None,
            actual_exit_price=None,
            target_hit=False,
            stop_hit=False,
            ambiguous_intrabar=False,
            bars_evaluated=len(bars),
            data_quality_warnings=dq_warnings,
        )
        # Update rec status
        StockRecommendation.objects.filter(pk=rec.pk, status="ACTIVE").update(
            status="EXPIRED",
            status_updated_at=django_tz.now(),
        )
        logger.info(
            f"OutcomeService: NO_ENTRY outcome created for rec {rec.id} ({rec.instrument.symbol})"
        )
        return outcome

    @transaction.atomic
    def _persist_outcome(
        self, rec, entry_result, exit_result, mfe_mae, pnl,
        hold_bars, hold_secs, bars_evaluated, dq_warnings
    ) -> RecommendationOutcome:
        """Create the full outcome record and update the recommendation status."""
        # Determine new recommendation status
        new_status = self._map_exit_to_status(exit_result)

        outcome = RecommendationOutcome.objects.create(
            recommendation=rec,
            evaluation_version=EVALUATION_VERSION,
            entry_triggered=True,
            entry_timestamp=entry_result.trigger_timestamp,
            actual_entry_price=Decimal(str(round(entry_result.trigger_price, 4)))
                               if entry_result.trigger_price else None,
            exit_reason=exit_result.exit_reason,
            exit_timestamp=exit_result.exit_timestamp,
            actual_exit_price=Decimal(str(round(exit_result.exit_price, 4)))
                              if exit_result.exit_price else None,
            gross_pnl_absolute=Decimal(str(pnl.gross_pnl_absolute)) if pnl and pnl.gross_pnl_absolute is not None else None,
            gross_pnl_percent=Decimal(str(pnl.gross_pnl_percent)) if pnl and pnl.gross_pnl_percent is not None else None,
            cost_absolute=Decimal(str(pnl.cost_absolute)) if pnl and pnl.cost_absolute is not None else None,
            net_pnl_absolute=Decimal(str(pnl.net_pnl_absolute)) if pnl and pnl.net_pnl_absolute is not None else None,
            net_pnl_percent=Decimal(str(pnl.net_pnl_percent)) if pnl and pnl.net_pnl_percent is not None else None,
            risk_amount=Decimal(str(pnl.risk_amount)) if pnl and pnl.risk_amount is not None else None,
            r_multiple=Decimal(str(pnl.r_multiple)) if pnl and pnl.r_multiple is not None else None,
            target_hit=exit_result.target_hit,
            stop_hit=exit_result.stop_hit,
            ambiguous_intrabar=exit_result.ambiguous_intrabar,
            max_favorable_excursion=Decimal(str(mfe_mae.max_favorable_excursion))
                                    if mfe_mae.max_favorable_excursion is not None else None,
            max_adverse_excursion=Decimal(str(mfe_mae.max_adverse_excursion))
                                   if mfe_mae.max_adverse_excursion is not None else None,
            holding_duration_bars=hold_bars,
            holding_duration_seconds=hold_secs,
            bars_evaluated=bars_evaluated,
            data_quality_warnings=dq_warnings,
        )

        # Update recommendation status (only from ACTIVE or TRIGGERED)
        StockRecommendation.objects.filter(
            pk=rec.pk, status__in=["ACTIVE", "TRIGGERED"]
        ).update(status=new_status, status_updated_at=django_tz.now())

        logger.info(
            f"OutcomeService: outcome={exit_result.exit_reason} "
            f"rec={rec.id} ({rec.instrument.symbol}) "
            f"r={pnl.r_multiple if pnl else 'N/A'}"
        )
        return outcome

    @staticmethod
    def _map_exit_to_status(exit_result) -> str:
        mapping = {
            "TARGET_HIT":           "TARGET_HIT",
            "TARGET_2_HIT":         "TARGET_HIT",
            "STOP_HIT":             "STOPPED",
            "EXPIRED_SESSION":      "EXPIRED",
            "EXPIRED_MAX_DURATION": "EXPIRED",
            "AMBIGUOUS_INTRABAR":   "AMBIGUOUS_INTRABAR",
            "CANCELLED":            "CANCELLED",
            "NO_ENTRY":             "EXPIRED",
        }
        return mapping.get(exit_result.exit_reason, "EXPIRED")
