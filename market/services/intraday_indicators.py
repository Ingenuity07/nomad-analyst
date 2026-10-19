"""
intraday_indicators.py — Intraday-specific indicator calculations.

All indicators are calculated in-memory from raw OHLCVBar objects.
They are NOT persisted and are recomputed fresh on every scan.

Uses TA-Lib exclusively. No new technical analysis library is introduced.

VWAP is implemented deterministically from session-anchored OHLCV — no
external library required. VWAP = sum(typical_price * volume) / sum(volume),
anchored to the session open bar.

Feature naming convention for persisted intraday features: use '_IT_' suffix
(e.g. RSI_7_IT) to distinguish from daily features (RSI_14, EMA_20).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any

import numpy as np

from market.intraday_strategy_config import INDICATOR_PARAMS, SESSION_WINDOWS

logger = logging.getLogger(__name__)

_p = INDICATOR_PARAMS


def _safe(val, default=None):
    """Return float or default if None/NaN/Inf."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


@dataclass
class IntradayIndicators:
    """
    Snapshot of all intraday indicator values for the latest bar.

    None = indicator unavailable due to insufficient history.
    Values are NOT probabilities — they are raw technical measurements.
    """
    # EMA
    ema_fast: Optional[float] = None       # EMA-9
    ema_slow: Optional[float] = None       # EMA-21
    ema_fast_prev: Optional[float] = None  # Prior bar EMA-9 (crossover detection)
    ema_slow_prev: Optional[float] = None  # Prior bar EMA-21

    # RSI
    rsi: Optional[float] = None            # RSI-7

    # ATR
    atr: Optional[float] = None            # ATR-10

    # ADX
    adx: Optional[float] = None            # ADX-10

    # MACD (intraday params: 5/13/3)
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None

    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None

    # VWAP (session-anchored)
    vwap: Optional[float] = None
    vwap_available: bool = False

    # Volume
    relative_volume: Optional[float] = None    # current_volume / mean(last N volumes)
    current_volume: Optional[int] = None
    avg_volume: Optional[float] = None

    # Relative strength vs index (stock return - index return over lookback bars)
    # None if index bars not available
    relative_strength: Optional[float] = None
    relative_strength_available: bool = False

    # Latest bar values
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    bar_count: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "rsi": self.rsi,
            "atr": self.atr,
            "adx": self.adx,
            "macd_line": self.macd_line,
            "macd_signal": self.macd_signal,
            "macd_hist": self.macd_hist,
            "bb_upper": self.bb_upper,
            "bb_lower": self.bb_lower,
            "vwap": self.vwap,
            "relative_volume": self.relative_volume,
            "relative_strength": self.relative_strength,
            "close": self.close,
            "bar_count": self.bar_count,
        }


