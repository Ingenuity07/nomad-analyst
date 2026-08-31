"""
opening_range.py — Opening Range framework for intraday strategy.

The Opening Range (OR) is defined as the high and low of the first N minutes
of the trading session. This period is configurable per timeframe.

Default:
  5m  → first 15 minutes (3 bars): 09:15–09:30
  15m → first 30 minutes (2 bars): 09:15–09:45

The OR is session-scoped — only bars from today's (IST) session are used.
No cross-session contamination.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

from market.services.market_session import IndianMarketSession, IST
from market.intraday_strategy_config import (
    OPENING_RANGE_MINUTES, MIN_OR_BARS_COMPLETE
)

logger = logging.getLogger(__name__)


@dataclass
class OpeningRange:
    """
    Computed opening range for a single trading session.

    Attributes:
        high:          Highest high across OR bars.
        low:           Lowest low across OR bars.
        range_size:    Absolute range (high - low).
        range_pct:     Range as percentage of low (volatility proxy).
        total_volume:  Cumulative volume during OR.
        bars_used:     Number of bars used in computation.
        session_date:  IST date of the session.
        is_complete:   True when sufficient OR bars have been loaded.
    """
    high: float
    low: float
    range_size: float
    range_pct: float
    total_volume: int
    bars_used: int
    session_date: date
    is_complete: bool

    def above_or_high(self, price: float, buffer_pct: float = 0.001) -> bool:
        """True if price is above OR high by at least buffer_pct."""
        return price > self.high * (1 + buffer_pct)

    def below_or_low(self, price: float, buffer_pct: float = 0.001) -> bool:
        """True if price is below OR low by at least buffer_pct."""
        return price < self.low * (1 - buffer_pct)

    def midpoint(self) -> float:
        return (self.high + self.low) / 2.0

    def measured_move_target_up(self, entry: float) -> float:
        """Target = entry + OR range (measured move above breakout)."""
        return round(entry + self.range_size, 2)

    def measured_move_target_down(self, entry: float) -> float:
        """Target = entry - OR range (measured move below breakdown)."""
        return round(entry - self.range_size, 2)


def compute_opening_range(
    bars: list,
    session_date: date,
    timeframe: str,
) -> Optional[OpeningRange]:
    """
    Compute the opening range from raw OHLCVBar objects.

    Only bars falling within the OR window for session_date are used.
    Bars outside market hours or outside the OR window are ignored.

    Args:
        bars:         OHLCVBar objects, sorted oldest-first.
        session_date: The NSE session date (IST) for which to compute OR.
        timeframe:    Timeframe string ('5m', '15m', etc.).

    Returns:
        OpeningRange or None if insufficient data.
    """
    or_minutes = OPENING_RANGE_MINUTES.get(timeframe, 15)
    min_bars_needed = MIN_OR_BARS_COMPLETE.get(timeframe, 2)

    # Session open in IST for this date
    session_open = datetime(
        session_date.year, session_date.month, session_date.day, 9, 15, tzinfo=IST
    )
    # OR window ends at session_open + or_minutes
    from datetime import timedelta
    or_end = session_open + timedelta(minutes=or_minutes)

    or_bars = []
    for b in bars:
        ts = b.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_ist = ts.astimezone(IST)
        # Bar must be in today's session AND within OR window
        if ts_ist.date() == session_date and session_open <= ts_ist < or_end:
            or_bars.append(b)

    if not or_bars:
        return None

    highs   = [float(b.high)   for b in or_bars]
    lows    = [float(b.low)    for b in or_bars]
    volumes = [int(b.volume)   for b in or_bars]

    or_high = max(highs)
    or_low  = min(lows)
    range_size = round(or_high - or_low, 4)
    range_pct  = round(range_size / or_low * 100, 4) if or_low > 0 else 0.0
    total_vol  = sum(volumes)
    is_complete = len(or_bars) >= min_bars_needed

    return OpeningRange(
        high=or_high,
        low=or_low,
        range_size=range_size,
        range_pct=range_pct,
        total_volume=total_vol,
        bars_used=len(or_bars),
        session_date=session_date,
        is_complete=is_complete,
    )
