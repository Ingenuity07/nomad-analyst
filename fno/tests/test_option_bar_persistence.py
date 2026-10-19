"""
Unit Tests for AC-1-U04: OptionBarAggregator & Idempotent Persistence.
Verifies 1-minute candle rollup, volume deltas, and unique constraint idempotency in OptionOHLCVBar.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from fno.models import OptionOHLCVBar
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionTick
from fno.services.option_registry import OptionContractMeta


def make_test_tick(
    token=12067586,
    price=Decimal("150.00"),
    volume_traded=1000,
    oi=50000,
    exchange_ts=None,
    arrival_ts=None,
    is_reset=False,
) -> OptionTick:
    """Helper to generate a lightweight OptionTick."""
    arrival = arrival_ts or datetime(2026, 10, 15, 9, 15, 10, tzinfo=timezone.utc)
    exch = exchange_ts or arrival
    return OptionTick(
        instrument_token=token,
        last_price=price,
        last_quantity=25,
        average_price=price,
        volume_traded=volume_traded,
        buy_quantity=100,
        sell_quantity=100,
        open=price,
        high=price,
        low=price,
        close=price,
        last_trade_timestamp_utc=exch,
        open_interest=oi,
        oi_day_high=oi,
        oi_day_low=oi,
        oi_status="VALID" if oi else "ZERO_ACTIVITY",
        exchange_timestamp_utc=exch,
        received_wall_clock_utc=arrival,
        received_monotonic_ns=0,
        exchange_time_status="VALID",
        feed_latency_ms=0,
        quote_age_seconds=Decimal("0.0"),
        last_trade_age_seconds=Decimal("0.0"),
        pipeline_latency_ms=Decimal("0.1"),
        best_bid=price - Decimal("0.10"),
        best_ask=price + Decimal("0.10"),
        bid_quantity_l1=50,
        ask_quantity_l1=50,
        depth={"buy": [], "sell": []},
        quote_status="VALID",
        is_execution_eligible=True,
        is_session_reset=is_reset,
    )


class TestOptionBarPersistence(TestCase):
    """Test suite for OptionBarAggregator meeting AC-1-U04."""

    def setUp(self):
        self.aggregator = OptionBarAggregator()
        self.meta = OptionContractMeta(
            instrument_token=12067586,
            exchange_token=47139,
            tradingsymbol="NIFTY26O1524500CE",
            name="NIFTY",
            expiry=date(2026, 10, 15),
            strike=Decimal("24500.00"),
            tick_size=Decimal("0.05"),
            lot_size=25,
            instrument_type="CE",
            segment="NFO-OPT",
            exchange="NFO",
        )

    def test_single_minute_aggregation_and_flush(self):
        """Ticks in the same minute must accumulate open, high, low, close, and volume delta."""
        # Minute 09:15:00 - Tick 1 (open)
        t1 = make_test_tick(
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 5, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta)

        # Tick 2 (high)
        t2 = make_test_tick(
            price=Decimal("110.00"),
            volume_traded=700,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 20, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t2, self.meta)

        # Tick 3 (low & close)
        t3 = make_test_tick(
            price=Decimal("95.00"),
            volume_traded=1000,
            oi=55000,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 50, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t3, self.meta)

        # Minute 09:16:00 - Tick 4 (triggers rollover of 09:15 bar)
        t4 = make_test_tick(
            price=Decimal("98.00"),
            volume_traded=1200,
            arrival_ts=datetime(2026, 10, 15, 9, 16, 2, tzinfo=timezone.utc),
        )
        closed_bar = self.aggregator.on_tick(t4, self.meta)
        self.assertIsNotNone(closed_bar)
        self.assertEqual(closed_bar.open, Decimal("100.00"))
        self.assertEqual(closed_bar.high, Decimal("110.00"))
        self.assertEqual(closed_bar.low, Decimal("95.00"))
        self.assertEqual(closed_bar.close, Decimal("95.00"))
        self.assertEqual(closed_bar.volume_delta, 500) # 1000 - 500
        self.assertEqual(closed_bar.open_interest, 55000)

        # Flush to database
        flushed_count = self.aggregator.flush_completed_bars()
        self.assertEqual(flushed_count, 1)

        # Query database record
        bar_row = OptionOHLCVBar.objects.get(
            instrument_token=12067586,
            timeframe="1m",
            timestamp=datetime(2026, 10, 15, 9, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(bar_row.tradingsymbol, "NIFTY26O1524500CE")
        self.assertEqual(bar_row.open, Decimal("100.00"))
        self.assertEqual(bar_row.high, Decimal("110.00"))
        self.assertEqual(bar_row.low, Decimal("95.00"))
        self.assertEqual(bar_row.close, Decimal("95.00"))
        self.assertEqual(bar_row.volume, 500)
        self.assertEqual(bar_row.open_interest, 55000)
        self.assertEqual(bar_row.oi_status, "VALID")

    def test_idempotence_and_zero_duplicate_rows(self):
        """Flushing identical or updated bars must update existing rows without creating duplicates."""
        # 1. Ingest and flush minute 09:15:00 bar
        t1 = make_test_tick(
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 5, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta)

        t_next = make_test_tick(
            price=Decimal("105.00"),
            volume_traded=800,
            arrival_ts=datetime(2026, 10, 15, 9, 16, 5, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t_next, self.meta)
        self.aggregator.flush_completed_bars()

        initial_count = OptionOHLCVBar.objects.filter(instrument_token=12067586).count()
        self.assertEqual(initial_count, 1)

        # 2. Simulate re-running aggregation or reprocessing the same minute with an updated high
        # We manually re-flush the same minute
        aggregator2 = OptionBarAggregator()
        t1_replay = make_test_tick(
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 5, tzinfo=timezone.utc),
        )
        aggregator2.on_tick(t1_replay, self.meta)
        # Higher tick in same minute
        t2_replay = make_test_tick(
            price=Decimal("120.00"), # New higher high
            volume_traded=900,
            arrival_ts=datetime(2026, 10, 15, 9, 15, 55, tzinfo=timezone.utc),
        )
        aggregator2.on_tick(t2_replay, self.meta)
        # Next minute tick to close
        aggregator2.on_tick(t_next, self.meta)
        aggregator2.flush_completed_bars()

        # Row count must STILL be 1 (strictly zero duplicates)
        final_count = OptionOHLCVBar.objects.filter(instrument_token=12067586).count()
        self.assertEqual(final_count, 1)

        # Record must reflect updated values
        updated_bar = OptionOHLCVBar.objects.get(
            instrument_token=12067586,
            timeframe="1m",
            timestamp=datetime(2026, 10, 15, 9, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(updated_bar.high, Decimal("120.00"))
        self.assertEqual(updated_bar.volume, 400) # 900 - 500
