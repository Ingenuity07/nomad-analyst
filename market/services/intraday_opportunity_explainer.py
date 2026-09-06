"""
Intraday Opportunity Explanation Engine for Nomad Analyst.

Transforms deterministic numerical metrics, market context, and dimensional scores into
structured, transparent evidence: supporting factors, contradicting factors, and warnings.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class IntradayOpportunityExplainer:
    """
    Generates structured, factual explanations grounded directly in computed intraday data.
    """

    @classmethod
    def explain_opportunity(
        cls,
        stock_context: Dict[str, Any],
        opportunity_type: str,
        bias: str,
        score_data: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
        sector_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Builds explainability payload answering:
        - Supporting factors (evidence confirming the opportunity)
        - Contradicting factors (contrary or unconfirmed signals)
        - Warnings (regime, breadth, or structural risks)
        - Invalidation conditions (what breaks this setup)
        """
        supporting: List[str] = []
        contradicting: List[str] = []
        warnings: List[str] = []

        change_pct = stock_context.get("change_pct", 0.0) or 0.0
        vwap_diff = stock_context.get("distance_from_vwap")
        vwap_diff_pct = float(vwap_diff) if vwap_diff is not None else 0.0
        
        m5 = stock_context.get("momentum_5m")
        m15 = stock_context.get("momentum_15m")
        rvol = stock_context.get("relative_volume")
        rvol_val = float(rvol) if rvol is not None else 1.0

        rs_mkt = stock_context.get("relative_strength_vs_market")
        rs_mkt_val = float(rs_mkt) if rs_mkt is not None else None

        rs_sec = stock_context.get("relative_strength_vs_sector")
        rs_sec_val = float(rs_sec) if rs_sec is not None else None

        orb_state = stock_context.get("opening_range_state", "INSIDE_ORB")
        vol_conf = stock_context.get("volume_confirmation", "NEUTRAL")

        # ── 1. VWAP Evidence ─────────────────────────────────────────────────
        if bias == "BULLISH":
            if vwap_diff_pct > 0.3:
                supporting.append(f"Trading +{vwap_diff_pct:.2f}% above session VWAP")
            elif vwap_diff_pct >= 0.0:
                supporting.append("Trading above session VWAP")
            else:
                contradicting.append(f"Trading below session VWAP ({vwap_diff_pct:.2f}%)")
        elif bias == "BEARISH":
            if vwap_diff_pct < -0.3:
                supporting.append(f"Trading {vwap_diff_pct:.2f}% below session VWAP")
            elif vwap_diff_pct <= 0.0:
                supporting.append("Trading below session VWAP")
            else:
                contradicting.append(f"Trading above session VWAP (+{vwap_diff_pct:.2f}%)")
        elif "EXHAUSTION" in bias:
            supporting.append(f"Extreme VWAP stretch ({vwap_diff_pct:+.2f}%) indicates mean-reversion context")

        # ── 2. Relative Strength Evidence ────────────────────────────────────
        if rs_mkt_val is not None:
            if bias == "BULLISH":
                if rs_mkt_val >= 0.5:
                    supporting.append(f"Outperforming NIFTY 50 by +{rs_mkt_val:.2f}%")
                elif rs_mkt_val < -0.3:
                    contradicting.append(f"Underperforming NIFTY 50 by {rs_mkt_val:.2f}%")
            elif bias == "BEARISH":
                if rs_mkt_val <= -0.5:
                    supporting.append(f"Underperforming NIFTY 50 by {rs_mkt_val:.2f}%")
                elif rs_mkt_val > 0.3:
                    contradicting.append(f"Outperforming NIFTY 50 by +{rs_mkt_val:.2f}%")

        if rs_sec_val is not None:
            if bias == "BULLISH":
                if rs_sec_val >= 0.5:
                    supporting.append(f"Outperforming sector by +{rs_sec_val:.2f}%")
                elif rs_sec_val < -0.3:
                    contradicting.append(f"Underperforming sector by {rs_sec_val:.2f}%")
            elif bias == "BEARISH":
                if rs_sec_val <= -0.5:
                    supporting.append(f"Underperforming sector by {rs_sec_val:.2f}%")
                elif rs_sec_val > 0.3:
                    contradicting.append(f"Outperforming sector by +{rs_sec_val:.2f}%")

        # ── 3. Volume Evidence ───────────────────────────────────────────────
        if rvol_val >= 1.5:
            supporting.append(f"Heavy volume participation (RVOL {rvol_val:.1f}x)")
        elif rvol_val >= 1.2:
            supporting.append(f"Confirmed volume participation (RVOL {rvol_val:.1f}x)")
        elif rvol_val < 0.8:
            warnings.append(f"Low relative volume (RVOL {rvol_val:.1f}x) limits move confirmation")

        # ── 4. Momentum Evidence ─────────────────────────────────────────────
        if m5 is not None and m15 is not None:
            m5_f = float(m5)
            m15_f = float(m15)
            if bias == "BULLISH":
                if m5_f > 0.2 and m15_f > 0.3:
                    supporting.append(f"Positive momentum across 5m (+{m5_f:.2f}%) and 15m (+{m15_f:.2f}%)")
                elif m5_f < 0.0:
                    warnings.append(f"Short-term 5m momentum decelerating ({m5_f:.2f}%)")
            elif bias == "BEARISH":
                if m5_f < -0.2 and m15_f < -0.3:
                    supporting.append(f"Negative momentum across 5m ({m5_f:.2f}%) and 15m ({m15_f:.2f}%)")
                elif m5_f > 0.0:
                    warnings.append(f"Short-term 5m momentum bouncing (+{m5_f:.2f}%)")

        # ── 5. Market Alignment Evidence ─────────────────────────────────────
        if market_context:
            regime = market_context.get("market_regime", "UNKNOWN")
            breadth_state = market_context.get("breadth", {}).get("breadth_state", "NEUTRAL")
            ad_ratio = market_context.get("breadth", {}).get("advance_decline_ratio", 1.0)
            
            if bias == "BULLISH":
                if regime == "TRENDING_UP":
                    supporting.append(f"Broad market strongly aligned in TRENDING_UP regime (A/D: {ad_ratio:.2f})")
                elif regime == "TRENDING_DOWN":
                    contradicting.append(f"Broader market is in opposing TRENDING_DOWN regime")
                    warnings.append("Fighting overall market trend")
            elif bias == "BEARISH":
                if regime == "TRENDING_DOWN":
                    supporting.append(f"Broad market strongly aligned in TRENDING_DOWN regime (A/D: {ad_ratio:.2f})")
                elif regime == "TRENDING_UP":
                    contradicting.append("Broader market is in opposing TRENDING_UP regime")
                    warnings.append("Fighting overall market trend")

            if regime == "VOLATILE":
                warnings.append("Market regime classified as VOLATILE; expect heightened whipsaw risk")

        # ── 6. Sector Evidence ───────────────────────────────────────────────
        if sector_info:
            sec_name = sector_info.get("name", "Unknown")
            sec_ret = float(sector_info.get("return_pct", 0.0))
            sec_rank = sector_info.get("rank")
            
            if bias == "BULLISH":
                if sec_rank is not None and sec_rank <= 2:
                    supporting.append(f"Sector '{sec_name}' is a session leader (Rank #{sec_rank}, +{sec_ret:.2f}%)")
                elif sec_ret < -0.3:
                    contradicting.append(f"Sector '{sec_name}' is negative ({sec_ret:.2f}%)")
            elif bias == "BEARISH":
                if sec_rank is not None and sec_rank >= 10:
                    supporting.append(f"Sector '{sec_name}' is a session laggard (Rank #{sec_rank}, {sec_ret:.2f}%)")
                elif sec_ret > 0.3:
                    contradicting.append(f"Sector '{sec_name}' is positive (+{sec_ret:.2f}%)")

        # ── 7. Opening Range Evidence ────────────────────────────────────────
        if orb_state == "ABOVE_ORB":
            if bias == "BULLISH":
                supporting.append("Trading above 15m Opening Range high (ORB breakout)")
        elif orb_state == "BELOW_ORB":
            if bias == "BEARISH":
                supporting.append("Trading below 15m Opening Range low (ORB breakdown)")

        # ── 8. Invalidation Level / Condition ────────────────────────────────
        if bias == "BULLISH":
            invalidation_condition = "Loss of session VWAP on high volume or fall below 15m ORB range"
        elif bias == "BEARISH":
            invalidation_condition = "Reclaim of session VWAP on high volume or break above 15m ORB range"
        else:
            invalidation_condition = "Breakout or breakdown from current consolidation range"

        return {
            "supporting_factors": supporting,
            "contradicting_factors": contradicting,
            "warnings": warnings,
            "invalidation_condition": invalidation_condition,
        }
