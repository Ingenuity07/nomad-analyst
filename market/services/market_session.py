"""
market_session.py — Indian market session semantics for Module 9.

Responsibilities:
  - Determine whether a datetime falls inside an NSE trading session
  - Determine whether a date is a trading day (weekday + not a holiday)
  - Compute expected candle counts per session for a given timeframe
  - Convert between UTC and IST for session boundary checks

All session times are in IST (Asia/Kolkata, UTC+05:30).
All returned datetimes are UTC-aware.

This module is PURELY DETERMINISTIC. It does not make network calls.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# ── Timezone constants ─────────────────────────────────────────────────────────
IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# ── Session boundaries (IST) ───────────────────────────────────────────────────
# NSE regular session: 09:15 – 15:30 IST
MARKET_OPEN_IST = time(9, 15, 0)
MARKET_CLOSE_IST = time(15, 30, 0)

# ── Supported intraday timeframes and their interval in minutes ───────────────
INTRADAY_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "60m": 60,
}

# ── Provider history limits (in calendar days) ────────────────────────────────
# Yahoo Finance documented limitations for intraday intervals:
PROVIDER_HISTORY_LIMIT_DAYS: dict[str, int] = {
    "1m": 7,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "1h": 730,
    "60m": 730,
}

# ── NSE Exchange Holidays (curated, verified against NSE official calendar) ───
# Format: (year, month, day)
# Sources: NSE official holiday calendar
# Note: This list must be updated annually. Only covers 2024 and 2025.
_NSE_HOLIDAYS_YMD: frozenset[tuple[int, int, int]] = frozenset([
    # 2024
    (2024, 1, 22),   # Ram Mandir Consecration (special holiday)
    (2024, 1, 26),   # Republic Day
    (2024, 3, 25),   # Holi
    (2024, 4, 14),   # Dr. Ambedkar Jayanti / Good Friday (combined)
    (2024, 4, 17),   # Ram Navami
    (2024, 4, 21),   # Mahavir Jayanti
    (2024, 5, 23),   # Buddha Purnima
    (2024, 6, 17),   # Bakri Id
    (2024, 7, 17),   # Moharram
    (2024, 8, 15),   # Independence Day
    (2024, 10, 2),   # Gandhi Jayanti / Dussehra
    (2024, 11, 1),   # Diwali Laxmi Pujan
    (2024, 11, 15),  # Gurunanak Jayanti
    (2024, 12, 25),  # Christmas

    # 2025
    (2025, 1, 26),   # Republic Day
    (2025, 2, 26),   # Maha Shivaratri
    (2025, 3, 14),   # Holi
    (2025, 3, 31),   # Id-ul-Fitr (Ramzan Id)
    (2025, 4, 10),   # Shri Ram Navami
    (2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    (2025, 4, 18),   # Good Friday
    (2025, 5, 1),    # Maharashtra Day
    (2025, 8, 15),   # Independence Day
    (2025, 8, 27),   # Ganesh Chaturthi
    (2025, 10, 2),   # Gandhi Jayanti / Dussehra
    (2025, 10, 20),  # Diwali Laxmi Pujan
    (2025, 10, 21),  # Diwali Balipratipada
    (2025, 11, 5),   # Gurunanak Jayanti
    (2025, 12, 25),  # Christmas
])

KNOWN_EXCHANGE_HOLIDAYS: frozenset[date] = frozenset(
    date(y, m, d) for y, m, d in _NSE_HOLIDAYS_YMD
)


class IndianMarketSession:
    """
    Deterministic service for Indian (NSE) market session semantics.

    All public methods accept either UTC-aware or IST-aware datetimes.
    Internally converts to IST for session boundary checks.
    Returned datetimes are UTC-aware.
    """

    @staticmethod
    def to_ist(dt: datetime) -> datetime:
        """Convert any timezone-aware datetime to IST."""
        if dt.tzinfo is None:
            raise ValueError("Naive datetime received — all datetimes must be timezone-aware.")
        return dt.astimezone(IST)

    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Convert any timezone-aware datetime to UTC."""
        if dt.tzinfo is None:
            raise ValueError("Naive datetime received — all datetimes must be timezone-aware.")
        return dt.astimezone(UTC)

    @classmethod
    def is_trading_day(cls, d: date) -> bool:
        """
        Return True if `d` is a weekday (Mon–Fri) and not an NSE exchange holiday.
        """
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        if d in KNOWN_EXCHANGE_HOLIDAYS:
            return False
        return True

    @classmethod
    def is_market_open(cls, dt: Optional[datetime] = None) -> bool:
        """
        Return True if `dt` falls within the NSE regular trading session
        (09:15:00–15:30:00 IST) on a valid trading day.
        Defaults to current datetime if dt is None.
        """
        if dt is None:
            dt = datetime.now(UTC)
        dt_ist = cls.to_ist(dt)
        if not cls.is_trading_day(dt_ist.date()):
            return False
        t = dt_ist.time().replace(tzinfo=None)
        return MARKET_OPEN_IST <= t <= MARKET_CLOSE_IST

    @classmethod
    def session_open_utc(cls, d: date) -> datetime:
        """Return the UTC datetime for market open on date `d`."""
        ist_open = datetime(d.year, d.month, d.day,
                            MARKET_OPEN_IST.hour, MARKET_OPEN_IST.minute, 0,
                            tzinfo=IST)
        return ist_open.astimezone(UTC)

    @classmethod
    def session_close_utc(cls, d: date) -> datetime:
        """Return the UTC datetime for market close on date `d`."""
        ist_close = datetime(d.year, d.month, d.day,
                             MARKET_CLOSE_IST.hour, MARKET_CLOSE_IST.minute, 0,
                             tzinfo=IST)
        return ist_close.astimezone(UTC)

    @classmethod
    def session_date_for_bar(cls, bar_ts_utc: datetime) -> Optional[date]:
        """
        Return the trading session date for a bar timestamp.
        Returns None if the timestamp does not fall within a valid session.
        """
        bar_ist = cls.to_ist(bar_ts_utc)
        bar_date = bar_ist.date()
        if not cls.is_trading_day(bar_date):
            return None
        t = bar_ist.time().replace(tzinfo=None)
        if MARKET_OPEN_IST <= t <= MARKET_CLOSE_IST:
            return bar_date
        return None

    @classmethod
    def expected_candles_for_session(cls, session_date: date, timeframe: str) -> int:
        """
        Return the expected number of candles in a complete NSE session for `timeframe`.
        Session duration: 09:15 → 15:30 = 375 minutes.
        Returns 0 for non-trading days or unsupported timeframes.
        """
        if not cls.is_trading_day(session_date):
            return 0
        interval_minutes = INTRADAY_TIMEFRAME_MINUTES.get(timeframe)
        if interval_minutes is None:
            return 0
        session_minutes = 375  # 09:15 to 15:30 inclusive
        # Ceiling division: 375 / 5 = 75 for 5m, 375 / 15 = 25 for 15m, etc.
        import math
        return math.ceil(session_minutes / interval_minutes)

    @classmethod
    def previous_trading_day(cls, d: date) -> date:
        """Return the most recent trading day strictly before `d`."""
        prev = d - timedelta(days=1)
        while not cls.is_trading_day(prev):
            prev -= timedelta(days=1)
        return prev

    @classmethod
    def next_trading_day(cls, d: date) -> date:
        """Return the next trading day strictly after `d`."""
        nxt = d + timedelta(days=1)
        while not cls.is_trading_day(nxt):
            nxt += timedelta(days=1)
        return nxt

    @classmethod
    def is_expected_gap(cls, ts_utc: datetime, timeframe: str) -> bool:
        """
        Return True if a missing candle at `ts_utc` is expected
        (weekend, holiday, pre-open, post-close).
        Returns False if the absence is a potential data gap.
        """
        ts_ist = cls.to_ist(ts_utc)
        bar_date = ts_ist.date()

        # Weekend
        if bar_date.weekday() >= 5:
            return True
        # Exchange holiday
        if bar_date in KNOWN_EXCHANGE_HOLIDAYS:
            return True
        # Outside trading hours
        t = ts_ist.time().replace(tzinfo=None)
        if t < MARKET_OPEN_IST or t > MARKET_CLOSE_IST:
            return True
        return False

    @classmethod
    def generate_expected_timestamps(
        cls, session_date: date, timeframe: str
    ) -> list[datetime]:
        """
        Generate all expected bar open timestamps for a trading session.
        Returns UTC-aware datetimes.

        For 5m: 09:15, 09:20, ..., 15:25 (75 candles)
        For 15m: 09:15, 09:30, ..., 15:15 (25 candles)
        For 1h: 09:15, 10:15, ..., 14:15 (6 candles)
        """
        if not cls.is_trading_day(session_date):
            return []
        interval_minutes = INTRADAY_TIMEFRAME_MINUTES.get(timeframe)
        if interval_minutes is None:
            return []

        open_ist = datetime(session_date.year, session_date.month, session_date.day,
                            MARKET_OPEN_IST.hour, MARKET_OPEN_IST.minute, 0,
                            tzinfo=IST)
        close_ist = datetime(session_date.year, session_date.month, session_date.day,
                             MARKET_CLOSE_IST.hour, MARKET_CLOSE_IST.minute, 0,
                             tzinfo=IST)

        timestamps = []
        current = open_ist
        while current <= close_ist - timedelta(minutes=interval_minutes):
            timestamps.append(current.astimezone(UTC))
            current += timedelta(minutes=interval_minutes)
        return timestamps
