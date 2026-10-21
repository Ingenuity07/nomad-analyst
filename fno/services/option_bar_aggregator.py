"""
F&O Option 1-Minute OHLCV Bar Aggregation & Idempotent Persistence Engine.
Aggregates normalized OptionTick events into 1-minute candle rollups.
Persists to fno_option_ohlcvbar table with compound unique constraint idempotency.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set

from django.db import transaction

from fno.models import OptionOHLCVBar
from fno.services.option_normalizer import OptionTick
from fno.services.option_registry import OptionContractMeta

logger = logging.getLogger(__name__)


@dataclass
class ActiveBar:
    """In-memory aggregation state for a 1-minute option bar."""
    instrument_token: int
    tradingsymbol: str
    underlying_symbol: str
    option_type: str
    strike_price: Decimal
    expiry_date: Optional[date]
    timeframe: str
    timestamp: datetime                 # Aligned to minute start UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_start: int                   # Cumulative volume at bar opening
    volume_delta: int                   # Traded volume in this bar
    open_interest: Optional[int]
    oi_status: str
    is_partial_bar: bool = False
    ticks_count: int = 0


class OptionBarAggregator:
    """
    Stateful candle rollup service for F&O contracts.
    Buffers open bars per token, rotates on 60-second boundaries,
    and idempotently writes completed bars to PostgreSQL.

    Thread-safe: State transitions on _active_bars and _completed_bars are
    synchronized via an internal RLock using an atomic drain-and-persist
    pattern so slow database operations never block WebSocket tick ingestion.
    """

    def __init__(self):
        self._lock = threading.RLock()
        # Key: instrument_token -> ActiveBar
        self._active_bars: Dict[int, ActiveBar] = {}
        # Buffer of completed bars ready for database flush
        self._completed_bars: List[ActiveBar] = []
        # Retains model instances from most recent flush for downstream strategy processing
        self.last_flushed_bars: List[OptionOHLCVBar] = []

    @staticmethod
    def align_to_minute(dt: datetime) -> datetime:
        """Truncates datetime to minute boundary (seconds=0, microsecond=0)."""
        return dt.replace(second=0, microsecond=0)

    def on_tick(
        self, 
        tick: OptionTick, 
        contract_meta: Optional[OptionContractMeta] = None
    ) -> Optional[ActiveBar]:
        """
        Processes an incoming OptionTick.
        If a minute boundary has passed for this token, closes the existing bar,
        queues it for flush, and opens a new bar.
        Returns closed bar if a rollover occurred, else None.
        """
        # Determine bar timestamp using exchange timestamp if valid, else received wall clock
        ref_dt = tick.exchange_timestamp_utc if tick.exchange_time_status == "VALID" and tick.exchange_timestamp_utc else tick.received_wall_clock_utc
        bar_ts = self.align_to_minute(ref_dt)
        token = tick.instrument_token

        closed_bar: Optional[ActiveBar] = None

        with self._lock:
            if token in self._active_bars:
                active = self._active_bars[token]
                if bar_ts > active.timestamp:
                    # Close active bar and queue for persistence
                    closed_bar = active
                    self._completed_bars.append(active)
                    # Initialize new bar
                    self._active_bars[token] = self._create_new_bar(tick, contract_meta, bar_ts)
                else:
                    # Update existing bar
                    active.high = max(active.high, tick.last_price)
                    active.low = min(active.low, tick.last_price)
                    active.close = tick.last_price

                    # Volume update with session reset safety
                    if tick.is_session_reset or tick.volume_traded < active.volume_start:
                        active.volume_start = tick.volume_traded
                        active.volume_delta = 0
                    else:
                        active.volume_delta = max(0, tick.volume_traded - active.volume_start)

                    # OI updates
                    if tick.open_interest is not None:
                        active.open_interest = tick.open_interest
                        active.oi_status = tick.oi_status
                    active.ticks_count += 1
            else:
                # First tick for this token
                self._active_bars[token] = self._create_new_bar(tick, contract_meta, bar_ts)

        return closed_bar

    def _create_new_bar(
        self, 
        tick: OptionTick, 
        contract_meta: Optional[OptionContractMeta], 
        bar_ts: datetime
    ) -> ActiveBar:
        """Helper to instantiate an ActiveBar with metadata."""
        tradingsymbol = contract_meta.tradingsymbol if contract_meta else f"OPT_{tick.instrument_token}"
        underlying = "^NSEI"
        opt_type = contract_meta.instrument_type if contract_meta else ("CE" if "CE" in tradingsymbol else "PE")
        strike = contract_meta.strike if contract_meta else Decimal("0.0")
        expiry = contract_meta.expiry if contract_meta else bar_ts.date()

        return ActiveBar(
            instrument_token=tick.instrument_token,
            tradingsymbol=tradingsymbol,
            underlying_symbol=underlying,
            option_type=opt_type,
            strike_price=strike,
            expiry_date=expiry,
            timeframe="1m",
            timestamp=bar_ts,
            open=tick.last_price,
            high=tick.last_price,
            low=tick.last_price,
            close=tick.last_price,
            volume_start=tick.volume_traded,
            volume_delta=0,
            open_interest=tick.open_interest,
            oi_status=tick.oi_status,
            is_partial_bar=False,
            ticks_count=1
        )

    def mark_partial_bars(self) -> None:
        """Flags all currently open active bars as partial (e.g. after a reconnect gap)."""
        with self._lock:
            for bar in self._active_bars.values():
                bar.is_partial_bar = True

    def handle_token_unsubscribed(
        self,
        token: int,
        as_of_datetime: Optional[datetime] = None
    ) -> Optional[ActiveBar]:
        """
        Safely evacuates an in-memory bar for a token that is being unsubscribed.
        Flags it as partial (is_partial_bar = True) and buffers it for persistence.
        If no active bar exists (e.g. no ticks received), returns None without fabricating.
        """
        with self._lock:
            bar = self._active_bars.pop(token, None)
            if bar is not None:
                bar.is_partial_bar = True
                self._completed_bars.append(bar)
            return bar

    def handle_tokens_unsubscribed(
        self,
        tokens: Set[int],
        as_of_datetime: Optional[datetime] = None
    ) -> List[ActiveBar]:
        """
        Safely evacuates accumulated in-memory bars for a collection of unsubscribed tokens.
        Synchronizes the entire state transition atomically under lock.
        """
        evacuated: List[ActiveBar] = []
        with self._lock:
            for token in tokens:
                bar = self._active_bars.pop(token, None)
                if bar is not None:
                    bar.is_partial_bar = True
                    self._completed_bars.append(bar)
                    evacuated.append(bar)
        return evacuated

    def drain_completed_bars(self, as_of_datetime: Optional[datetime] = None) -> List[ActiveBar]:
        """
        Atomically extracts completed bars under lock without holding the lock during DB writes.
        """
        with self._lock:
            if as_of_datetime is not None:
                cutoff_minute = self.align_to_minute(as_of_datetime)
                tokens_to_close = [
                    token for token, bar in self._active_bars.items()
                    if bar.timestamp < cutoff_minute
                ]
                for token in tokens_to_close:
                    self._completed_bars.append(self._active_bars.pop(token))

                bars_to_flush = [b for b in self._completed_bars if b.timestamp <= as_of_datetime]
                self._completed_bars = [b for b in self._completed_bars if b.timestamp > as_of_datetime]
            else:
                bars_to_flush = list(self._completed_bars)
                self._completed_bars.clear()
            return bars_to_flush

    def flush_completed_bars(self, as_of_datetime: Optional[datetime] = None) -> int:
        """
        Persists completed bars to the database idempotently using bulk_create
        with update_conflicts=True on (instrument_token, timeframe, timestamp).

        Extracts bars via drain_completed_bars() under lock, then performs database
        I/O outside the lock to prevent blocking WebSocket tick ingestion.

        Returns the number of bars written.
        """
        bars_to_flush = self.drain_completed_bars(as_of_datetime=as_of_datetime)
        if not bars_to_flush:
            self.last_flushed_bars = []
            return 0

        model_instances = [
            OptionOHLCVBar(
                instrument_token=b.instrument_token,
                tradingsymbol=b.tradingsymbol,
                underlying_symbol=b.underlying_symbol,
                option_type=b.option_type,
                strike_price=b.strike_price,
                expiry_date=b.expiry_date,
                timeframe=b.timeframe,
                timestamp=b.timestamp,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume_delta,
                open_interest=b.open_interest,
                oi_status=b.oi_status,
                is_partial_bar=b.is_partial_bar,
            )
            for b in bars_to_flush
        ]

        with transaction.atomic():
            OptionOHLCVBar.objects.bulk_create(
                model_instances,
                update_conflicts=True,
                unique_fields=['instrument_token', 'timeframe', 'timestamp'],
                update_fields=[
                    'open', 'high', 'low', 'close', 
                    'volume', 'open_interest', 'oi_status', 'is_partial_bar'
                ]
            )

        logger.info(f"Persisted {len(model_instances)} completed OptionOHLCVBar records.")
        self.last_flushed_bars = model_instances
        return len(model_instances)

    def force_close_and_flush_all(self) -> int:
        """Closes all in-flight bars, marks them partial, and flushes everything to DB."""
        with self._lock:
            for bar in self._active_bars.values():
                bar.is_partial_bar = True
                self._completed_bars.append(bar)
            self._active_bars.clear()
        return self.flush_completed_bars()
