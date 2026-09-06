import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.utils import timezone

from research.models import ResearchRun
from market.models import (
    Instrument,
    IntradayOpportunitySnapshot,
    StockIntradayContext,
    MarketContextSnapshot
)

logger = logging.getLogger(__name__)

# Configurable freshness thresholds
STALENESS_AGE_MINUTES = 30
AGING_AGE_MINUTES = 15
SIGNIFICANT_SCORE_CHANGE = 10.0


class ResearchDeltaService:
    """
    Deterministically computes the delta between the research run snapshot and
    the current live market/opportunity state with ZERO LLM calls.
    """

    def compute_delta(self, research_run: ResearchRun) -> Dict[str, Any]:
        now = timezone.now()
        snapshot = research_run.evidence_snapshot or {}
        mode = research_run.research_mode
        symbol = research_run.symbol

        # Baseline snapshot values
        snap_opp = snapshot.get("opportunity", {})
        snap_market = snapshot.get("market_context", {})
        snap_stock = snapshot.get("stock_context", {})
        snap_sector = snapshot.get("sector_context", {})

        snap_score = research_run.opportunity_score_at_research or snap_opp.get("score")
        snap_rank = snap_opp.get("rank")
        snap_state = research_run.opportunity_state_at_research or snap_opp.get("state", "UNKNOWN")
        snap_regime = snap_market.get("regime", "UNKNOWN")
        snap_sector_rank = snap_sector.get("rank")
        snap_momentum_5m = snap_stock.get("momentum_5m")
        snap_vwap_diff = snap_stock.get("distance_from_vwap")
        snap_rs_market = snap_stock.get("relative_strength_vs_market")

        # Current live state
        curr_opp = IntradayOpportunitySnapshot.objects.filter(
            symbol__iexact=symbol
        ).order_by('-timestamp').first()

        curr_market = MarketContextSnapshot.objects.all().order_by('-as_of').first()

        instrument = research_run.instrument or Instrument.objects.filter(symbol__iexact=symbol).first()
        curr_stock_ctx = None
        if instrument:
            curr_stock_ctx = StockIntradayContext.objects.filter(
                instrument=instrument
            ).order_by('-timestamp').first()

        # Current values
        curr_score = float(curr_opp.score) if curr_opp and curr_opp.score is not None else None
        curr_rank = curr_opp.rank if curr_opp else None
        curr_state = curr_opp.state if curr_opp else "UNKNOWN"
        curr_regime = (getattr(curr_market, 'market_regime', None) or getattr(curr_market, 'regime', 'UNKNOWN')) if curr_market else "UNKNOWN"

        curr_sector_rank = None
        if curr_market and curr_market.sector_rankings and snap_sector.get("sector"):
            for item in curr_market.sector_rankings:
                sec_name = item.get("sector") or item.get("sector_name") or ""
                if snap_sector.get("sector", "").lower() in sec_name.lower():
                    curr_sector_rank = item.get("rank")
                    break

        curr_momentum_5m = None
        curr_vwap_diff = None
        curr_rs_market = None
        if curr_stock_ctx:
            curr_momentum_5m = float(curr_stock_ctx.momentum_5m) if curr_stock_ctx.momentum_5m is not None else None
            curr_vwap_diff = float(curr_stock_ctx.distance_from_vwap) if curr_stock_ctx.distance_from_vwap is not None else None
            curr_rs_market = float(curr_stock_ctx.relative_strength_vs_market) if curr_stock_ctx.relative_strength_vs_market is not None else None
        elif curr_opp and curr_opp.metrics:
            curr_momentum_5m = curr_opp.metrics.get("momentum_5m")
            curr_vwap_diff = curr_opp.metrics.get("vwap_diff_pct")
            curr_rs_market = curr_opp.metrics.get("relative_strength_vs_market")

        # Compute numerical and categorical changes
        score_change = (curr_score - snap_score) if (curr_score is not None and snap_score is not None) else 0.0
        rank_change = (curr_rank - snap_rank) if (curr_rank is not None and snap_rank is not None) else 0
        state_changed = (curr_state != snap_state) and snap_state != "UNKNOWN"
        regime_changed = (curr_regime != snap_regime) and snap_regime != "UNKNOWN"
        sector_rank_change = (curr_sector_rank - snap_sector_rank) if (curr_sector_rank is not None and snap_sector_rank is not None) else 0

        momentum_change = (curr_momentum_5m - snap_momentum_5m) if (curr_momentum_5m is not None and snap_momentum_5m is not None) else 0.0
        vwap_diff_change = (curr_vwap_diff - snap_vwap_diff) if (curr_vwap_diff is not None and snap_vwap_diff is not None) else 0.0
        rs_change = (curr_rs_market - snap_rs_market) if (curr_rs_market is not None and snap_rs_market is not None) else 0.0

        # Freshness / Staleness assessment
        elapsed_seconds = (now - research_run.started_at).total_seconds()
        elapsed_minutes = round(elapsed_seconds / 60, 1)

        staleness_reasons: List[str] = []
        freshness_tier = "FRESH"

        if elapsed_minutes >= STALENESS_AGE_MINUTES:
            staleness_reasons.append(f"Analysis was generated {int(elapsed_minutes)} minutes ago")
            freshness_tier = "STALE"
        elif elapsed_minutes >= AGING_AGE_MINUTES:
            staleness_reasons.append(f"Analysis is aging ({int(elapsed_minutes)} minutes old)")
            freshness_tier = "AGING"

        if abs(score_change) >= SIGNIFICANT_SCORE_CHANGE:
            sign = "+" if score_change > 0 else ""
            staleness_reasons.append(f"Opportunity score shifted significantly ({sign}{score_change:.1f} pts)")
            freshness_tier = "STALE" if freshness_tier != "FRESH" else "AGING"

        if state_changed:
            staleness_reasons.append(f"Opportunity state changed from {snap_state} to {curr_state}")
            freshness_tier = "STALE" if freshness_tier != "FRESH" else "AGING"

        if regime_changed:
            staleness_reasons.append(f"Market regime changed from {snap_regime} to {curr_regime}")
            freshness_tier = "STALE" if freshness_tier != "FRESH" else "AGING"

        # Change summaries
        changes_detected = []
        if score_change != 0:
            changes_detected.append(f"Score: {snap_score:.1f} → {curr_score:.1f} ({'+' if score_change > 0 else ''}{score_change:.1f})")
        if rank_change != 0:
            changes_detected.append(f"Rank: #{snap_rank} → #{curr_rank}")
        if state_changed:
            changes_detected.append(f"State: {snap_state} → {curr_state}")
        if regime_changed:
            changes_detected.append(f"Market Regime: {snap_regime} → {curr_regime}")
        if sector_rank_change != 0:
            changes_detected.append(f"Sector Rank: #{snap_sector_rank} → #{curr_sector_rank}")
        if momentum_change != 0:
            changes_detected.append(f"5m Momentum: {snap_momentum_5m:.2f}% → {curr_momentum_5m:.2f}%")
        if vwap_diff_change != 0:
            changes_detected.append(f"vs VWAP: {snap_vwap_diff:.2f}% → {curr_vwap_diff:.2f}%")

        return {
            "research_id": str(research_run.id),
            "symbol": symbol,
            "mode": mode,
            "research_timestamp": research_run.started_at.isoformat(),
            "evaluated_at": now.isoformat(),
            "age_minutes": elapsed_minutes,
            "freshness": freshness_tier,
            "staleness_reasons": staleness_reasons,
            "has_material_changes": len(staleness_reasons) > 0 or len(changes_detected) > 0,
            "changes_summary": changes_detected,
            "basis": {
                "score": snap_score,
                "rank": snap_rank,
                "state": snap_state,
                "market_regime": snap_regime,
                "sector_rank": snap_sector_rank,
                "momentum_5m": snap_momentum_5m,
                "distance_from_vwap": snap_vwap_diff,
                "rs_vs_market": snap_rs_market
            },
            "current": {
                "score": curr_score,
                "rank": curr_rank,
                "state": curr_state,
                "market_regime": curr_regime,
                "sector_rank": curr_sector_rank,
                "momentum_5m": curr_momentum_5m,
                "distance_from_vwap": curr_vwap_diff,
                "rs_vs_market": curr_rs_market
            },
            "deltas": {
                "score_change": round(score_change, 2),
                "rank_change": rank_change,
                "state_changed": state_changed,
                "regime_changed": regime_changed,
                "sector_rank_change": sector_rank_change,
                "momentum_change": round(momentum_change, 2),
                "vwap_diff_change": round(vwap_diff_change, 2),
                "relative_strength_change": round(rs_change, 2)
            },
            "zero_llm_call_verified": True
        }
