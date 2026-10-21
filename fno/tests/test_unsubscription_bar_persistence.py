"""
fno/tests/test_unsubscription_bar_persistence.py — Unit Tests for Mid-Minute Option Unsubscription Bar Persistence.

Verifies:
1. Token receives ticks and is unsubscribed mid-minute: accumulated data is persisted as a partial bar.
2. Token has no accumulated ticks: no empty or fabricated bar is created.
3. Token is unsubscribed exactly at a minute boundary: no duplicate bar.
4. Normal minute-boundary flush still works.
5. Repeated unsubscribe/reconciliation events do not duplicate persistence.
6. OI zero and missing OI remain distinguishable.
7. Reconciliation and subsequent resubscription do not corrupt bar state.
8. Concurrent tick handling, unsubscription, and flushing preserve data consistency under lock.
9. Integration with FnoTickerConsumer dynamic rebalancing.
10. Equity ingestion and equity state management remain unaffected.
"""

import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TransactionTestCase

from fno.models import OptionOHLCVBar
from fno.services.desired_universe import CONFIG_NIFTY, DesiredUniverseManager
from fno.services.fno_ticker_consumer import FnoTickerConsumer
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionTick
from fno.services.option_registry import OptionContractMeta, OptionInstrumentRegistry
from market.models import OHLCVBar, StockIntradayContext


def make_test_tick(
    token=13143042,
    price=Decimal("150.00"),
    volume_traded=1000,
    oi=50000,
    exchange_ts=None,
    arrival_ts=None,
    is_reset=False,
    tradingsymbol="NIFTY26OCT22700CE",
) -> OptionTick:
    """Helper to generate a lightweight OptionTick."""
    arrival = arrival_ts or datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc)
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
        oi_day_high=oi if oi is not None else None,
        oi_day_low=oi if oi is not None else None,
        oi_status="VALID" if oi is not None else "MISSING",
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


