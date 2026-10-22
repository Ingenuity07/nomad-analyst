"""
Nomad Analyst — Decision-Time Option Contract Selector & Lot Size Resolver
Reference: DEC-01, Section 3.2, 3.3 in docs/historical_options_backtester_architecture.md
"""

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any, Dict, Optional

from fno.backtester.calendar import NiftyExpiryCalendar

logger = logging.getLogger(__name__)


def resolve_historical_lot_size(expiry_date: date) -> int:
    """
    Authoritative NIFTY index option lot size resolver.
    - Expiries up to 2025-12-30: 75 units (verified from volume multiples in 2025 dataset).
    - Expiries from 2026-01-06 onwards: 65 units (verified from volume multiples in 2026 dataset).
    """
    if expiry_date <= date(2025, 12, 30):
        return 75
    return 65


class OptionContractSelector:
    """
    Selects the liquid ATM CE (bullish) or ATM PE (bearish) contract using strictly
    data available at the decision timestamp.
    """

    def __init__(
        self,
        calendar: NiftyExpiryCalendar,
        roll_cutoff_time: Optional[Any] = None,
    ):
        self.calendar = calendar
        self.roll_cutoff_time = roll_cutoff_time

    @staticmethod
    def resolve_lot_size(session_date: date) -> int:
        return resolve_historical_lot_size(session_date)

    @staticmethod
    def calculate_atm_strike(spot_price: Decimal) -> int:
        """
        Calculates nearest ATM strike using confirmed ₹50 strike interval.
        Uses explicit ROUND_HALF_UP tie-breaker to eliminate Python's implicit banker-rounding.
        - Exact midpoint (e.g. 24525.00) rounds up to 24550.
        """
        step = Decimal("50")
        multiple = (spot_price / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(multiple * step)

    def resolve_contract(
        self,
        session_date: date,
        spot_price: Decimal,
        option_type: str,
        current_time: Optional[Any] = None,
        allow_zero_dte_after_1300: bool = False,
    ) -> Optional[Dict[str, Any]]:
        direction = "BULLISH" if option_type.upper() == "CE" else "BEARISH"
        return self.select_contract(
            session_date=session_date,
            spot_price=spot_price,
            direction=direction,
            signal_time=datetime.combine(session_date, current_time) if isinstance(current_time, time) else (current_time or datetime.combine(session_date, time(9, 30))),
            allow_zero_dte_after_1300=allow_zero_dte_after_1300,
        )

    def select_contract(
        self,
        session_date: date,
        spot_price: Decimal,
        direction: str,  # "BULLISH" or "BEARISH"
        signal_time: datetime,
        allow_zero_dte_after_1300: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the appropriate option contract for the breakout signal.
        Returns contract dictionary or None if contract is ineligible.
        """
        # 1. Determine Option Type
        direction_upper = direction.upper()
        if direction_upper == "BULLISH":
            option_type = "CE"
        elif direction_upper == "BEARISH":
            option_type = "PE"
        else:
            raise ValueError(f"Invalid breakout direction: {direction}")

        # 2. Determine ATM Strike
        strike = self.calculate_atm_strike(spot_price)

        # 3. Resolve Expiry with 0-DTE Policy (roll to next weekly if signal >= 13:00 IST on expiry day)
        expiry = self.calendar.resolve_session_expiry(
            session_date=session_date,
            current_time=signal_time,
            roll_cutoff_time=self.roll_cutoff_time or time(13, 0, 0),
        )
        if not expiry:
            logger.warning(
                "Contract selection failed: No valid local expiry data for session %s (Hard Failure).",
                session_date,
            )
            return None

        # 4. Resolve Historical Lot Size
        lot_size = resolve_historical_lot_size(expiry)
        expiry_str = expiry.isoformat()
        tradingsymbol = f"NIFTY_{expiry_str}_{strike}_{option_type}"

        return {
            "tradingsymbol": tradingsymbol,
            "symbol": "NIFTY",
            "strike": strike,
            "option_type": option_type,
            "expiry": expiry_str,
            "expiry_date": expiry,
            "lot_size": lot_size,
        }
