"""
Nomad Analyst — NIFTY Effective-Dated Expiry Calendar & Schedule Validator
Reference: DEC-01 in docs/historical_options_backtester_architecture.md
"""

from datetime import date, datetime, time
import logging
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# Authoritative schedule of NIFTY weekly index option expiries (July 2025 to July 2026).
# Sourced from NSE contract specifications and official trading holiday calendars.
AUTHORITATIVE_EXCHANGE_EXPIRIES: List[date] = [
    # 2025: Thursday weekly expiries (July - August 2025)
    date(2025, 7, 3),
    date(2025, 7, 10),
    date(2025, 7, 17),
    date(2025, 7, 24),
    date(2025, 7, 31),
    date(2025, 8, 7),
    date(2025, 8, 14),
    date(2025, 8, 21),
    date(2025, 8, 28),

    # 2025: Tuesday weekly expiries (NSE contract rationalization eff Sep 2025)
    date(2025, 9, 2),
    date(2025, 9, 9),
    date(2025, 9, 16),
    date(2025, 9, 23),
    date(2025, 9, 30),
    date(2025, 10, 7),
    date(2025, 10, 14),
    date(2025, 10, 21),  # Official exchange expiry (omitted in Hugging Face upload)
    date(2025, 10, 28),
    date(2025, 11, 4),
    date(2025, 11, 11),
    date(2025, 11, 18),
    date(2025, 11, 25),
    date(2025, 12, 2),
    date(2025, 12, 9),
    date(2025, 12, 16),
    date(2025, 12, 23),
    date(2025, 12, 30),

    # 2026: Tuesday weekly expiries (with Monday pre-ponements for holidays)
    date(2026, 1, 6),
    date(2026, 1, 13),
    date(2026, 1, 20),
    date(2026, 1, 27),
    date(2026, 2, 3),
    date(2026, 2, 10),
    date(2026, 2, 17),
    date(2026, 2, 24),
    date(2026, 3, 2),   # Monday (pre-poned due to Holi holiday on Tue 2026-03-03)
    date(2026, 3, 10),
    date(2026, 3, 17),
    date(2026, 3, 24),
    date(2026, 3, 30),  # Monday (pre-poned due to Mahavir Jayanti holiday)
    date(2026, 4, 7),
    date(2026, 4, 13),  # Monday (pre-poned due to Ambedkar Jayanti on Tue 2026-04-14)
    date(2026, 4, 21),
    date(2026, 4, 28),
    date(2026, 5, 5),
    date(2026, 5, 12),
    date(2026, 5, 19),
    date(2026, 5, 26),
    date(2026, 6, 2),
    date(2026, 6, 9),
    date(2026, 6, 16),  # Official exchange expiry (omitted in Hugging Face upload)
    date(2026, 6, 23),  # Official exchange expiry (omitted in Hugging Face upload)
    date(2026, 6, 30),  # Official exchange expiry (omitted in Hugging Face upload)
    date(2026, 7, 7),
    date(2026, 7, 14),
    date(2026, 7, 21),
    date(2026, 7, 28),
    date(2026, 8, 4),
]


class NiftyExpiryCalendar:
    """
    Manages and validates NIFTY option expiries against official exchange schedules.
    Enforces hard session eligibility failures when required expiry data is missing.
    """

    def __init__(
        self,
        dataset_expiries: Optional[List[date]] = None,
        exchange_schedule: Optional[List[date]] = None,
        reader: Optional[Any] = None,
    ):
        if dataset_expiries is None:
            if reader is not None:
                exp_strs = reader.get_available_expiries()
            else:
                from fno.services.historical_reader import HistoricalParquetReader
                exp_strs = HistoricalParquetReader().get_available_expiries()
            dataset_expiries = [date.fromisoformat(e) for e in exp_strs]

        self.dataset_expiries: Set[date] = set(dataset_expiries)
        self.exchange_schedule: List[date] = sorted(exchange_schedule or AUTHORITATIVE_EXCHANGE_EXPIRIES)
        self.missing_dataset_expiries: Set[date] = set(self.exchange_schedule) - self.dataset_expiries
        if self.missing_dataset_expiries:
            logger.warning(
                "DATASET_EXPIRY_GAP_ALERT: %d scheduled exchange expiries are missing from dataset storage: %s",
                len(self.missing_dataset_expiries),
                sorted(self.missing_dataset_expiries),
            )

    def get_nearest_scheduled_expiry(self, session_date: date) -> Optional[date]:
        """Returns the nearest official exchange expiry on or after session_date."""
        for exp in self.exchange_schedule:
            if exp >= session_date:
                return exp
        return None

    def get_next_scheduled_expiry(self, session_date: date) -> Optional[date]:
        """Returns the subsequent official exchange expiry after the nearest one."""
        found_nearest = False
        for exp in self.exchange_schedule:
            if exp >= session_date:
                if not found_nearest:
                    found_nearest = True
                else:
                    return exp
        return None

    def has_local_expiry_data(self, expiry: date) -> bool:
        """Returns True if the option parquet file for expiry exists locally."""
        return expiry in self.dataset_expiries

    def is_session_expiry_available(self, session_date: date, roll_to_next: bool = False) -> bool:
        """
        Verifies whether local data is present for the target expiry.
        Hard eligibility check: if local file is missing, returns False.
        """
        if roll_to_next:
            target_exp = self.get_next_scheduled_expiry(session_date)
        else:
            target_exp = self.get_nearest_scheduled_expiry(session_date)

        if not target_exp:
            return False
        return self.has_local_expiry_data(target_exp)

    def is_session_eligible(self, session_date: date, has_rolled: bool = False) -> bool:
        """
        Hard session eligibility gate: returns True if authentic local option data
        exists for the scheduled exchange expiry.
        """
        return self.is_session_expiry_available(session_date=session_date, roll_to_next=has_rolled)

    def resolve_session_expiry(
        self,
        session_date: date,
        current_time: Optional[Union[time, datetime]] = None,
        roll_cutoff_time: time = time(13, 0, 0),
    ) -> Optional[date]:
        """
        Resolves active expiry date for a session.
        Applies 0-DTE roll policy: on expiry day for signals at or after 13:00 IST,
        rolls to next weekly expiry. For signals before 13:00 IST, retains 0-DTE contract.
        Returns None if local data for resolved expiry is absent (Hard Failure).
        """
        nearest = self.get_nearest_scheduled_expiry(session_date)
        if not nearest:
            return None

        # Check 0-DTE rollover policy: roll only on expiry day at or after cutoff
        is_expiry_day = (nearest == session_date)
        roll_to_next = False
        if is_expiry_day and current_time is not None:
            t = current_time.time() if isinstance(current_time, datetime) else current_time
            if t >= roll_cutoff_time:
                roll_to_next = True

        target_exp = self.get_next_scheduled_expiry(session_date) if roll_to_next else nearest
        if not target_exp or not self.has_local_expiry_data(target_exp):
            return None
        return target_exp