class TestOptionUnsubscriptionBarPersistence(TransactionTestCase):
    """Test suite covering option bar evacuation upon unsubscription."""

    def setUp(self):
        OptionOHLCVBar.objects.all().delete()
        self.meta_ce = OptionContractMeta(
            instrument_token=13143042,
            exchange_token=51340,
            tradingsymbol="NIFTY26OCT22700CE",
            name="NIFTY",
            expiry=date(2026, 10, 21),
            strike=Decimal("22700.00"),
            tick_size=Decimal("0.05"),
            lot_size=25,
            instrument_type="CE",
            segment="NFO-OPT",
            exchange="NFO",
        )
        self.meta_pe = OptionContractMeta(
            instrument_token=13143298,
            exchange_token=51341,
            tradingsymbol="NIFTY26OCT22700PE",
            name="NIFTY",
            expiry=date(2026, 10, 21),
            strike=Decimal("22700.00"),
            tick_size=Decimal("0.05"),
            lot_size=25,
            instrument_type="PE",
            segment="NFO-OPT",
            exchange="NFO",
        )
        self.aggregator = OptionBarAggregator()

    def tearDown(self):
        OptionOHLCVBar.objects.all().delete()

    def test_mid_minute_unsubscribe_persists_partial_bar(self):
        """1. Token receives ticks and is unsubscribed mid-minute: accumulated data is persisted as a partial bar."""
        token = 13143042
        # Ingest 3 ticks in minute 10:41:00
        t1 = make_test_tick(
            token=token,
            price=Decimal("120.00"),
            volume_traded=500,
            oi=40000,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 5, tzinfo=timezone.utc),
        )
        t2 = make_test_tick(
            token=token,
            price=Decimal("125.00"),
            volume_traded=700,
            oi=41000,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc),
        )
        t3 = make_test_tick(
            token=token,
            price=Decimal("118.00"),
            volume_traded=950,
            oi=42000,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 14, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)
        self.aggregator.on_tick(t2, self.meta_ce)
        self.aggregator.on_tick(t3, self.meta_ce)

        # Token is unsubscribed at 10:41:15
        unsub_dt = datetime(2026, 10, 21, 10, 41, 15, tzinfo=timezone.utc)
        evacuated = self.aggregator.handle_tokens_unsubscribed({token}, as_of_datetime=unsub_dt)
        self.assertEqual(len(evacuated), 1)
        bar = evacuated[0]
        self.assertTrue(bar.is_partial_bar)
        self.assertEqual(bar.open, Decimal("120.00"))
        self.assertEqual(bar.high, Decimal("125.00"))
        self.assertEqual(bar.low, Decimal("118.00"))
        self.assertEqual(bar.close, Decimal("118.00"))
        self.assertEqual(bar.volume_delta, 450)  # 950 - 500
        self.assertEqual(bar.open_interest, 42000)
        self.assertEqual(bar.ticks_count, 3)

        # Flush to DB
        flushed = self.aggregator.flush_completed_bars()
        self.assertEqual(flushed, 1)

        db_bar = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timeframe="1m",
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(db_bar.is_partial_bar)
        self.assertEqual(db_bar.open, Decimal("120.00"))
        self.assertEqual(db_bar.high, Decimal("125.00"))
        self.assertEqual(db_bar.low, Decimal("118.00"))
        self.assertEqual(db_bar.close, Decimal("118.00"))
        self.assertEqual(db_bar.volume, 450)
        self.assertEqual(db_bar.open_interest, 42000)

    def test_unsubscribe_with_no_accumulated_ticks_creates_no_bar(self):
        """2. Token has no accumulated ticks: no empty or fabricated bar is created."""
        token = 13143042
        evacuated = self.aggregator.handle_tokens_unsubscribed({token})
        self.assertEqual(len(evacuated), 0)

        flushed = self.aggregator.flush_completed_bars()
        self.assertEqual(flushed, 0)
        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 0)

    def test_minute_boundary_unsubscribe_no_duplicate(self):
        """3. Token is unsubscribed exactly at a minute boundary: no duplicate bar."""
        token = 13143042
        # Tick in minute 10:40
        t1 = make_test_tick(
            token=token,
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 21, 10, 40, 30, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)

        # Minute boundary rollover triggered by flush with as_of_datetime=10:41:00
        boundary_dt = datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc)
        self.aggregator.flush_completed_bars(as_of_datetime=boundary_dt)

        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

        # Now token is unsubscribed at 10:41:00
        evacuated = self.aggregator.handle_tokens_unsubscribed({token}, as_of_datetime=boundary_dt)
        self.assertEqual(len(evacuated), 0)  # No active bar in 10:41 to evacuate

        self.aggregator.flush_completed_bars()
        # Row count must still be exactly 1
        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

    def test_normal_minute_boundary_flush_unaffected(self):
        """4. Normal minute-boundary flush still works for active contracts."""
        token = 13143042
        t1 = make_test_tick(
            token=token,
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 21, 10, 40, 10, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)

        # Rollover with next minute tick
        t2 = make_test_tick(
            token=token,
            price=Decimal("105.00"),
            volume_traded=800,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 5, tzinfo=timezone.utc),
        )
        closed = self.aggregator.on_tick(t2, self.meta_ce)
        self.assertIsNotNone(closed)
        self.assertFalse(closed.is_partial_bar)

        flushed = self.aggregator.flush_completed_bars()
        self.assertEqual(flushed, 1)

        db_bar = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timeframe="1m",
            timestamp=datetime(2026, 10, 21, 10, 40, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(db_bar.is_partial_bar)
        self.assertEqual(db_bar.close, Decimal("100.00"))

    def test_repeated_reconciliation_idempotence(self):
        """5. Repeated unsubscribe/reconciliation events do not duplicate persistence."""
        token = 13143042
        t1 = make_test_tick(
            token=token,
            price=Decimal("110.00"),
            volume_traded=300,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)

        # First unsubscribe
        self.aggregator.handle_tokens_unsubscribed({token})
        self.aggregator.flush_completed_bars()
        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

        # Repeated unsubscribe for the same token
        evacuated2 = self.aggregator.handle_tokens_unsubscribed({token})
        self.assertEqual(len(evacuated2), 0)
        self.aggregator.flush_completed_bars()

        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

    def test_oi_zero_and_missing_oi_distinguishable(self):
        """6. OI zero and missing OI remain distinguishable on partial bars."""
        token_zero = 13143042
        token_missing = 13143298

        t_zero = make_test_tick(
            token=token_zero,
            oi=0,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 5, tzinfo=timezone.utc),
        )
        t_missing = make_test_tick(
            token=token_missing,
            oi=None,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 5, tzinfo=timezone.utc),
        )

        self.aggregator.on_tick(t_zero, self.meta_ce)
        self.aggregator.on_tick(t_missing, self.meta_pe)

        self.aggregator.handle_tokens_unsubscribed({token_zero, token_missing})
        self.aggregator.flush_completed_bars()

        bar_zero = OptionOHLCVBar.objects.get(
            instrument_token=token_zero,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        bar_missing = OptionOHLCVBar.objects.get(
            instrument_token=token_missing,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(bar_zero.open_interest, 0)
        self.assertEqual(bar_zero.oi_status, "VALID")

        self.assertIsNone(bar_missing.open_interest)
        self.assertEqual(bar_missing.oi_status, "MISSING")

    def test_resubscription_after_unsubscribe_clean_state(self):
        """7. Reconciliation and subsequent resubscription do not corrupt bar state."""
        token = 13143042
        # Tick in 10:41
        t1 = make_test_tick(
            token=token,
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)
        self.aggregator.handle_tokens_unsubscribed({token})
        self.aggregator.flush_completed_bars()

        bar_41 = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(bar_41.is_partial_bar)
        self.assertEqual(bar_41.volume, 0)

        # Resubscribed in 10:42 with higher volume traded
        t2 = make_test_tick(
            token=token,
            price=Decimal("105.00"),
            volume_traded=800,
            arrival_ts=datetime(2026, 10, 21, 10, 42, 10, tzinfo=timezone.utc),
        )
        t3 = make_test_tick(
            token=token,
            price=Decimal("110.00"),
            volume_traded=950,
            arrival_ts=datetime(2026, 10, 21, 10, 42, 40, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t2, self.meta_ce)
        self.aggregator.on_tick(t3, self.meta_ce)

        # Rollover to 10:43
        t4 = make_test_tick(
            token=token,
            price=Decimal("112.00"),
            volume_traded=1100,
            arrival_ts=datetime(2026, 10, 21, 10, 43, 5, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t4, self.meta_ce)
        self.aggregator.flush_completed_bars()

        bar_42 = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 42, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(bar_42.is_partial_bar)
        self.assertEqual(bar_42.open, Decimal("105.00"))
        self.assertEqual(bar_42.close, Decimal("110.00"))
        self.assertEqual(bar_42.volume, 150)  # 950 - 800

    def test_concurrent_tick_handling_and_unsubscribe(self):
        """8. Concurrent tick handling, unsubscription, and flushing preserve data consistency under lock."""
        token = 99999991
        meta = OptionContractMeta(
            instrument_token=token,
            exchange_token=99999,
            tradingsymbol="NIFTY26OCT22800CE",
            name="NIFTY",
            expiry=date(2026, 10, 21),
            strike=Decimal("22800.00"),
            tick_size=Decimal("0.05"),
            lot_size=25,
            instrument_type="CE",
            segment="NFO-OPT",
            exchange="NFO",
        )
        errors = []

        def tick_worker():
            try:
                for i in range(50):
                    t = make_test_tick(
                        token=token,
                        price=Decimal(f"{100 + (i % 10)}.00"),
                        volume_traded=1000 + i * 10,
                        arrival_ts=datetime(2026, 10, 21, 10, 41, i % 60, tzinfo=timezone.utc),
                    )
                    self.aggregator.on_tick(t, meta)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def unsub_worker():
            try:
                time.sleep(0.02)
                self.aggregator.handle_tokens_unsubscribed({token})
            except Exception as e:
                errors.append(e)

        def flush_worker():
            try:
                for _ in range(5):
                    self.aggregator.flush_completed_bars()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=tick_worker),
            threading.Thread(target=unsub_worker),
            threading.Thread(target=flush_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # Final flush
        self.aggregator.flush_completed_bars()
        self.assertGreaterEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

    def test_dynamic_rebalance_integration_in_fno_consumer(self):
        """9. Integration: FnoTickerConsumer.on_underlying_spot_update evacuates partial bars for unsubscribed tokens."""
        mock_registry = MagicMock(spec=OptionInstrumentRegistry)
        mock_registry._loaded_at = datetime.now(timezone.utc)
        mock_registry.get_by_token.return_value = self.meta_ce

        universe_mgr = DesiredUniverseManager(mock_registry, CONFIG_NIFTY)
        consumer = FnoTickerConsumer(
            registry=mock_registry,
            universe_manager=universe_mgr,
            bar_aggregator=self.aggregator,
            config=CONFIG_NIFTY,
        )

        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"

        # Initialize at 22700 (ATM = 22700)
        universe_mgr.calculate_desired_tokens = MagicMock(return_value={13143042, 13143298})
        consumer.on_connect(mock_ws)

        # Feed ticks to token 13143042
        t1 = make_test_tick(
            token=13143042,
            price=Decimal("150.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc),
        )
        consumer.on_tick(t1)

        # Now spot moves and universe manager decides to unsubscribe 13143042
        universe_mgr.should_rebalance = MagicMock(return_value=True)
        universe_mgr.reconcile = MagicMock(return_value=({99999999}, {13143042}))

        rebal_time = datetime(2026, 10, 21, 10, 41, 25, tzinfo=timezone.utc)
        to_sub, to_unsub = consumer.on_underlying_spot_update(
            spot_price=Decimal("22900.0"),
            ws=mock_ws,
            as_of_datetime=rebal_time,
        )

        self.assertIn(13143042, to_unsub)
        mock_ws.unsubscribe.assert_called_once_with([13143042])

        # Verify bar for 13143042 was immediately persisted to PostgreSQL as a partial bar!
        db_bar = OptionOHLCVBar.objects.get(
            instrument_token=13143042,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(db_bar.is_partial_bar)
        self.assertEqual(db_bar.open, Decimal("150.00"))

    def test_equity_isolation_integrity(self):
        """10. Equity ingestion and market_ohlcvbar remain 100% unaffected by option bar unsubscription."""
        token = 13143042
        t1 = make_test_tick(token=token)
        self.aggregator.on_tick(t1, self.meta_ce)
        self.aggregator.handle_tokens_unsubscribed({token})
        self.aggregator.flush_completed_bars()

        # Zero equity bar pollution
        self.assertEqual(OHLCVBar.objects.filter(instrument__symbol="NIFTY26OCT22700CE").count(), 0)
        self.assertEqual(StockIntradayContext.objects.filter(instrument__symbol="NIFTY26OCT22700CE").count(), 0)

    def test_active_bar_disconnect_and_shutdown_without_post_gap_tick(self):
        """11. Active bar + disconnect + shutdown before another tick: must persist as partial bar."""
        token = 13143042
        # Tick in minute 10:41
        t1 = make_test_tick(
            token=token,
            price=Decimal("155.00"),
            volume_traded=600,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 15, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)

        # Disconnect occurs: marks active bars as partial in memory
        self.aggregator.mark_partial_bars()

        # CRITICAL: No tick in minute 10:42 ever arrives (connection stays down)
        # Process shuts down gracefully
        flushed = self.aggregator.force_close_and_flush_all()
        self.assertEqual(flushed, 1)

        db_bar = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(db_bar.is_partial_bar, "Bar interrupted by disconnect must be persisted as partial on shutdown")
        self.assertEqual(db_bar.open, Decimal("155.00"))
        self.assertEqual(db_bar.close, Decimal("155.00"))
        self.assertEqual(db_bar.volume, 0)

    def test_active_bar_ordinary_graceful_shutdown(self):
        """12. Active bar + ordinary graceful shutdown: in-flight bar truncated by shutdown persisted as partial."""
        token = 13143042
        t1 = make_test_tick(
            token=token,
            price=Decimal("200.00"),
            volume_traded=1000,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 20, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)

        # Normal shutdown at 10:41:40 before minute rollover
        flushed = self.aggregator.force_close_and_flush_all()
        self.assertEqual(flushed, 1)

        db_bar = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(db_bar.is_partial_bar, "In-flight bar truncated early by shutdown must be flagged partial")
        self.assertEqual(db_bar.open, Decimal("200.00"))

    def test_completed_and_active_bars_present_simultaneously_on_shutdown(self):
        """13. Completed bar and active bar present simultaneously: complete bar is NEVER downgraded to partial."""
        token = 13143042
        # Minute 10:40: full minute observed
        t1 = make_test_tick(
            token=token,
            price=Decimal("100.00"),
            volume_traded=500,
            arrival_ts=datetime(2026, 10, 21, 10, 40, 5, tzinfo=timezone.utc),
        )
        t2 = make_test_tick(
            token=token,
            price=Decimal("110.00"),
            volume_traded=800,
            arrival_ts=datetime(2026, 10, 21, 10, 40, 55, tzinfo=timezone.utc),
        )
        self.aggregator.on_tick(t1, self.meta_ce)
        self.aggregator.on_tick(t2, self.meta_ce)

        # Minute 10:41 rollover tick: moves 10:40 bar to _completed_bars (is_partial_bar=False)
        t3 = make_test_tick(
            token=token,
            price=Decimal("115.00"),
            volume_traded=1000,
            arrival_ts=datetime(2026, 10, 21, 10, 41, 10, tzinfo=timezone.utc),
        )
        closed = self.aggregator.on_tick(t3, self.meta_ce)
        self.assertIsNotNone(closed)
        self.assertFalse(closed.is_partial_bar)

        # At this moment: _completed_bars has 10:40 (complete), _active_bars has 10:41 (active)
        # Shutdown occurs before regular periodic snapshot flush
        flushed = self.aggregator.force_close_and_flush_all()
        self.assertEqual(flushed, 2)

        bar_1040 = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 40, 0, tzinfo=timezone.utc),
        )
        bar_1041 = OptionOHLCVBar.objects.get(
            instrument_token=token,
            timestamp=datetime(2026, 10, 21, 10, 41, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(bar_1040.is_partial_bar, "Completed bar must NEVER be downgraded to partial")
        self.assertEqual(bar_1040.volume, 300)

        self.assertTrue(bar_1041.is_partial_bar, "Active bar truncated by shutdown must be marked partial")
        self.assertEqual(bar_1041.volume, 0)

        # Strictly 2 distinct rows
        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 2)

    def test_repeated_shutdown_flush_is_idempotent(self):
        """14. Repeated force_close_and_flush_all calls must be strictly idempotent."""
        token = 13143042
        t1 = make_test_tick(token=token)
        self.aggregator.on_tick(t1, self.meta_ce)

        first_flush = self.aggregator.force_close_and_flush_all()
        self.assertEqual(first_flush, 1)

        second_flush = self.aggregator.force_close_and_flush_all()
        self.assertEqual(second_flush, 0)

        self.assertEqual(OptionOHLCVBar.objects.filter(instrument_token=token).count(), 1)

    def test_shutdown_with_no_active_bars_is_safe(self):
        """15. Shutdown with no active bars is safe and performs zero writes."""
        flushed = self.aggregator.force_close_and_flush_all()
        self.assertEqual(flushed, 0)
        self.assertEqual(OptionOHLCVBar.objects.count(), 0)
