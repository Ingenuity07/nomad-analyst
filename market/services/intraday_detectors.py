"""
intraday_detectors.py — Dedicated intraday setup detectors for Module 10.

CRITICAL: These detectors MUST NOT be run against daily candles.
They are purpose-built for 5m/15m intraday bars with intraday indicators.

Each detector:
  1. Receives IntradayIndicators and OpeningRange (both computed from intraday bars)
  2. Returns SetupResult from setup_detectors.py (shared dataclass, not shared logic)
  3. Carries setup_version from intraday_strategy_config.STRATEGY_VERSION
  4. Does NOT call any external service or LLM

7 Detectors:
  1. detect_or_breakout            — Opening Range Breakout (bullish)
  2. detect_or_breakdown           — Opening Range Breakdown (bearish)
  3. detect_momentum_continuation  — Intraday EMA trend + momentum
  4. detect_intraday_pullback      — EMA trend + retracement to EMA21
  5. detect_vwap_reclaim           — Price reclaims VWAP from below
  6. detect_vwap_rejection         — Price rejects at VWAP from above
  7. detect_intraday_range_breakout — Low-ADX range then breakout above 20-bar high
"""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

from market.services.setup_detectors import SetupResult
from market.services.intraday_indicators import IntradayIndicators
from market.services.opening_range import OpeningRange
from market.signal_enums import SetupType, SignalDirection
from market.intraday_strategy_config import (
    STRATEGY_VERSION,
    MIN_RELATIVE_VOLUME, RSI_OVERSOLD, RSI_OVERBOUGHT,
    RSI_MOMENTUM_MIN, RSI_MOMENTUM_MAX,
    RSI_PULLBACK_MIN, RSI_PULLBACK_MAX,
    VWAP_PROXIMITY_PCT, ADX_RANGE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _sr(setup_type, detected, score, met, failed, vals) -> SetupResult:
    """Convenience builder for SetupResult."""
    return SetupResult(
        setup_type=setup_type,
        detected=detected,
        score=max(0.0, min(100.0, score)),
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={**vals, "strategy_version": STRATEGY_VERSION},
    )


# ─── 1. OPENING RANGE BREAKOUT ────────────────────────────────────────────────

def detect_or_breakout(
    ind: IntradayIndicators,
    or_range: Optional[OpeningRange],
    session_window: str = "MORNING",
) -> SetupResult:
    """
    OPENING_RANGE_BREAKOUT — bullish breakout above the session OR high.

    Conditions required:
      1. Opening range is complete (enough OR bars loaded)
      2. Current close > OR high (price breaking out)
      3. Relative volume >= 1.2 (volume confirms the move)
      4. RSI > 50 (momentum is positive, not already exhausted)
      5. EMA-9 >= EMA-21 (intraday trend aligned bullish) — optional booster
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    # Condition 0 — OR must be complete
    if not or_range or not or_range.is_complete:
        return _sr(SetupType.OPENING_RANGE_BREAKOUT, False, 0.0, [],
                   ["Opening range not yet formed (insufficient OR bars)"],
                   {"close": close, "or_high": or_range.high if or_range else None})

    or_high = or_range.high

    # Condition 1 — Price above OR high
    if close > or_high:
        pct_above = (close - or_high) / or_high * 100
        met.append(f"Price {close:.2f} above OR high {or_high:.2f} (+{pct_above:.2f}%)")
        score += 35.0
    else:
        failed.append(f"Price {close:.2f} not yet above OR high {or_high:.2f}")

    # Condition 2 — Volume confirmation
    rv = ind.relative_volume
    if rv is not None and rv >= MIN_RELATIVE_VOLUME:
        met.append(f"Volume confirmation (rel_vol={rv:.2f}x)")
        score += 30.0
    else:
        failed.append(f"Insufficient volume (rel_vol={rv}; need >= {MIN_RELATIVE_VOLUME})")

    # Condition 3 — RSI momentum
    rsi = ind.rsi
    if rsi is not None and rsi > 50:
        met.append(f"Positive momentum (RSI={rsi:.1f})")
        score += 25.0
    elif rsi is not None and rsi > RSI_OVERBOUGHT:
        failed.append(f"RSI overbought — may be extended (RSI={rsi:.1f})")
        score -= 10.0
    else:
        failed.append(f"RSI not bullish (RSI={rsi})")

    # Condition 4 — EMA alignment (booster, not gate)
    if ind.ema_fast is not None and ind.ema_slow is not None:
        if ind.ema_fast >= ind.ema_slow:
            met.append(f"EMA9 {ind.ema_fast:.2f} >= EMA21 {ind.ema_slow:.2f} — trend aligned bullish")
            score += 10.0
        else:
            failed.append(f"EMA9 {ind.ema_fast:.2f} < EMA21 {ind.ema_slow:.2f} — trend mixed")

    # OR size context
    if or_range.range_pct < 0.3:
        failed.append(f"OR range very tight ({or_range.range_pct:.2f}%) — breakout may be weak")
    elif or_range.range_pct > 3.0:
        failed.append(f"OR range very wide ({or_range.range_pct:.2f}%) — high-risk breakout")
    else:
        met.append(f"OR range healthy ({or_range.range_pct:.2f}%)")

    # Gate: must be above OR high AND have volume confirmation
    detected = (close > or_high) and (rv is not None and rv >= MIN_RELATIVE_VOLUME)

    return _sr(SetupType.OPENING_RANGE_BREAKOUT, detected, score, met, failed, {
        "close": close, "or_high": or_high, "or_low": or_range.low,
        "or_range_pct": or_range.range_pct, "rsi": rsi,
        "relative_volume": rv, "ema_fast": ind.ema_fast, "ema_slow": ind.ema_slow,
        "session_window": session_window,
    })


# ─── 2. OPENING RANGE BREAKDOWN ───────────────────────────────────────────────

def detect_or_breakdown(
    ind: IntradayIndicators,
    or_range: Optional[OpeningRange],
    session_window: str = "MORNING",
) -> SetupResult:
    """
    OPENING_RANGE_BREAKDOWN — bearish breakdown below the session OR low.

    Conditions required:
      1. Opening range is complete
      2. Current close < OR low
      3. Relative volume >= 1.2 (distribution volume)
      4. RSI < 50 (downward momentum)
      5. EMA-9 <= EMA-21 (trend aligned bearish) — optional booster
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    if not or_range or not or_range.is_complete:
        return _sr(SetupType.OPENING_RANGE_BREAKDOWN, False, 0.0, [],
                   ["Opening range not yet formed"], {"close": close})

    or_low = or_range.low

    # Condition 1 — Price below OR low
    if close < or_low:
        pct_below = (or_low - close) / or_low * 100
        met.append(f"Price {close:.2f} below OR low {or_low:.2f} (-{pct_below:.2f}%)")
        score += 35.0
    else:
        failed.append(f"Price {close:.2f} not below OR low {or_low:.2f}")

    # Condition 2 — Distribution volume
    rv = ind.relative_volume
    if rv is not None and rv >= MIN_RELATIVE_VOLUME:
        met.append(f"Distribution volume (rel_vol={rv:.2f}x)")
        score += 30.0
    else:
        failed.append(f"Insufficient volume (rel_vol={rv})")

    # Condition 3 — Bearish momentum
    rsi = ind.rsi
    if rsi is not None and rsi < 50:
        met.append(f"Bearish momentum (RSI={rsi:.1f})")
        score += 25.0
    else:
        failed.append(f"RSI not bearish (RSI={rsi})")

    # Condition 4 — EMA alignment (booster)
    if ind.ema_fast is not None and ind.ema_slow is not None:
        if ind.ema_fast <= ind.ema_slow:
            met.append(f"EMA9 {ind.ema_fast:.2f} <= EMA21 {ind.ema_slow:.2f} — trend aligned bearish")
            score += 10.0
        else:
            failed.append("EMA trend still bullish — bearish structure weak")

    detected = (close < or_low) and (rv is not None and rv >= MIN_RELATIVE_VOLUME)

    return _sr(SetupType.OPENING_RANGE_BREAKDOWN, detected, score, met, failed, {
        "close": close, "or_high": or_range.high, "or_low": or_low,
        "or_range_pct": or_range.range_pct, "rsi": rsi,
        "relative_volume": rv, "ema_fast": ind.ema_fast, "ema_slow": ind.ema_slow,
    })


# ─── 3. MOMENTUM CONTINUATION ─────────────────────────────────────────────────

def detect_momentum_continuation(
    ind: IntradayIndicators,
    session_window: str = "MORNING",
) -> SetupResult:
    """
    INTRADAY_MOMENTUM_CONTINUATION — established intraday uptrend with confirming momentum.

    Conditions required:
      1. EMA-9 > EMA-21 (intraday uptrend established)
      2. Price above EMA-9 (riding the trend)
      3. RSI in 55–72 range (momentum zone, not yet overbought)
      4. Relative volume >= 1.2 (trend confirmed by participation)
      5. MACD line > signal line (directional confirmation) — optional booster
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    # Condition 1 — EMA alignment
    ema_aligned = (ind.ema_fast is not None and ind.ema_slow is not None
                   and ind.ema_fast > ind.ema_slow)
    if ema_aligned:
        met.append(f"EMA9 {ind.ema_fast:.2f} > EMA21 {ind.ema_slow:.2f} — uptrend established")
        score += 30.0
    elif ind.ema_fast is not None and ind.ema_slow is not None:
        failed.append(f"EMA9 {ind.ema_fast:.2f} <= EMA21 {ind.ema_slow:.2f} — no uptrend")
    else:
        failed.append("EMA values unavailable (insufficient bars)")

    # Condition 2 — Price above EMA-9
    above_ema_fast = ind.ema_fast is not None and close > ind.ema_fast
    if above_ema_fast:
        met.append(f"Price {close:.2f} above EMA9 {ind.ema_fast:.2f}")
        score += 20.0
    else:
        failed.append(f"Price {close:.2f} below EMA9 {ind.ema_fast}")

    # Condition 3 — RSI momentum zone
    rsi = ind.rsi
    rsi_ok = rsi is not None and RSI_MOMENTUM_MIN <= rsi <= RSI_MOMENTUM_MAX
    if rsi_ok:
        met.append(f"RSI in momentum zone (RSI={rsi:.1f})")
        score += 30.0
    elif rsi is not None and rsi > RSI_OVERBOUGHT:
        failed.append(f"RSI overbought (RSI={rsi:.1f}) — momentum may be exhausted")
        score -= 5.0
    else:
        failed.append(f"RSI not in momentum zone {RSI_MOMENTUM_MIN}–{RSI_MOMENTUM_MAX} (RSI={rsi})")

    # Condition 4 — Volume
    rv = ind.relative_volume
    vol_ok = rv is not None and rv >= MIN_RELATIVE_VOLUME
    if vol_ok:
        met.append(f"Volume confirmation (rel_vol={rv:.2f}x)")
        score += 15.0
    else:
        failed.append(f"Insufficient volume (rel_vol={rv})")

    # Condition 5 — MACD (booster)
    if ind.macd_line is not None and ind.macd_signal is not None:
        if ind.macd_line > ind.macd_signal:
            met.append(f"MACD bullish ({ind.macd_line:.4f} > {ind.macd_signal:.4f})")
            score += 5.0
        else:
            failed.append(f"MACD not yet bullish ({ind.macd_line:.4f})")

    detected = ema_aligned and above_ema_fast and rsi_ok and vol_ok

    return _sr(SetupType.INTRADAY_MOMENTUM_CONTINUATION, detected, score, met, failed, {
        "close": close, "ema_fast": ind.ema_fast, "ema_slow": ind.ema_slow,
        "rsi": rsi, "relative_volume": rv,
        "macd_line": ind.macd_line, "macd_signal": ind.macd_signal,
    })


# ─── 4. INTRADAY PULLBACK ─────────────────────────────────────────────────────

def detect_intraday_pullback(
    ind: IntradayIndicators,
    session_window: str = "MORNING",
) -> SetupResult:
    """
    INTRADAY_PULLBACK — established intraday uptrend + controlled retracement.

    Conditions required:
      1. EMA-9 > EMA-21 (uptrend established)
      2. Price near or below EMA-9 but not below EMA-21 (retracement into EMA zone)
      3. RSI in 35–55 (stabilising, not broken)
      4. Price above VWAP (if available) — pullback is within bullish structure
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    # Condition 1 — EMA trend
    ema_trend = (ind.ema_fast is not None and ind.ema_slow is not None
                 and ind.ema_fast > ind.ema_slow)
    if ema_trend:
        met.append(f"EMA9 {ind.ema_fast:.2f} > EMA21 {ind.ema_slow:.2f} — uptrend active")
        score += 30.0
    else:
        failed.append(f"No established EMA uptrend (EMA9={ind.ema_fast}, EMA21={ind.ema_slow})")

    # Condition 2 — Retracing to EMA zone
    retracing = False
    if ind.ema_fast is not None and ind.ema_slow is not None:
        # Price should be between EMA-21 and EMA-9 (or very slightly below EMA-9)
        pct_below_ema_fast = (ind.ema_fast - close) / ind.ema_fast if ind.ema_fast > 0 else 0
        pct_above_ema_slow = (close - ind.ema_slow) / ind.ema_slow if ind.ema_slow > 0 else 0

        if 0 <= pct_below_ema_fast <= 0.015 and close > ind.ema_slow:
            retracing = True
            met.append(f"Retracing to EMA9 zone (close={close:.2f}, EMA9={ind.ema_fast:.2f})")
            score += 30.0
        elif close > ind.ema_fast:
            failed.append(f"Not retracing — price {close:.2f} still above EMA9 {ind.ema_fast:.2f}")
        elif close < ind.ema_slow:
            failed.append(f"Retracement too deep — price {close:.2f} below EMA21 {ind.ema_slow:.2f}")
        else:
            retracing = True
            met.append(f"In EMA zone (close={close:.2f}, EMA21={ind.ema_slow:.2f})")
            score += 20.0

    # Condition 3 — RSI stabilising
    rsi = ind.rsi
    rsi_ok = rsi is not None and RSI_PULLBACK_MIN <= rsi <= RSI_PULLBACK_MAX
    if rsi_ok:
        met.append(f"RSI stabilising in pullback zone ({rsi:.1f})")
        score += 25.0
    else:
        failed.append(f"RSI not in pullback zone {RSI_PULLBACK_MIN}–{RSI_PULLBACK_MAX} (RSI={rsi})")

    # Condition 4 — Above VWAP (optional but strong)
    if ind.vwap_available and ind.vwap is not None:
        if close > ind.vwap:
            met.append(f"Price {close:.2f} above VWAP {ind.vwap:.2f} — bullish structure intact")
            score += 10.0
        else:
            failed.append(f"Price {close:.2f} below VWAP {ind.vwap:.2f} — pullback may be deeper")
            score -= 5.0
    else:
        failed.append("VWAP unavailable — structure context limited")

    detected = ema_trend and retracing and rsi_ok

    return _sr(SetupType.INTRADAY_PULLBACK, detected, score, met, failed, {
        "close": close, "ema_fast": ind.ema_fast, "ema_slow": ind.ema_slow,
        "rsi": rsi, "vwap": ind.vwap,
    })


# ─── 5. VWAP RECLAIM ──────────────────────────────────────────────────────────

def detect_vwap_reclaim(
    ind: IntradayIndicators,
    prev_bar_close: Optional[float] = None,
    session_window: str = "MORNING",
) -> SetupResult:
    """
    VWAP_RECLAIM — price was below VWAP and reclaims it with volume.

    Conditions required:
      1. VWAP is available (requires session bars)
      2. Current close > VWAP (price above VWAP now)
      3. Previous close was below VWAP (reclaim event confirmed)
      4. Relative volume >= 1.2 (reclaim is confirmed by buyers)
      5. RSI > 45 (not still deeply oversold — reclaim is credible)
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    # VWAP must exist
    if not ind.vwap_available or ind.vwap is None:
        return _sr(SetupType.VWAP_RECLAIM, False, 0.0, [],
                   ["VWAP unavailable — insufficient session bars"],
                   {"close": close, "vwap": None})

    vwap = ind.vwap

    # Condition 1 — Currently above VWAP
    above_vwap = close > vwap
    if above_vwap:
        met.append(f"Price {close:.2f} above VWAP {vwap:.2f}")
        score += 30.0
    else:
        failed.append(f"Price {close:.2f} still below VWAP {vwap:.2f} — reclaim not confirmed")

    # Condition 2 — Previous bar was below VWAP (actual reclaim)
    if prev_bar_close is not None:
        if prev_bar_close < vwap:
            met.append(f"Previous bar {prev_bar_close:.2f} was below VWAP — reclaim event")
            score += 30.0
        else:
            failed.append(f"Previous bar {prev_bar_close:.2f} was already above VWAP — not a fresh reclaim")
            score -= 10.0
    else:
        failed.append("Previous bar close unavailable — cannot confirm reclaim event")

    # Condition 3 — Volume confirmation
    rv = ind.relative_volume
    vol_ok = rv is not None and rv >= MIN_RELATIVE_VOLUME
    if vol_ok:
        met.append(f"Buyers supporting reclaim (rel_vol={rv:.2f}x)")
        score += 25.0
    else:
        failed.append(f"Low volume reclaim — untrustworthy (rel_vol={rv})")

    # Condition 4 — RSI credibility
    rsi = ind.rsi
    if rsi is not None and rsi > 45:
        met.append(f"RSI supports reclaim (RSI={rsi:.1f})")
        score += 15.0
    else:
        failed.append(f"RSI too weak for credible reclaim (RSI={rsi})")

    detected = above_vwap and vol_ok and (rsi is not None and rsi > 45)

    return _sr(SetupType.VWAP_RECLAIM, detected, score, met, failed, {
        "close": close, "vwap": vwap, "prev_close": prev_bar_close,
        "relative_volume": rv, "rsi": rsi,
    })


# ─── 6. VWAP REJECTION ────────────────────────────────────────────────────────

def detect_vwap_rejection(
    ind: IntradayIndicators,
    prev_bar_close: Optional[float] = None,
    session_window: str = "MORNING",
) -> SetupResult:
    """
    VWAP_REJECTION — price tested VWAP from below, was rejected, now below VWAP.

    Conditions required:
      1. VWAP is available
      2. Current close < VWAP (back below after test)
      3. Previous bar close was near or above VWAP (tested the level)
      4. Relative volume >= 1.2 (sellers confirmed the rejection)
      5. RSI < 55 (downward pressure)
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    if not ind.vwap_available or ind.vwap is None:
        return _sr(SetupType.VWAP_REJECTION, False, 0.0, [],
                   ["VWAP unavailable"], {"close": close})

    vwap = ind.vwap

    # Condition 1 — Currently below VWAP
    below_vwap = close < vwap
    if below_vwap:
        met.append(f"Price {close:.2f} below VWAP {vwap:.2f} — rejection confirmed")
        score += 30.0
    else:
        failed.append(f"Price {close:.2f} still above VWAP {vwap:.2f}")

    # Condition 2 — Previous bar was at or above VWAP (test + rejection)
    if prev_bar_close is not None:
        pct_from_vwap = (prev_bar_close - vwap) / vwap
        if pct_from_vwap >= -VWAP_PROXIMITY_PCT:
            met.append(f"Previous bar {prev_bar_close:.2f} tested VWAP {vwap:.2f} — clean rejection")
            score += 30.0
        else:
            failed.append(f"Previous bar {prev_bar_close:.2f} was well below VWAP — not a test")
            score -= 10.0
    else:
        failed.append("Previous bar unavailable — cannot confirm rejection event")

    # Condition 3 — Selling volume
    rv = ind.relative_volume
    vol_ok = rv is not None and rv >= MIN_RELATIVE_VOLUME
    if vol_ok:
        met.append(f"Sellers active (rel_vol={rv:.2f}x)")
        score += 25.0
    else:
        failed.append(f"Low volume rejection — weak signal (rel_vol={rv})")

    # Condition 4 — RSI bearish
    rsi = ind.rsi
    if rsi is not None and rsi < 55:
        met.append(f"RSI supports bearish direction (RSI={rsi:.1f})")
        score += 15.0
    else:
        failed.append(f"RSI too high for reliable rejection (RSI={rsi})")

    detected = below_vwap and vol_ok and (rsi is not None and rsi < 55)

    return _sr(SetupType.VWAP_REJECTION, detected, score, met, failed, {
        "close": close, "vwap": vwap, "prev_close": prev_bar_close,
        "relative_volume": rv, "rsi": rsi,
    })


# ─── 7. INTRADAY RANGE BREAKOUT ───────────────────────────────────────────────

def detect_intraday_range_breakout(
    ind: IntradayIndicators,
    bars: list,
    session_window: str = "MORNING",
) -> SetupResult:
    """
    INTRADAY_RANGE_BREAKOUT — low-volatility range followed by directional breakout.

    Conditions required:
      1. ADX < 20 in recent history (confirms ranging / low trend strength)
      2. Current price breaks above the 20-bar intraday high (range boundary)
      3. Relative volume >= 1.2 (breakout is real, not thin air)
      4. RSI > 50 (direction is bullish)

    Note: Uses only recent bars for the range high — not the OR.
    This is a generic intraday range expansion setup.
    """
    met: List[str] = []
    failed: List[str] = []
    score = 0.0
    close = ind.close or 0.0

    # Condition 1 — ADX indicates range (low trend strength)
    adx = ind.adx
    ranging = adx is not None and adx < ADX_RANGE_THRESHOLD
    if ranging:
        met.append(f"ADX {adx:.1f} < {ADX_RANGE_THRESHOLD} — ranging market confirmed")
        score += 25.0
    elif adx is not None:
        failed.append(f"ADX {adx:.1f} >= {ADX_RANGE_THRESHOLD} — already trending, not a range breakout")
    else:
        failed.append("ADX unavailable — cannot confirm ranging condition")

    # Condition 2 — 20-bar high (rolling max over recent bars, excluding current)
    range_high = None
    if len(bars) >= 3:
        lookback = min(20, len(bars) - 1)
        range_high = max(float(b.high) for b in bars[-lookback - 1:-1])
        if close > range_high:
            pct = (close - range_high) / range_high * 100
            met.append(f"Price {close:.2f} breaks above 20-bar high {range_high:.2f} (+{pct:.2f}%)")
            score += 35.0
        else:
            failed.append(f"Price {close:.2f} has not broken 20-bar high {range_high:.2f}")
    else:
        failed.append("Insufficient bars for range high calculation")

    # Condition 3 — Volume
    rv = ind.relative_volume
    vol_ok = rv is not None and rv >= MIN_RELATIVE_VOLUME
    if vol_ok:
        met.append(f"Volume confirms breakout (rel_vol={rv:.2f}x)")
        score += 25.0
    else:
        failed.append(f"Low volume breakout — suspect (rel_vol={rv})")

    # Condition 4 — RSI direction
    rsi = ind.rsi
    if rsi is not None and rsi > 50:
        met.append(f"RSI positive (RSI={rsi:.1f})")
        score += 15.0
    else:
        failed.append(f"RSI not positive (RSI={rsi})")

    detected = ranging and (range_high is not None and close > range_high) and vol_ok

    return _sr(SetupType.INTRADAY_RANGE_BREAKOUT, detected, score, met, failed, {
        "close": close, "adx": adx, "range_high": range_high,
        "relative_volume": rv, "rsi": rsi,
    })


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_intraday_detectors(
    ind: IntradayIndicators,
    or_range: Optional[OpeningRange],
    bars: list,
    session_window: str,
    allowed_setups: Optional[set] = None,
    prev_bar_close: Optional[float] = None,
) -> list:
    """
    Run all applicable intraday detectors filtered by session window.

    Args:
        ind:            IntradayIndicators for the latest bar.
        or_range:       Computed OpeningRange for this session.
        bars:           Raw intraday bars (oldest-first).
        session_window: Current session classification.
        allowed_setups: If provided, restrict to these setup names.
        prev_bar_close: Close of the second-to-last bar (for VWAP cross detection).

    Returns:
        List of SetupResult sorted by (detected DESC, score DESC).
    """
    from market.intraday_strategy_config import SETUP_SESSION_FILTERS

    results = []

    def _should_run(setup_name: str) -> bool:
        if allowed_setups and setup_name not in allowed_setups:
            return False
        windows = SETUP_SESSION_FILTERS.get(setup_name, set())
        return session_window in windows

    try:
        if _should_run("OPENING_RANGE_BREAKOUT"):
            results.append(detect_or_breakout(ind, or_range, session_window))
    except Exception as e:
        logger.warning(f"detect_or_breakout failed: {e}")

    try:
        if _should_run("OPENING_RANGE_BREAKDOWN"):
            results.append(detect_or_breakdown(ind, or_range, session_window))
    except Exception as e:
        logger.warning(f"detect_or_breakdown failed: {e}")

    try:
        if _should_run("INTRADAY_MOMENTUM_CONTINUATION"):
            results.append(detect_momentum_continuation(ind, session_window))
    except Exception as e:
        logger.warning(f"detect_momentum_continuation failed: {e}")

    try:
        if _should_run("INTRADAY_PULLBACK"):
            results.append(detect_intraday_pullback(ind, session_window))
    except Exception as e:
        logger.warning(f"detect_intraday_pullback failed: {e}")

    try:
        if _should_run("VWAP_RECLAIM"):
            results.append(detect_vwap_reclaim(ind, prev_bar_close, session_window))
    except Exception as e:
        logger.warning(f"detect_vwap_reclaim failed: {e}")

    try:
        if _should_run("VWAP_REJECTION"):
            results.append(detect_vwap_rejection(ind, prev_bar_close, session_window))
    except Exception as e:
        logger.warning(f"detect_vwap_rejection failed: {e}")

    try:
        if _should_run("INTRADAY_RANGE_BREAKOUT"):
            results.append(detect_intraday_range_breakout(ind, bars, session_window))
    except Exception as e:
        logger.warning(f"detect_intraday_range_breakout failed: {e}")

    return sorted(results, key=lambda r: (r.detected, r.score), reverse=True)
