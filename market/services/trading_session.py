"""
Indian Equity Market Trading Session Service.

Handles timezone normalization to Asia/Kolkata (IST), session classification
(PRE_MARKET, REGULAR, POST_MARKET, CLOSED), market open/close validation,
and session boundary computation for NSE/BSE equities.
"""

from datetime import datetime, time, date, timedelta
from enum import Enum
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

IST_TIMEZONE = ZoneInfo("Asia/Kolkata")

# NSE Equity Standard Trading Hours (IST)
PRE_MARKET_START = time(9, 0)
PRE_MARKET_END = time(9, 15)
REGULAR_SESSION_START = time(9, 15)
REGULAR_SESSION_END = time(15, 30)
POST_MARKET_START = time(15, 40)
POST_MARKET_END = time(16, 0)

# Standard NSE Trading Holidays for 2026 (YYYY-MM-DD)
# Source: NSE Annual Holiday Calendar
NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 3),   # Holi
    date(2026, 3, 20),  # Id-Ul-Fitr
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 5, 27),  # Bakri Id / Eid ul-Adha
    date(2026, 8, 15),  # Independence Day (Saturday)
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 8),  # Diwali Laxmi Pujan (Muhurat trading in evening)
    date(2026, 11, 10), # Diwali Balipratipada (trading holiday)
    date(2026, 11, 24), # Gurunanak Jayanti
    date(2026, 12, 25), # Christmas
}


class TradingSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    REGULAR = "REGULAR"
    POST_MARKET = "POST_MARKET"
    CLOSED = "CLOSED"


class TradingSessionService:
    """
    Centralized service for NSE/BSE equity trading session handling.
    """

    @staticmethod
    def to_ist(dt: Optional[datetime] = None) -> datetime:
        """
        Converts any datetime to Asia/Kolkata (IST). If dt is None, returns current IST datetime.
        """
        if dt is None:
            return datetime.now(IST_TIMEZONE)
        if dt.tzinfo is None:
            # Assume UTC if naive, or localize directly to IST
            return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(IST_TIMEZONE)
        return dt.astimezone(IST_TIMEZONE)

    @staticmethod
    def is_trading_day(d: Optional[date] = None) -> bool:
        """
        Checks if a given date is a valid NSE trading day (weekday and not a recognized holiday).
        """
        if d is None:
            d = TradingSessionService.to_ist().date()
        elif isinstance(d, datetime):
            d = TradingSessionService.to_ist(d).date()

        # Monday is 0, Sunday is 6
        if d.weekday() >= 5:
            return False

        if d in NSE_HOLIDAYS_2026:
            return False

        return True

    @classmethod
    def get_current_session(cls, dt: Optional[datetime] = None) -> TradingSession:
        """
        Returns the active TradingSession enum for the given timestamp in IST.
        """
        ist_dt = cls.to_ist(dt)
        curr_date = ist_dt.date()
        curr_time = ist_dt.time()

        if not cls.is_trading_day(curr_date):
            return TradingSession.CLOSED

        if PRE_MARKET_START <= curr_time < PRE_MARKET_END:
            return TradingSession.PRE_MARKET
        elif REGULAR_SESSION_START <= curr_time < REGULAR_SESSION_END:
            return TradingSession.REGULAR
        elif POST_MARKET_START <= curr_time < POST_MARKET_END:
            return TradingSession.POST_MARKET
        else:
            return TradingSession.CLOSED

    @classmethod
    def is_market_open(cls, dt: Optional[datetime] = None, include_pre_market: bool = False) -> bool:
        """
        Returns True if regular trading session is active (or pre-market if flag set).
        """
        session = cls.get_current_session(dt)
        if session == TradingSession.REGULAR:
            return True
        if include_pre_market and session == TradingSession.PRE_MARKET:
            return True
        return False

    @classmethod
    def is_trading_timestamp(cls, dt: datetime) -> bool:
        """
        Returns True if the given timestamp falls inside regular NSE equity market hours (09:15-15:30 IST on a trading day).
        """
        return cls.get_current_session(dt) == TradingSession.REGULAR

    @classmethod
    def is_plausible_exchange_timestamp(cls, dt: Optional[datetime]) -> bool:
        """
        Validates whether an exchange timestamp is plausible for Indian equity markets.
        Plausible timestamps must:
        - Not be None
        - Fall on an active NSE trading day (weekday and non-holiday)
        - Fall within standard exchange trading/reporting hours (09:00 - 16:05 IST)
        - Not be in the distant future (> 2 minutes ahead of now)
        Returns False for off-hours timestamps (e.g. 22:24 IST).
        """
        if dt is None:
            return False
        ist_dt = cls.to_ist(dt)
        curr_date = ist_dt.date()
        curr_time = ist_dt.time()

        if not cls.is_trading_day(curr_date):
            return False

        # Plausible market trading & reporting hours: 09:00:00 to 16:05:00 IST
        if not (time(9, 0) <= curr_time <= time(16, 5)):
            return False

        # Cannot be more than 2 minutes in the future
        now_ist = cls.to_ist()
        if ist_dt > now_ist + timedelta(minutes=2):
            return False

        return True

    @classmethod
    def get_session_boundaries(cls, dt: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        """
        Returns the (open_datetime, close_datetime) in IST for the regular trading session of the given date.
        """
        ist_dt = cls.to_ist(dt)
        d = ist_dt.date()
        session_start = datetime.combine(d, REGULAR_SESSION_START, tzinfo=IST_TIMEZONE)
        session_end = datetime.combine(d, REGULAR_SESSION_END, tzinfo=IST_TIMEZONE)
        return session_start, session_end

    @classmethod
    def get_previous_trading_day(cls, dt: Optional[datetime] = None) -> date:
        """
        Returns the preceding valid NSE trading day.
        """
        ist_dt = cls.to_ist(dt)
        target = ist_dt.date() - timedelta(days=1)
        while not cls.is_trading_day(target):
            target -= timedelta(days=1)
        return target
