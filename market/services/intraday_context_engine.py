"""
Intraday Market Context Calculation Engine for Nomad Analyst.

Provides deterministic, explainable calculations for:
- Market breadth (advances, declines, unchanged, A/D ratio, above/below VWAP)
- Sector strength and ranking (equal-weighted returns, constituent breadth, momentum)
- Relative strength (Stock vs NIFTY, Stock vs Sector)
- Volume confirmation states (CONFIRMED_UP, WEAK_UP, CONFIRMED_DOWN, WEAK_DOWN, NEUTRAL)
- Opening range structure (5m/15m ORB range and position)
- Deterministic market regime classification (TRENDING_UP, TRENDING_DOWN, RANGE, VOLATILE, TRANSITIONING)
- Intraday Opportunity Foundation dimensional scoring

Architecturally compatible with both live streaming and historical backtesting/replay.
"""

import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import statistics

from market.services.intraday_config import (
    UNCHANGED_TOLERANCE_PCT,
    BREADTH_STRONG_RATIO,
    BREADTH_MODERATE_RATIO,
    BREADTH_STRONG_PCT,
    BREADTH_MODERATE_PCT,
    BREADTH_WEAK_PCT,
    PROXIMITY_TO_EXTREME_PCT,
    RS_STRONG_OUTPERFORM_PCT,
    RS_OUTPERFORM_PCT,
    RS_UNDERPERFORM_PCT,
    RS_STRONG_UNDERPERFORM_PCT,
    RVOL_CONFIRMED_HIGH,
    RVOL_WEAK_LOW,
    REGIME_VOLATILE_RANGE_PCT,
    REGIME_NIFTY_MOMENTUM_MIN_PCT,
    CONTEXT_FOUNDATION_WEIGHTS,
)
from market.services.trading_session import TradingSessionService

logger = logging.getLogger(__name__)


