"""
intraday_cooldown.py — Duplicate signal prevention for intraday recommendations.

Prevents repeated identical signals within a configured cooldown window.
Pure read-based gate — does NOT modify or delete any historical records.

Cooldown logic:
  A cooldown is ACTIVE if an ACTIVE recommendation exists for:
    instrument + direction + setup_type within the last COOLDOWN_MINUTES.

  A materially changed setup (different setup_type or direction) is NOT
  blocked by cooldown — only identical (same direction + same setup).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from market.intraday_strategy_config import COOLDOWN_MINUTES

logger = logging.getLogger(__name__)


def is_in_cooldown(
    instrument,
    direction: str,
    setup_type: str,
    as_of: datetime,
    cooldown_minutes: int = COOLDOWN_MINUTES,
) -> bool:
    """
    Check if a cooldown is active for this instrument + direction + setup combination.

    Args:
        instrument:       Instrument model instance.
        direction:        Signal direction value (e.g. 'BUY', 'SELL').
        setup_type:       Setup type value (e.g. 'OPENING_RANGE_BREAKOUT').
        as_of:            Point-in-time anchor for the check.
        cooldown_minutes: Window in minutes to look back.

    Returns:
        True if cooldown is active (new recommendation should be blocked).
        False if no recent duplicate found.
    """
    from market.models import StockRecommendation
    from market.signal_enums import RecommendationStatus

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    cooldown_start = as_of - timedelta(minutes=cooldown_minutes)

    exists = StockRecommendation.objects.filter(
        instrument=instrument,
        signal=direction,
        setup_type=setup_type,
        horizon="INTRADAY",
        status__in=[
            RecommendationStatus.ACTIVE.value,
            RecommendationStatus.TRIGGERED.value,
        ],
        generated_at__gte=cooldown_start,
        generated_at__lte=as_of,
    ).exists()

    if exists:
        logger.info(
            f"Cooldown active: {instrument.symbol} {direction} {setup_type} "
            f"within last {cooldown_minutes}min"
        )

    return exists


def cooldown_reason(
    instrument,
    direction: str,
    setup_type: str,
    as_of: datetime,
    cooldown_minutes: int = COOLDOWN_MINUTES,
) -> Optional[str]:
    """
    Return a human-readable reason if cooldown is active, else None.
    """
    if is_in_cooldown(instrument, direction, setup_type, as_of, cooldown_minutes):
        return (
            f"Cooldown active: identical {direction} {setup_type} recommendation "
            f"for {instrument.symbol} generated within last {cooldown_minutes} minutes. "
            f"Waiting for cooldown to expire or setup to materially change."
        )
    return None
