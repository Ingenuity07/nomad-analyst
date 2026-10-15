"""
Intraday Candle Aggregator for Nomad Analyst.

Aggregates streaming NomadMarketTick instances into canonical 1m, 5m, and 15m OHLCV bars.
Handles:
- Boundary alignment in Asia/Kolkata (IST)
- OHLC updates (open, high, low, close)
- Volume accumulation using cumulative day volume deltas or last_traded_quantity
- Tick counting
- Out-of-order and duplicate ticks safely
- Bar finalization and durable persistence into OHLCVBar model
- In-memory querying for low-latency context calculations
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List
from django.db import transaction

from market.models import Instrument, OHLCVBar
from market.normalizers.kite import NomadMarketTick
from market.services.trading_session import TradingSessionService, IST_TIMEZONE

logger = logging.getLogger(__name__)


class AggregatedBar:
    """
    In-memory representation of an intraday bar under construction.
    """
    def __init__(self, symbol: str, timeframe: str, timestamp: datetime, open_price: Decimal):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timestamp = timestamp
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.volume = 0
        self.tick_count = 0
        self.is_finalized = False
        self.last_updated = timestamp

    def update(self, price: Decimal, volume_delta: int, tick_time: datetime):
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        if volume_delta > 0:
            self.volume += volume_delta
        self.tick_count += 1
        self.last_updated = tick_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": self.volume,
            "tick_count": self.tick_count,
            "is_finalized": self.is_finalized,
        }


class IntradayBarAggregator:
    """
    Aggregates live and historical ticks into 1-minute, 5-minute, and 15-minute bars.
    """

    TIMEFRAMES = ("1m", "5m", "15m")

    def __init__(self, persist_to_db: bool = True):
        self.persist_to_db = persist_to_db
        # Key: (symbol, timeframe) -> AggregatedBar
        self._current_bars: Dict[Tuple[str, str], AggregatedBar] = {}
        # Key: symbol -> last known cumulative day volume
        self._last_day_volumes: Dict[str, int] = {}
        # Key: symbol -> Instrument instance cache
        self._instrument_cache: Dict[str, Optional[Instrument]] = {}

    @classmethod
    def get_bucket_timestamp(cls, dt: datetime, timeframe: str) -> datetime:
        """
        Aligns a timezone-aware datetime to the opening boundary of the timeframe in IST.
        """
        ist_dt = TradingSessionService.to_ist(dt)
        if timeframe == "1m":
            return ist_dt.replace(second=0, microsecond=0)
        elif timeframe == "5m":
            minute = ist_dt.minute - (ist_dt.minute % 5)
            return ist_dt.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "15m":
            minute = ist_dt.minute - (ist_dt.minute % 15)
            return ist_dt.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "1d":
            return ist_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def _get_instrument(self, symbol: str) -> Optional[Instrument]:
        if symbol not in self._instrument_cache:
            self._instrument_cache[symbol] = Instrument.objects.filter(symbol=symbol).first()
        return self._instrument_cache[symbol]

    def process_tick(self, tick: NomadMarketTick) -> Dict[str, Optional[AggregatedBar]]:
        """
        Ingests a normalized tick, updates open bars across all supported timeframes,
        and finalizes previous bars if a timeframe boundary has been crossed.
        Returns dict mapping timeframe -> current bar.
        """
        symbol = tick.symbol
        price = tick.last_price
        tick_time = tick.exchange_timestamp or tick.received_timestamp

        # Calculate volume delta from cumulative day volume
        volume_delta = 0
        current_cum_vol = tick.volume or 0
        if current_cum_vol > 0:
            if symbol in self._last_day_volumes:
                prev_vol = self._last_day_volumes[symbol]
                if current_cum_vol >= prev_vol:
                    volume_delta = current_cum_vol - prev_vol
            else:
                volume_delta = tick.last_traded_quantity if (tick.last_traded_quantity is not None and tick.last_traded_quantity > 0) else current_cum_vol
            self._last_day_volumes[symbol] = current_cum_vol
        elif tick.last_traded_quantity is not None and tick.last_traded_quantity > 0:
            volume_delta = tick.last_traded_quantity

        updated_bars = {}

        for tf in self.TIMEFRAMES:
            bucket_ts = self.get_bucket_timestamp(tick_time, tf)
            key = (symbol, tf)
            current_bar = self._current_bars.get(key)

            if current_bar is None:
                # Initialize new bar
                new_bar = AggregatedBar(symbol=symbol, timeframe=tf, timestamp=bucket_ts, open_price=price)
                new_bar.update(price=price, volume_delta=volume_delta, tick_time=tick_time)
                self._current_bars[key] = new_bar
                updated_bars[tf] = new_bar

            elif bucket_ts > current_bar.timestamp:
                # Time boundary crossed -> finalize current bar
                current_bar.is_finalized = True
                if self.persist_to_db:
                    self._persist_bar(current_bar)

                # Start next bar
                new_bar = AggregatedBar(symbol=symbol, timeframe=tf, timestamp=bucket_ts, open_price=price)
                new_bar.update(price=price, volume_delta=volume_delta, tick_time=tick_time)
                self._current_bars[key] = new_bar
                updated_bars[tf] = new_bar

            elif bucket_ts == current_bar.timestamp:
                # Update current open bar
                current_bar.update(price=price, volume_delta=volume_delta, tick_time=tick_time)
                updated_bars[tf] = current_bar

            else:
                # Out-of-order tick arriving for an earlier timestamp
                logger.debug(f"Out-of-order tick for {symbol} [{tf}]: tick {bucket_ts} < current {current_bar.timestamp}")
                if self.persist_to_db:
                    self._update_historical_bar(symbol, tf, bucket_ts, price, volume_delta)
                updated_bars[tf] = current_bar

        return updated_bars

    def get_current_bar(self, symbol: str, timeframe: str = "1m") -> Optional[AggregatedBar]:
        """
        Retrieves the in-memory open bar for symbol and timeframe.
        """
        return self._current_bars.get((symbol, timeframe))

    def finalize_all(self):
        """
        Finalizes and persists all in-flight bars (e.g. at end of market session or shutdown).
        """
        for key, bar in self._current_bars.items():
            if not bar.is_finalized:
                bar.is_finalized = True
                if self.persist_to_db:
                    self._persist_bar(bar)

    @classmethod
    def validate_bar(cls, bar: AggregatedBar, allow_out_of_session: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validates OHLCV integrity and optional session plausibility for an aggregated bar.
        Returns (is_valid, rejection_reason).
        """
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            return False, f"Non-positive price detected: O={bar.open}, H={bar.high}, L={bar.low}, C={bar.close}"
        if bar.high < bar.low:
            return False, f"High ({bar.high}) cannot be less than low ({bar.low})"
        if bar.high < max(bar.open, bar.close):
            return False, f"High ({bar.high}) must be >= max(open, close) ({max(bar.open, bar.close)})"
        if bar.low > min(bar.open, bar.close):
            return False, f"Low ({bar.low}) must be <= min(open, close) ({min(bar.open, bar.close)})"
        if bar.volume < 0:
            return False, f"Volume ({bar.volume}) cannot be negative"
        if not allow_out_of_session and bar.timeframe != "1d":
            if not TradingSessionService.is_plausible_exchange_timestamp(bar.timestamp):
                return False, f"Timestamp {bar.timestamp} is outside plausible market session hours"
        return True, None

    def _persist_bar(self, bar: AggregatedBar):
        """
        Persists finalized bar into OHLCVBar table idempotently after validating integrity and session.
        """
        is_valid, reason = self.validate_bar(bar)
        if not is_valid:
            logger.warning(f"Rejected malformed or out-of-session bar for {bar.symbol} [{bar.timeframe}] @ {bar.timestamp}: {reason}")
            return

        inst = self._get_instrument(bar.symbol)
        if not inst:
            return

        try:
            OHLCVBar.objects.update_or_create(
                instrument=inst,
                timeframe=bar.timeframe,
                timestamp=bar.timestamp,
                defaults={
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "source": "NomadAggregator",
                },
            )
        except Exception as e:
            logger.error(f"Failed to persist {bar.symbol} [{bar.timeframe}] bar at {bar.timestamp}: {e}")

    def _update_historical_bar(
        self, symbol: str, timeframe: str, timestamp: datetime, price: Decimal, volume_delta: int
    ):
        """
        Safely updates an existing historical bar for an out-of-order tick without corrupting OHLC integrity.
        """
        if price <= 0 or volume_delta < 0:
            logger.warning(f"Rejected invalid historical update for {symbol} [{timeframe}]: price={price}, vol={volume_delta}")
            return

        inst = self._get_instrument(symbol)
        if not inst:
            return

        bar = OHLCVBar.objects.filter(instrument=inst, timeframe=timeframe, timestamp=timestamp).first()
        if bar:
            bar.high = max(bar.high, price)
            bar.low = min(bar.low, price)
            bar.close = price
            if volume_delta > 0:
                bar.volume += volume_delta
            bar.save()
