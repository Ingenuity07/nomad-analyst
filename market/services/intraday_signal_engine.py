"""
intraday_signal_engine.py — Dedicated intraday signal generation engine (Module 10).

CRITICAL SEPARATION:
  This class is SEPARATE from signal_engine.py (Module 8).
  The daily/delivery SignalEngine is untouched.
  This engine only handles INTRADAY horizon recommendations.

Responsibilities:
  1. Gate on IntradayReadinessService (Module 9)
  2. Load intraday bars (PIT-safe, bounded lookback)
  3. Compute IntradayIndicators from raw bars (in-memory, not from TechnicalFeature table)
  4. Compute OpeningRange for today's session
  5. Classify session window
  6. Evaluate no-trade conditions
  7. Run applicable intraday detectors (session-filtered)
  8. Check cooldown
  9. Calculate entry (setup-specific), stop (structure → ATR), targets (T1 + T2)
  10. Validate R:R — reject if below minimum
  11. Compute multi-dimensional confidence
  12. Compute session expiry
  13. Return RecommendationDraft

The LLM never touches this module.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from market.signal_enums import (
    SignalDirection, SignalHorizon, SetupType, ConfidenceLevel,
    RecommendationStatus, EntryType, StopMethod, TargetMethod,
)
from market.services.signal_engine import RecommendationDraft, _s, _parse_as_of
from market.services.setup_detectors import SetupResult
from market.intraday_strategy_config import (
    STRATEGY_VERSION, DEFAULT_INTRADAY_TIMEFRAME, MIN_BARS_FOR_ANALYSIS,
    MIN_RISK_REWARD_INTRADAY, MIN_RELATIVE_VOLUME, MIN_TAPE_VOLUME,
    MAX_VOLATILITY_RATIO, STOP_ATR_MULTIPLIER, TARGET_1_ATR_MULTIPLIER,
    TARGET_2_ATR_MULTIPLIER, REGIME_GATE_RULES, COOLDOWN_MINUTES,
)
from market.services.intraday_readiness import IntradayReadinessService
from market.services.intraday_session import classify_session
from market.services.intraday_indicators import compute_intraday_indicators
from market.services.opening_range import compute_opening_range
from market.services.intraday_detectors import run_intraday_detectors
from market.services.intraday_cooldown import is_in_cooldown, cooldown_reason
from market.services.intraday_lifecycle import compute_session_expiry

logger = logging.getLogger(__name__)

REGIME_GATE_RULES_INTRADAY = {
    "BULLISH_BUY_BOOST":   10.0,
    "BEARISH_BUY_PENALTY": -20.0,
    "HIGH_VOL_PENALTY":    -10.0,
    "WEAK_SECTOR_PENALTY": -10.0,
    "STRONG_SECTOR_BOOST":  5.0,
}

INTRADAY_CONFIDENCE_WEIGHTS = {
    "setup_quality":    0.30,
    "volume_confirm":   0.25,
    "market_alignment": 0.20,
    "sector_alignment": 0.15,
    "relative_strength": 0.10,
}


class IntradaySignalEngine:
    """
    Deterministic intraday signal generation service.

    Usage:
        engine = IntradaySignalEngine()
        draft = engine.generate_recommendation(instrument, timeframe="5m", as_of=dt)
    """

    def generate_recommendation(
        self,
        instrument,
        timeframe: str = DEFAULT_INTRADAY_TIMEFRAME,
        as_of: Any = None,
    ) -> RecommendationDraft:
        """
        Generate a fully deterministic intraday recommendation.
        Returns a RecommendationDraft (NOT persisted here).
        """
        from market.models import OHLCVBar, MarketContextSnapshot
        from market.services.market_session import IndianMarketSession, IST

        dt_as_of = _parse_as_of(as_of)
        dt_ist = dt_as_of.astimezone(IST)

        # ── Gate 1: IntradayReadinessService ─────────────────────────────────
        readiness = IntradayReadinessService().check_readiness(
            instrument, timeframe, as_of=dt_as_of
        )
        if not readiness.is_ready:
            return self._not_ready_draft(instrument, timeframe, dt_as_of,
                                         f"INTRADAY NOT_READY [{timeframe}]: {readiness.reason}")

        # ── Load intraday bars (PIT-safe, bounded lookback) ───────────────────
        # Load last 200 bars, all with timestamp <= as_of
        bars = list(OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__lte=dt_as_of,
        ).order_by("-timestamp")[:200])
        bars.reverse()  # oldest-first

        min_bars = MIN_BARS_FOR_ANALYSIS.get(timeframe, 30)
        if len(bars) < min_bars:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"Insufficient intraday bars ({len(bars)} < {min_bars} required)",
                {}, {}, {"status": "PARTIAL"}
            )

        latest_bar = bars[-1]
        close = float(latest_bar.close)

        # ── Gate 2: Stale data check ──────────────────────────────────────────
        bar_age_minutes = (dt_as_of - latest_bar.timestamp).total_seconds() / 60
        if bar_age_minutes > 10:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"Latest intraday bar is {bar_age_minutes:.0f} minutes old (stale data)",
                {}, {}, {"status": "STALE"}
            )

        # ── Compute indicators (in-memory, session-anchored) ──────────────────
        session_date = dt_ist.date()

        # Try to load NIFTY index bars for relative strength
        index_bars = self._load_index_bars(dt_as_of, timeframe, bars)

        ind = compute_intraday_indicators(bars, session_date, index_bars=index_bars)

        # ── Compute Opening Range ─────────────────────────────────────────────
        or_range = compute_opening_range(bars, session_date, timeframe)

        # ── Session window classification ─────────────────────────────────────
        sw = classify_session(dt_as_of)
        session_window = sw.window

        # ── Gate 3: Outside trading session ───────────────────────────────────
        if not sw.is_valid_for_trading:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"Outside trading session (window={session_window})",
                {}, {}, {"status": "OUTSIDE_SESSION"}
            )

        # ── Gate 4: Dead tape check ───────────────────────────────────────────
        if ind.relative_volume is not None and ind.relative_volume < MIN_TAPE_VOLUME:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"Extremely low volume (rel_vol={ind.relative_volume:.2f} < {MIN_TAPE_VOLUME}) — dead tape",
                {}, {}, {"status": "LOW_VOLUME"}
            )

        # ── Gate 5: Extreme volatility check ─────────────────────────────────
        if ind.atr is not None and close > 0:
            atr_ratio = ind.atr / close
            if atr_ratio > MAX_VOLATILITY_RATIO:
                return self._no_action_draft(
                    instrument, timeframe, dt_as_of,
                    f"Extreme intraday volatility (ATR/price={atr_ratio:.3f} > {MAX_VOLATILITY_RATIO})",
                    {}, {}, {"status": "HIGH_VOLATILITY"}
                )

        # ── Market context ─────────────────────────────────────────────────────
        mkt_snapshot = MarketContextSnapshot.objects.filter(
            as_of__lte=dt_as_of
        ).order_by('-as_of').first()

        market_context: Dict[str, Any] = {}
        if mkt_snapshot:
            market_context = {
                "index_regimes": mkt_snapshot.index_regimes or {},
                "breadth": mkt_snapshot.breadth or {},
            }

        sector_context: Dict[str, Any] = {}
        sector_name = instrument.company.sector if instrument.company else None
        if mkt_snapshot and mkt_snapshot.sector_rankings and sector_name:
            for item in mkt_snapshot.sector_rankings:
                if item.get("sector") == sector_name:
                    sector_context = item
                    break

        # ── Run intraday detectors (session-filtered) ─────────────────────────
        prev_close = float(bars[-2].close) if len(bars) >= 2 else None

        all_results = run_intraday_detectors(
            ind=ind,
            or_range=or_range,
            bars=bars,
            session_window=session_window,
            prev_bar_close=prev_close,
        )

        # Pick best detected setup
        detected_results = [r for r in all_results if r.detected]
        if not detected_results:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"No intraday setup detected (session={session_window}, "
                f"evaluated {len(all_results)} detectors)",
                market_context, sector_context,
                {"status": "NO_SETUP", "session_window": session_window}
            )

        best = detected_results[0]

        # ── Determine direction ───────────────────────────────────────────────
        if best.setup_type in (
            SetupType.OPENING_RANGE_BREAKDOWN,
            SetupType.VWAP_REJECTION,
        ):
            direction = SignalDirection.SELL.value
        else:
            direction = SignalDirection.BUY.value

        # ── Gate 6: Cooldown ──────────────────────────────────────────────────
        cd_reason = cooldown_reason(
            instrument, direction, best.setup_type.value, dt_as_of, COOLDOWN_MINUTES
        )
        if cd_reason:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of, cd_reason,
                market_context, sector_context,
                {"status": "COOLDOWN", "setup": best.setup_type.value}
            )

        # ── Entry, Stop, Target ───────────────────────────────────────────────
        entry_type, entry_price, entry_condition = self._compute_entry(
            best, close, ind, or_range, direction
        )
        stop_price, stop_method, invalidation_reason = self._compute_stop(
            best, entry_price, close, ind, direction
        )
        target_1_price, target_1_method, target_2_price, target_2_method = self._compute_targets(
            best, entry_price, stop_price, ind, or_range, direction
        )

        # ── Risk / Reward ─────────────────────────────────────────────────────
        risk = reward = rr_ratio = None
        rr_rejected = False
        if entry_price and stop_price and target_1_price:
            if direction == SignalDirection.BUY.value:
                risk   = abs(entry_price - stop_price)
                reward = abs(target_1_price - entry_price)
            else:
                risk   = abs(stop_price - entry_price)
                reward = abs(entry_price - target_1_price)

            if risk > 0:
                rr_ratio = round(reward / risk, 2)
                if rr_ratio < MIN_RISK_REWARD_INTRADAY:
                    rr_rejected = True

        if rr_rejected:
            return self._no_action_draft(
                instrument, timeframe, dt_as_of,
                f"R:R={rr_ratio:.2f} < minimum {MIN_RISK_REWARD_INTRADAY} — setup rejected",
                market_context, sector_context,
                {"status": "POOR_RR", "rr": rr_ratio}
            )

        # ── Confidence ────────────────────────────────────────────────────────
        confidence_level, confidence_components = self._compute_confidence(
            best, ind, market_context, sector_context, direction
        )

        # ── Supporting / risk factors ─────────────────────────────────────────
        supporting = list(best.conditions_met)
        risks = list(best.conditions_failed)

        nifty_trend = market_context.get("index_regimes", {}).get("^NSEI", {}).get("trend", "sideways")
        if direction == SignalDirection.BUY.value:
            if nifty_trend == "bullish":
                supporting.append("Market regime bullish — aligns with BUY")
            elif nifty_trend == "bearish":
                risks.append("Market regime bearish — headwind for BUY setup")

        sector_tier = sector_context.get("tier", "neutral")
        if sector_tier == "strongest":
            supporting.append(f"Sector '{sector_name}' is a top-performing sector")
        elif sector_tier == "weakest":
            risks.append(f"Sector '{sector_name}' is underperforming — added risk")

        if ind.relative_strength_available and ind.relative_strength is not None:
            if ind.relative_strength > 1.0:
                supporting.append(f"Relative strength vs index: +{ind.relative_strength:.2f}%")
            elif ind.relative_strength < -1.0:
                risks.append(f"Relative weakness vs index: {ind.relative_strength:.2f}%")

        # ── Session expiry ─────────────────────────────────────────────────────
        expires_at = compute_session_expiry(session_date, timeframe)

        # ── Build draft ───────────────────────────────────────────────────────
        draft = RecommendationDraft(
            instrument_id=str(instrument.id),
            horizon=SignalHorizon.INTRADAY.value,
            signal=direction,
            setup_type=best.setup_type.value,
            as_of=dt_as_of,
            entry_type=entry_type,
            entry_price=entry_price,
            entry_condition=entry_condition,
            stop_price=stop_price,
            stop_method=stop_method,
            invalidation_reason=invalidation_reason,
            target_price=target_1_price,
            target_method=target_1_method,
            risk=round(risk, 2) if risk else None,
            reward=round(reward, 2) if reward else None,
            risk_reward_ratio=rr_ratio,
            confidence=confidence_level,
            confidence_components=confidence_components,
            market_context=market_context,
            sector_context=sector_context,
            supporting_factors=supporting,
            risk_factors=risks,
            setup_details={
                **best.as_dict(),
                "session_window": session_window,
                "or_range": {
                    "high": or_range.high, "low": or_range.low,
                    "range_pct": or_range.range_pct, "is_complete": or_range.is_complete,
                } if or_range else None,
                "intraday_indicators": ind.as_dict(),
                "strategy_version": STRATEGY_VERSION,
                "target_2_price": target_2_price,
                "target_2_method": target_2_method,
            },
            data_quality={"status": "COMPLETE", "timeframe": timeframe,
                          "bar_count": len(bars), "session_window": session_window},
            calculation_version=1,
        )

        # Attach intraday-specific extras so RecommendationService can persist them
        draft._intraday_extras = {
            "timeframe": timeframe,
            "target_2_price": target_2_price,
            "target_2_method": target_2_method,
            "session_window": session_window,
            "strategy_version": STRATEGY_VERSION,
            "expires_at": expires_at,
        }

        return draft

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_index_bars(self, as_of, timeframe, stock_bars):
        """Try to load NIFTY 5m bars for relative strength computation."""
        try:
            from market.models import OHLCVBar, Instrument
            nifty = Instrument.objects.filter(symbol="^NSEI").first()
            if not nifty:
                return None
            lookback = min(25, len(stock_bars))
            start_ts = stock_bars[-lookback].timestamp if stock_bars else as_of
            index_bars = list(OHLCVBar.objects.filter(
                instrument=nifty,
                timeframe=timeframe,
                timestamp__gte=start_ts,
                timestamp__lte=as_of,
            ).order_by("timestamp"))
            return index_bars or None
        except Exception:
            return None

    def _compute_entry(self, setup, close, ind, or_range, direction):
        """Setup-specific entry logic."""
        if setup.setup_type == SetupType.OPENING_RANGE_BREAKOUT and or_range:
            ep = round(or_range.high * 1.002, 2)
            return (
                EntryType.BREAKOUT_CONFIRMATION.value, ep,
                f"Enter only if price sustains above {ep:.2f} (0.2% above OR high {or_range.high:.2f})"
            )
        elif setup.setup_type == SetupType.OPENING_RANGE_BREAKDOWN and or_range:
            ep = round(or_range.low * 0.998, 2)
            return (
                EntryType.BREAKOUT_CONFIRMATION.value, ep,
                f"Enter short on close below {ep:.2f} (0.2% below OR low {or_range.low:.2f})"
            )
        elif setup.setup_type == SetupType.INTRADAY_MOMENTUM_CONTINUATION:
            ep = round(close, 2)
            return (
                EntryType.MOMENTUM_CONFIRMATION.value, ep,
                f"Enter at market {ep:.2f} with volume confirmation (rel_vol > {MIN_RELATIVE_VOLUME}x)"
            )
        elif setup.setup_type == SetupType.INTRADAY_PULLBACK:
            ema = ind.ema_slow or ind.ema_fast or close
            ep = round(close, 2)
            return (
                EntryType.SUPPORT_RETEST.value, ep,
                f"Enter near EMA21 {ema:.2f} zone — confirm stabilisation with bullish candle"
            )
        elif setup.setup_type == SetupType.VWAP_RECLAIM:
            ep = round(close, 2)
            vwap = ind.vwap or close
            return (
                EntryType.SUPPORT_RETEST.value, ep,
                f"Enter on VWAP reclaim confirmation above {vwap:.2f}. Wait for 1 bar close above VWAP."
            )
        elif setup.setup_type == SetupType.VWAP_REJECTION:
            ep = round(close, 2)
            vwap = ind.vwap or close
            return (
                EntryType.BREAKOUT_CONFIRMATION.value, ep,
                f"Enter short at {ep:.2f} after VWAP rejection from {vwap:.2f}"
            )
        elif setup.setup_type == SetupType.INTRADAY_RANGE_BREAKOUT:
            ep = round(close, 2)
            return (
                EntryType.BREAKOUT_CONFIRMATION.value, ep,
                f"Enter at {ep:.2f} on range expansion. Confirm with volume and close above range high."
            )
        else:
            return (EntryType.CURRENT_MARKET_PRICE.value, round(close, 2),
                    f"Enter at current market price {close:.2f}")

    def _compute_stop(self, setup, entry_price, close, ind, direction):
        """Stop logic: structure → ATR fallback."""
        atr = ind.atr
        ep = entry_price or close

        if setup.setup_type == SetupType.OPENING_RANGE_BREAKOUT:
            # Stop below OR low (setup invalidated if OR low breaks)
            rvals = setup.relevant_values
            or_low = rvals.get("or_low")
            if or_low and or_low < ep:
                stop = round(float(or_low) * 0.998, 2)
                return (stop, StopMethod.STRUCTURAL.value,
                        f"Setup invalidated if close below OR low {or_low:.2f}")

        elif setup.setup_type == SetupType.OPENING_RANGE_BREAKDOWN:
            or_high = setup.relevant_values.get("or_high")
            if or_high and or_high > ep:
                stop = round(float(or_high) * 1.002, 2)
                return (stop, StopMethod.STRUCTURAL.value,
                        f"Short invalidated if price reclaims above OR high {or_high:.2f}")

        elif setup.setup_type in (SetupType.INTRADAY_MOMENTUM_CONTINUATION, SetupType.INTRADAY_PULLBACK):
            ema_slow = ind.ema_slow
            if ema_slow and ema_slow < ep:
                stop = round(float(ema_slow) * 0.997, 2)
                return (stop, StopMethod.STRUCTURAL.value,
                        f"Setup invalidated if close below EMA21 {ema_slow:.2f}")

        elif setup.setup_type in (SetupType.VWAP_RECLAIM, SetupType.VWAP_REJECTION):
            vwap = ind.vwap
            if vwap:
                if direction == SignalDirection.BUY.value:
                    stop = round(float(vwap) * 0.997, 2)
                    return (stop, StopMethod.STRUCTURAL.value,
                            f"VWAP reclaim invalidated if close falls below VWAP {vwap:.2f}")
                else:
                    stop = round(float(vwap) * 1.003, 2)
                    return (stop, StopMethod.STRUCTURAL.value,
                            f"VWAP rejection invalidated if price reclaims above VWAP {vwap:.2f}")

        # ATR-based fallback
        if atr:
            if direction == SignalDirection.BUY.value:
                stop = round(ep - STOP_ATR_MULTIPLIER * atr, 2)
                return (stop, StopMethod.ATR_BASED.value,
                        f"Stop at {stop:.2f} = entry {ep:.2f} - {STOP_ATR_MULTIPLIER}×ATR({atr:.2f})")
            else:
                stop = round(ep + STOP_ATR_MULTIPLIER * atr, 2)
                return (stop, StopMethod.ATR_BASED.value,
                        f"Stop at {stop:.2f} = entry {ep:.2f} + {STOP_ATR_MULTIPLIER}×ATR({atr:.2f})")

        # Last resort: 1.5% stop
        pct = 0.015
        if direction == SignalDirection.BUY.value:
            stop = round(ep * (1 - pct), 2)
            return (stop, StopMethod.PERCENTAGE_FALLBACK.value, f"1.5% fallback stop")
        else:
            stop = round(ep * (1 + pct), 2)
            return (stop, StopMethod.PERCENTAGE_FALLBACK.value, f"1.5% fallback stop (short)")

    def _compute_targets(self, setup, entry_price, stop_price, ind, or_range, direction):
        """Compute T1 and T2 targets — structure or ATR-based."""
        atr = ind.atr
        ep = entry_price or 0.0
        risk = abs(ep - stop_price) if stop_price else None

        t1_price = t2_price = None
        t1_method = t2_method = TargetMethod.ATR_MULTIPLE.value

        # OR setups use measured-move targets
        if or_range and setup.setup_type in (
            SetupType.OPENING_RANGE_BREAKOUT, SetupType.OPENING_RANGE_BREAKDOWN
        ):
            if direction == SignalDirection.BUY.value:
                t1_price = or_range.measured_move_target_up(ep)
                t2_price = round(ep + or_range.range_size * 2, 2)
            else:
                t1_price = or_range.measured_move_target_down(ep)
                t2_price = round(ep - or_range.range_size * 2, 2)
            t1_method = TargetMethod.MEASURED_MOVE.value
            t2_method = TargetMethod.MEASURED_MOVE.value
            return t1_price, t1_method, t2_price, t2_method

        # ATR-based targets
        if atr:
            if direction == SignalDirection.BUY.value:
                t1_price = round(ep + TARGET_1_ATR_MULTIPLIER * atr, 2)
                t2_price = round(ep + TARGET_2_ATR_MULTIPLIER * atr, 2)
            else:
                t1_price = round(ep - TARGET_1_ATR_MULTIPLIER * atr, 2)
                t2_price = round(ep - TARGET_2_ATR_MULTIPLIER * atr, 2)
            t1_method = TargetMethod.ATR_MULTIPLE.value
            t2_method = TargetMethod.ATR_MULTIPLE.value
            return t1_price, t1_method, t2_price, t2_method

        # R:R derived fallback
        if risk:
            if direction == SignalDirection.BUY.value:
                t1_price = round(ep + MIN_RISK_REWARD_INTRADAY * risk, 2)
                t2_price = round(ep + MIN_RISK_REWARD_INTRADAY * 2 * risk, 2)
            else:
                t1_price = round(ep - MIN_RISK_REWARD_INTRADAY * risk, 2)
                t2_price = round(ep - MIN_RISK_REWARD_INTRADAY * 2 * risk, 2)
            t1_method = TargetMethod.RISK_REWARD_DERIVED.value
            t2_method = TargetMethod.RISK_REWARD_DERIVED.value

        return t1_price, t1_method, t2_price, t2_method

    def _compute_confidence(self, setup, ind, market_context, sector_context, direction):
        """5-dimension intraday confidence: setup, volume, market, sector, RS."""
        from market.signal_enums import ConfidenceLevel
        from market.intraday_strategy_config import (
            REGIME_GATE_RULES as GATE_RULES,
        )

        components = {}

        # 1. Setup quality
        components["setup_quality"] = {
            "score": round(setup.score, 1),
            "weight": INTRADAY_CONFIDENCE_WEIGHTS["setup_quality"],
            "note": f"Setup '{setup.setup_type.value}' scored {setup.score:.0f}/100",
        }

        # 2. Volume confirmation
        rv = ind.relative_volume or 0.0
        if rv >= MIN_RELATIVE_VOLUME * 1.5:
            vol_score = 90.0
        elif rv >= MIN_RELATIVE_VOLUME:
            vol_score = 70.0
        elif rv >= 1.0:
            vol_score = 45.0
        else:
            vol_score = 20.0
        components["volume_confirm"] = {
            "score": vol_score,
            "weight": INTRADAY_CONFIDENCE_WEIGHTS["volume_confirm"],
            "note": f"Relative volume = {rv:.2f}x",
        }

        # 3. Market alignment
        nifty_trend = market_context.get("index_regimes", {}).get("^NSEI", {}).get("trend", "sideways")
        volatility   = market_context.get("index_regimes", {}).get("^NSEI", {}).get("volatility", "normal")
        mkt_score = 50.0
        if direction == SignalDirection.BUY.value:
            if nifty_trend == "bullish": mkt_score += 10.0
            elif nifty_trend == "bearish": mkt_score -= 20.0
        if volatility == "high": mkt_score -= 10.0
        mkt_score = max(0.0, min(100.0, mkt_score))
        components["market_alignment"] = {
            "score": mkt_score,
            "weight": INTRADAY_CONFIDENCE_WEIGHTS["market_alignment"],
            "note": f"NIFTY trend={nifty_trend}, volatility={volatility}",
        }

        # 4. Sector alignment
        sec_tier = sector_context.get("tier", "neutral")
        sec_score = 50.0
        if direction == SignalDirection.BUY.value:
            if sec_tier == "strongest": sec_score += 20.0
            elif sec_tier == "weakest": sec_score -= 15.0
        sec_score = max(0.0, min(100.0, sec_score))
        components["sector_alignment"] = {
            "score": sec_score,
            "weight": INTRADAY_CONFIDENCE_WEIGHTS["sector_alignment"],
            "note": f"Sector tier={sec_tier}",
        }

        # 5. Relative strength
        rs = ind.relative_strength
        if ind.relative_strength_available and rs is not None:
            if rs > 1.0: rs_score = 80.0
            elif rs > 0:  rs_score = 60.0
            elif rs > -1.0: rs_score = 40.0
            else:         rs_score = 20.0
        else:
            rs_score = 50.0  # Neutral if no index data
        components["relative_strength"] = {
            "score": rs_score,
            "weight": INTRADAY_CONFIDENCE_WEIGHTS["relative_strength"],
            "note": f"RS vs index = {rs:.2f}%" if rs is not None else "RS unavailable — index bars not loaded",
        }

        total = sum(v["score"] * v["weight"] for v in components.values())
        if total >= 70.0: level = ConfidenceLevel.HIGH.value
        elif total >= 45.0: level = ConfidenceLevel.MEDIUM.value
        else: level = ConfidenceLevel.LOW.value

        components["overall"] = {"score": round(total, 1), "level": level}
        return level, components

    # ── Draft builders ──────────────────────────────────────────────────────────

    def _not_ready_draft(self, inst, timeframe, dt_as_of, reason) -> RecommendationDraft:
        draft = RecommendationDraft(
            instrument_id=str(inst.id),
            horizon=SignalHorizon.INTRADAY.value,
            signal=SignalDirection.NOT_READY.value,
            setup_type=SetupType.NONE.value,
            as_of=dt_as_of,
            entry_type=EntryType.CURRENT_MARKET_PRICE.value,
            entry_price=None, entry_condition=reason,
            stop_price=None, stop_method=StopMethod.PERCENTAGE_FALLBACK.value,
            invalidation_reason=reason,
            target_price=None, target_method=TargetMethod.RISK_REWARD_DERIVED.value,
            risk=None, reward=None, risk_reward_ratio=None,
            confidence=ConfidenceLevel.LOW.value,
            confidence_components={},
            market_context={}, sector_context={},
            supporting_factors=[], risk_factors=[reason],
            setup_details={"strategy_version": STRATEGY_VERSION},
            data_quality={"status": "NOT_READY", "timeframe": timeframe},
            status=RecommendationStatus.CANCELLED.value,
        )
        draft._intraday_extras = {}
        return draft

    def _no_action_draft(self, inst, timeframe, dt_as_of, reason,
                         mkt, sec, dq) -> RecommendationDraft:
        draft = RecommendationDraft(
            instrument_id=str(inst.id),
            horizon=SignalHorizon.INTRADAY.value,
            signal=SignalDirection.NO_ACTION.value,
            setup_type=SetupType.NONE.value,
            as_of=dt_as_of,
            entry_type=EntryType.CURRENT_MARKET_PRICE.value,
            entry_price=None, entry_condition=reason,
            stop_price=None, stop_method=StopMethod.PERCENTAGE_FALLBACK.value,
            invalidation_reason=reason,
            target_price=None, target_method=TargetMethod.RISK_REWARD_DERIVED.value,
            risk=None, reward=None, risk_reward_ratio=None,
            confidence=ConfidenceLevel.LOW.value,
            confidence_components={},
            market_context=mkt, sector_context=sec,
            supporting_factors=[], risk_factors=[reason],
            setup_details={"strategy_version": STRATEGY_VERSION, **dq},
            data_quality=dq,
            status=RecommendationStatus.CANCELLED.value,
        )
        draft._intraday_extras = {}
        return draft
