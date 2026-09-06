"""
Intraday Opportunity Candidate Detection for Nomad Analyst.

Identifies eligible NIFTY 50 constituent candidates and classifies them into
deterministic opportunity families without black-box models or trade signals.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

from market.services.intraday_opportunity_config import (
    MIN_PRICE_INR,
    MAX_FRESHNESS_AGE_SECONDS,
    MIN_CUMULATIVE_VOLUME,
    MOMENTUM_MIN_5M_PCT,
    MOMENTUM_MIN_15M_PCT,
    RS_MIN_OUTPERFORM_PCT,
    RS_STRONG_OUTPERFORM_PCT,
    RS_MIN_UNDERPERFORM_PCT,
    RS_STRONG_UNDERPERFORM_PCT,
    VWAP_TREND_MIN_PCT,
    VWAP_MEAN_REVERSION_EXTREME_PCT,
    ORB_BREAKOUT_BUFFER_PCT,
)

logger = logging.getLogger(__name__)


class IntradayOpportunityDetector:
    """
    Evaluates candidate eligibility and detects deterministic intraday opportunity families.
    """

    @classmethod
    def evaluate_eligibility(
        cls,
        stock_context: Dict[str, Any],
        freshness_age_seconds: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines if a stock has sufficient, valid, and fresh data to assess opportunity quality.
        Returns (is_eligible, exclusion_reason).
        """
        last_price = stock_context.get("last_price")
        if last_price is None or Decimal(str(last_price)) < MIN_PRICE_INR:
            return False, "INVALID_OR_MISSING_PRICE"

        prev_close = stock_context.get("previous_close")
        if prev_close is None or Decimal(str(prev_close)) <= Decimal("0.0"):
            return False, "MISSING_PREVIOUS_CLOSE"

        vwap = stock_context.get("vwap")
        if vwap is None or Decimal(str(vwap)) <= Decimal("0.0"):
            return False, "MISSING_SESSION_VWAP"

        volume = stock_context.get("volume", 0) or 0
        if volume < MIN_CUMULATIVE_VOLUME:
            return False, "INSUFFICIENT_LIQUIDITY_VOLUME"

        if freshness_age_seconds is not None and freshness_age_seconds > MAX_FRESHNESS_AGE_SECONDS:
            return False, "STALE_MARKET_DATA"

        return True, None

    @classmethod
    def detect_opportunity_type(
        cls,
        stock_context: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
        sector_info: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Classifies stock into an opportunity family and directional bias.
        Returns (opportunity_type, bias, detection_metadata).
        Bias is either 'BULLISH', 'BEARISH', or 'NEUTRAL'.
        """
        change_pct = Decimal(str(stock_context.get("change_pct", 0.0) or 0.0))
        vwap_diff = stock_context.get("distance_from_vwap")
        vwap_diff_pct = Decimal(str(vwap_diff)) if vwap_diff is not None else Decimal("0.0")
        
        m5 = stock_context.get("momentum_5m")
        mom_5m = Decimal(str(m5)) if m5 is not None else None
        
        m15 = stock_context.get("momentum_15m")
        mom_15m = Decimal(str(m15)) if m15 is not None else None

        rs_market = stock_context.get("relative_strength_vs_market")
        rs_market_val = Decimal(str(rs_market)) if rs_market is not None else None

        rs_sector = stock_context.get("relative_strength_vs_sector")
        rs_sector_val = Decimal(str(rs_sector)) if rs_sector is not None else None

        vol_conf = stock_context.get("volume_confirmation", "NEUTRAL")
        orb_state = stock_context.get("opening_range_state", "INSIDE_ORB")
        
        sec_rank = sector_info.get("rank") if sector_info else None
        sec_ret = Decimal(str(sector_info.get("return_pct", 0.0))) if sector_info else None

        # 1. Check Mean Reversion Context first (extreme deviation with exhaustion)
        if abs(vwap_diff_pct) >= VWAP_MEAN_REVERSION_EXTREME_PCT:
            # Check if short-term momentum is slowing/exhausting compared to deviation
            if vwap_diff_pct > 0 and mom_5m is not None and mom_5m < Decimal("0.0"):
                return "MEAN_REVERSION_CONTEXT", "BEARISH_EXHAUSTION", {
                    "vwap_diff_pct": float(vwap_diff_pct),
                    "mom_5m": float(mom_5m),
                    "reason": f"Extreme upward VWAP deviation ({vwap_diff_pct:.2f}%) with 5m momentum deceleration ({mom_5m:.2f}%)"
                }
            elif vwap_diff_pct < 0 and mom_5m is not None and mom_5m > Decimal("0.0"):
                return "MEAN_REVERSION_CONTEXT", "BULLISH_EXHAUSTION", {
                    "vwap_diff_pct": float(vwap_diff_pct),
                    "mom_5m": float(mom_5m),
                    "reason": f"Extreme downward VWAP deviation ({vwap_diff_pct:.2f}%) with 5m momentum recovery ({mom_5m:.2f}%)"
                }

        # 2. Check Opening Range Breakout / Breakdown
        if orb_state == "ABOVE_ORB" and vwap_diff_pct > Decimal("0.0"):
            if (mom_5m is not None and mom_5m > Decimal("0.0")) or vol_conf == "CONFIRMED_UP":
                return "OPENING_RANGE_BREAKOUT", "BULLISH", {
                    "orb_state": orb_state,
                    "vwap_diff_pct": float(vwap_diff_pct),
                    "reason": "Price sustained above 15m Opening Range high with VWAP support"
                }
        elif orb_state == "BELOW_ORB" and vwap_diff_pct < Decimal("0.0"):
            if (mom_5m is not None and mom_5m < Decimal("0.0")) or vol_conf == "CONFIRMED_DOWN":
                return "OPENING_RANGE_BREAKDOWN", "BEARISH", {
                    "orb_state": orb_state,
                    "vwap_diff_pct": float(vwap_diff_pct),
                    "reason": "Price sustained below 15m Opening Range low with VWAP breakdown"
                }

        # 3. Check Sector Leadership / Laggard
        if sec_rank is not None and sec_rank <= 2 and sec_ret is not None and sec_ret > Decimal("0.2"):
            if change_pct > sec_ret and vwap_diff_pct > Decimal("0.0") and (rs_market_val is not None and rs_market_val > Decimal("0.0")):
                return "SECTOR_LEADERSHIP", "BULLISH", {
                    "sector_rank": sec_rank,
                    "sector_return": float(sec_ret),
                    "reason": f"Top sector leader (Sector Rank #{sec_rank}) outperforming both sector and NIFTY"
                }

        # 4. Check Relative Strength
        if rs_market_val is not None and rs_sector_val is not None:
            if rs_market_val >= RS_MIN_OUTPERFORM_PCT and rs_sector_val >= RS_MIN_OUTPERFORM_PCT and vwap_diff_pct >= Decimal("0.0"):
                return "RELATIVE_STRENGTH", "BULLISH", {
                    "rs_market": float(rs_market_val),
                    "rs_sector": float(rs_sector_val),
                    "reason": f"Strong dual relative strength (+{rs_market_val:.2f}% vs Market, +{rs_sector_val:.2f}% vs Sector)"
                }
            elif rs_market_val <= RS_MIN_UNDERPERFORM_PCT and rs_sector_val <= RS_MIN_UNDERPERFORM_PCT and vwap_diff_pct <= Decimal("0.0"):
                return "RELATIVE_STRENGTH", "BEARISH", {
                    "rs_market": float(rs_market_val),
                    "rs_sector": float(rs_sector_val),
                    "reason": f"Dual relative weakness ({rs_market_val:.2f}% vs Market, {rs_sector_val:.2f}% vs Sector)"
                }

        # 5. Check Momentum Continuation
        if mom_5m is not None and mom_15m is not None:
            if mom_5m >= MOMENTUM_MIN_5M_PCT and mom_15m >= MOMENTUM_MIN_15M_PCT and vwap_diff_pct > Decimal("0.0"):
                return "MOMENTUM_CONTINUATION", "BULLISH", {
                    "momentum_5m": float(mom_5m),
                    "momentum_15m": float(mom_15m),
                    "reason": f"Consistent bullish momentum (5m: +{mom_5m:.2f}%, 15m: +{mom_15m:.2f}%) above VWAP"
                }
            elif mom_5m <= -MOMENTUM_MIN_5M_PCT and mom_15m <= -MOMENTUM_MIN_15M_PCT and vwap_diff_pct < Decimal("0.0"):
                return "MOMENTUM_CONTINUATION", "BEARISH", {
                    "momentum_5m": float(mom_5m),
                    "momentum_15m": float(mom_15m),
                    "reason": f"Consistent bearish momentum (5m: {mom_5m:.2f}%, 15m: {mom_15m:.2f}%) below VWAP"
                }

        # 6. Check VWAP Trend
        if vwap_diff_pct >= VWAP_TREND_MIN_PCT and (vol_conf == "CONFIRMED_UP" or (mom_5m is not None and mom_5m > Decimal("0.0"))):
            return "VWAP_TREND", "BULLISH", {
                "vwap_diff_pct": float(vwap_diff_pct),
                "vol_confirmation": vol_conf,
                "reason": f"Persistent VWAP trend (+{vwap_diff_pct:.2f}% above VWAP) with volume confirmation"
            }
        elif vwap_diff_pct <= -VWAP_TREND_MIN_PCT and (vol_conf == "CONFIRMED_DOWN" or (mom_5m is not None and mom_5m < Decimal("0.0"))):
            return "VWAP_TREND", "BEARISH", {
                "vwap_diff_pct": float(vwap_diff_pct),
                "vol_confirmation": vol_conf,
                "reason": f"Persistent VWAP downtrend ({vwap_diff_pct:.2f}% below VWAP) with volume confirmation"
            }

        return "NO_CLEAR_OPPORTUNITY", "NEUTRAL", {
            "reason": "Intraday signals do not satisfy any primary opportunity criteria threshold"
        }
