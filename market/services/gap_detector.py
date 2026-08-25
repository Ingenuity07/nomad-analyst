"""
gap_detector.py — Deterministic intraday gap detection for Module 9.

Distinguishes:
  EXPECTED_GAP  — weekend, exchange holiday, pre-open, post-close
  DATA_GAP      — missing candle during a valid NSE trading session

Does NOT fabricate candles. Reports gaps explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Optional

from market.services.market_session import IndianMarketSession, INTRADAY_TIMEFRAME_MINUTES


class GapType(str, Enum):
    EXPECTED_GAP = "EXPECTED_GAP"   # weekend / holiday / outside session hours
    DATA_GAP = "DATA_GAP"           # missing candle during a valid session window


@dataclass
class GapEntry:
    timestamp_utc: datetime
    gap_type: GapType
    session_date: Optional[date]
    reason: str


@dataclass
class GapReport:
    instrument_symbol: str
    timeframe: str
    from_dt: datetime
    to_dt: datetime
    expected_gaps: List[GapEntry] = field(default_factory=list)
    data_gaps: List[GapEntry] = field(default_factory=list)

    @property
    def total_missing(self) -> int:
        return len(self.expected_gaps) + len(self.data_gaps)

    @property
    def has_data_gaps(self) -> bool:
        return len(self.data_gaps) > 0

    @property
    def data_gap_count(self) -> int:
        return len(self.data_gaps)

    def summary(self) -> dict:
        return {
            "instrument": self.instrument_symbol,
            "timeframe": self.timeframe,
            "from": self.from_dt.isoformat(),
            "to": self.to_dt.isoformat(),
            "expected_gaps": len(self.expected_gaps),
            "data_gaps": len(self.data_gaps),
            "total_missing": self.total_missing,
        }


def detect_gaps(
    instrument,  # Instrument model instance
    timeframe: str,
    from_dt: datetime,
    to_dt: datetime,
) -> GapReport:
    """
    Detect missing candles between from_dt and to_dt for instrument+timeframe.

    Algorithm:
      1. Generate all expected timestamps for trading days in the range
      2. Load the set of actual timestamps from the DB
      3. Diff: any expected timestamp absent from actual = gap
      4. Classify each gap as EXPECTED_GAP or DATA_GAP

    from_dt and to_dt must be UTC-aware.
    """
    from market.models import OHLCVBar

    session = IndianMarketSession()
    interval_minutes = INTRADAY_TIMEFRAME_MINUTES.get(timeframe)
    if interval_minutes is None:
        # Not an intraday timeframe — return empty report
        return GapReport(
            instrument_symbol=instrument.symbol,
            timeframe=timeframe,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    # 1. Build set of expected timestamps across all trading days in range
    expected_timestamps: List[datetime] = []
    current_date = from_dt.date()
    end_date = to_dt.date()

    while current_date <= end_date:
        if session.is_trading_day(current_date):
            day_ts = session.generate_expected_timestamps(current_date, timeframe)
            # Filter to range window
            for ts in day_ts:
                if from_dt <= ts <= to_dt:
                    expected_timestamps.append(ts)
        current_date += timedelta(days=1)

    if not expected_timestamps:
        return GapReport(
            instrument_symbol=instrument.symbol,
            timeframe=timeframe,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    # 2. Fetch actual timestamps from DB
    actual_timestamps: set[datetime] = set(
        OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__gte=from_dt,
            timestamp__lte=to_dt,
        ).values_list("timestamp", flat=True)
    )

    # 3. Identify missing
    report = GapReport(
        instrument_symbol=instrument.symbol,
        timeframe=timeframe,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    for expected_ts in expected_timestamps:
        if expected_ts in actual_timestamps:
            continue  # Present — no gap

        # 4. Classify the gap
        # Within a valid session? → DATA_GAP. Otherwise → EXPECTED_GAP.
        session_date = session.session_date_for_bar(expected_ts)
        if session_date is not None:
            report.data_gaps.append(GapEntry(
                timestamp_utc=expected_ts,
                gap_type=GapType.DATA_GAP,
                session_date=session_date,
                reason=f"Missing {timeframe} bar during valid session on {session_date.isoformat()}"
            ))
        else:
            report.expected_gaps.append(GapEntry(
                timestamp_utc=expected_ts,
                gap_type=GapType.EXPECTED_GAP,
                session_date=None,
                reason="Outside NSE trading session (weekend, holiday, or off-hours)"
            ))

    return report
