"""
Intraday Opportunity Scorer for Nomad Analyst.

Calculates an explainable 0-100 composite opportunity score decomposed across 8 independent
dimensions with transparent penalties, evidence confidence (0.0-1.0), and lifecycle state tracking.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from market.services.intraday_opportunity_config import (
    OPPORTUNITY_SCORE_WEIGHTS,
    PENALTY_STALE_DATA_POINTS,
    PENALTY_MISSING_SECTOR_POINTS,
    PENALTY_MISSING_INDEX_POINTS,
    PENALTY_WEAK_VOLUME_POINTS,
    PENALTY_MARKET_DIVERGENCE_POINTS,
    PENALTY_SECTOR_DIVERGENCE_POINTS,
    CONFIDENCE_DATA_WEIGHT,
    CONFIDENCE_EVIDENCE_AGREEMENT_WEIGHT,
    CONFIDENCE_VOLUME_WEIGHT,
    STATE_CONFIRMED_MIN_SCORE,
    STATE_CONFIRMED_MIN_CONFIDENCE,
    STATE_EMERGING_MIN_SCORE,
    STATE_WEAKENING_SCORE_DROP,
    RVOL_CONFIRMED_THRESHOLD,
    RVOL_HIGH_CONFIRMED_THRESHOLD,
    RVOL_WEAK_THRESHOLD,
)

logger = logging.getLogger(__name__)


class IntradayOpportunityScorer:
    """
    Computes dimensional component scores, transparent penalties, confidence, and lifecycle state.
    """

    @classmethod
    def calculate_opportunity_score(
        cls,
        stock_context: Dict[str, Any],
        opportunity_type: str,
        bias: str,
        market_context: Optional[Dict[str, Any]] = None,
        sector_info: Optional[Dict[str, Any]] = None,
        freshness_info: Optional[Dict[str, Any]] = None,
        previous_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes complete scoring, penalty auditing, confidence estimation, and lifecycle classification.
        """
        penalties: List[Dict[str, Any]] = []

        # ── 1. Momentum Dimension (0-100) ────────────────────────────────────
        mom_5m = stock_context.get("momentum_5m")
        mom_15m = stock_context.get("momentum_15m")
        m5_val = Decimal(str(mom_5m)) if mom_5m is not None else Decimal("0.0")
        m15_val = Decimal(str(mom_15m)) if mom_15m is not None else Decimal("0.0")

        if bias == "BULLISH":
            # Target positive momentum
            m5_score = min(Decimal("100.0"), max(Decimal("0.0"), (m5_val / Decimal("0.5")) * Decimal("50.0") + Decimal("50.0")))
            m15_score = min(Decimal("100.0"), max(Decimal("0.0"), (m15_val / Decimal("0.75")) * Decimal("50.0") + Decimal("50.0")))
            momentum_score = (m5_score * Decimal("0.5")) + (m15_score * Decimal("0.5"))
        elif bias == "BEARISH":
            # Target negative momentum
            m5_score = min(Decimal("100.0"), max(Decimal("0.0"), (-m5_val / Decimal("0.5")) * Decimal("50.0") + Decimal("50.0")))
            m15_score = min(Decimal("100.0"), max(Decimal("0.0"), (-m15_val / Decimal("0.75")) * Decimal("50.0") + Decimal("50.0")))
            momentum_score = (m5_score * Decimal("0.5")) + (m15_score * Decimal("0.5"))
        elif "EXHAUSTION" in bias:
            # Mean-reversion favors decelerating momentum
            momentum_score = Decimal("70.0")
        else:
            momentum_score = Decimal("50.0")

        # ── 2. Relative Strength Dimension (0-100) ───────────────────────────
        rs_mkt = stock_context.get("relative_strength_vs_market")
        rs_sec = stock_context.get("relative_strength_vs_sector")
        rs_mkt_val = Decimal(str(rs_mkt)) if rs_mkt is not None else None
        rs_sec_val = Decimal(str(rs_sec)) if rs_sec is not None else None

        if rs_mkt_val is not None and rs_sec_val is not None:
            if bias == "BULLISH":
                rs_m_score = min(Decimal("100.0"), max(Decimal("0.0"), (rs_mkt_val / Decimal("1.0")) * Decimal("50.0") + Decimal("50.0")))
                rs_s_score = min(Decimal("100.0"), max(Decimal("0.0"), (rs_sec_val / Decimal("1.0")) * Decimal("50.0") + Decimal("50.0")))
            elif bias == "BEARISH":
                rs_m_score = min(Decimal("100.0"), max(Decimal("0.0"), (-rs_mkt_val / Decimal("1.0")) * Decimal("50.0") + Decimal("50.0")))
                rs_s_score = min(Decimal("100.0"), max(Decimal("0.0"), (-rs_sec_val / Decimal("1.0")) * Decimal("50.0") + Decimal("50.0")))
            else:
                rs_m_score = Decimal("50.0")
                rs_s_score = Decimal("50.0")
            relative_strength_score = (rs_m_score * Decimal("0.5")) + (rs_s_score * Decimal("0.5"))
        elif rs_mkt_val is not None:
            relative_strength_score = min(Decimal("100.0"), max(Decimal("0.0"), (rs_mkt_val / Decimal("1.0")) * Decimal("50.0") + Decimal("50.0")))
        else:
            relative_strength_score = Decimal("50.0")

        # ── 3. Volume Confirmation Dimension (0-100) ─────────────────────────
        rvol = stock_context.get("relative_volume")
        rvol_val = Decimal(str(rvol)) if rvol is not None else Decimal("1.0")

        if rvol_val >= RVOL_HIGH_CONFIRMED_THRESHOLD:
            volume_score = Decimal("100.0")
        elif rvol_val >= RVOL_CONFIRMED_THRESHOLD:
            volume_score = Decimal("80.0")
        elif rvol_val >= Decimal("1.0"):
            volume_score = Decimal("60.0")
        elif rvol_val >= RVOL_WEAK_THRESHOLD:
            volume_score = Decimal("40.0")
        else:
            volume_score = Decimal("25.0")
            penalties.append({"reason": "LOW_VOLUME_CONFIRMATION", "points": float(PENALTY_WEAK_VOLUME_POINTS)})

        # ── 4. VWAP Positioning Dimension (0-100) ────────────────────────────
        vwap_diff = stock_context.get("distance_from_vwap")
        vwap_diff_pct = Decimal(str(vwap_diff)) if vwap_diff is not None else Decimal("0.0")

        if bias == "BULLISH":
            if vwap_diff_pct >= Decimal("0.30"):
                vwap_score = Decimal("95.0")
            elif vwap_diff_pct >= Decimal("0.0"):
                vwap_score = Decimal("75.0")
            elif vwap_diff_pct >= Decimal("-0.20"):
                vwap_score = Decimal("40.0")
            else:
                vwap_score = Decimal("15.0")
        elif bias == "BEARISH":
            if vwap_diff_pct <= Decimal("-0.30"):
                vwap_score = Decimal("95.0")
            elif vwap_diff_pct <= Decimal("0.0"):
                vwap_score = Decimal("75.0")
            elif vwap_diff_pct <= Decimal("0.20"):
                vwap_score = Decimal("40.0")
            else:
                vwap_score = Decimal("15.0")
        elif "EXHAUSTION" in bias:
            # Stretched from VWAP
            vwap_score = Decimal("85.0")
        else:
            vwap_score = Decimal("50.0")

        # ── 5. Market Alignment Dimension (0-100) ────────────────────────────
        market_alignment_state = "NEUTRAL"
        market_regime = market_context.get("market_regime", "UNKNOWN") if market_context else "UNKNOWN"
        nifty_ret = Decimal(str(market_context.get("nifty", {}).get("return_pct", 0.0))) if market_context else Decimal("0.0")
        breadth_ratio = Decimal(str(market_context.get("breadth", {}).get("advance_decline_ratio", 1.0))) if market_context else Decimal("1.0")

        if market_context is None:
            market_alignment_score = Decimal("40.0")
            penalties.append({"reason": "MISSING_MARKET_CONTEXT", "points": float(PENALTY_MISSING_INDEX_POINTS)})
            market_alignment_state = "NEUTRAL"
        else:
            if bias == "BULLISH":
                if market_regime == "TRENDING_UP" and breadth_ratio >= Decimal("1.5"):
                    market_alignment_score = Decimal("100.0")
                    market_alignment_state = "STRONGLY_ALIGNED"
                elif nifty_ret > Decimal("0.1") or breadth_ratio >= Decimal("1.2"):
                    market_alignment_score = Decimal("80.0")
                    market_alignment_state = "ALIGNED"
                elif nifty_ret < Decimal("-0.3") or breadth_ratio <= Decimal("0.6"):
                    market_alignment_score = Decimal("20.0")
                    market_alignment_state = "DIVERGENT"
                    penalties.append({"reason": "BEARISH_MARKET_DIVERGENCE", "points": float(PENALTY_MARKET_DIVERGENCE_POINTS)})
                else:
                    market_alignment_score = Decimal("55.0")
                    market_alignment_state = "NEUTRAL"
            elif bias == "BEARISH":
                if market_regime == "TRENDING_DOWN" and breadth_ratio <= Decimal("0.67"):
                    market_alignment_score = Decimal("100.0")
                    market_alignment_state = "STRONGLY_ALIGNED"
                elif nifty_ret < Decimal("-0.1") or breadth_ratio <= Decimal("0.8"):
                    market_alignment_score = Decimal("80.0")
                    market_alignment_state = "ALIGNED"
                elif nifty_ret > Decimal("0.3") or breadth_ratio >= Decimal("1.5"):
                    market_alignment_score = Decimal("20.0")
                    market_alignment_state = "DIVERGENT"
                    penalties.append({"reason": "BULLISH_MARKET_DIVERGENCE", "points": float(PENALTY_MARKET_DIVERGENCE_POINTS)})
                else:
                    market_alignment_score = Decimal("55.0")
                    market_alignment_state = "NEUTRAL"
            else:
                market_alignment_score = Decimal("50.0")
                market_alignment_state = "NEUTRAL"

        # ── 6. Sector Alignment Dimension (0-100) ────────────────────────────
        sector_alignment_state = "NEUTRAL"
        sec_ret = Decimal(str(sector_info.get("return_pct") if sector_info.get("return_pct") is not None else sector_info.get("average_return", 0.0))) if sector_info else Decimal("0.0")
        sec_rank = sector_info.get("rank") if sector_info else None

        if sector_info is None or stock_context.get("sector") in (None, "Unknown"):
            sector_alignment_score = Decimal("40.0")
            sector_alignment_state = "NEUTRAL"
            penalties.append({"reason": "MISSING_SECTOR_CONTEXT", "points": float(PENALTY_MISSING_SECTOR_POINTS)})
        else:
            if bias == "BULLISH":
                if sec_rank is not None and sec_rank <= 3 and sec_ret > Decimal("0.3"):
                    sector_alignment_score = Decimal("100.0")
                    sector_alignment_state = "STRONGLY_ALIGNED"
                elif sec_ret > Decimal("0.0"):
                    sector_alignment_score = Decimal("80.0")
                    sector_alignment_state = "ALIGNED"
                elif sec_ret < Decimal("-0.3"):
                    sector_alignment_score = Decimal("25.0")
                    sector_alignment_state = "DIVERGENT"
                    penalties.append({"reason": "SECTOR_RETURN_NEGATIVE", "points": float(PENALTY_SECTOR_DIVERGENCE_POINTS)})
                else:
                    sector_alignment_score = Decimal("55.0")
                    sector_alignment_state = "NEUTRAL"
            elif bias == "BEARISH":
                if sec_ret < Decimal("-0.3"):
                    sector_alignment_score = Decimal("95.0")
                    sector_alignment_state = "STRONGLY_ALIGNED"
                elif sec_ret < Decimal("0.0"):
                    sector_alignment_score = Decimal("80.0")
                    sector_alignment_state = "ALIGNED"
                elif sec_ret > Decimal("0.3"):
                    sector_alignment_score = Decimal("25.0")
                    sector_alignment_state = "DIVERGENT"
                    penalties.append({"reason": "SECTOR_RETURN_POSITIVE", "points": float(PENALTY_SECTOR_DIVERGENCE_POINTS)})
                else:
                    sector_alignment_score = Decimal("55.0")
                    sector_alignment_state = "NEUTRAL"
            else:
                sector_alignment_score = Decimal("50.0")
                sector_alignment_state = "NEUTRAL"

        # ── 7. ORB / Structure Dimension (0-100) ─────────────────────────────
        orb_state = stock_context.get("opening_range_state", "INSIDE_ORB")
        if bias == "BULLISH":
            if orb_state == "ABOVE_ORB":
                orb_score = Decimal("100.0")
            elif orb_state == "INSIDE_ORB":
                orb_score = Decimal("60.0")
            else:
                orb_score = Decimal("20.0")
        elif bias == "BEARISH":
            if orb_state == "BELOW_ORB":
                orb_score = Decimal("100.0")
            elif orb_state == "INSIDE_ORB":
                orb_score = Decimal("60.0")
            else:
                orb_score = Decimal("20.0")
        else:
            orb_score = Decimal("50.0")

        # ── 8. Data Quality Dimension (0-100) ────────────────────────────────
        dq_freshness = freshness_info.get("freshness", "FRESH") if freshness_info else "FRESH"
        data_quality_label = "HIGH"

        if dq_freshness == "FRESH":
            data_quality_score = Decimal("100.0")
        elif dq_freshness == "STALE":
            data_quality_score = Decimal("50.0")
            data_quality_label = "MEDIUM"
            penalties.append({"reason": "STALE_MARKET_DATA", "points": float(PENALTY_STALE_DATA_POINTS)})
        else:
            data_quality_score = Decimal("15.0")
            data_quality_label = "LOW"
            penalties.append({"reason": "UNAVAILABLE_MARKET_DATA", "points": float(PENALTY_STALE_DATA_POINTS)})

        # ── Composite Base Score ─────────────────────────────────────────────
        base_score = (
            momentum_score * OPPORTUNITY_SCORE_WEIGHTS["momentum"]
            + relative_strength_score * OPPORTUNITY_SCORE_WEIGHTS["relative_strength"]
            + volume_score * OPPORTUNITY_SCORE_WEIGHTS["volume"]
            + vwap_score * OPPORTUNITY_SCORE_WEIGHTS["vwap"]
            + market_alignment_score * OPPORTUNITY_SCORE_WEIGHTS["market_alignment"]
            + sector_alignment_score * OPPORTUNITY_SCORE_WEIGHTS["sector_alignment"]
            + orb_score * OPPORTUNITY_SCORE_WEIGHTS["orb"]
            + data_quality_score * OPPORTUNITY_SCORE_WEIGHTS["data_quality"]
        )

        # Apply transparent penalties
        total_penalty_points = sum(Decimal(str(p["points"])) for p in penalties)
        final_score = max(Decimal("0.0"), min(Decimal("100.0"), base_score - total_penalty_points))

        # ── Evidence Confidence (0.00 to 1.00) ───────────────────────────────
        data_conf = data_quality_score / Decimal("100.0")
        volume_conf = min(Decimal("1.0"), rvol_val / Decimal("1.5")) if rvol_val else Decimal("0.5")
        
        # Agreement between momentum, vwap, and market
        agreement_points = 0
        if (bias == "BULLISH" and momentum_score >= 60) or (bias == "BEARISH" and momentum_score >= 60):
            agreement_points += 1
        if (bias == "BULLISH" and vwap_score >= 60) or (bias == "BEARISH" and vwap_score >= 60):
            agreement_points += 1
        if market_alignment_state in ("STRONGLY_ALIGNED", "ALIGNED"):
            agreement_points += 1
        if sector_alignment_state in ("STRONGLY_ALIGNED", "ALIGNED"):
            agreement_points += 1
        agreement_conf = Decimal(str(agreement_points)) / Decimal("4.0")

        confidence = (
            data_conf * CONFIDENCE_DATA_WEIGHT
            + agreement_conf * CONFIDENCE_EVIDENCE_AGREEMENT_WEIGHT
            + volume_conf * CONFIDENCE_VOLUME_WEIGHT
        )
        confidence = round(max(Decimal("0.0"), min(Decimal("1.0"), confidence)), 2)

        # ── Lifecycle State ──────────────────────────────────────────────────
        if dq_freshness in ("STALE", "UNAVAILABLE"):
            state = "STALE"
        elif opportunity_type == "NO_CLEAR_OPPORTUNITY" or final_score < STATE_EMERGING_MIN_SCORE:
            if previous_snapshot and previous_snapshot.get("state") in ("CONFIRMED", "EMERGING"):
                state = "INVALIDATED"
            else:
                state = "INVALIDATED"
        elif final_score >= STATE_CONFIRMED_MIN_SCORE and confidence >= STATE_CONFIRMED_MIN_CONFIDENCE:
            state = "CONFIRMED"
        elif previous_snapshot and previous_snapshot.get("score") is not None:
            prev_sc = Decimal(str(previous_snapshot["score"]))
            if (prev_sc - final_score) >= STATE_WEAKENING_SCORE_DROP:
                state = "WEAKENING"
            else:
                state = "EMERGING"
        else:
            state = "EMERGING"

        return {
            "score": round(final_score, 2),
            "base_score": round(base_score, 2),
            "confidence": float(confidence),
            "state": state,
            "bias": bias,
            "market_alignment": market_alignment_state,
            "sector_alignment": sector_alignment_state,
            "data_quality": data_quality_label,
            "freshness": dq_freshness,
            "penalties": penalties,
            "component_scores": {
                "momentum_score": round(momentum_score, 2),
                "relative_strength_score": round(relative_strength_score, 2),
                "volume_score": round(volume_score, 2),
                "vwap_score": round(vwap_score, 2),
                "market_alignment_score": round(market_alignment_score, 2),
                "sector_alignment_score": round(sector_alignment_score, 2),
                "orb_score": round(orb_score, 2),
                "data_quality_score": round(data_quality_score, 2),
            }
        }
