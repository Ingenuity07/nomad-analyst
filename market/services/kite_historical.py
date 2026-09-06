"""
Kite Historical Data Ingestion Service.

Provides idempotent ingestion of Kite historical candles (1D, 1m, 5m, 15m)
into Nomad's canonical OHLCVBar model.

Enforces:
- Unique constraint: (instrument, timeframe, timestamp)
- Timezone awareness: Asia/Kolkata (IST)
- Deduplication and idempotency on repeated runs
- Strict OHLC relationships validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone

from market.models import Instrument, OHLCVBar
from market.providers.kite import KiteMarketDataProvider
from market.normalizers.kite import KiteNormalizer
from market.services.trading_session import TradingSessionService

logger = logging.getLogger(__name__)


class KiteHistoricalIngestionService:
    """
    Idempotently ingests and backfills historical bars from Kite Connect into OHLCVBar.
    """

    def __init__(self, provider: Optional[KiteMarketDataProvider] = None):
        self.provider = provider or KiteMarketDataProvider()

    def ingest_symbol(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetches, validates, and stores historical candles for a symbol.
        Safe to re-run; will not duplicate existing bars.
        """
        inst = Instrument.objects.filter(symbol=symbol).first()
        if not inst:
            raise ValueError(f"Instrument '{symbol}' does not exist in Nomad database.")

        now_ist = TradingSessionService.to_ist().replace(second=0, microsecond=0)
        if end_date is None:
            end_date = now_ist
        else:
            end_date = TradingSessionService.to_ist(end_date).replace(second=0, microsecond=0)

        if start_date is None:
            if timeframe in ("1d", "day"):
                start_date = (end_date - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif "minute" in timeframe or timeframe in ("1m", "5m", "15m"):
                start_date = (end_date - timedelta(days=15)).replace(second=0, microsecond=0)
            else:
                start_date = (end_date - timedelta(days=60)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = TradingSessionService.to_ist(start_date).replace(second=0, microsecond=0)

        logger.info(
            f"KiteHistoricalIngestion: fetching {symbol} [{timeframe}] "
            f"from {start_date.date()} to {end_date.date()}"
        )

        raw_payload = self.provider.get_historical_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        raw_candles = raw_payload.get("candles", [])
        if not raw_candles:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "total_fetched": 0,
                "created": 0,
                "existing": 0,
                "errors": 0,
            }

        # Normalize and validate candles
        normalized_bars = []
        parse_errors = 0
        timestamps = []

        for item in raw_candles:
            try:
                bar_dict = KiteNormalizer.normalize_candle(item, symbol, timeframe=timeframe)
                normalized_bars.append(bar_dict)
                timestamps.append(bar_dict["timestamp"])
            except Exception as e:
                parse_errors += 1
                logger.error(f"Integrity failure in candle for {symbol} ({timeframe}): {e}")

        if not normalized_bars:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "total_fetched": len(raw_candles),
                "created": 0,
                "existing": 0,
                "errors": parse_errors,
            }

        # Query existing timestamps for idempotency
        existing_ts_set = set(
            OHLCVBar.objects.filter(
                instrument=inst,
                timeframe=timeframe,
                timestamp__in=timestamps,
            ).values_list("timestamp", flat=True)
        )

        bars_to_create = []
        for bar in normalized_bars:
            if bar["timestamp"] not in existing_ts_set:
                bars_to_create.append(
                    OHLCVBar(
                        instrument=inst,
                        timeframe=timeframe,
                        timestamp=bar["timestamp"],
                        open=bar["open"],
                        high=bar["high"],
                        low=bar["low"],
                        close=bar["close"],
                        volume=bar["volume"],
                        source="Kite",
                    )
                )

        created_count = 0
        if bars_to_create:
            with transaction.atomic():
                created = OHLCVBar.objects.bulk_create(bars_to_create, ignore_conflicts=True)
                created_count = len(created)

        existing_count = len(normalized_bars) - created_count

        logger.info(
            f"KiteHistoricalIngestion: {symbol} [{timeframe}] -> "
            f"created {created_count}, existing {existing_count}, errors {parse_errors}"
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_fetched": len(raw_candles),
            "created": created_count,
            "existing": existing_count,
            "errors": parse_errors,
        }
