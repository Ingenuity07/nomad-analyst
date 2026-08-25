"""
intraday_service.py — Idempotent intraday market data ingestion for Module 9.

Responsibilities:
  - Historical backfill with provider limits awareness
  - Incremental update (from last known bar)
  - Delegating to existing MarketService for actual HTTP + persistence
  - No duplicate candles (idempotency guaranteed by OHLCVBar UniqueConstraint)
  - Batch control to avoid huge single requests

Provider limits (Yahoo Finance):
  5m / 15m / 30m  → max 60 calendar days history
  1h / 60m        → max 730 calendar days history
  1m              → max 7 calendar days history

Design rule: This service NEVER bypasses the provider's validated ingestion
path. It always calls MarketService.fetch_and_save_historical_ohlcv().
"""
from __future__ import annotations

import logging
import time as time_module
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from market.services.market_session import (
    IndianMarketSession,
    INTRADAY_TIMEFRAME_MINUTES,
    PROVIDER_HISTORY_LIMIT_DAYS,
)

logger = logging.getLogger(__name__)

# ── Ingestion batch configuration ──────────────────────────────────────────────
# Split backfill into batches of this many days to avoid oversized requests
BATCH_SIZE_DAYS: dict[str, int] = {
    "1m": 1,
    "5m": 7,
    "15m": 14,
    "30m": 14,
    "1h": 30,
    "60m": 30,
}

# Delay between batches (seconds) to be respectful of provider rate limits
INTER_BATCH_DELAY_SECONDS: float = 1.5

# Number of recent days to fetch in incremental update
INCREMENTAL_LOOKBACK_DAYS: dict[str, int] = {
    "1m": 1,
    "5m": 2,
    "15m": 3,
    "30m": 3,
    "1h": 5,
    "60m": 5,
}


