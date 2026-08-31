"""
intraday_lifecycle.py — Session-close expiry and lifecycle management for intraday recs.

Intraday recommendations expire at end of the trading session.
They MUST NOT be carried into the next trading day.

Rules:
  1. expire_intraday_session_recommendations() marks ACTIVE intraday recs
     as EXPIRED when their expires_at <= as_of.
  2. TARGET_HIT and STOPPED transitions require market-data price evidence
     and are NOT performed here — they belong to a future price-monitoring service.
  3. Historical records are never deleted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def expire_intraday_session_recommendations(as_of: datetime) -> int:
    """
    Mark all ACTIVE intraday recommendations whose expires_at has passed as EXPIRED.

    This should be called at or after market close (15:30 IST) each trading day.

    Args:
        as_of: Point-in-time (usually current time or market close time).

    Returns:
        Number of recommendations marked as EXPIRED.
    """
    from market.models import StockRecommendation
    from market.signal_enums import RecommendationStatus
    from django.utils import timezone as tz

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    now = tz.now()
    expired_count = StockRecommendation.objects.filter(
        horizon="INTRADAY",
        status=RecommendationStatus.ACTIVE.value,
        expires_at__isnull=False,
        expires_at__lte=as_of,
    ).update(
        status=RecommendationStatus.EXPIRED.value,
        status_updated_at=now,
    )

    if expired_count:
        logger.info(f"expire_intraday_session_recommendations: expired {expired_count} intraday recs (as_of={as_of})")

    return expired_count


def compute_session_expiry(session_date, timeframe: str = "5m") -> datetime:
    """
    Compute the UTC expires_at for an intraday recommendation.
    Intraday recommendations expire at market close (15:30 IST) on session_date.

    Args:
        session_date: datetime.date (IST calendar date of the session).
        timeframe:    Not used currently — placeholder for future per-timeframe rules.

    Returns:
        timezone-aware UTC datetime of market close.
    """
    from market.services.market_session import IST
    from datetime import date as date_type

    if isinstance(session_date, datetime):
        dt_ist = session_date.astimezone(IST)
        session_date = dt_ist.date()

    # NSE market close: 15:30 IST
    close_ist = datetime(
        session_date.year, session_date.month, session_date.day, 15, 30, tzinfo=IST
    )
    return close_ist.astimezone(timezone.utc)