class IntradayMarketContextEngine:
    """
    Pure functional calculation engine for intraday market context.
    """

    @classmethod
    def calculate_stock_context(
        cls,
        stock_state: Dict[str, Any],
        nifty_return: Optional[Decimal] = None,
        sector_return: Optional[Decimal] = None,
        sector_rank: Optional[int] = None,
        total_sectors: int = 14,
        market_regime: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        Computes stock-level intraday metrics, relative strength, volume confirmation,
        opening-range state, and foundation scores.
        """
        symbol = stock_state.get("symbol", "UNKNOWN")
        last_price = Decimal(str(stock_state.get("last_price", 0)))
        prev_close = Decimal(str(stock_state.get("close") or stock_state.get("previous_close") or last_price))
        open_price = Decimal(str(stock_state.get("open") or last_price))
        high_price = Decimal(str(stock_state.get("high") or last_price))
        low_price = Decimal(str(stock_state.get("low") or last_price))
        volume = int(stock_state.get("volume", 0) or 0)
        
        # Change %
        change_pct = stock_state.get("change_percent") or stock_state.get("change_pct")
        if change_pct is not None:
            change_pct = Decimal(str(change_pct))
        elif prev_close > 0:
            change_pct = ((last_price - prev_close) / prev_close) * Decimal("100.0")
        else:
            change_pct = Decimal("0.0")

        # VWAP
        vwap = stock_state.get("vwap") or stock_state.get("average_price")
        if vwap is not None and float(vwap) > 0:
            vwap = Decimal(str(vwap))
            distance_from_vwap = ((last_price - vwap) / vwap) * Decimal("100.0")
            is_above_vwap = (last_price >= vwap)
        else:
            vwap = None
            distance_from_vwap = None
            is_above_vwap = None

        # Relative Volume
        rvol = stock_state.get("relative_volume")
        if rvol is not None:
            rvol = Decimal(str(rvol))

        # Momentums
        m5 = stock_state.get("momentum_5m")
        m15 = stock_state.get("momentum_15m")
        m30 = stock_state.get("momentum_30m")
        mom_5m = Decimal(str(m5)) if m5 is not None else None
        mom_15m = Decimal(str(m15)) if m15 is not None else None
        mom_30m = Decimal(str(m30)) if m30 is not None else None

        # Relative Strength
        rs_market = None
        if nifty_return is not None:
            rs_market = change_pct - nifty_return

        rs_sector = None
        if sector_return is not None:
            rs_sector = change_pct - sector_return

        # Volume Confirmation
        vol_confirmation = cls.classify_volume_confirmation(change_pct, rvol)

        # Opening Range Structure
        orb_state, opening_gap_pct = cls.classify_opening_structure(
            open_price, prev_close, last_price,
            stock_state.get("orb_15m_high"), stock_state.get("orb_15m_low")
        )

        # Foundation Component Scores
        component_scores = cls.calculate_foundation_scores(
            change_pct=change_pct,
            mom_5m=mom_5m,
            mom_15m=mom_15m,
            rs_market=rs_market,
            rs_sector=rs_sector,
            vol_confirmation=vol_confirmation,
            distance_from_vwap=distance_from_vwap,
            sector_rank=sector_rank,
            total_sectors=total_sectors,
            market_regime=market_regime,
        )

        # Weighted composite score
        context_score = Decimal("0.0")
        for key, weight in CONTEXT_FOUNDATION_WEIGHTS.items():
            sub_score = Decimal(str(component_scores.get(f"{key}_score", 50.0)))
            context_score += sub_score * Decimal(str(weight))

        return {
            "symbol": symbol,
            "last_price": last_price,
            "previous_close": prev_close,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "change_pct": change_pct,
            "vwap": vwap,
            "distance_from_vwap": distance_from_vwap,
            "is_above_vwap": is_above_vwap,
            "volume": volume,
            "relative_volume": rvol,
            "momentum_5m": mom_5m,
            "momentum_15m": mom_15m,
            "momentum_30m": mom_30m,
            "relative_strength_vs_market": rs_market,
            "relative_strength_vs_sector": rs_sector,
            "sector": stock_state.get("sector", "Unknown"),
            "sector_return": sector_return,
            "volume_confirmation": vol_confirmation,
            "opening_gap_pct": opening_gap_pct,
            "opening_range_state": orb_state,
            "component_scores": component_scores,
            "context_score": round(context_score, 2),
        }

    @classmethod
    def classify_volume_confirmation(
        cls, change_pct: Decimal, rvol: Optional[Decimal]
    ) -> str:
        """
        Determines whether volume behavior supports the price move.
        """
        if rvol is None:
            return "NEUTRAL"

        if change_pct > UNCHANGED_TOLERANCE_PCT:
            if rvol >= RVOL_CONFIRMED_HIGH:
                return "CONFIRMED_UP"
            elif rvol < RVOL_WEAK_LOW:
                return "WEAK_UP"
            return "NEUTRAL"
        elif change_pct < -UNCHANGED_TOLERANCE_PCT:
            if rvol >= RVOL_CONFIRMED_HIGH:
                return "CONFIRMED_DOWN"
            elif rvol < RVOL_WEAK_LOW:
                return "WEAK_DOWN"
            return "NEUTRAL"
        return "NEUTRAL"

    @classmethod
    def classify_opening_structure(
        cls,
        open_price: Decimal,
        prev_close: Decimal,
        last_price: Decimal,
        orb_high: Optional[Any],
        orb_low: Optional[Any],
    ) -> Tuple[str, Decimal]:
        """
        Evaluates opening gap and price position relative to 15m opening range.
        """
        opening_gap = Decimal("0.0")
        if prev_close > 0:
            opening_gap = ((open_price - prev_close) / prev_close) * Decimal("100.0")

        if orb_high is not None and orb_low is not None:
            high_val = Decimal(str(orb_high))
            low_val = Decimal(str(orb_low))
            if last_price > high_val:
                return "ABOVE_ORB", opening_gap
            elif last_price < low_val:
                return "BELOW_ORB", opening_gap
            else:
                return "INSIDE_ORB", opening_gap

        return "INSIDE_ORB", opening_gap

    @classmethod
    def calculate_foundation_scores(
        cls,
        change_pct: Decimal,
        mom_5m: Optional[Decimal],
        mom_15m: Optional[Decimal],
        rs_market: Optional[Decimal],
        rs_sector: Optional[Decimal],
        vol_confirmation: str,
        distance_from_vwap: Optional[Decimal],
        sector_rank: Optional[int],
        total_sectors: int,
        market_regime: str,
    ) -> Dict[str, float]:
        """
        Calculates separate, explainable component scores (0.0 to 100.0).
        """
        # 1. Momentum Score
        m_val = float(change_pct)
        if mom_15m is not None:
            m_val = (m_val * 0.5) + (float(mom_15m) * 0.5)
        momentum_score = min(max(50.0 + (m_val * 20.0), 0.0), 100.0)

        # 2. Relative Strength Score
        rs_m = float(rs_market) if rs_market is not None else 0.0
        rs_s = float(rs_sector) if rs_sector is not None else 0.0
        combined_rs = (rs_m * 0.6) + (rs_s * 0.4)
        relative_strength_score = min(max(50.0 + (combined_rs * 25.0), 0.0), 100.0)

        # 3. Volume Confirmation Score
        vol_map = {
            "CONFIRMED_UP": 90.0,
            "WEAK_UP": 40.0,
            "CONFIRMED_DOWN": 20.0,
            "WEAK_DOWN": 45.0,
            "NEUTRAL": 50.0,
        }
        volume_score = vol_map.get(vol_confirmation, 50.0)

        # 4. VWAP Alignment Score
        if distance_from_vwap is not None:
            d = float(distance_from_vwap)
            if d >= 0:
                # Modest positive distance (+0.2% to +1.5%) is ideal
                vwap_score = min(60.0 + (d * 25.0), 95.0) if d <= 1.5 else max(95.0 - ((d - 1.5) * 20.0), 50.0)
            else:
                vwap_score = max(50.0 + (d * 20.0), 5.0)
        else:
            vwap_score = 50.0

        # 5. Sector Alignment Score
        if sector_rank is not None and total_sectors > 0:
            rank_ratio = (total_sectors - sector_rank + 1) / total_sectors
            sector_score = 30.0 + (rank_ratio * 65.0)
        else:
            sector_score = 50.0

        # 6. Market Alignment Score
        is_bullish_regime = market_regime in ("TRENDING_UP", "BULLISH")
        is_bearish_regime = market_regime in ("TRENDING_DOWN", "BEARISH")
        if is_bullish_regime:
            market_score = 85.0 if change_pct > 0 else 30.0
        elif is_bearish_regime:
            market_score = 25.0 if change_pct > 0 else 80.0
        else:
            market_score = 50.0

        return {
            "momentum_score": round(momentum_score, 1),
            "relative_strength_score": round(relative_strength_score, 1),
            "volume_confirmation_score": round(volume_score, 1),
            "vwap_alignment_score": round(vwap_score, 1),
            "sector_alignment_score": round(sector_score, 1),
            "market_alignment_score": round(market_score, 1),
        }

    @classmethod
    def get_daily_smas(cls) -> Dict[str, Dict[str, float]]:
        """
        Retrieves latest daily SMA50 and SMA200 values from cache or TechnicalFeature DB.
        Caches for 5 minutes.
        """
        from django.core.cache import cache
        cache_key = "market:intraday:daily_smas"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        smas: Dict[str, Dict[str, float]] = {}
        try:
            from market.models import TechnicalFeature
            from django.db.models import Max
            latest_ts = TechnicalFeature.objects.filter(
                timeframe="1d",
                name__in=["SMA_50", "SMA_200"]
            ).aggregate(m=Max("timestamp"))["m"]

            if latest_ts:
                records = TechnicalFeature.objects.filter(
                    timeframe="1d",
                    name__in=["SMA_50", "SMA_200"],
                    timestamp=latest_ts
                ).select_related("instrument")
                for r in records:
                    sym = r.instrument.symbol
                    if sym not in smas:
                        smas[sym] = {}
                    if r.name == "SMA_50" and r.value is not None:
                        smas[sym]["sma50"] = float(r.value)
                    elif r.name == "SMA_200" and r.value is not None:
                        smas[sym]["sma200"] = float(r.value)

            cache.set(cache_key, smas, timeout=300)
        except Exception as e:
            logger.debug(f"Error loading daily SMAs for breadth: {e}")

        return smas

    @classmethod
    def calculate_market_breadth(cls, constituent_states: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates NIFTY 50 breadth metrics:
        advances, declines, unchanged, A/D ratio, above/below VWAP, new highs/lows,
        and daily SMA participation (SMA50, SMA200).
        """
        total = len(constituent_states)
        if total == 0:
            return {
                "total_constituents": 0,
                "advance_count": 0,
                "decline_count": 0,
                "unchanged_count": 0,
                "advance_pct": Decimal("0.0"),
                "decline_pct": Decimal("0.0"),
                "unchanged_pct": Decimal("0.0"),
                "advance_decline_ratio": Decimal("1.0"),
                "above_vwap_count": 0,
                "below_vwap_count": 0,
                "above_vwap_pct": Decimal("0.0"),
                "below_vwap_pct": Decimal("0.0"),
                "at_high_count": 0,
                "at_low_count": 0,
                "breadth_state": "NEUTRAL",
                "pct_above_sma50": Decimal("0.0"),
                "pct_above_sma200": Decimal("0.0"),
                "pct_above_50_sma": Decimal("0.0"),
                "pct_above_200_sma": Decimal("0.0"),
                "participation": {
                    "pct_above_sma50": 0.0,
                    "pct_above_sma200": 0.0,
                },
            }

        advances = 0
        declines = 0
        unchanged = 0
        above_vwap = 0
        below_vwap = 0
        at_high = 0
        at_low = 0

        # SMA Participation counters
        above_sma50_count = 0
        above_sma200_count = 0
        sma_covered_50 = 0
        sma_covered_200 = 0
        daily_smas = cls.get_daily_smas()

        for state in constituent_states:
            chg = state.get("change_pct")
            if chg is None:
                chg = state.get("change_percent", Decimal("0.0"))
            chg = Decimal(str(chg))

            if chg > UNCHANGED_TOLERANCE_PCT:
                advances += 1
            elif chg < -UNCHANGED_TOLERANCE_PCT:
                declines += 1
            else:
                unchanged += 1

            # VWAP position
            price = Decimal(str(state.get("last_price", 0)))
            vwap = state.get("vwap") or state.get("average_price")
            if vwap is not None and float(vwap) > 0:
                v_dec = Decimal(str(vwap))
                if price >= v_dec:
                    above_vwap += 1
                else:
                    below_vwap += 1

            # High/Low proximity
            high = Decimal(str(state.get("high", 0)))
            low = Decimal(str(state.get("low", 0)))
            if high > 0 and (high - price) / high * Decimal("100.0") <= PROXIMITY_TO_EXTREME_PCT:
                at_high += 1
            if low > 0 and (price - low) / low * Decimal("100.0") <= PROXIMITY_TO_EXTREME_PCT:
                at_low += 1

            # SMA participation
            sym = state.get("symbol")
            p_float = float(price)
            if "above_sma50" in state and state["above_sma50"] is not None:
                sma_covered_50 += 1
                if state["above_sma50"]:
                    above_sma50_count += 1
            else:
                s50 = state.get("sma50") or (daily_smas.get(sym, {}).get("sma50") if sym else None)
                if s50 and s50 > 0:
                    sma_covered_50 += 1
                    if p_float >= s50:
                        above_sma50_count += 1

            if "above_sma200" in state and state["above_sma200"] is not None:
                sma_covered_200 += 1
                if state["above_sma200"]:
                    above_sma200_count += 1
            else:
                s200 = state.get("sma200") or (daily_smas.get(sym, {}).get("sma200") if sym else None)
                if s200 and s200 > 0:
                    sma_covered_200 += 1
                    if p_float >= s200:
                        above_sma200_count += 1

        total_dec = Decimal(str(total))
        adv_pct = round((Decimal(str(advances)) / total_dec) * Decimal("100.0"), 2)
        dec_pct = round((Decimal(str(declines)) / total_dec) * Decimal("100.0"), 2)
        unch_pct = round((Decimal(str(unchanged)) / total_dec) * Decimal("100.0"), 2)

        vwap_total = above_vwap + below_vwap
        above_vwap_pct = round((Decimal(str(above_vwap)) / Decimal(str(vwap_total))) * Decimal("100.0"), 2) if vwap_total > 0 else Decimal("0.0")
        below_vwap_pct = round((Decimal(str(below_vwap)) / Decimal(str(vwap_total))) * Decimal("100.0"), 2) if vwap_total > 0 else Decimal("0.0")

        ad_ratio = round(Decimal(str(advances)) / Decimal(str(max(declines, 1))), 2)

        pct_above_sma50 = round(Decimal(str(above_sma50_count)) / Decimal(str(sma_covered_50)) * Decimal("100.0"), 2) if sma_covered_50 > 0 else Decimal("0.0")
        pct_above_sma200 = round(Decimal(str(above_sma200_count)) / Decimal(str(sma_covered_200)) * Decimal("100.0"), 2) if sma_covered_200 > 0 else Decimal("0.0")

        # Breadth State determination
        if adv_pct >= BREADTH_STRONG_PCT and ad_ratio >= BREADTH_STRONG_RATIO:
            breadth_state = "STRONG_POSITIVE"
        elif adv_pct >= BREADTH_MODERATE_PCT and ad_ratio >= BREADTH_MODERATE_RATIO:
            breadth_state = "POSITIVE"
        elif dec_pct >= BREADTH_STRONG_PCT and ad_ratio <= Decimal("0.5"):
            breadth_state = "STRONG_NEGATIVE"
        elif dec_pct >= BREADTH_MODERATE_PCT and ad_ratio <= Decimal("0.77"):
            breadth_state = "NEGATIVE"
        else:
            breadth_state = "NEUTRAL"

        return {
            "total_constituents": total,
            "advance_count": advances,
            "decline_count": declines,
            "unchanged_count": unchanged,
            "advance_pct": adv_pct,
            "decline_pct": dec_pct,
            "unchanged_pct": unch_pct,
            "advance_decline_ratio": ad_ratio,
            "above_vwap_count": above_vwap,
            "below_vwap_count": below_vwap,
            "above_vwap_pct": above_vwap_pct,
            "below_vwap_pct": below_vwap_pct,
            "at_high_count": at_high,
            "at_low_count": at_low,
            "breadth_state": breadth_state,
            "pct_above_sma50": pct_above_sma50,
            "pct_above_sma200": pct_above_sma200,
            "pct_above_50_sma": pct_above_sma50,
            "pct_above_200_sma": pct_above_sma200,
            "participation": {
                "pct_above_sma50": float(pct_above_sma50),
                "pct_above_sma200": float(pct_above_sma200),
            },
        }

    @classmethod
    def calculate_sector_strengths(
        cls,
        constituent_states: List[Dict[str, Any]],
        nifty_return: Optional[Decimal] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregates constituent performance by sector, calculating equal-weighted returns,
        constituent counts, breadth, momentum, and deterministic rankings.
        """
        sectors_map: Dict[str, List[Dict[str, Any]]] = {}
        for item in constituent_states:
            sec = item.get("sector") or "Unknown"
            if sec not in sectors_map:
                sectors_map[sec] = []
            sectors_map[sec].append(item)

        results = []
        for sector_name, items in sectors_map.items():
            count = len(items)
            returns = [float(it.get("change_pct", it.get("change_percent", 0)) or 0) for it in items]
            avg_return = Decimal(str(round(sum(returns) / count, 2))) if count > 0 else Decimal("0.0")
            med_return = Decimal(str(round(statistics.median(returns), 2))) if count > 0 else Decimal("0.0")

            adv_count = sum(1 for r in returns if r > float(UNCHANGED_TOLERANCE_PCT))
            dec_count = sum(1 for r in returns if r < -float(UNCHANGED_TOLERANCE_PCT))
            adv_pct = round((Decimal(str(adv_count)) / Decimal(str(count))) * Decimal("100.0"), 2)

            above_v_count = 0
            v_total = 0
            for it in items:
                p = float(it.get("last_price", 0))
                v = it.get("vwap") or it.get("average_price")
                if v and float(v) > 0:
                    v_total += 1
                    if p >= float(v):
                        above_v_count += 1
            above_vwap_pct = round((Decimal(str(above_v_count)) / Decimal(str(v_total))) * Decimal("100.0"), 2) if v_total > 0 else Decimal("0.0")

            rs_nifty = None
            if nifty_return is not None:
                rs_nifty = avg_return - nifty_return

            results.append({
                "sector": sector_name,
                "name": sector_name,
                "constituent_count": count,
                "average_return": avg_return,
                "return_pct": avg_return,
                "median_return": med_return,
                "advance_count": adv_count,
                "decline_count": dec_count,
                "advance_pct": adv_pct,
                "above_vwap_pct": above_vwap_pct,
                "relative_strength_vs_nifty": rs_nifty,
            })

        # Deterministic sorting: highest average return first (tiebreak: advance_pct, above_vwap_pct)
        results.sort(key=lambda s: (s["average_return"], s["advance_pct"], s["above_vwap_pct"]), reverse=True)

        # Assign ranks
        for idx, item in enumerate(results):
            item["rank"] = idx + 1

        return results

    @classmethod
    def classify_market_regime(
        cls,
        nifty_state: Dict[str, Any],
        banknifty_state: Dict[str, Any],
        breadth: Dict[str, Any],
        sector_strengths: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Classifies overall market regime deterministically into:
        TRENDING_UP, TRENDING_DOWN, RANGE, VOLATILE, TRANSITIONING, or UNKNOWN.
        Provides a transparent array of supporting reasons.
        """
        reasons: List[str] = []
        nifty_chg = Decimal(str(nifty_state.get("change_percent") or nifty_state.get("change_pct", 0) or 0))
        nifty_price = Decimal(str(nifty_state.get("last_price", 0) or 0))
        nifty_open = Decimal(str(nifty_state.get("open", 0) or nifty_price))
        nifty_high = Decimal(str(nifty_state.get("high", 0) or nifty_price))
        nifty_low = Decimal(str(nifty_state.get("low", 0) or nifty_price))
        nifty_vwap = nifty_state.get("vwap") or nifty_state.get("average_price")

        banknifty_chg = Decimal(str(banknifty_state.get("change_percent") or banknifty_state.get("change_pct", 0) or 0))

        # 1. Volatility check
        day_range_pct = Decimal("0.0")
        if nifty_open > 0:
            day_range_pct = ((nifty_high - nifty_low) / nifty_open) * Decimal("100.0")

        is_high_volatility = day_range_pct >= REGIME_VOLATILE_RANGE_PCT
        if is_high_volatility:
            reasons.append(f"NIFTY day range {day_range_pct:.2f}% exceeds volatility threshold ({REGIME_VOLATILE_RANGE_PCT}%)")

        # 2. VWAP position
        is_nifty_above_vwap = False
        if nifty_vwap and float(nifty_vwap) > 0:
            is_nifty_above_vwap = nifty_price >= Decimal(str(nifty_vwap))
            reasons.append(f"NIFTY {'above' if is_nifty_above_vwap else 'below'} session VWAP ({Decimal(str(nifty_vwap)):.2f})")

        # 3. Breadth confirmation
        adv_pct = breadth.get("advance_pct", Decimal("0.0"))
        dec_pct = breadth.get("decline_pct", Decimal("0.0"))
        ad_ratio = breadth.get("advance_decline_ratio", Decimal("1.0"))
        reasons.append(f"Breadth: {breadth.get('advance_count', 0)} advancing ({adv_pct}%), {breadth.get('decline_count', 0)} declining (A/D {ad_ratio:.2f})")

        # 4. Sector participation
        pos_sectors = sum(1 for s in sector_strengths if s["average_return"] > 0)
        tot_sectors = len(sector_strengths) or 1
        sec_ratio = pos_sectors / tot_sectors
        reasons.append(f"Sector breadth: {pos_sectors}/{tot_sectors} positive ({sec_ratio*100:.0f}%)")

        # 5. Index Confirmation
        index_confirmed_bullish = nifty_chg > Decimal("0.15") and banknifty_chg > Decimal("0.15")
        index_confirmed_bearish = nifty_chg < Decimal("-0.15") and banknifty_chg < Decimal("-0.15")
        index_divergent = (nifty_chg * banknifty_chg < 0) and (abs(nifty_chg) > Decimal("0.1") or abs(banknifty_chg) > Decimal("0.1"))
        if index_confirmed_bullish:
            reasons.append(f"Index confirmation: NIFTY ({nifty_chg:+.2f}%) and BANKNIFTY ({banknifty_chg:+.2f}%) both advancing")
        elif index_confirmed_bearish:
            reasons.append(f"Index confirmation: NIFTY ({nifty_chg:+.2f}%) and BANKNIFTY ({banknifty_chg:+.2f}%) both declining")
        elif index_divergent:
            reasons.append(f"Index divergence: NIFTY ({nifty_chg:+.2f}%) vs BANKNIFTY ({banknifty_chg:+.2f}%)")

        # Classification decision matrix
        if is_high_volatility and (abs(adv_pct - dec_pct) < Decimal("20.0")):
            regime = "VOLATILE"
            confidence = 0.80
        elif (
            nifty_chg >= Decimal("0.3")
            and is_nifty_above_vwap
            and adv_pct >= BREADTH_MODERATE_PCT
            and sec_ratio >= 0.55
        ):
            regime = "TRENDING_UP"
            confidence = 0.85 if adv_pct >= BREADTH_STRONG_PCT else 0.72
        elif (
            nifty_chg <= Decimal("-0.3")
            and not is_nifty_above_vwap
            and dec_pct >= BREADTH_MODERATE_PCT
            and sec_ratio <= 0.45
        ):
            regime = "TRENDING_DOWN"
            confidence = 0.85 if dec_pct >= BREADTH_STRONG_PCT else 0.72
        elif index_divergent:
            regime = "TRANSITIONING"
            confidence = 0.65
        elif abs(nifty_chg) < Decimal("0.25") and abs(adv_pct - dec_pct) < Decimal("20.0"):
            regime = "RANGE"
            confidence = 0.75
        else:
            regime = "TRANSITIONING" if abs(nifty_chg) >= Decimal("0.2") else "RANGE"
            confidence = 0.60

        return {
            "regime": regime,
            "confidence": confidence,
            "reasons": reasons,
            "day_range_pct": day_range_pct,
            "index_confirmation": "CONFIRMED_BULLISH" if index_confirmed_bullish else ("CONFIRMED_BEARISH" if index_confirmed_bearish else ("DIVERGENT" if index_divergent else "NEUTRAL")),
        }

    @classmethod
    def build_market_context_snapshot(
        cls,
        constituent_states: List[Dict[str, Any]],
        index_states: Dict[str, Dict[str, Any]],
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Executes full pipeline and returns unified market context payload.
        """
        as_of_dt = TradingSessionService.to_ist(as_of or datetime.now())

        # Extract index states
        nifty_state = index_states.get("NIFTY") or index_states.get("^NSEI") or {}
        banknifty_state = index_states.get("BANKNIFTY") or index_states.get("^NSEBANK") or {}
        sensex_state = index_states.get("SENSEX") or index_states.get("^BSESN") or {}
        nifty_it_state = index_states.get("NIFTYIT") or index_states.get("^CNXIT") or {}
        nifty_ret = Decimal(str(nifty_state.get("change_percent") or nifty_state.get("change_pct", 0) or 0))
        banknifty_ret = Decimal(str(banknifty_state.get("change_percent") or banknifty_state.get("change_pct", 0) or 0))
        sensex_ret = Decimal(str(sensex_state.get("change_percent") or sensex_state.get("change_pct", 0) or 0))
        nifty_it_ret = Decimal(str(nifty_it_state.get("change_percent") or nifty_it_state.get("change_pct", 0) or 0))

        # 1. Breadth
        breadth = cls.calculate_market_breadth(constituent_states)

        # 2. Sector Strengths
        sector_strengths = cls.calculate_sector_strengths(constituent_states, nifty_return=nifty_ret)
        sector_leader = sector_strengths[0]["sector"] if sector_strengths else None
        sector_laggard = sector_strengths[-1]["sector"] if sector_strengths else None

        # Build sector lookup for constituent context
        sector_map = {s["sector"]: s for s in sector_strengths}

        # 3. Market Regime
        regime_info = cls.classify_market_regime(nifty_state, banknifty_state, breadth, sector_strengths)

        # Market direction
        if nifty_ret > Decimal("0.25"):
            direction = "BULLISH"
        elif nifty_ret < Decimal("-0.25"):
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        # 4. Enriched Stock Contexts
        stock_contexts = []
        tot_sectors = len(sector_strengths)
        for st in constituent_states:
            sec_name = st.get("sector") or "Unknown"
            sec_info = sector_map.get(sec_name, {})
            ctx = cls.calculate_stock_context(
                stock_state=st,
                nifty_return=nifty_ret,
                sector_return=sec_info.get("average_return"),
                sector_rank=sec_info.get("rank"),
                total_sectors=tot_sectors,
                market_regime=regime_info["regime"],
            )
            stock_contexts.append(ctx)

        return {
            "as_of": as_of_dt.isoformat(),
            "market_direction": direction,
            "market_regime": regime_info["regime"],
            "regime_confidence": regime_info["confidence"],
            "regime_reasons": regime_info["reasons"],
            "index_confirmation": regime_info["index_confirmation"],
            "market_volatility": "HIGH" if regime_info["day_range_pct"] >= REGIME_VOLATILE_RANGE_PCT else "NORMAL",
            "nifty": {
                "symbol": "^NSEI",
                "name": "NIFTY 50",
                "price": float(nifty_state.get("last_price", 0) or 0),
                "change": float(nifty_state.get("change", 0) or 0),
                "change_percent": float(nifty_ret),
                "open": float(nifty_state.get("open", 0) or 0),
                "high": float(nifty_state.get("high", 0) or 0),
                "low": float(nifty_state.get("low", 0) or 0),
                "vwap": float(nifty_state.get("vwap") or nifty_state.get("average_price") or 0) or None,
            },
            "banknifty": {
                "symbol": "^NSEBANK",
                "name": "NIFTY BANK",
                "price": float(banknifty_state.get("last_price", 0) or 0),
                "change": float(banknifty_state.get("change", 0) or 0),
                "change_percent": float(banknifty_ret),
                "open": float(banknifty_state.get("open", 0) or 0),
                "high": float(banknifty_state.get("high", 0) or 0),
                "low": float(banknifty_state.get("low", 0) or 0),
                "vwap": float(banknifty_state.get("vwap") or banknifty_state.get("average_price") or 0) or None,
            },
            "sensex": {
                "symbol": "^BSESN",
                "name": "S&P BSE SENSEX",
                "price": float(sensex_state.get("last_price", 0) or 0),
                "change": float(sensex_state.get("change", 0) or 0),
                "change_percent": float(sensex_ret),
                "open": float(sensex_state.get("open", 0) or 0),
                "high": float(sensex_state.get("high", 0) or 0),
                "low": float(sensex_state.get("low", 0) or 0),
                "vwap": float(sensex_state.get("vwap") or sensex_state.get("average_price") or 0) or None,
            } if sensex_state else None,
            "nifty_it": {
                "symbol": "^CNXIT",
                "name": "NIFTY IT",
                "price": float(nifty_it_state.get("last_price", 0) or 0),
                "change": float(nifty_it_state.get("change", 0) or 0),
                "change_percent": float(nifty_it_ret),
                "open": float(nifty_it_state.get("open", 0) or 0),
                "high": float(nifty_it_state.get("high", 0) or 0),
                "low": float(nifty_it_state.get("low", 0) or 0),
                "vwap": float(nifty_it_state.get("vwap") or nifty_it_state.get("average_price") or 0) or None,
            } if nifty_it_state else None,
            "breadth": breadth,
            "sectors": sector_strengths,
            "sector_leader": sector_leader,
            "sector_laggard": sector_laggard,
            "stocks": stock_contexts,
        }
