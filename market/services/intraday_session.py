"""
intraday_session.py — Session window classification using Module 9 IndianMarketSession.

Classifies any datetime into a named session window:
  OPENING   09:15–09:45  (OR formation, high uncertainty)
  MORNING   09:45–11:30  (primary trending window)
  MIDDAY    11:30–13:00  (lower volume, choppy)
  AFTERNOON 13:00–14:30  (second trend window)
  CLOSING   14:30–15:30  (closing dynamics, position squaring)
  OUTSIDE              (pre-market, post-market)

No external data source required — purely deterministic from datetime.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from market.services.market_session import IndianMarketSession, IST
from market.intraday_strategy_config import SESSION_WINDOWS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionWindow:
    """
    Classification result for a given datetime.

    Attributes:
        window:              Named window (OPENING / MORNING / MIDDAY / AFTERNOON / CLOSING / OUTSIDE)
        minutes_elapsed:     Minutes since session open (09:15 IST). -1 if outside session.
        minutes_remaining:   Minutes until session close (15:30 IST). -1 if outside session.
        is_valid_for_trading: True only when window is within market hours
        session_date:        Calendar date of the NSE session (IST)
    """
    window: str
    minutes_elapsed: int
    minutes_remaining: int
    is_valid_for_trading: bool
    session_date: date


def classify_session(dt: datetime) -> SessionWindow:
    """
    Classify a UTC-aware or IST datetime into the appropriate intraday session window.

    Args:
        dt: A timezone-aware datetime. Naive datetimes are treated as UTC.

    Returns:
        SessionWindow dataclass.
    """
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to IST
    dt_ist = dt.astimezone(IST)
    session_date = dt_ist.date()

    # Session boundary datetimes in IST for this calendar date
    session_open  = datetime(session_date.year, session_date.month, session_date.day, 9, 15, tzinfo=IST)
    session_close = datetime(session_date.year, session_date.month, session_date.day, 15, 30, tzinfo=IST)

    # Outside hours
    if dt_ist < session_open or dt_ist >= session_close:
        return SessionWindow(
            window="OUTSIDE",
            minutes_elapsed=-1,
            minutes_remaining=-1,
            is_valid_for_trading=False,
            session_date=session_date,
        )

    # Weekends / holidays → OUTSIDE
    if not IndianMarketSession.is_trading_day(session_date):
        return SessionWindow(
            window="OUTSIDE",
            minutes_elapsed=-1,
            minutes_remaining=-1,
            is_valid_for_trading=False,
            session_date=session_date,
        )

    # Minutes from session open
    minutes_elapsed = int((dt_ist - session_open).total_seconds() // 60)
    minutes_remaining = int((session_close - dt_ist).total_seconds() // 60)

    # Classify into window
    window = "CLOSING"  # Default to last window
    for name, (start, end) in SESSION_WINDOWS.items():
        if start <= minutes_elapsed < end:
            window = name
            break

    return SessionWindow(
        window=window,
        minutes_elapsed=minutes_elapsed,
        minutes_remaining=minutes_remaining,
        is_valid_for_trading=True,
        session_date=session_date,
    )


def is_opening_range_complete(dt: datetime, timeframe: str) -> bool:
    """
    Returns True if the opening range formation period has elapsed for the given timeframe.
    OR is complete after OR_MINUTES from session open.

    5m  → after 09:30 IST (15 min)
    15m → after 09:45 IST (30 min)
    """
    from market.intraday_strategy_config import OPENING_RANGE_MINUTES
    sw = classify_session(dt)
    if not sw.is_valid_for_trading:
        return False
    or_minutes = OPENING_RANGE_MINUTES.get(timeframe, 15)
    return sw.minutes_elapsed >= or_minutes
