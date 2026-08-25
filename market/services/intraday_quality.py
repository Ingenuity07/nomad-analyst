"""
intraday_quality.py — Intraday data freshness and quality assessment for Module 9.

Determines:
  - Latest available candle vs expected candle for the current session
  - Ingestion lag in seconds
  - Session completeness %
  - Data gap count
  - Overall quality status

Quality States:
  HEALTHY     — data is current and complete enough for signal generation
  STALE       — data exists but is too old (lag > threshold)
  INCOMPLETE  — data exists but session is missing many candles
  UNAVAILABLE — no intraday data exists at all

This is a DETERMINISTIC read-only service. No network calls.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from market.services.market_session import (
    IndianMarketSession,
    INTRADAY_TIMEFRAME_MINUTES,
)

logger = logging.getLogger(__name__)

# ── Staleness thresholds (in minutes of lag) ──────────────────────────────────
# How many minutes behind the expected last candle we tolerate before marking STALE.
STALENESS_THRESHOLD_MINUTES: dict[str, int] = {
    "1m": 5,
    "5m": 15,
    "15m": 30,
    "30m": 45,
    "1h": 90,
    "60m": 90,
}

# ── Completeness threshold ────────────────────────────────────────────────────
# Minimum session completeness % required to be HEALTHY vs INCOMPLETE
COMPLETENESS_THRESHOLD_PCT: float = 80.0


class IntradayQualityStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class IntradayDataQuality:
    """
    Structured quality assessment for a single instrument+timeframe.
    """
    status: IntradayQualityStatus
    latest_timestamp: Optional[datetime]          # Latest bar in DB (UTC)
    expected_timestamp: Optional[datetime]         # Expected last bar for session (UTC)
    lag_seconds: Optional[float]                   # How far behind (positive = lagging)
    completeness_pct: Optional[float]              # % of expected session candles present
    data_gaps_count: int = 0                       # Number of DATA_GAP entries
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status.value,
            "latest_timestamp": self.latest_timestamp.isoformat() if self.latest_timestamp else None,
            "expected_timestamp": self.expected_timestamp.isoformat() if self.expected_timestamp else None,
            "lag_seconds": round(self.lag_seconds, 1) if self.lag_seconds is not None else None,
            "completeness_pct": round(self.completeness_pct, 1) if self.completeness_pct is not None else None,
            "data_gaps_count": self.data_gaps_count,
            "notes": self.notes,
        }


def get_data_quality(
    instrument,          # Instrument model instance
    timeframe: str,
    as_of: Optional[datetime] = None,
) -> IntradayDataQuality:
    """
    Assess the intraday data quality for instrument+timeframe.

    as_of: defaults to current UTC time if not provided.
    Returns IntradayDataQuality with the appropriate status.
    """
    from market.models import OHLCVBar
    from market.services.gap_detector import detect_gaps

    if as_of is None:
        as_of = datetime.now(timezone.utc)

    # ── Check if any intraday data exists ────────────────────────────────────
    latest_bar = (
        OHLCVBar.objects
        .filter(instrument=instrument, timeframe=timeframe, timestamp__lte=as_of)
        .order_by("-timestamp")
        .first()
    )

    if latest_bar is None:
        return IntradayDataQuality(
            status=IntradayQualityStatus.UNAVAILABLE,
            latest_timestamp=None,
            expected_timestamp=None,
            lag_seconds=None,
            completeness_pct=None,
            data_gaps_count=0,
            notes="No intraday bars found in database for this instrument+timeframe."
        )

    latest_ts = latest_bar.timestamp
    interval_minutes = INTRADAY_TIMEFRAME_MINUTES.get(timeframe)
    if interval_minutes is None:
        return IntradayDataQuality(
            status=IntradayQualityStatus.UNAVAILABLE,
            latest_timestamp=latest_ts,
            expected_timestamp=None,
            lag_seconds=None,
            completeness_pct=None,
            notes=f"Unsupported timeframe: {timeframe}"
        )

    session = IndianMarketSession()
    as_of_date = as_of.date()

    # ── Determine the most recent session we should have data for ────────────
    # If market is currently open: expected last bar = interval before as_of
    # If market is closed: expected last bar = last bar of previous trading day
    if session.is_market_open(as_of):
        # Expected last bar: most recent complete bar before as_of
        # (we round down to nearest interval boundary)
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        as_of_ist = as_of.astimezone(IST)
        total_min = as_of_ist.hour * 60 + as_of_ist.minute
        session_open_min = 9 * 60 + 15
        offset = (total_min - session_open_min)
        if offset < interval_minutes:
            # Session just opened — no complete bar yet
            expected_timestamp = None
        else:
            completed_intervals = (offset // interval_minutes) - 1
            expected_ist = datetime(
                as_of_ist.year, as_of_ist.month, as_of_ist.day,
                9, 15, 0, tzinfo=IST
            ) + timedelta(minutes=completed_intervals * interval_minutes)
            expected_timestamp = expected_ist.astimezone(timezone.utc)
    else:
        # Market closed — find last session and its expected last bar
        ref_date = as_of_date
        if not session.is_trading_day(ref_date) or as_of.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
        ).time().hour < 9:
            ref_date = session.previous_trading_day(ref_date)

        expected_ts_list = session.generate_expected_timestamps(ref_date, timeframe)
        expected_timestamp = expected_ts_list[-1] if expected_ts_list else None

    # ── Compute lag ──────────────────────────────────────────────────────────
    lag_seconds: Optional[float] = None
    if expected_timestamp is not None:
        lag_seconds = (expected_timestamp - latest_ts).total_seconds()

    # ── Compute session completeness ─────────────────────────────────────────
    completeness_pct: Optional[float] = None
    data_gaps_count = 0

    # Use last 3 trading days for completeness assessment
    assessment_start = latest_ts - timedelta(days=3)
    assessment_end = latest_ts

    if assessment_start <= assessment_end:
        gap_report = detect_gaps(instrument, timeframe, assessment_start, assessment_end)
        data_gaps_count = gap_report.data_gap_count

        # Completeness = actual / expected bars in that window
        expected_count = (
            OHLCVBar.objects
            .filter(instrument=instrument, timeframe=timeframe,
                    timestamp__gte=assessment_start, timestamp__lte=assessment_end)
            .count()
        )
        # Rough expected: 3 trading days worth
        expected_total = 0
        d = assessment_start.date()
        while d <= assessment_end.date():
            expected_total += session.expected_candles_for_session(d, timeframe)
            d += timedelta(days=1)

        if expected_total > 0:
            completeness_pct = min(100.0, (expected_count / expected_total) * 100.0)
        else:
            completeness_pct = 100.0

    # ── Determine status ─────────────────────────────────────────────────────
    stale_threshold = STALENESS_THRESHOLD_MINUTES.get(timeframe, 60) * 60  # seconds

    if lag_seconds is not None and lag_seconds > stale_threshold:
        status = IntradayQualityStatus.STALE
        notes = (f"Data is {lag_seconds:.0f}s behind expected "
                 f"(threshold {stale_threshold:.0f}s).")
    elif completeness_pct is not None and completeness_pct < COMPLETENESS_THRESHOLD_PCT:
        status = IntradayQualityStatus.INCOMPLETE
        notes = (f"Session completeness {completeness_pct:.1f}% < "
                 f"{COMPLETENESS_THRESHOLD_PCT:.0f}% threshold. "
                 f"Data gaps: {data_gaps_count}.")
    else:
        status = IntradayQualityStatus.HEALTHY
        notes = (f"Data quality healthy. Latest bar: {latest_ts.isoformat()}. "
                 f"Lag: {lag_seconds:.0f}s." if lag_seconds is not None
                 else "Data quality healthy.")

    return IntradayDataQuality(
        status=status,
        latest_timestamp=latest_ts,
        expected_timestamp=expected_timestamp,
        lag_seconds=lag_seconds,
        completeness_pct=completeness_pct,
        data_gaps_count=data_gaps_count,
        notes=notes,
    )
