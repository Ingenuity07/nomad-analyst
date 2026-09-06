"""
Intraday Opportunity Engine for Nomad Analyst.

Main coordinator transforming real-time market context and stock states into
ranked, explainable intraday opportunities across the NIFTY 50 universe.
"""

import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from market.models import Instrument, IntradayOpportunitySnapshot
from market.services.intraday_opportunity_config import (
    DEFAULT_TOP_OPPORTUNITIES_LIMIT,
)
from market.services.intraday_opportunity_detector import IntradayOpportunityDetector
from market.services.intraday_opportunity_scorer import IntradayOpportunityScorer
from market.services.intraday_opportunity_explainer import IntradayOpportunityExplainer
from market.services.intraday_opportunity_ranker import IntradayOpportunityRanker

logger = logging.getLogger(__name__)


class IntradayOpportunityEngine:
    """
    Pure functional / state-aware engine producing explainable intraday opportunity evaluations.
    """

    def __init__(self):
        # Key: symbol -> last opportunity state dict (for tracking state transitions & score changes)
        self._history_cache: Dict[str, Dict[str, Any]] = {}
        # Key: symbol -> Instrument model instance
        self._instrument_cache: Dict[str, Optional[Instrument]] = {}

    def _get_instrument(self, symbol: str) -> Optional[Instrument]:
        if symbol not in self._instrument_cache:
            self._instrument_cache[symbol] = Instrument.objects.filter(symbol=symbol).first()
        return self._instrument_cache[symbol]

    def evaluate_universe_opportunities(
        self,
        market_context: Dict[str, Any],
        constituent_contexts: List[Dict[str, Any]],
        freshness_info: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
        persist_to_db: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates the full universe of constituents against market context.
        Returns full opportunity evaluation summary including eligible, excluded, and ranked candidates.
        """
        now = as_of or datetime.now(timezone.utc)
        as_of_iso = now.isoformat()

        # Build sector lookup from market context
        sectors_list = market_context.get("sectors", [])
        sector_lookup = {sec.get("name"): sec for sec in sectors_list if sec.get("name")}

        eligible_opportunities: List[Dict[str, Any]] = []
        excluded_candidates: List[Dict[str, Any]] = []

        freshness_age = freshness_info.get("age_seconds") if freshness_info else None

        for stock in constituent_contexts:
            symbol = stock.get("symbol", "UNKNOWN")
            
            # 1. Eligibility Filter
            is_eligible, exclusion_reason = IntradayOpportunityDetector.evaluate_eligibility(
                stock, freshness_age_seconds=freshness_age
            )

            if not is_eligible:
                excluded_candidates.append({
                    "symbol": symbol,
                    "eligible": False,
                    "exclusion_reason": exclusion_reason,
                    "sector": stock.get("sector", "Unknown"),
                })
                continue

            sec_info = sector_lookup.get(stock.get("sector"))
            prev_snapshot = self._history_cache.get(symbol)

            # 2. Opportunity Family Detection
            opp_type, bias, detection_meta = IntradayOpportunityDetector.detect_opportunity_type(
                stock_context=stock,
                market_context=market_context,
                sector_info=sec_info,
            )

            # 3. Dimensional Scoring & Lifecycle State
            score_data = IntradayOpportunityScorer.calculate_opportunity_score(
                stock_context=stock,
                opportunity_type=opp_type,
                bias=bias,
                market_context=market_context,
                sector_info=sec_info,
                freshness_info=freshness_info,
                previous_snapshot=prev_snapshot,
            )

            # 4. Structured Explanations
            explanation_data = IntradayOpportunityExplainer.explain_opportunity(
                stock_context=stock,
                opportunity_type=opp_type,
                bias=bias,
                score_data=score_data,
                market_context=market_context,
                sector_info=sec_info,
            )

            # 5. Score change calculations
            score_now = float(score_data["score"])
            score_change_1m = 0.0
            if prev_snapshot and prev_snapshot.get("score") is not None:
                score_change_1m = round(score_now - float(prev_snapshot["score"]), 2)

            first_detected = (
                prev_snapshot.get("first_detected_at")
                if prev_snapshot and prev_snapshot.get("opportunity_type") == opp_type
                else as_of_iso
            )

            # Assemble full opportunity item
            opp_item = {
                "symbol": symbol,
                "timestamp": as_of_iso,
                "opportunity_type": opp_type,
                "state": score_data["state"],
                "score": score_now,
                "base_score": float(score_data["base_score"]),
                "confidence": score_data["confidence"],
                "bias": bias,
                "score_change": score_change_1m,
                "component_scores": score_data["component_scores"],
                "penalties": score_data["penalties"],
                "supporting_factors": explanation_data["supporting_factors"],
                "contradicting_factors": explanation_data["contradicting_factors"],
                "warnings": explanation_data["warnings"],
                "invalidation_condition": explanation_data["invalidation_condition"],
                "metrics": {
                    "last_price": float(stock.get("last_price", 0.0)),
                    "change_pct": float(stock.get("change_pct", 0.0) or 0.0),
                    "vwap": float(stock.get("vwap", 0.0)) if stock.get("vwap") else None,
                    "vwap_diff_pct": float(stock.get("distance_from_vwap", 0.0) or 0.0),
                    "volume": int(stock.get("volume", 0) or 0),
                    "relative_volume": float(stock.get("relative_volume", 1.0) or 1.0),
                    "momentum_5m": float(stock.get("momentum_5m", 0.0) or 0.0),
                    "momentum_15m": float(stock.get("momentum_15m", 0.0) or 0.0),
                    "relative_strength_vs_market": float(stock.get("relative_strength_vs_market", 0.0) or 0.0),
                    "relative_strength_vs_sector": float(stock.get("relative_strength_vs_sector", 0.0) or 0.0),
                    "opening_range_state": stock.get("opening_range_state", "INSIDE_ORB"),
                    "volume_confirmation": stock.get("volume_confirmation", "NEUTRAL"),
                },
                "sector": {
                    "name": stock.get("sector", "Unknown"),
                    "rank": sec_info.get("rank") if sec_info else None,
                    "return_pct": float(sec_info.get("return_pct", 0.0)) if sec_info else 0.0,
                },
                "market_alignment": score_data["market_alignment"],
                "sector_alignment": score_data["sector_alignment"],
                "data_quality": score_data["data_quality"],
                "freshness": score_data["freshness"],
                "first_detected_at": first_detected,
                "last_updated_at": as_of_iso,
            }

            self._history_cache[symbol] = opp_item
            eligible_opportunities.append(opp_item)

        # 6. Rank opportunities
        ranking_result = IntradayOpportunityRanker.rank_opportunities(
            opportunities=eligible_opportunities,
            mode="RAW_RANKING",
            limit=DEFAULT_TOP_OPPORTUNITIES_LIMIT,
        )

        # 7. Optional DB persistence
        if persist_to_db:
            self._persist_opportunities(ranking_result["opportunities"], now)

        return {
            "timestamp": as_of_iso,
            "market_context": {
                "regime": market_context.get("market_regime", "UNKNOWN"),
                "regime_confidence": market_context.get("regime_confidence", 0.0),
                "breadth_state": market_context.get("breadth", {}).get("breadth_state", "NEUTRAL"),
                "advance_decline_ratio": market_context.get("breadth", {}).get("advance_decline_ratio", 1.0),
                "sector_leader": market_context.get("sector_leader"),
                "sector_laggard": market_context.get("sector_laggard"),
            },
            "total_evaluated": len(constituent_contexts),
            "total_eligible": len(eligible_opportunities),
            "total_excluded": len(excluded_candidates),
            "excluded_candidates": excluded_candidates,
            "ranking_mode": ranking_result["mode"],
            "sector_concentration": ranking_result["sector_concentration"],
            "opportunities": ranking_result["opportunities"],
            "all_eligible_opportunities": eligible_opportunities,
        }

    def _persist_opportunities(self, opportunities: List[Dict[str, Any]], timestamp: datetime):
        """
        Saves snapshot records into IntradayOpportunitySnapshot table.
        """
        snapshots_to_create = []
        for opp in opportunities:
            inst = self._get_instrument(opp["symbol"])
            if not inst:
                continue

            first_dt = None
            if opp.get("first_detected_at"):
                try:
                    first_dt = datetime.fromisoformat(opp["first_detected_at"])
                except Exception:
                    first_dt = timestamp

            snapshots_to_create.append(
                IntradayOpportunitySnapshot(
                    instrument=inst,
                    symbol=opp["symbol"],
                    timestamp=timestamp,
                    opportunity_type=opp["opportunity_type"],
                    state=opp["state"],
                    score=Decimal(str(opp["score"])),
                    confidence=Decimal(str(opp["confidence"])),
                    momentum_score=Decimal(str(opp["component_scores"]["momentum_score"])),
                    relative_strength_score=Decimal(str(opp["component_scores"]["relative_strength_score"])),
                    volume_score=Decimal(str(opp["component_scores"]["volume_score"])),
                    vwap_score=Decimal(str(opp["component_scores"]["vwap_score"])),
                    market_alignment_score=Decimal(str(opp["component_scores"]["market_alignment_score"])),
                    sector_alignment_score=Decimal(str(opp["component_scores"]["sector_alignment_score"])),
                    orb_score=Decimal(str(opp["component_scores"]["orb_score"])),
                    data_quality_score=Decimal(str(opp["component_scores"]["data_quality_score"])),
                    supporting_factors=opp["supporting_factors"],
                    contradicting_factors=opp["contradicting_factors"],
                    warnings=opp["warnings"],
                    penalties=opp["penalties"],
                    metrics=opp["metrics"],
                    rank=opp.get("rank"),
                    sector=opp.get("sector", {}).get("name", "Unknown"),
                    market_alignment=opp["market_alignment"],
                    sector_alignment=opp["sector_alignment"],
                    data_quality=opp["data_quality"],
                    freshness=opp["freshness"],
                    first_detected_at=first_dt,
                    last_updated_at=timestamp,
                )
            )

        if snapshots_to_create:
            try:
                IntradayOpportunitySnapshot.objects.bulk_create(snapshots_to_create)
                logger.info(f"Persisted {len(snapshots_to_create)} IntradayOpportunitySnapshot records @ {timestamp}")
            except Exception as e:
                logger.error(f"Failed to bulk_create IntradayOpportunitySnapshot records: {e}")
