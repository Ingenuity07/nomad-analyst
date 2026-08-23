"""
recommendation_service.py — Orchestrates signal generation + persistence for Module 8.

Responsibilities:
  1. Call SignalEngine for a single instrument and persist the draft as a
     StockRecommendation record (append-only, never overwrites history).
  2. Provide batch scan across a universe.
  3. Expose recommendation lifecycle transitions (status updates only).

The LLM never touches this module.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from django.utils import timezone as django_timezone
from django.db import transaction

from market.models import (
    Instrument, Universe, UniverseMembership, StockRecommendation
)
from market.services.signal_engine import SignalEngine, RecommendationDraft
from market.signal_enums import (
    SignalDirection, SignalHorizon, RecommendationStatus
)

logger = logging.getLogger(__name__)


def _to_decimal(val: Optional[float]) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(round(val, 4)))
    except Exception:
        return None


class RecommendationService:
    """
    Orchestration service for generating and persisting StockRecommendations.

    Design rules:
      - append_only: every .generate_and_save() creates a NEW record
      - lifecycle transitions (.update_status()) only update mutable fields
      - LLM explanation (.save_explanation()) only updates llm_explanation
    """

    def __init__(self):
        self.engine = SignalEngine()

    # ── Single instrument ──────────────────────────────────────────────────────

    def generate_and_save(
        self,
        instrument: Instrument,
        horizon: str,
        as_of: Optional[Any] = None
    ) -> StockRecommendation:
        """
        Generate a deterministic recommendation for an instrument and persist it.
        Returns the newly created StockRecommendation record.
        """
        draft: RecommendationDraft = self.engine.generate_recommendation(
            instrument=instrument,
            horizon=horizon,
            as_of=as_of
        )

        rec = StockRecommendation(
            instrument=instrument,
            horizon=draft.horizon,
            signal=draft.signal,
            setup_type=draft.setup_type,
            as_of=draft.as_of,
            entry_type=draft.entry_type,
            entry_price=_to_decimal(draft.entry_price),
            entry_condition=draft.entry_condition,
            stop_price=_to_decimal(draft.stop_price),
            stop_method=draft.stop_method,
            invalidation_reason=draft.invalidation_reason,
            target_price=_to_decimal(draft.target_price),
            target_method=draft.target_method,
            risk=_to_decimal(draft.risk),
            reward=_to_decimal(draft.reward),
            risk_reward_ratio=_to_decimal(draft.risk_reward_ratio),
            confidence=draft.confidence,
            confidence_components=draft.confidence_components,
            market_context=draft.market_context,
            sector_context=draft.sector_context,
            supporting_factors=draft.supporting_factors,
            risk_factors=draft.risk_factors,
            setup_details=draft.setup_details,
            data_quality=draft.data_quality,
            status=draft.status,
            calculation_version=draft.calculation_version,
        )
        rec.save()
        logger.info(
            f"RecommendationService: saved {rec.signal} [{rec.horizon}] "
            f"for {instrument.symbol} @ {rec.as_of.date()} (id={rec.id})"
        )
        return rec

    # ── Batch universe scan ────────────────────────────────────────────────────

    def scan_and_recommend(
        self,
        universe_name: str,
        horizon: str,
        as_of: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Scan all active members of a universe and generate recommendations.
        Returns a summary dict with counts and any errors.
        """
        universe = Universe.objects.filter(name=universe_name, is_active=True).first()
        if not universe:
            logger.warning(f"RecommendationService: Universe '{universe_name}' not found.")
            return {"universe": universe_name, "status": "UNIVERSE_NOT_FOUND", "count": 0}

        as_of_dt = self.engine._parse_as_of_internal(as_of)

        # Get active members
        members = list(
            UniverseMembership.objects.filter(
                universe=universe,
                added_at__lte=as_of_dt,
            ).filter(
                removed_at__isnull=True
            ).select_related('instrument__company')
        )

        total = len(members)
        created = 0
        errors = 0
        by_signal: Dict[str, int] = {}

        for membership in members:
            try:
                rec = self.generate_and_save(
                    instrument=membership.instrument,
                    horizon=horizon,
                    as_of=as_of_dt
                )
                by_signal[rec.signal] = by_signal.get(rec.signal, 0) + 1
                created += 1
            except Exception as e:
                logger.error(
                    f"RecommendationService: Failed for {membership.instrument.symbol}: {e}",
                    exc_info=True
                )
                errors += 1

        logger.info(
            f"RecommendationService: scan done for {universe_name} [{horizon}]: "
            f"{created}/{total} processed, {errors} errors"
        )
        return {
            "universe": universe_name,
            "horizon": horizon,
            "as_of": as_of_dt.isoformat(),
            "total_members": total,
            "generated": created,
            "errors": errors,
            "signal_summary": by_signal
        }

    # ── Lifecycle transitions ─────────────────────────────────────────────────

    def update_status(
        self,
        recommendation: StockRecommendation,
        new_status: str,
        reason: Optional[str] = None
    ) -> StockRecommendation:
        """
        Update the lifecycle status of a recommendation.
        Only the status and status_updated_at fields are modified.
        Deterministic fields (entry/stop/target/signal) are NEVER touched.
        """
        now = django_timezone.now()
        recommendation.status = new_status
        recommendation.status_updated_at = now
        recommendation.save(update_fields=["status", "status_updated_at"])
        logger.info(
            f"RecommendationService: {recommendation.instrument.symbol} status "
            f"→ {new_status} @ {now.isoformat()}"
        )
        return recommendation

    def expire_old_active_recommendations(self, max_age_days: int = 10) -> int:
        """
        Mark ACTIVE recommendations older than max_age_days as EXPIRED.
        Only called by scheduled tasks, not by the LLM.
        """
        cutoff = django_timezone.now() - timedelta(days=max_age_days)
        updated = StockRecommendation.objects.filter(
            status="ACTIVE",
            generated_at__lt=cutoff
        ).update(
            status=RecommendationStatus.EXPIRED.value,
            status_updated_at=django_timezone.now()
        )
        if updated:
            logger.info(f"RecommendationService: expired {updated} stale recommendations.")
        return updated

    # ── LLM explanation (safe write-back) ─────────────────────────────────────

    def save_explanation(
        self,
        recommendation: StockRecommendation,
        explanation: str
    ) -> StockRecommendation:
        """
        Save the LLM-generated explanation text.
        This is the ONLY field the LLM is ever allowed to write.
        Deterministic fields are never touched.
        """
        recommendation.llm_explanation = explanation
        recommendation.save(update_fields=["llm_explanation"])
        return recommendation

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_active_recommendations(
        self,
        horizon: Optional[str] = None,
        signal: Optional[str] = None,
        limit: int = 50
    ) -> List[StockRecommendation]:
        """Return ACTIVE recommendations, filtered by optional horizon/signal."""
        qs = StockRecommendation.objects.filter(
            status="ACTIVE"
        ).select_related('instrument__company').order_by('-generated_at')

        if horizon:
            qs = qs.filter(horizon=horizon)
        if signal:
            qs = qs.filter(signal=signal)

        return list(qs[:limit])

    def get_recommendations_for_symbol(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[StockRecommendation]:
        """Return the most recent N recommendations for a ticker."""
        return list(
            StockRecommendation.objects.filter(
                instrument__symbol=symbol
            ).select_related('instrument__company')
            .order_by('-generated_at')[:limit]
        )