def compute_intraday_indicators(
    bars: list,
    session_date: date,
    index_bars: Optional[list] = None,
) -> IntradayIndicators:
    """
    Compute all intraday indicators from a list of OHLCVBar objects.

    Args:
        bars:         OHLCVBar objects, sorted oldest-first, same timeframe.
                      Must all be within or before as_of.
        session_date: Calendar date of the NSE session (IST). Used for VWAP anchor.
        index_bars:   NIFTY/index OHLCVBar objects for relative strength (optional).

    Returns:
        IntradayIndicators dataclass with all computed values.
    """
    import talib

    result = IntradayIndicators(bar_count=len(bars))

    if not bars:
        return result

    # Build numpy arrays
    highs   = np.array([float(b.high)   for b in bars], dtype=np.float64)
    lows    = np.array([float(b.low)    for b in bars], dtype=np.float64)
    closes  = np.array([float(b.close)  for b in bars], dtype=np.float64)
    opens   = np.array([float(b.open)   for b in bars], dtype=np.float64)
    volumes = np.array([float(b.volume) for b in bars], dtype=np.float64)

    n = len(bars)

    result.close  = _safe(closes[-1])
    result.high   = _safe(highs[-1])
    result.low    = _safe(lows[-1])
    result.open   = _safe(opens[-1])
    result.current_volume = int(volumes[-1]) if volumes[-1] > 0 else 0

    # ── EMA-9 and EMA-21 ──────────────────────────────────────────────────────
    if n >= _p.ema_slow + 1:
        ema_fast_arr = talib.EMA(closes, timeperiod=_p.ema_fast)
        ema_slow_arr = talib.EMA(closes, timeperiod=_p.ema_slow)
        result.ema_fast = _safe(ema_fast_arr[-1])
        result.ema_slow = _safe(ema_slow_arr[-1])
        if n >= _p.ema_slow + 2:
            result.ema_fast_prev = _safe(ema_fast_arr[-2])
            result.ema_slow_prev = _safe(ema_slow_arr[-2])
    elif n >= _p.ema_fast + 1:
        ema_fast_arr = talib.EMA(closes, timeperiod=_p.ema_fast)
        result.ema_fast = _safe(ema_fast_arr[-1])
        if n >= _p.ema_fast + 2:
            result.ema_fast_prev = _safe(ema_fast_arr[-2])

    # ── RSI-7 ─────────────────────────────────────────────────────────────────
    if n >= _p.rsi_period + 1:
        rsi_arr = talib.RSI(closes, timeperiod=_p.rsi_period)
        result.rsi = _safe(rsi_arr[-1])

    # ── ATR-10 ────────────────────────────────────────────────────────────────
    if n >= _p.atr_period + 1:
        atr_arr = talib.ATR(highs, lows, closes, timeperiod=_p.atr_period)
        result.atr = _safe(atr_arr[-1])

    # ── ADX-10 ────────────────────────────────────────────────────────────────
    if n >= _p.adx_period * 2:
        adx_arr = talib.ADX(highs, lows, closes, timeperiod=_p.adx_period)
        result.adx = _safe(adx_arr[-1])

    # ── MACD (5/13/3) ─────────────────────────────────────────────────────────
    if n >= _p.macd_slow + _p.macd_signal:
        macd_line, macd_signal, macd_hist = talib.MACD(
            closes,
            fastperiod=_p.macd_fast,
            slowperiod=_p.macd_slow,
            signalperiod=_p.macd_signal
        )
        result.macd_line   = _safe(macd_line[-1])
        result.macd_signal = _safe(macd_signal[-1])
        result.macd_hist   = _safe(macd_hist[-1])

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    if n >= _p.bb_period:
        upper, middle, lower = talib.BBANDS(closes, timeperiod=_p.bb_period, nbdevup=_p.bb_std, nbdevdn=_p.bb_std)
        result.bb_upper  = _safe(upper[-1])
        result.bb_middle = _safe(middle[-1])
        result.bb_lower  = _safe(lower[-1])

    # ── Volume — relative volume ───────────────────────────────────────────────
    lookback = min(_p.volume_lookback, n - 1)
    if lookback > 0:
        avg_vol = float(np.mean(volumes[-(lookback + 1):-1]))
        result.avg_volume = avg_vol
        if avg_vol > 0:
            result.relative_volume = round(volumes[-1] / avg_vol, 4)

    # ── VWAP — session-anchored ────────────────────────────────────────────────
    # Filter bars that belong to this session_date only (in IST)
    # Ensure VWAP uses only valid regular-session bars (09:15 IST <= time < 15:30 IST)
    from market.services.market_session import IST
    from market.services.trading_session import REGULAR_SESSION_START, REGULAR_SESSION_END

    session_bars = []
    for b in bars:
        bar_ts = b.timestamp
        if bar_ts.tzinfo is None:
            bar_ts = bar_ts.replace(tzinfo=timezone.utc)
        bar_ist = bar_ts.astimezone(IST)
        if bar_ist.date() == session_date:
            bar_time = bar_ist.time()
            if REGULAR_SESSION_START <= bar_time < REGULAR_SESSION_END:
                session_bars.append(b)

    if session_bars:
        typical_prices = np.array(
            [(float(b.high) + float(b.low) + float(b.close)) / 3.0 for b in session_bars],
            dtype=np.float64
        )
        sess_volumes = np.array([float(b.volume) for b in session_bars], dtype=np.float64)
        total_vol = np.sum(sess_volumes)
        if total_vol > 0:
            result.vwap = round(float(np.sum(typical_prices * sess_volumes) / total_vol), 4)
            result.vwap_available = True

    # ── Relative strength vs index ─────────────────────────────────────────────
    if index_bars and len(index_bars) >= 2:
        lookback_rs = min(_p.rs_lookback, len(bars) - 1, len(index_bars) - 1)
        if lookback_rs > 0:
            stock_ret = (closes[-1] - closes[-(lookback_rs + 1)]) / closes[-(lookback_rs + 1)] * 100
            idx_closes = np.array([float(b.close) for b in index_bars], dtype=np.float64)
            idx_ret = (idx_closes[-1] - idx_closes[-(lookback_rs + 1)]) / idx_closes[-(lookback_rs + 1)] * 100
            result.relative_strength = round(stock_ret - idx_ret, 4)
            result.relative_strength_available = True

    return result