class IntradayMarketDataService:
    """
    High-level service for fetching and persisting intraday OHLCV bars.

    Designed to be idempotent: calling backfill() or incremental_update()
    multiple times for the same parameters is safe — no duplicate candles.
    """

    def __init__(self, market_service=None):
        # Lazy import to avoid circular dependency
        self._market_service = market_service

    @property
    def _svc(self):
        if self._market_service is None:
            from market.services.market_service import MarketService
            self._market_service = MarketService()
        return self._market_service

    # ── Public API ─────────────────────────────────────────────────────────────

    def backfill(
        self,
        symbol: str,
        timeframe: str,
        days_back: Optional[int] = None,
    ) -> dict:
        """
        Controlled historical intraday backfill for `symbol` at `timeframe`.

        - Enforces provider history limits (60d for 5m/15m, 730d for 1h)
        - Batches requests to avoid large payloads
        - Fully idempotent — re-running is safe

        Returns a summary dict.
        """
        from market.exceptions import ProviderConnectionError, RateLimitExceededError

        if timeframe not in INTRADAY_TIMEFRAME_MINUTES:
            raise ValueError(f"backfill: unsupported timeframe '{timeframe}'. "
                             f"Supported: {sorted(INTRADAY_TIMEFRAME_MINUTES.keys())}")

        max_days = PROVIDER_HISTORY_LIMIT_DAYS.get(timeframe, 60)
        if days_back is None:
            days_back = max_days
        else:
            days_back = min(days_back, max_days)

        batch_days = BATCH_SIZE_DAYS.get(timeframe, 7)
        now_utc = datetime.now(timezone.utc)
        end_dt = now_utc
        start_dt = now_utc - timedelta(days=days_back)

        logger.info(
            f"IntradayService: starting backfill for {symbol} [{timeframe}] "
            f"from {start_dt.date()} to {end_dt.date()} "
            f"({days_back} days, batch={batch_days}d)"
        )

        total_new_bars = 0
        batches_run = 0
        errors = 0

        batch_start = start_dt
        while batch_start < end_dt:
            batch_end = min(batch_start + timedelta(days=batch_days), end_dt)
            try:
                bars_before = self._count_bars(symbol, timeframe)
                self._svc.fetch_and_save_historical_ohlcv(
                    symbol, timeframe, batch_start, batch_end
                )
                bars_after = self._count_bars(symbol, timeframe)
                new_bars = bars_after - bars_before
                total_new_bars += new_bars
                batches_run += 1
                logger.info(
                    f"IntradayService: batch {batches_run} [{batch_start.date()}→{batch_end.date()}]: "
                    f"+{new_bars} new bars"
                )
            except RateLimitExceededError:
                logger.warning(
                    f"IntradayService: rate limit hit for {symbol} [{timeframe}]. "
                    f"Sleeping 30s before retrying."
                )
                time_module.sleep(30)
                try:
                    self._svc.fetch_and_save_historical_ohlcv(
                        symbol, timeframe, batch_start, batch_end
                    )
                    batches_run += 1
                except Exception as e:
                    logger.error(f"IntradayService: retry also failed: {e}")
                    errors += 1
            except ProviderConnectionError as e:
                logger.error(
                    f"IntradayService: provider connection error for batch "
                    f"[{batch_start.date()}→{batch_end.date()}]: {e}"
                )
                errors += 1
            except Exception as e:
                logger.error(
                    f"IntradayService: unexpected error for batch "
                    f"[{batch_start.date()}→{batch_end.date()}]: {e}"
                )
                errors += 1

            batch_start = batch_end
            if batch_start < end_dt:
                time_module.sleep(INTER_BATCH_DELAY_SECONDS)

        result = {
            "symbol": symbol,
            "timeframe": timeframe,
            "days_back": days_back,
            "batches_run": batches_run,
            "new_bars_ingested": total_new_bars,
            "errors": errors,
            "status": "COMPLETE" if errors == 0 else "PARTIAL",
        }
        logger.info(f"IntradayService: backfill done: {result}")
        return result

    def incremental_update(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict:
        """
        Fetch the most recent intraday bars from the last known bar to now.

        - Fetches only the last INCREMENTAL_LOOKBACK_DAYS days
        - Idempotent — safe to call repeatedly
        - If no bars exist yet: runs a full backfill instead
        """
        from market.models import Instrument

        if timeframe not in INTRADAY_TIMEFRAME_MINUTES:
            raise ValueError(f"incremental_update: unsupported timeframe '{timeframe}'.")

        lookback = INCREMENTAL_LOOKBACK_DAYS.get(timeframe, 3)
        now_utc = datetime.now(timezone.utc)
        start_dt = now_utc - timedelta(days=lookback)

        # Check if any bars exist; if not, trigger a backfill
        try:
            instrument = Instrument.objects.filter(
                symbol=symbol.strip().upper(), is_active=True
            ).first()
            if instrument is None:
                logger.warning(f"IntradayService: instrument not found for {symbol}")
                return {"symbol": symbol, "timeframe": timeframe, "status": "INSTRUMENT_NOT_FOUND"}

            latest_ts = self.get_latest_bar_timestamp(instrument, timeframe)
            if latest_ts is None:
                logger.info(
                    f"IntradayService: no existing bars for {symbol} [{timeframe}]. "
                    f"Running initial backfill."
                )
                return self.backfill(symbol, timeframe)

            # Fetch from a little before last known bar (handles edge case of partial last batch)
            effective_start = max(
                start_dt,
                latest_ts - timedelta(minutes=INTRADAY_TIMEFRAME_MINUTES[timeframe] * 2)
            )
        except Exception as e:
            logger.error(f"IntradayService: incremental_update failed for {symbol}: {e}")
            return {"symbol": symbol, "timeframe": timeframe, "status": "ERROR", "error": str(e)}

        try:
            bars_before = self._count_bars(symbol, timeframe)
            self._svc.fetch_and_save_historical_ohlcv(symbol, timeframe, effective_start, now_utc)
            bars_after = self._count_bars(symbol, timeframe)
            new_bars = bars_after - bars_before
            logger.info(
                f"IntradayService: incremental update for {symbol} [{timeframe}]: "
                f"+{new_bars} new bars (from {effective_start.date()})"
            )
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "from": effective_start.isoformat(),
                "to": now_utc.isoformat(),
                "new_bars": new_bars,
                "status": "COMPLETE",
            }
        except Exception as e:
            logger.error(f"IntradayService: incremental_update error for {symbol}: {e}")
            return {"symbol": symbol, "timeframe": timeframe, "status": "ERROR", "error": str(e)}

    def get_latest_bar_timestamp(
        self,
        instrument,    # Instrument model instance
        timeframe: str,
    ) -> Optional[datetime]:
        """Return the timestamp of the most recent intraday bar in the DB."""
        from market.models import OHLCVBar
        bar = (
            OHLCVBar.objects
            .filter(instrument=instrument, timeframe=timeframe)
            .order_by("-timestamp")
            .first()
        )
        return bar.timestamp if bar else None

    def get_bar_count(
        self,
        instrument,
        timeframe: str,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> int:
        """Return count of stored bars for instrument+timeframe within optional range."""
        from market.models import OHLCVBar
        qs = OHLCVBar.objects.filter(instrument=instrument, timeframe=timeframe)
        if from_dt:
            qs = qs.filter(timestamp__gte=from_dt)
        if to_dt:
            qs = qs.filter(timestamp__lte=to_dt)
        return qs.count()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _count_bars(self, symbol: str, timeframe: str) -> int:
        """Count total bars for symbol+timeframe (used for delta tracking)."""
        from market.models import OHLCVBar, Instrument
        try:
            instrument = Instrument.objects.filter(
                symbol=symbol.strip().upper()
            ).first()
            if instrument is None:
                return 0
            return OHLCVBar.objects.filter(instrument=instrument, timeframe=timeframe).count()
        except Exception:
            return 0
