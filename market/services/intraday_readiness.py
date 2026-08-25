"""
intraday_readiness.py — Intraday signal-engine readiness gate for Module 9.

Determines whether a specific instrument+timeframe has sufficient,
fresh, gap-free intraday data to safely generate an intraday recommendation.

This is the ONLY component that Module 8's SignalEngine consults when
deciding whether to lift the INTRADAY NOT_READY gate.

Readiness checks (all must pass):
  1. Timeframe is a supported intraday interval
  2. Minimum bar count met (per timeframe)
  3. Data quality is HEALTHY or INCOMPLETE (not STALE or UNAVAILABLE)
  4. Critical data gaps in the last session do not exceed threshold
  5. Technical features exist for this timeframe at or before as_of

Design rule: This service is DETERMINISTIC and READ-ONLY.
It never writes data, never makes network calls.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from market.services.market_session import INTRADAY_TIMEFRAME_MINUTES
from market.services.intraday_quality import (
    IntradayDataQuality,
    IntradayQualityStatus,
    get_data_quality,
)

logger = logging.getLogger(__name__)

# ── Minimum bar requirements per timeframe ─────────────────────────────────────
# These are the minimum number of bars required before the signal engine can
# safely calculate indicators and generate an intraday recommendation.
MINIMUM_BARS_REQUIRED: dict[str, int] = {
    "1m": 60,
    "5m": 100,
    "15m": 50,
    "30m": 30,
    "1h": 30,
    "60m": 30,
}

# ── Maximum tolerated data gaps in last session ───────────────────────────────
MAX_DATA_GAPS_LAST_SESSION: int = 5


@dataclass
class ReadinessResult:
    """
    Result of an intraday readiness check.

    is_ready  — True if the signal engine may generate an intraday recommendation.
    reason    — Human-readable explanation of why it is/isn't ready.
    quality   — Full IntradayDataQuality assessment.
    bar_count — Actual bar count at as_of.
    required_bars — Minimum bars required for this timeframe.
    checks_passed — List of checks that passed.
    checks_failed — List of checks that failed.
    """
    is_ready: bool
    reason: str
    quality: Optional[IntradayDataQuality] = None
    bar_count: int = 0
    required_bars: int = 0
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "is_ready": self.is_ready,
            "reason": self.reason,
            "bar_count": self.bar_count,
            "required_bars": self.required_bars,
            "quality": self.quality.as_dict() if self.quality else None,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
        }


class IntradayReadinessService:
    """
    Determines whether a specific instrument+timeframe is ready for
    intraday signal generation.

    Called by SignalEngine when horizon == INTRADAY.
    """

    def check_readiness(
        self,
        instrument,       # Instrument model instance
        timeframe: str,
        as_of: Optional[datetime] = None,
    ) -> ReadinessResult:
        """
        Run all readiness checks and return a ReadinessResult.

        Parameters:
          instrument : Instrument model instance
          timeframe  : One of '5m', '15m', '1h' (or others in INTRADAY_TIMEFRAME_MINUTES)
          as_of      : Point-in-time (UTC-aware). Defaults to current UTC time.

        Returns ReadinessResult with is_ready=True only if ALL checks pass.
        """
        from market.models import OHLCVBar, TechnicalFeature

        if as_of is None:
            as_of = datetime.now(timezone.utc)

        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # ── Check 1: Supported timeframe ─────────────────────────────────────
        if timeframe not in INTRADAY_TIMEFRAME_MINUTES:
            checks_failed.append(
                f"Timeframe '{timeframe}' is not a supported intraday interval. "
                f"Supported: {sorted(INTRADAY_TIMEFRAME_MINUTES.keys())}"
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append(f"Timeframe '{timeframe}' is supported.")

        # ── Check 2: Minimum bar count ────────────────────────────────────────
        min_bars = MINIMUM_BARS_REQUIRED.get(timeframe, 50)
        bar_count = OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__lte=as_of,
        ).count()

        if bar_count < min_bars:
            checks_failed.append(
                f"Insufficient bars: {bar_count} available, {min_bars} required for {timeframe}."
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                bar_count=bar_count,
                required_bars=min_bars,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append(f"Bar count OK: {bar_count} >= {min_bars}.")

        # ── Check 3: Data quality ─────────────────────────────────────────────
        quality = get_data_quality(instrument, timeframe, as_of)

        if quality.status == IntradayQualityStatus.UNAVAILABLE:
            checks_failed.append(
                f"Data quality UNAVAILABLE for {instrument.symbol} [{timeframe}]: "
                f"{quality.notes}"
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                quality=quality,
                bar_count=bar_count,
                required_bars=min_bars,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )

        if quality.status == IntradayQualityStatus.STALE:
            checks_failed.append(
                f"Data quality STALE for {instrument.symbol} [{timeframe}]: "
                f"{quality.notes}"
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                quality=quality,
                bar_count=bar_count,
                required_bars=min_bars,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )

        checks_passed.append(f"Data quality acceptable: {quality.status.value}.")

        # ── Check 4: Critical data gaps ───────────────────────────────────────
        if quality.data_gaps_count > MAX_DATA_GAPS_LAST_SESSION:
            checks_failed.append(
                f"Too many data gaps: {quality.data_gaps_count} detected "
                f"(max tolerated: {MAX_DATA_GAPS_LAST_SESSION}) for {timeframe}."
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                quality=quality,
                bar_count=bar_count,
                required_bars=min_bars,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append(
            f"Data gaps within tolerance: {quality.data_gaps_count} "
            f"<= {MAX_DATA_GAPS_LAST_SESSION}."
        )

        # ── Check 5: Technical features exist ────────────────────────────────
        has_features = TechnicalFeature.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__lte=as_of,
        ).exists()

        if not has_features:
            checks_failed.append(
                f"No technical features found for {instrument.symbol} [{timeframe}] "
                f"at or before {as_of.isoformat()}. Run feature calculation first."
            )
            return ReadinessResult(
                is_ready=False,
                reason=checks_failed[-1],
                quality=quality,
                bar_count=bar_count,
                required_bars=min_bars,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append(f"Technical features exist for {timeframe}.")

        # ── All checks passed ─────────────────────────────────────────────────
        reason = (
            f"INTRADAY READY: {instrument.symbol} [{timeframe}] | "
            f"bars={bar_count}, quality={quality.status.value}, "
            f"gaps={quality.data_gaps_count}."
        )
        logger.info(f"IntradayReadinessService: {reason}")

        return ReadinessResult(
            is_ready=True,
            reason=reason,
            quality=quality,
            bar_count=bar_count,
            required_bars=min_bars,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )
