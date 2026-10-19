"""
F&O Option Quote Snapshot Manager Service.
Captures high-frequency bid/ask and 5-level depth snapshots for realistic taker execution evaluation.
Implements indexed retrieval and a rolling 5-day retention policy.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from django.db import transaction

from fno.models import OptionQuoteSnapshot
from fno.services.option_normalizer import OptionTick

logger = logging.getLogger(__name__)


class OptionQuoteManager:
    """
    Manages persistence and point-in-time retrieval of option limit order book snapshots.
    """

    @staticmethod
    def record_quote_snapshot(
        tick: OptionTick, 
        tradingsymbol: Optional[str] = None
    ) -> OptionQuoteSnapshot:
        """
        Persists an authentic quote snapshot from an OptionTick.
        If exchange_time_status is not VALID, exchange_timestamp_utc is set to None.
        Enforces execution-eligibility and classification flags.
        """
        symbol = tradingsymbol or f"OPT_{tick.instrument_token}"
        exch_ts = tick.exchange_timestamp_utc if tick.exchange_time_status == "VALID" else None

        # Sanitize depth for JSONField (convert Decimal prices to float)
        sanitized_depth = {}
        if isinstance(tick.depth, dict):
            for side in ("buy", "sell"):
                levels = tick.depth.get(side, [])
                sanitized_depth[side] = [
                    {
                        k: (float(v) if isinstance(v, Decimal) else v)
                        for k, v in item.items()
                    }
                    for item in levels
                ]

        snapshot = OptionQuoteSnapshot.objects.create(
            instrument_token=tick.instrument_token,
            tradingsymbol=symbol,
            exchange_timestamp_utc=exch_ts,
            received_wall_clock_utc=tick.received_wall_clock_utc,
            exchange_time_status=tick.exchange_time_status,
            best_bid=tick.best_bid,
            best_ask=tick.best_ask,
            bid_quantity_l1=tick.bid_quantity_l1,
            ask_quantity_l1=tick.ask_quantity_l1,
            depth=sanitized_depth,
            quote_status=tick.quote_status,
            is_stale=tick.is_stale,
            is_locked=tick.is_locked,
            is_crossed=tick.is_crossed,
            is_execution_eligible=tick.is_execution_eligible,
        )
        return snapshot

    @staticmethod
    def get_latest_quote(instrument_token: int) -> Optional[OptionQuoteSnapshot]:
        """
        Returns the most recent quote snapshot for an instrument token.
        Leverages composite index on (instrument_token, exchange_timestamp_utc DESC).
        """
        return (
            OptionQuoteSnapshot.objects.filter(instrument_token=instrument_token)
            .order_by("-received_wall_clock_utc")
            .first()
        )

    @staticmethod
    def get_quote_at_timestamp(
        instrument_token: int,
        target_timestamp: datetime,
        max_lookback_seconds: int = 10
    ) -> Optional[OptionQuoteSnapshot]:
        """
        Point-in-time query returning the nearest quote snapshot preceding target_timestamp
        within the specified lookback window.
        """
        min_ts = target_timestamp - timedelta(seconds=max_lookback_seconds)
        return (
            OptionQuoteSnapshot.objects.filter(
                instrument_token=instrument_token,
                received_wall_clock_utc__lte=target_timestamp,
                received_wall_clock_utc__gte=min_ts,
            )
            .order_by("-received_wall_clock_utc")
            .first()
        )

    @staticmethod
    def purge_expired_quotes(days: int = 5) -> int:
        """
        Purges snapshots older than the specified retention window (default: 5 days).
        Returns number of deleted rows.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted_count, _ = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__lt=cutoff
        ).delete()
        logger.info(f"Purged {deleted_count} quote snapshots older than {cutoff.isoformat()}")
        return deleted_count
