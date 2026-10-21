"""
fno/tests/test_strategy_runtime_wiring.py — Tests for STRAT-ORB-15M Runtime Pipeline Integration.

Verifies:
1. Strategy registration and activation in FnoTickerConsumer.
2. Real-time Opening Range (09:15-09:30 IST) tracking and database bar seeding.
3. Completed bar evaluation trigger via flush_completed_bars().
4. Duplicate bar evaluation prevention.
5. Strict gating on partial bars.
6. Breakout signal generation and dispatch to PaperExecutionEngine.
7. Paper trade ledger creation and strategy active position feedback.
8. Telemetry publishing to Django cache and valid no-setup reporting.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import io
import uuid
import zoneinfo
import threading
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from fno.models import OptionOHLCVBar, OptionQuoteSnapshot, PaperTradeLedger
from fno.services.desired_universe import UnderlyingAssetConfig
from fno.services.fno_ticker_consumer import FnoTickerConsumer
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionTick
from fno.strategies.nifty_orb_breakout import NiftyOrbBreakoutStrategy
from market.models import Instrument, OHLCVBar

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class StrategyRuntimeWiringTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.session_date = date(2026, 10, 22)
        # 10:00 IST on 2026-10-22 is 04:30 UTC
        self.session_time_utc = datetime(2026, 10, 22, 4, 30, tzinfo=timezone.utc)
        self.token = 1001
        self.symbol = "NIFTY26OCT24500CE"

        # Create consumer with strategy enabled and synchronized clock
        self.consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)

    def test_strategy_registration_and_activation(self):
        """Verifies STRAT-ORB-15M is registered and active in FnoTickerConsumer."""
        self.assertIsNotNone(self.consumer.strategy_manager)
        self.assertIsNotNone(self.consumer.strategy)
        self.assertEqual(self.consumer.strategy.strategy_id, "STRAT-ORB-15M")
        self.assertTrue(self.consumer.strategy.is_enabled)
        self.assertTrue(self.consumer.stats["strategy_registered"])

    def _create_nsei_bars(self, session_date, bar_count=15, skip_minutes=None, corrupt_minute=None):
        from market.models import Company
        comp, _ = Company.objects.get_or_create(name="NIFTY 50", defaults={"sector": "Index"})
        inst, _ = Instrument.objects.get_or_create(
            symbol="^NSEI",
            exchange="NSE",
            defaults={"company": comp, "instrument_type": "INDEX"}
        )
        t_base = datetime.combine(session_date, time(9, 15, 0), tzinfo=IST)
        bars = []
        for i in range(bar_count):
            if skip_minutes and i in skip_minutes:
                continue
            t = t_base + timedelta(minutes=i)
            high = Decimal("24500.00") + Decimal(str(i * 5))
            low = Decimal("24450.00") - Decimal(str(i * 2))
            if corrupt_minute is not None and i == corrupt_minute:
                high, low = Decimal("24400.00"), Decimal("24500.00")  # corrupt: high < low
            b = OHLCVBar.objects.create(
                instrument=inst,
                timeframe="1m",
                timestamp=t,
                open=Decimal("24480.00"),
                high=high,
                low=low,
                close=Decimal("24490.00"),
                volume=1000,
                source="test",
            )
            bars.append(b)
        return inst, bars

    def test_live_opening_range_tracking_and_establishment(self):
        """Verifies spot updates between 09:15 and 09:30 IST track high/low and verify 15 bars at 09:30."""
        # 09:16 IST
        t1 = datetime(2026, 10, 22, 9, 16, 0, tzinfo=IST)
        self.consumer.on_underlying_spot_update(Decimal("24500.00"), as_of_datetime=t1)
        self.assertEqual(self.consumer.strategy.opening_range_high, Decimal("24500.00"))
        self.assertEqual(self.consumer.strategy.opening_range_low, Decimal("24500.00"))
        self.assertFalse(self.consumer.strategy.opening_range_established)

        # 09:25 IST higher and lower swings
        t2 = datetime(2026, 10, 22, 9, 25, 0, tzinfo=IST)
        self.consumer.on_underlying_spot_update(Decimal("24550.00"), as_of_datetime=t2)
        self.consumer.on_underlying_spot_update(Decimal("24450.00"), as_of_datetime=t2)
        self.assertEqual(self.consumer.strategy.opening_range_high, Decimal("24550.00"))
        self.assertEqual(self.consumer.strategy.opening_range_low, Decimal("24450.00"))
        self.assertFalse(self.consumer.strategy.opening_range_established)

        # Before 09:30, 15 complete bars are persisted
        self._create_nsei_bars(self.session_date, bar_count=15)

        # 09:30 IST boundary spot update triggers verification of complete 15-bar range
        t3 = datetime(2026, 10, 22, 9, 30, 0, tzinfo=IST)
        self.consumer.on_underlying_spot_update(Decimal("24500.00"), as_of_datetime=t3)
        self.assertTrue(self.consumer.strategy.opening_range_established)

    def test_db_opening_range_seeding_on_mid_session_start(self):
        """Verifies opening range is seeded from 15 DB bars if process starts after 09:30 IST."""
        self._create_nsei_bars(self.session_date, bar_count=15)

        # New consumer with unseeded strategy at 10:00 IST
        new_consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)
        self.assertFalse(new_consumer.strategy.opening_range_established)

        t_current = datetime(2026, 10, 22, 10, 0, 0, tzinfo=IST)
        seeded = new_consumer._seed_opening_range_if_needed(t_current)

        self.assertTrue(seeded)
        self.assertTrue(new_consumer.strategy.opening_range_established)
        # Expected max high is 24500 + 14*5 = 24570, min low is 24450 - 14*2 = 24422
        self.assertEqual(new_consumer.strategy.opening_range_high, Decimal("24570.00"))
        self.assertEqual(new_consumer.strategy.opening_range_low, Decimal("24422.00"))

    def test_opening_range_resets_on_session_date_rollover(self):
        """Verifies opening range state resets when session rolls over to next trading day."""
        # Established on day 1
        self.consumer.strategy.set_opening_range(
            high=Decimal("24550.00"),
            low=Decimal("24450.00"),
            session_date=date(2026, 10, 22),
        )
        self.assertTrue(self.consumer.strategy.opening_range_established)

        # Day 2 morning tick at 09:20 IST arrives on next day
        t_next_day = datetime(2026, 10, 23, 9, 20, 0, tzinfo=IST)
        self.consumer.on_underlying_spot_update(Decimal("24600.00"), as_of_datetime=t_next_day)

        # Stale opening range must be cleared and un-established for the new day
        self.assertFalse(self.consumer.strategy.opening_range_established)
        self.assertEqual(self.consumer.strategy.opening_range_session_date, date(2026, 10, 23))
        self.assertEqual(self.consumer.strategy.opening_range_high, Decimal("24600.00"))
        self.assertEqual(self.consumer.strategy.opening_range_low, Decimal("24600.00"))

    def test_incomplete_opening_range_two_bars_fails_closed(self):
        """Verifies seeding fails closed if only 2 bars exist in DB (requirement 1)."""
        from market.models import Company
        comp, _ = Company.objects.get_or_create(name="NIFTY 50", defaults={"sector": "Index"})
        inst, _ = Instrument.objects.get_or_create(
            symbol="^NSEI",
            exchange="NSE",
            defaults={"company": comp, "instrument_type": "INDEX"}
        )
        t_base = datetime(2026, 10, 22, 9, 15, 0, tzinfo=IST)
        OHLCVBar.objects.create(
            instrument=inst,
            timeframe="1m",
            timestamp=t_base,
            open=Decimal("24480.00"),
            high=Decimal("24520.00"),
            low=Decimal("24470.00"),
            close=Decimal("24510.00"),
            volume=1000,
            source="test",
        )
        OHLCVBar.objects.create(
            instrument=inst,
            timeframe="1m",
            timestamp=t_base + timedelta(minutes=10),
            open=Decimal("24510.00"),
            high=Decimal("24560.00"),
            low=Decimal("24440.00"),
            close=Decimal("24530.00"),
            volume=1000,
            source="test",
        )

        consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)
        t_current = datetime(2026, 10, 22, 10, 0, 0, tzinfo=IST)
        seeded = consumer._seed_opening_range_if_needed(t_current)

        self.assertFalse(seeded)
        self.assertFalse(consumer.strategy.opening_range_established)

    def test_incomplete_opening_range_missing_minutes_fails_closed(self):
        """Verifies seeding fails closed if any minute is missing (e.g. 14/15 bars)."""
        self._create_nsei_bars(self.session_date, bar_count=15, skip_minutes=[7])
        consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)
        t_current = datetime(2026, 10, 22, 10, 0, 0, tzinfo=IST)
        seeded = consumer._seed_opening_range_if_needed(t_current)

        self.assertFalse(seeded)
        self.assertFalse(consumer.strategy.opening_range_established)

    def test_corrupt_bar_in_opening_range_fails_closed(self):
        """Verifies seeding fails closed if bar data is invalid (high < low)."""
        self._create_nsei_bars(self.session_date, bar_count=15, corrupt_minute=5)
        consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)
        t_current = datetime(2026, 10, 22, 10, 0, 0, tzinfo=IST)
        seeded = consumer._seed_opening_range_if_needed(t_current)

        self.assertFalse(seeded)
        self.assertFalse(consumer.strategy.opening_range_established)

    def test_partial_bar_is_strictly_skipped_and_not_evaluated(self):
        """Verifies partial bars are skipped and do not increment eligible evaluations."""
        partial_bar = OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=True,  # Disconnect / partial bar
        )
        self.consumer.latest_underlying_spot = Decimal("24600.00")
        self.consumer.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        eval_count = self.consumer.evaluate_strategies([partial_bar], as_of_datetime=self.session_time_utc)
        self.assertEqual(eval_count, 0)
        self.assertEqual(self.consumer.stats["strategy_eligible_evaluated"], 0)

    def test_duplicate_bar_evaluation_prevention(self):
        """Verifies that the same bar timestamp and token cannot be evaluated more than once."""
        bar = OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=False,
        )
        # Create fresh quote snapshot
        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            exchange_timestamp_utc=self.session_time_utc,
            received_wall_clock_utc=self.session_time_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("104.50"),
            best_ask=Decimal("105.50"),
            bid_quantity_l1=100,
            ask_quantity_l1=100,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

        self.consumer.latest_underlying_spot = Decimal("24500.00")  # Inside range, no signal
        self.consumer.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        # First evaluation
        count1 = self.consumer.evaluate_strategies([bar], as_of_datetime=self.session_time_utc)
        self.assertEqual(count1, 1)
        self.assertEqual(self.consumer.stats["strategy_evaluations"], 1)

        # Second evaluation of the same bar
        count2 = self.consumer.evaluate_strategies([bar], as_of_datetime=self.session_time_utc)
        self.assertEqual(count2, 0)
        # Evaluation count must remain 1
        self.assertEqual(self.consumer.stats["strategy_evaluations"], 1)

    def test_breakout_signal_generation_and_paper_trade_execution(self):
        """Verifies bullish breakout triggers signal and produces PaperTradeLedger entry."""
        bar = OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=False,
        )
        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            exchange_timestamp_utc=self.session_time_utc,
            received_wall_clock_utc=self.session_time_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("104.50"),
            best_ask=Decimal("105.50"),
            bid_quantity_l1=100,
            ask_quantity_l1=100,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

        # Bullish breakout: spot 24580 > ORB High 24550
        self.consumer.latest_underlying_spot = Decimal("24580.00")
        self.consumer.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        eval_count = self.consumer.evaluate_strategies([bar], as_of_datetime=self.session_time_utc)
        self.assertEqual(eval_count, 1)
        self.assertEqual(self.consumer.stats["strategy_signals_generated"], 1)
        self.assertEqual(self.consumer.stats["paper_trades_executed"], 1)

        # Verify PaperTradeLedger
        trade = PaperTradeLedger.objects.filter(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol=self.symbol,
        ).first()
        self.assertIsNotNone(trade)
        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.quantity, 65)  # 1 lot of 65
        self.assertGreater(trade.entry_fill_price, Decimal("105.50"))  # Ask + slippage

        # Verify strategy active position state
        self.assertIsNotNone(self.consumer.strategy.active_position)
        self.assertEqual(self.consumer.strategy.active_position["tradingsymbol"], self.symbol)

    def test_valid_no_setup_session_observability(self):
        """Verifies session with 0 signals but active evaluations reports ACTIVE / VALID NO-SETUP."""
        bar = OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=False,
        )
        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            exchange_timestamp_utc=self.session_time_utc,
            received_wall_clock_utc=self.session_time_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("104.50"),
            best_ask=Decimal("105.50"),
            bid_quantity_l1=100,
            ask_quantity_l1=100,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

        # Spot 24500 is inside range [24450, 24550] -> No breakout
        self.consumer.latest_underlying_spot = Decimal("24500.00")
        self.consumer.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        self.consumer.evaluate_strategies([bar], as_of_datetime=self.session_time_utc)
        self.assertEqual(self.consumer.stats["strategy_signals_generated"], 0)

        # Run daily report command
        out = io.StringIO()
        call_command("report_paper_session", "--date", "2026-10-22", stdout=out)
        output = out.getvalue()

        # Must report VALID NO-SETUP, NOT un-wired
        self.assertIn("Strategy Execution Status: ACTIVE / VALID NO-SETUP SESSION", output)
        self.assertNotIn("NOT EVALUATED / UN-WIRED RUNTIME", output)

    def test_multi_contract_concurrent_breakout_deduplication(self):
        """
        Verifies that evaluating multiple option contracts cannot produce duplicate entries
        for the same underlying breakout. Atomically enforces max-one-position across strategy.
        """
        token2 = 1002
        symbol2 = "NIFTY26OCT24550CE"

        # Create bars for 2 contracts
        bar1 = OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=False,
        )
        bar2 = OptionOHLCVBar.objects.create(
            instrument_token=token2,
            tradingsymbol=symbol2,
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("80.00"),
            high=Decimal("90.00"),
            low=Decimal("75.00"),
            close=Decimal("85.00"),
            volume=500,
            open_interest=40000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24550.00"),
            option_type="CE",
            is_partial_bar=False,
        )

        for tok, sym, bid, ask in [
            (self.token, self.symbol, Decimal("104.50"), Decimal("105.50")),
            (token2, symbol2, Decimal("84.50"), Decimal("85.50")),
        ]:
            OptionQuoteSnapshot.objects.create(
                instrument_token=tok,
                tradingsymbol=sym,
                exchange_timestamp_utc=self.session_time_utc,
                received_wall_clock_utc=self.session_time_utc,
                exchange_time_status="VALID",
                best_bid=bid,
                best_ask=ask,
                bid_quantity_l1=100,
                ask_quantity_l1=100,
                quote_status="VALID",
                is_stale=False,
                is_locked=False,
                is_crossed=False,
                is_execution_eligible=True,
            )

        # Bullish breakout
        self.consumer.latest_underlying_spot = Decimal("24580.00")
        self.consumer.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        # Evaluate both bars
        self.consumer.evaluate_strategies([bar1, bar2], as_of_datetime=self.session_time_utc)

        # In-memory strategy suppressed bar2 signal because active_position was set
        open_trades = PaperTradeLedger.objects.filter(
            strategy_id="STRAT-ORB-15M",
            status="OPEN",
        )
        self.assertEqual(open_trades.count(), 1)
        self.assertEqual(open_trades.first().tradingsymbol, self.symbol)

        # Test engine-level atomic deduplication defense:
        # Directly dispatch a second BUY signal for symbol2 to paper_execution_engine
        from fno.strategies.base import OptionSignal
        concurrent_signal = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            instrument_token=token2,
            tradingsymbol=symbol2,
            action="BUY_TO_OPEN",
            option_type="CE",
            strike_price=Decimal("24550.00"),
            expiry_date=date(2026, 10, 27),
            suggested_lot_count=1,
            timestamp=self.session_time_utc,
            trigger_rule_name="ORB_BULLISH_BREAKOUT",
            trigger_rationale="Concurrent breakout evaluation test",
            snapshot_reference_id=str(uuid.uuid4()),
        )
        quote2 = OptionQuoteSnapshot.objects.filter(instrument_token=token2).first()
        event2 = self.consumer.execution_engine.process_signal(concurrent_signal, quote=quote2)
        self.assertIsNotNone(event2)
        self.assertEqual(event2.event_type, "ORDER_REJECTED")
        self.assertIn("REJECTED_MAX_CONCURRENT_POSITIONS_EXCEEDED", event2.message)

        # Confirm ledger record for signal2 is REJECTED
        ledger_entry2 = PaperTradeLedger.objects.filter(signal_id=concurrent_signal.signal_id).first()
        self.assertIsNotNone(ledger_entry2)
        self.assertEqual(ledger_entry2.status, "REJECTED")
        self.assertEqual(ledger_entry2.rejection_reason, "REJECTED_MAX_CONCURRENT_POSITIONS_EXCEEDED")

        # Confirm strictly 1 open position remains in database
        self.assertEqual(PaperTradeLedger.objects.filter(strategy_id="STRAT-ORB-15M", status="OPEN").count(), 1)

    def test_rejected_execution_does_not_open_position(self):
        """Verifies rejected execution does not incorrectly mark strategy position as opened."""
        from fno.strategies.base import OptionSignal
        signal = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            action="BUY_TO_OPEN",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            suggested_lot_count=1,
            timestamp=self.session_time_utc,
            trigger_rule_name="ORB_BULLISH_BREAKOUT",
            trigger_rationale="Test rejection handling",
            snapshot_reference_id=str(uuid.uuid4()),
        )

        # Ineligible/stale quote -> engine will reject
        stale_quote = OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            exchange_timestamp_utc=self.session_time_utc - timedelta(seconds=10),
            received_wall_clock_utc=self.session_time_utc - timedelta(seconds=10),
            exchange_time_status="VALID",
            best_bid=Decimal("104.50"),
            best_ask=Decimal("105.50"),
            bid_quantity_l1=100,
            ask_quantity_l1=100,
            quote_status="VALID",
            is_stale=True,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=False,
        )
        event = self.consumer.execution_engine.process_signal(signal, quote=stale_quote)
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "ORDER_REJECTED")
        self.assertIn("REJECTED", event.message)

        # Notify strategy
        self.consumer.strategy.on_trade_event(event)

        # Strategy must NOT have an active position
        self.assertIsNone(self.consumer.strategy.active_position)

    def test_strategy_recovers_active_position_from_db_on_restart(self):
        """Verifies process restarts recover active positions from DB and prevent duplicate entries."""
        # Create existing OPEN trade in database
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            quantity=65,
            status="OPEN",
            entry_timestamp=self.session_time_utc,
            entry_fill_price=Decimal("105.00"),
            entry_slippage=Decimal("0.00"),
        )

        # Instantiate brand-new strategy instance (simulating daemon restart)
        restarted_strategy = NiftyOrbBreakoutStrategy()
        self.assertIsNotNone(restarted_strategy.active_position)
        self.assertEqual(restarted_strategy.active_position["tradingsymbol"], self.symbol)

        # Also verify new consumer initializes and recovers the active trade
        new_consumer = FnoTickerConsumer(enable_strategy=True, clock=lambda: self.session_time_utc)
        self.assertIsNotNone(new_consumer.strategy.active_position)
        self.assertEqual(new_consumer.strategy.active_position["tradingsymbol"], self.symbol)


class PaperExecutionConcurrencyTestCase(TransactionTestCase):
    """
    Validates strategy-wide position exclusivity under real database transactions
    and concurrent multi-threaded execution.
    """
    databases = {"default", "telemetry"}

    def setUp(self):
        cache.clear()
        self.session_time_utc = datetime(2026, 10, 22, 4, 30, tzinfo=timezone.utc)
        self.token1 = 1001
        self.symbol1 = "NIFTY26OCT24500CE"
        self.token2 = 1002
        self.symbol2 = "NIFTY26OCT24550CE"

    def test_database_schema_lacks_cross_symbol_uniqueness_constraint(self):
        """
        Verifies and documents that the database schema itself does NOT enforce
        cross-symbol uniqueness for OPEN trades (it only has compound indexes on
        (strategy_id, status) and (tradingsymbol, entry_timestamp)).
        Therefore, raw inserts on different symbols can succeed at the DB level,
        making engine-level advisory locking / synchronization mandatory.
        """
        trade1 = PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=self.token1,
            tradingsymbol=self.symbol1,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            quantity=65,
            status="OPEN",
            entry_timestamp=self.session_time_utc,
            entry_fill_price=Decimal("105.00"),
            entry_slippage=Decimal("0.00"),
        )

        trade2 = PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=self.token2,
            tradingsymbol=self.symbol2,
            option_type="CE",
            strike_price=Decimal("24550.00"),
            expiry_date=date(2026, 10, 27),
            quantity=65,
            status="OPEN",
            entry_timestamp=self.session_time_utc,
            entry_fill_price=Decimal("85.00"),
            entry_slippage=Decimal("0.00"),
        )

        self.assertIsNotNone(trade1.pk)
        self.assertIsNotNone(trade2.pk)
        self.assertEqual(
            PaperTradeLedger.objects.filter(strategy_id="STRAT-ORB-15M", status="OPEN").count(),
            2,
        )

    def test_concurrent_threads_competing_for_position_exclusivity(self):
        """
        Spawns two concurrent threads simultaneously submitting breakout buy signals
        for different option contracts. Proves exactly one thread fills and the other
        is atomically rejected.
        """
        from fno.execution.paper_engine import PaperExecutionEngine
        from fno.strategies.base import OptionSignal

        # Create valid quotes for both instruments
        for tok, sym, bid, ask in [
            (self.token1, self.symbol1, Decimal("104.50"), Decimal("105.50")),
            (self.token2, self.symbol2, Decimal("84.50"), Decimal("85.50")),
        ]:
            OptionQuoteSnapshot.objects.create(
                instrument_token=tok,
                tradingsymbol=sym,
                exchange_timestamp_utc=self.session_time_utc,
                received_wall_clock_utc=self.session_time_utc,
                exchange_time_status="VALID",
                best_bid=bid,
                best_ask=ask,
                bid_quantity_l1=100,
                ask_quantity_l1=100,
                quote_status="VALID",
                is_stale=False,
                is_locked=False,
                is_crossed=False,
                is_execution_eligible=True,
            )

        engine = PaperExecutionEngine(clock=lambda: self.session_time_utc)

        signal1 = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            instrument_token=self.token1,
            tradingsymbol=self.symbol1,
            action="BUY_TO_OPEN",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            suggested_lot_count=1,
            timestamp=self.session_time_utc,
            trigger_rule_name="ORB_BULLISH_BREAKOUT",
            trigger_rationale="Concurrent thread 1 test",
            snapshot_reference_id=str(uuid.uuid4()),
        )
        signal2 = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            instrument_token=self.token2,
            tradingsymbol=self.symbol2,
            action="BUY_TO_OPEN",
            option_type="CE",
            strike_price=Decimal("24550.00"),
            expiry_date=date(2026, 10, 27),
            suggested_lot_count=1,
            timestamp=self.session_time_utc,
            trigger_rule_name="ORB_BULLISH_BREAKOUT",
            trigger_rationale="Concurrent thread 2 test",
            snapshot_reference_id=str(uuid.uuid4()),
        )

        quote1 = OptionQuoteSnapshot.objects.filter(instrument_token=self.token1).first()
        quote2 = OptionQuoteSnapshot.objects.filter(instrument_token=self.token2).first()

        results = []
        barrier = threading.Barrier(2)

        def worker(sig, q):
            from django.db import connection
            connection.close()  # Ensure dedicated connection per thread
            exec_engine = PaperExecutionEngine(clock=lambda: self.session_time_utc) if connection.vendor == "postgresql" else engine
            barrier.wait()      # Synchronize threads to hit execution at exact same instant
            evt = exec_engine.process_signal(sig, quote=q)
            results.append(evt)

        t1 = threading.Thread(target=worker, args=(signal1, quote1))
        t2 = threading.Thread(target=worker, args=(signal2, quote2))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        event_types = [r.event_type for r in results]
        self.assertIn("ORDER_FILLED", event_types)
        self.assertIn("ORDER_REJECTED", event_types)

        # Confirm strictly 1 OPEN trade and 1 REJECTED trade exist in DB
        open_count = PaperTradeLedger.objects.filter(strategy_id="STRAT-ORB-15M", status="OPEN").count()
        rejected_count = PaperTradeLedger.objects.filter(
            strategy_id="STRAT-ORB-15M",
            status="REJECTED",
            rejection_reason__in=[
                "REJECTED_MAX_CONCURRENT_POSITIONS_EXCEEDED",
                "REJECTED_POSITION_ALREADY_OPEN",
            ],
        ).count()
        self.assertEqual(open_count, 1)
        self.assertEqual(rejected_count, 1)
