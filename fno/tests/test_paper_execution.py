"""
Unit tests for StatutoryFeeCalculator, PaperExecutionEngine, and StrategyPerformanceEvaluator.
Reference: Phase 22D Specification
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid
import zoneinfo
from django.test import TestCase

from fno.execution.evaluator import StrategyComparisonMatrix, StrategyPerformanceEvaluator
from fno.execution.fee_calculator import StatutoryFeeCalculator
from fno.execution.paper_engine import PaperExecutionEngine, round_to_tick
from fno.models import OptionQuoteSnapshot, PaperTradeLedger
from fno.strategies.base import OptionSignal

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class PaperExecutionTestCase(TestCase):
    def setUp(self):
        self.fee_calc = StatutoryFeeCalculator()
        self.now_utc = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
        self.engine = PaperExecutionEngine(
            fee_calculator=self.fee_calc,
            clock=lambda: self.now_utc,
        )
        self.expiry = date(2026, 10, 22)

        self.quote_valid = OptionQuoteSnapshot.objects.create(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=self.now_utc,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            bid_quantity_l1=100,
            ask_quantity_l1=100,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

        self.signal_buy = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="BUY_TO_OPEN",
            suggested_lot_count=1,
            limit_price_hint=Decimal("121.00"),
            trigger_rule_name="ORB_BULLISH_CE_BREAKOUT",
            trigger_rationale="Spot breakout test",
            snapshot_reference_id="snap-123",
        )

    def test_statutory_fee_calculator_exact_paisa(self):
        """Verifies statutory fee calculations match regulatory formulas to the exact paisa."""
        fees = self.fee_calc.calculate_round_trip(
            buy_price=Decimal("100.00"),
            sell_price=Decimal("120.00"),
            quantity=65,
            trade_date=date(2026, 10, 19),
        )

        self.assertEqual(fees.buy_turnover, Decimal("6500.00"))
        self.assertEqual(fees.sell_turnover, Decimal("7800.00"))
        self.assertEqual(fees.brokerage, Decimal("40.00"))  # 2 orders * 20
        self.assertEqual(fees.exchange_charges, Decimal("5.08"))
        self.assertEqual(fees.sebi_charges, Decimal("0.01"))
        self.assertEqual(fees.stamp_duty, Decimal("0.20"))
        self.assertEqual(fees.stt, Decimal("11.70"))
        self.assertEqual(fees.gst, Decimal("8.12"))
        self.assertEqual(fees.total_frictions, Decimal("65.11"))
        self.assertEqual(fees.statutory_levies, Decimal("25.11"))
        self.assertEqual(fees.effective_schedule_date, "2026-04-01")

    def test_conservative_taker_buy_fill(self):
        """Verifies buy fill occurs at Ask + max(0.05, 0.005 * Ask)."""
        ask = Decimal("120.00")
        expected_fill = Decimal("120.60")
        fill = self.engine.calculate_taker_buy_fill(ask)
        self.assertEqual(fill, expected_fill)

        event = self.engine.process_signal(
            signal=self.signal_buy,
            quote=self.quote_valid,
            market_regime="TRENDING_BULLISH",
            vix_level=Decimal("14.00"),
            execution_wall_time=self.now_utc,
        )
        self.assertEqual(event.event_type, "ORDER_FILLED")
        self.assertGreater(event.fill_price, self.quote_valid.best_ask)
        self.assertEqual(event.fill_quantity, 65)

        # Check DB ledger
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.entry_fill_price, event.fill_price)
        self.assertEqual(trade.quantity, 65)

    def test_quote_microstructure_rejections(self):
        """Verifies rejection of stale, locked, crossed, empty, and excessive spread quotes."""
        # Stale
        q_stale = OptionQuoteSnapshot.objects.create(
            instrument_token=2001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=self.now_utc,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("100.00"),
            best_ask=Decimal("101.00"),
            is_stale=True,
            quote_status="STALE",
        )
        sig_stale = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt = self.engine.process_signal(sig_stale, q_stale)
        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "REJECTED_STALE_QUOTE")

        # Wide spread (> 2.5%)
        q_wide = OptionQuoteSnapshot.objects.create(
            instrument_token=2002,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=self.now_utc,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("100.00"),
            best_ask=Decimal("105.00"),
            quote_status="VALID",
        )
        sig_wide = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt2 = self.engine.process_signal(sig_wide, q_wide)
        self.assertEqual(evt2.event_type, "ORDER_REJECTED")
        self.assertEqual(evt2.message, "REJECTED_EXCESSIVE_SPREAD")

    def test_tiny_positive_bid_below_slippage(self):
        """Verifies that tiny positive bids <= slippage return None and transition to PENDING_LIQUIDITY."""
        # Bid = 0.05. Slippage = max(0.05, 0.05 * 0.005) = 0.05. Fill would be 0.00 -> None!
        fill = self.engine.calculate_taker_sell_fill(Decimal("0.05"))
        self.assertIsNone(fill)

        # 1. Fill buy order
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)

        # 2. Quote has tiny bid of 0.05
        q_tiny = OptionQuoteSnapshot.objects.create(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=self.now_utc,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("0.05"),
            best_ask=Decimal("0.10"),
            quote_status="VALID",
        )

        signal_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_STOP",
            trigger_rule_name="EXIT_STOP",
            trigger_rationale="Stop breached",
            snapshot_reference_id="snap-exit-tiny",
        )

        exit_evt = self.engine.process_signal(signal_exit, q_tiny, execution_wall_time=self.now_utc)
        self.assertEqual(exit_evt.event_type, "ORDER_REJECTED")
        self.assertEqual(exit_evt.message, "EXIT_UNEXECUTABLE_TINY_BID")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "EXIT_UNEXECUTABLE_TINY_BID")
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)

    def test_zero_bid_unexecutable_exit_handling(self):
        """Verifies that an exit trigger encountering a zero bid is marked PENDING_LIQUIDITY without fabricating fills."""
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)

        q_zero_bid = OptionQuoteSnapshot.objects.create(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=self.now_utc,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("0.00"),
            best_ask=Decimal("15.00"),
            quote_status="ZERO_BID",
        )

        signal_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_STOP",
            trigger_rule_name="EXIT_STOP",
            trigger_rationale="Stop breached",
            snapshot_reference_id="snap-exit",
        )

        exit_evt = self.engine.process_signal(signal_exit, q_zero_bid, execution_wall_time=self.now_utc)
        self.assertEqual(exit_evt.event_type, "ORDER_REJECTED")
        self.assertEqual(exit_evt.message, "EXIT_UNEXECUTABLE_ZERO_BID")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)

    def test_session_close_cutoff_handling(self):
        """Verifies 15:30 IST cutoff differentiates expiring contracts from unexpired overnight carry."""
        today = date(2026, 10, 22)
        cutoff_dt = datetime(2026, 10, 22, 15, 30, 0, tzinfo=IST)

        # Trade 1: Expiring today
        t1 = PaperTradeLedger.objects.create(
            strategy_id="STRAT-EXP",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=3001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=today,
            entry_timestamp=cutoff_dt,
            entry_fill_price=Decimal("50.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="PENDING_LIQUIDITY",
        )

        # Trade 2: Expiring next week
        t2 = PaperTradeLedger.objects.create(
            strategy_id="STRAT-EXP",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=3002,
            tradingsymbol="NIFTY26O2924500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 29),
            entry_timestamp=cutoff_dt,
            entry_fill_price=Decimal("120.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="OPEN",
        )

        res = self.engine.handle_session_close_cutoff(cutoff_dt)
        self.assertEqual(res["pending_expiry_settlement"], 1)
        self.assertEqual(res["unexecutable_overnight_carry"], 1)

        t1.refresh_from_db()
        t2.refresh_from_db()

        self.assertEqual(t1.status, "PENDING_EXPIRY_SETTLEMENT")
        self.assertEqual(t2.status, "UNEXECUTABLE_OVERNIGHT_CARRY")

    def test_expiry_settlement_unavailable_data(self):
        """Verifies that unavailable settlement data does NOT fabricate prices and leaves position pending."""
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        evt = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=None,  # Unavailable
            settlement_timestamp=self.now_utc,
        )
        self.assertIsNone(evt)

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertIn(trade.status, ["OPEN", "PENDING_EXPIRY_SETTLEMENT"])
        self.assertIsNone(trade.exit_fill_price)

    def test_official_expiry_cash_settlement_otm_and_itm(self):
        """Verifies separate handling of official expiry settlement without market slippage."""
        # 1. Expired Worthless (OTM Call: Spot 24400 < Strike 24500)
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        settle_evt = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24400.00"),
            settlement_timestamp=self.now_utc,
        )
        self.assertEqual(settle_evt.event_type, "SETTLEMENT")
        self.assertEqual(settle_evt.fill_price, Decimal("0.00"))
        self.assertEqual(settle_evt.slippage, Decimal("0.00"))

        trade_otm = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade_otm.status, "CLOSED_EXPIRED_WORTHLESS")
        self.assertEqual(trade_otm.fill_type, "SETTLEMENT")
        self.assertEqual(trade_otm.exit_slippage, Decimal("0.00"))
        self.assertLess(trade_otm.net_pnl, Decimal("0.00"))
        self.assertEqual(trade_otm.net_pnl, trade_otm.gross_pnl - trade_otm.total_frictions)

        # 2. Expired ITM (Spot 24650 > Strike 24500 -> intrinsic 150.00)
        sig_itm = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        self.engine.process_signal(sig_itm, self.quote_valid, execution_wall_time=self.now_utc)
        settle_itm = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24650.00"),
            settlement_timestamp=self.now_utc,
        )
        self.assertEqual(settle_itm.fill_price, Decimal("150.00"))
        trade_itm = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig_itm.signal_id))
        self.assertEqual(trade_itm.status, "CLOSED_EXPIRED_ITM_SETTLED")
        self.assertEqual(trade_itm.net_pnl, trade_itm.gross_pnl - trade_itm.total_frictions)

    def test_strategy_performance_evaluator(self):
        """Verifies multi-trade performance metrics and comparison matrix generation."""
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-A",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            entry_timestamp=self.now_utc,
            entry_fill_price=Decimal("100.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            exit_fill_price=Decimal("120.00"),
            exit_slippage=Decimal("0.50"),
            gross_pnl=Decimal("1300.00"),
            total_frictions=Decimal("65.00"),
            net_pnl=Decimal("1235.00"),
            market_regime_at_entry="TRENDING_BULLISH",
            status="CLOSED",
        )
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-A",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            entry_timestamp=self.now_utc,
            entry_fill_price=Decimal("100.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            exit_fill_price=Decimal("85.00"),
            exit_slippage=Decimal("0.50"),
            gross_pnl=Decimal("-975.00"),
            total_frictions=Decimal("60.00"),
            net_pnl=Decimal("-1035.00"),
            market_regime_at_entry="SIDEWAYS_CHOP",
            status="CLOSED",
        )

        metrics = StrategyPerformanceEvaluator.evaluate_strategy("STRAT-A")
        self.assertEqual(metrics.total_trades, 2)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertEqual(metrics.win_rate_pct, Decimal("50.00"))
        self.assertEqual(metrics.net_pnl, Decimal("200.00"))
        self.assertEqual(metrics.expectancy_per_trade, Decimal("100.00"))
        self.assertIn("TRENDING_BULLISH", metrics.regime_breakdown)
        self.assertIn("SIDEWAYS_CHOP", metrics.regime_breakdown)

        matrix = StrategyComparisonMatrix([metrics])
        md_table = matrix.to_markdown_table()
        self.assertIn("STRAT-A", md_table)
        self.assertIn("50.0%", md_table)

    def test_tick_grid_rounding_rules(self):
        """Verifies explicit tick-grid rounding (multiples of 0.05) using ceiling for buys and floor for sells."""
        tick = Decimal("0.05")

        # Buys (ROUND_CEILING - never more favorable than ask + slippage)
        self.assertEqual(round_to_tick(Decimal("120.00"), tick, direction="UP"), Decimal("120.00"))
        self.assertEqual(round_to_tick(Decimal("120.01"), tick, direction="UP"), Decimal("120.05"))
        self.assertEqual(round_to_tick(Decimal("120.02"), tick, direction="UP"), Decimal("120.05"))
        self.assertEqual(round_to_tick(Decimal("120.05"), tick, direction="UP"), Decimal("120.05"))
        self.assertEqual(round_to_tick(Decimal("120.06"), tick, direction="UP"), Decimal("120.10"))
        self.assertEqual(round_to_tick(Decimal("120.09"), tick, direction="UP"), Decimal("120.10"))

        # Sells (ROUND_FLOOR - never more favorable than bid - slippage)
        self.assertEqual(round_to_tick(Decimal("120.00"), tick, direction="DOWN"), Decimal("120.00"))
        self.assertEqual(round_to_tick(Decimal("120.01"), tick, direction="DOWN"), Decimal("120.00"))
        self.assertEqual(round_to_tick(Decimal("120.04"), tick, direction="DOWN"), Decimal("120.00"))
        self.assertEqual(round_to_tick(Decimal("120.05"), tick, direction="DOWN"), Decimal("120.05"))
        self.assertEqual(round_to_tick(Decimal("120.08"), tick, direction="DOWN"), Decimal("120.05"))
        self.assertEqual(round_to_tick(Decimal("120.09"), tick, direction="DOWN"), Decimal("120.05"))

        # Non-tick ask with default slippage
        # Ask 120.02: rate 0.005 -> 120.02 * 0.005 = 0.6001 -> slippage = 0.65.
        # Raw = 120.02 + 0.65 = 120.6700 -> fill = 120.70 (exact 0.05 multiple)
        fill = self.engine.calculate_taker_buy_fill(Decimal("120.02"))
        self.assertEqual(fill, Decimal("120.70"))
        self.assertEqual(fill % tick, Decimal("0.00"))

    def test_explicit_zero_slippage_handling(self):
        """Verifies configured_slippage_rate=Decimal('0.00') is preserved and not replaced by default."""
        zero_slippage = Decimal("0.00")

        # Buy fill with zero slippage on tick-aligned price
        fill_buy = self.engine.calculate_taker_buy_fill(Decimal("120.00"), configured_slippage_rate=zero_slippage)
        self.assertEqual(fill_buy, Decimal("120.00"))

        # Buy fill with zero slippage on non-tick price (must round up to next tick)
        fill_buy_non_tick = self.engine.calculate_taker_buy_fill(Decimal("120.02"), configured_slippage_rate=zero_slippage)
        self.assertEqual(fill_buy_non_tick, Decimal("120.05"))

        # Sell fill with zero slippage on tick-aligned price
        fill_sell = self.engine.calculate_taker_sell_fill(Decimal("120.00"), configured_slippage_rate=zero_slippage)
        self.assertEqual(fill_sell, Decimal("120.00"))

        # Sell fill with zero slippage on non-tick price (must round down to previous tick)
        fill_sell_non_tick = self.engine.calculate_taker_sell_fill(Decimal("120.04"), configured_slippage_rate=zero_slippage)
        self.assertEqual(fill_sell_non_tick, Decimal("120.00"))

    def test_bids_around_minimum_tick(self):
        """Verifies fill behavior for bids around the minimum tick threshold (0.05)."""
        # Bid = 0.05: slippage is 0.05 -> bid <= slippage -> returns None
        self.assertIsNone(self.engine.calculate_taker_sell_fill(Decimal("0.05")))

        # Bid = 0.06: slippage is 0.05 -> bid - slippage = 0.01 < tick (0.05) -> returns None
        self.assertIsNone(self.engine.calculate_taker_sell_fill(Decimal("0.06")))

        # Bid = 0.10: slippage is 0.05 -> bid - slippage = 0.05 >= tick (0.05) -> returns 0.05
        self.assertEqual(self.engine.calculate_taker_sell_fill(Decimal("0.10")), Decimal("0.05"))

        # Bid = 0.00: returns None
        self.assertIsNone(self.engine.calculate_taker_sell_fill(Decimal("0.00")))

        # Bid = -0.05: returns None
        self.assertIsNone(self.engine.calculate_taker_sell_fill(Decimal("-0.05")))

    def test_repeated_cutoff_idempotency_and_unresolved_exposure(self):
        """Verifies that calling handle_session_close_cutoff repeatedly is idempotent and does not corrupt state."""
        cutoff_dt = datetime(2026, 10, 22, 15, 30, 0, tzinfo=IST)
        t = PaperTradeLedger.objects.create(
            strategy_id="STRAT-IDEMP",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=4001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 29),
            entry_timestamp=cutoff_dt,
            entry_fill_price=Decimal("120.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="OPEN",
        )

        res1 = self.engine.handle_session_close_cutoff(cutoff_dt)
        self.assertEqual(res1["unexecutable_overnight_carry"], 1)

        t.refresh_from_db()
        self.assertEqual(t.status, "UNEXECUTABLE_OVERNIGHT_CARRY")

        # Second call: trade is already UNEXECUTABLE_OVERNIGHT_CARRY, must remain so without error
        res2 = self.engine.handle_session_close_cutoff(cutoff_dt)
        self.assertEqual(res2["unexecutable_overnight_carry"], 1)

        t.refresh_from_db()
        self.assertEqual(t.status, "UNEXECUTABLE_OVERNIGHT_CARRY")

    def test_restart_and_reload_recovery(self):
        """Verifies sync_active_trades_from_db restores in-memory tracking after engine restart."""
        # Create an unresolved trade directly in DB
        trade_id = uuid.uuid4()
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-RELOAD",
            strategy_version="1.0.0",
            signal_id=trade_id,
            instrument_token=5001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            entry_timestamp=self.now_utc,
            entry_fill_price=Decimal("110.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="PENDING_LIQUIDITY",
        )

        # Clear engine in-memory state simulating a restart
        self.engine.active_trades.clear()
        self.assertEqual(len(self.engine.active_trades), 0)

        # Sync from DB
        synced_count = self.engine.sync_active_trades_from_db()
        self.assertGreaterEqual(synced_count, 1)
        self.assertIn("STRAT-RELOAD:NIFTY26OCT24500CE", self.engine.active_trades)
        restored_trade = self.engine.active_trades["STRAT-RELOAD:NIFTY26OCT24500CE"]
        self.assertEqual(restored_trade.status, "PENDING_LIQUIDITY")

    def test_duplicate_expiry_settlement_prevents_double_charging(self):
        """Verifies that duplicate settlement resolution calls do not re-apply statutory fees or double P&L."""
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)

        # First settlement resolution
        evt1 = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24600.00"),  # Intrinsic = 100.00
            settlement_timestamp=self.now_utc,
        )
        self.assertIsNotNone(evt1)
        trade1 = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        initial_net_pnl = trade1.net_pnl
        initial_frictions = trade1.total_frictions
        self.assertEqual(trade1.status, "CLOSED_EXPIRED_ITM_SETTLED")

        # Second settlement call for same contract
        evt2 = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24600.00"),
            settlement_timestamp=self.now_utc,
        )
        trade2 = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade2.net_pnl, initial_net_pnl)
        self.assertEqual(trade2.total_frictions, initial_frictions)
        self.assertEqual(trade2.status, "CLOSED_EXPIRED_ITM_SETTLED")

    def test_statutory_fee_effective_date_boundaries_and_unsupported_dates(self):
        """Verifies effective date boundary enforcement and unsupported date handling."""
        # Supported effective date: 2026-04-01 onwards
        breakdown = StatutoryFeeCalculator.calculate_round_trip(
            buy_price=Decimal("100.00"),
            sell_price=Decimal("120.00"),
            quantity=65,
            trade_date=date(2026, 4, 1),
        )
        self.assertEqual(breakdown.effective_schedule_date, "2026-04-01")

        # Unsupported historical date before 2026-04-01
        with self.assertRaises(ValueError) as ctx:
            StatutoryFeeCalculator.calculate_round_trip(
                buy_price=Decimal("100.00"),
                sell_price=Decimal("120.00"),
                quantity=65,
                trade_date=date(2026, 3, 31),
            )
        self.assertIn("Historical trade date 2026-03-31 is unsupported", str(ctx.exception))

    def test_statutory_fee_missing_trade_date_without_policy_raises(self):
        """Verifies trade_date=None raises ValueError if allow_default_schedule is not explicitly True."""
        with self.assertRaises(ValueError) as ctx:
            StatutoryFeeCalculator.calculate_round_trip(
                buy_price=Decimal("100.00"),
                sell_price=Decimal("120.00"),
                quantity=65,
                trade_date=None,
                allow_default_schedule=False,
            )
        self.assertIn("Missing trade_date", str(ctx.exception))

    def test_statutory_fee_missing_trade_date_with_explicit_policy_succeeds(self):
        """Verifies trade_date=None succeeds when allow_default_schedule is explicitly True."""
        breakdown = StatutoryFeeCalculator.calculate_round_trip(
            buy_price=Decimal("100.00"),
            sell_price=Decimal("120.00"),
            quantity=65,
            trade_date=None,
            allow_default_schedule=True,
        )
        self.assertEqual(breakdown.effective_schedule_date, "2026-04-01")

    def test_position_uniqueness_invariant_in_entry_signal(self):
        """Verifies that an entry signal is rejected if an unresolved position already exists in memory or DB."""
        # 1. Fill first order
        evt1 = self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt1.event_type, "ORDER_FILLED")

        # 2. Attempt second order for same (strategy_id, tradingsymbol) while first is OPEN
        sig_dup = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt2 = self.engine.process_signal(sig_dup, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt2.event_type, "ORDER_REJECTED")
        self.assertEqual(evt2.message, "REJECTED_POSITION_ALREADY_OPEN")

        # 3. Simulate process restart (clear in-memory active_trades cache)
        self.engine.active_trades.clear()
        # Even with memory cleared, engine checks DB and enforces uniqueness invariant
        sig_dup3 = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt3 = self.engine.process_signal(sig_dup3, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt3.event_type, "ORDER_REJECTED")
        self.assertEqual(evt3.message, "REJECTED_POSITION_ALREADY_OPEN")

    def test_position_uniqueness_collision_detection_in_sync_from_db(self):
        """Verifies sync_active_trades_from_db raises ValueError if duplicate unresolved rows exist in DB."""
        # Create first unresolved trade
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-COLLIDE",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=9001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            entry_timestamp=self.now_utc,
            entry_fill_price=Decimal("100.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="OPEN",
        )
        # Directly insert a second unresolved trade for the SAME strategy and contract (violating invariant)
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-COLLIDE",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=9001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            entry_timestamp=self.now_utc,
            entry_fill_price=Decimal("105.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            status="PENDING_LIQUIDITY",
        )

        # Attempt to sync: must raise ValueError and prevent silent collision
        with self.assertRaises(ValueError) as ctx:
            self.engine.sync_active_trades_from_db()
        self.assertIn("Uniqueness invariant violated", str(ctx.exception))

    def test_tick_size_and_rounding_direction_validation(self):
        """Verifies round_to_tick validates positive tick size and permitted directions."""
        # Non-positive tick size
        with self.assertRaises(ValueError) as ctx1:
            round_to_tick(Decimal("120.00"), tick_size=Decimal("0.00"))
        self.assertIn("tick_size must be positive", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            round_to_tick(Decimal("120.00"), tick_size=Decimal("-0.05"))
        self.assertIn("tick_size must be positive", str(ctx2.exception))

        # Invalid rounding direction
        with self.assertRaises(ValueError) as ctx3:
            round_to_tick(Decimal("120.00"), tick_size=Decimal("0.05"), direction="INVALID_MODE")
        self.assertIn("Invalid rounding direction", str(ctx3.exception))

    def test_fill_calculation_parameter_boundaries(self):
        """Verifies calculate_taker_buy_fill and calculate_taker_sell_fill reject negative slippage or invalid tick size."""
        # Negative slippage rate
        with self.assertRaises(ValueError) as ctx1:
            self.engine.calculate_taker_buy_fill(Decimal("120.00"), configured_slippage_rate=Decimal("-0.01"))
        self.assertIn("configured_slippage_rate must be non-negative", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            self.engine.calculate_taker_sell_fill(Decimal("120.00"), configured_slippage_rate=Decimal("-0.01"))
        self.assertIn("configured_slippage_rate must be non-negative", str(ctx2.exception))

        # Non-positive tick size in fill calculation
        with self.assertRaises(ValueError) as ctx3:
            self.engine.calculate_taker_buy_fill(Decimal("120.00"), tick_size=Decimal("0.00"))
        self.assertIn("tick_size must be positive", str(ctx3.exception))

        with self.assertRaises(ValueError) as ctx4:
            self.engine.calculate_taker_sell_fill(Decimal("120.00"), tick_size=Decimal("-0.05"))
        self.assertIn("tick_size must be positive", str(ctx4.exception))

    def test_missing_execution_timestamp_preserves_pending_state(self):
        """Verifies missing execution timestamp rejects exit, preserves PENDING_LIQUIDITY, and never fabricates dates."""
        # 1. Fill buy order
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "OPEN")

        # 2. Quote with no timestamps (in-memory snapshot)
        q_no_time = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=None,
            received_wall_clock_utc=None,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            quote_status="VALID",
        )
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target reached",
            snapshot_reference_id="snap-exit-notime",
        )

        # 3. Process exit signal without execution_wall_time (timestamps completely unresolvable)
        evt = self.engine.process_signal(sig_exit, q_no_time, execution_wall_time=None)
        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "EXIT_MISSING_EXECUTION_TIMESTAMP")

        # 4. Verify DB state is preserved in PENDING_LIQUIDITY, not CLOSED
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "EXIT_MISSING_EXECUTION_TIMESTAMP")
        self.assertIsNone(trade.exit_timestamp)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)
        self.assertEqual(trade.total_frictions, Decimal("0.00"))

    def test_missing_settlement_timestamp_preserves_pending_state(self):
        """Verifies missing settlement timestamp leaves position in PENDING_EXPIRY_SETTLEMENT without fabricating fees."""
        # 1. Fill buy order
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "OPEN")

        # 2. Call resolve_expiry_settlement with None timestamp
        evt = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24600.00"),
            settlement_timestamp=None,
        )
        self.assertIsNone(evt)

        # 3. Verify DB state is preserved in PENDING_EXPIRY_SETTLEMENT
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_EXPIRY_SETTLEMENT")
        self.assertEqual(trade.rejection_reason, "SETTLEMENT_MISSING_TIMESTAMP")
        self.assertIsNone(trade.exit_timestamp)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)
        self.assertEqual(trade.total_frictions, Decimal("0.00"))

    def test_unsupported_historical_trade_date_rejections(self):
        """Verifies trade dates before 2026-04-01 are rejected and positions preserved in pending states."""
        historical_dt = datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

        # 1. Buy signal with historical timestamp rejected
        sig_buy_hist = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt_buy = self.engine.process_signal(sig_buy_hist, self.quote_valid, execution_wall_time=historical_dt)
        self.assertEqual(evt_buy.event_type, "ORDER_REJECTED")
        self.assertIn("UNSUPPORTED_TRADE_DATE_2025-10-15", evt_buy.message)

        # 2. Exit with historical timestamp rejected & preserved in PENDING_LIQUIDITY
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-exit-hist",
        )
        evt_exit = self.engine.process_signal(sig_exit, self.quote_valid, execution_wall_time=historical_dt)
        self.assertEqual(evt_exit.event_type, "ORDER_REJECTED")
        self.assertIn("FEE_CALCULATION_FAILED", evt_exit.message)
        self.assertIn("Historical trade date 2025-10-15 is unsupported", evt_exit.message)

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertIn("Historical trade date 2025-10-15 is unsupported", trade.rejection_reason)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)

        # 3. Settlement with historical timestamp rejected & preserved in PENDING_EXPIRY_SETTLEMENT
        evt_settle = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24600.00"),
            settlement_timestamp=historical_dt,
        )
        self.assertIsNone(evt_settle)
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_EXPIRY_SETTLEMENT")
        self.assertIn("Historical trade date 2025-10-15 is unsupported", trade.rejection_reason)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)

    def test_valid_timestamp_with_expected_fee_schedule(self):
        """Verifies valid timestamps on/after 2026-04-01 execute with the regulatory fee schedule."""
        # 1. Exit with valid 2026-10-19 timestamp
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-valid",
        )
        evt = self.engine.process_signal(sig_exit, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt.event_type, "POSITION_CLOSED")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "CLOSED")
        self.assertEqual(trade.exit_timestamp, self.now_utc)
        self.assertEqual(trade.friction_breakdown["effective_schedule_date"], "2026-04-01")
        self.assertGreater(trade.total_frictions, Decimal("0.00"))
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.total_frictions)

    def test_retry_after_timestamp_failure_succeeds(self):
        """Verifies that an exit or settlement can safely resume and succeed after timestamp failure."""
        # 1. Open trade
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))

        # 2. Quote with no timestamps -> exit fails into PENDING_LIQUIDITY
        q_no_time = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=None,
            received_wall_clock_utc=None,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            quote_status="VALID",
        )
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_STOP",
            trigger_rule_name="EXIT_STOP",
            trigger_rationale="Stop",
            snapshot_reference_id="snap-retry",
        )
        evt_fail = self.engine.process_signal(sig_exit, q_no_time, execution_wall_time=None)
        self.assertEqual(evt_fail.event_type, "ORDER_REJECTED")
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")

        # 3. Retry exit with valid timestamp: succeeds!
        retry_time = datetime(2026, 10, 19, 14, 0, 0, tzinfo=timezone.utc)
        evt_retry = self.engine.process_signal(sig_exit, self.quote_valid, execution_wall_time=retry_time)
        self.assertEqual(evt_retry.event_type, "POSITION_CLOSED")

        trade.refresh_from_db()
        self.assertEqual(trade.status, "CLOSED")
        self.assertEqual(trade.exit_timestamp, retry_time)
        self.assertIsNotNone(trade.exit_fill_price)
        self.assertIsNotNone(trade.net_pnl)
        self.assertIsNone(trade.rejection_reason)

    def test_duplicate_execution_and_settlement_prevention(self):
        """Verifies duplicate exits and settlements do not double-deduct fees or alter ledger records."""
        # 1. Complete an exit
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-dup",
        )
        evt_close = self.engine.process_signal(sig_exit, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt_close.event_type, "POSITION_CLOSED")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        orig_net_pnl = trade.net_pnl
        orig_frictions = trade.total_frictions

        # 2. Attempt duplicate exit: Rejected with NO_OPEN_POSITION_FOUND
        evt_dup = self.engine.process_signal(sig_exit, self.quote_valid, execution_wall_time=self.now_utc)
        self.assertEqual(evt_dup.event_type, "ORDER_REJECTED")
        self.assertEqual(evt_dup.message, "NO_OPEN_POSITION_FOUND")

        trade.refresh_from_db()
        self.assertEqual(trade.net_pnl, orig_net_pnl)
        self.assertEqual(trade.total_frictions, orig_frictions)

        # 3. Settle an ITM trade
        sig_itm = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        self.engine.process_signal(sig_itm, self.quote_valid, execution_wall_time=self.now_utc)
        settle_evt = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24650.00"),
            settlement_timestamp=self.now_utc,
        )
        self.assertEqual(settle_evt.event_type, "SETTLEMENT")

        trade_itm = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig_itm.signal_id))
        self.assertEqual(trade_itm.status, "CLOSED_EXPIRED_ITM_SETTLED")
        orig_itm_frictions = trade_itm.total_frictions
        orig_itm_pnl = trade_itm.net_pnl

        # 4. Attempt duplicate settlement: Ignored idempotently without double-applying fees
        settle_dup = self.engine.resolve_expiry_settlement(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24650.00"),
            settlement_timestamp=self.now_utc,
        )
        self.assertIn("DUPLICATE_SETTLEMENT_IGNORED", settle_dup.message)

        trade_itm.refresh_from_db()
        self.assertEqual(trade_itm.net_pnl, orig_itm_pnl)
        self.assertEqual(trade_itm.total_frictions, orig_itm_frictions)

    def test_public_methods_reject_allow_default_schedule_keyword_argument(self):
        """Verifies public process_signal and resolve_expiry_settlement strictly disallow allow_default_schedule."""
        with self.assertRaises(TypeError):
            self.engine.process_signal(
                self.signal_buy,
                self.quote_valid,
                execution_wall_time=self.now_utc,
                allow_default_schedule=True,  # type: ignore[call-arg]
            )

        with self.assertRaises(TypeError):
            self.engine.resolve_expiry_settlement(
                strategy_id="STRAT-ORB-15M",
                tradingsymbol="NIFTY26OCT24500CE",
                underlying_settlement_price=Decimal("24650.00"),
                settlement_timestamp=self.now_utc,
                allow_default_schedule=True,  # type: ignore[call-arg]
            )

    def test_explicit_test_only_override_behavior(self):
        """Verifies isolated _test_only_ helper methods enable deliberate test execution/settlement without timestamp."""
        # 1. Exit with isolated test helper and no execution timestamp
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-override",
        )
        q_no_time = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=None,
            received_wall_clock_utc=None,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            quote_status="VALID",
        )
        evt_exit = self.engine._test_only_process_signal_with_override(
            sig_exit,
            q_no_time,
            execution_wall_time=None,
            allow_default_schedule=True,
        )
        self.assertEqual(evt_exit.event_type, "POSITION_CLOSED")
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "CLOSED")
        self.assertEqual(trade.friction_breakdown["effective_schedule_date"], "2026-04-01")

        # 2. Settlement with isolated test helper and settlement_timestamp=None
        sig_itm = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        self.engine.process_signal(sig_itm, self.quote_valid, execution_wall_time=self.now_utc)
        settle_evt = self.engine._test_only_resolve_expiry_settlement_with_override(
            strategy_id="STRAT-ORB-15M",
            tradingsymbol="NIFTY26OCT24500CE",
            underlying_settlement_price=Decimal("24650.00"),
            settlement_timestamp=None,
            allow_default_schedule=True,
        )
        self.assertEqual(settle_evt.event_type, "SETTLEMENT")
        trade_itm = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig_itm.signal_id))
        self.assertEqual(trade_itm.status, "CLOSED_EXPIRED_ITM_SETTLED")
        self.assertEqual(trade_itm.friction_breakdown["effective_schedule_date"], "2026-04-01")

    def test_unverified_exchange_timestamp_status_rejected_for_entry_and_exit(self):
        """Verifies FALLBACK_TO_RECEIVED receipt wall clocks are never silently promoted to exchange execution time."""
        # Quote where exchange timestamp is missing and marked FALLBACK_TO_RECEIVED
        q_fallback = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=None,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="FALLBACK_TO_RECEIVED",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            quote_status="VALID",
        )

        # 1. Buy signal must be rejected (cannot execute on unverified exchange time)
        sig_buy = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt_buy = self.engine.process_signal(sig_buy, q_fallback, execution_wall_time=None)
        self.assertEqual(evt_buy.event_type, "ORDER_REJECTED")
        self.assertEqual(evt_buy.message, "ENTRY_UNVERIFIED_EXCHANGE_TIMESTAMP")

        # 2. Open valid position using authoritative quote
        self.engine.process_signal(self.signal_buy, self.quote_valid, execution_wall_time=self.now_utc)
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.status, "OPEN")

        # 3. Exit signal against fallback quote must preserve PENDING_LIQUIDITY
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-fallback-exit",
        )
        evt_exit = self.engine.process_signal(sig_exit, q_fallback, execution_wall_time=None)
        self.assertEqual(evt_exit.event_type, "ORDER_REJECTED")
        self.assertEqual(evt_exit.message, "EXIT_UNVERIFIED_EXCHANGE_TIMESTAMP")

        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "EXIT_UNVERIFIED_EXCHANGE_TIMESTAMP")
        self.assertIsNone(trade.exit_timestamp)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.net_pnl)

    def test_exchange_vs_receipt_timestamp_provenance_isolation(self):
        """Verifies trade execution uses matching engine timestamp exactly and not daemon arrival wall clock."""
        exch_time = datetime(2026, 10, 19, 9, 30, 0, tzinfo=timezone.utc)
        arrival_time = datetime(2026, 10, 19, 9, 30, 1, 850000, tzinfo=timezone.utc)

        q_skew = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=exch_time,
            received_wall_clock_utc=arrival_time,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("121.00"),
            quote_status="VALID",
        )

        # 1. Entry fill records exchange_time (09:30:00), not arrival_time (09:30:01.850)
        # Advance engine's trusted clock to arrival_time via controlled clock injection
        self.engine.clock = lambda: arrival_time
        evt_buy = self.engine.process_signal(
            self.signal_buy,
            q_skew,
            execution_wall_time=None,
        )
        self.assertEqual(evt_buy.event_type, "ORDER_FILLED")
        self.assertEqual(evt_buy.timestamp, exch_time)
        self.assertNotEqual(evt_buy.timestamp, arrival_time)

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(self.signal_buy.signal_id))
        self.assertEqual(trade.entry_timestamp, exch_time)
        self.assertNotEqual(trade.entry_timestamp, arrival_time)

        # 2. Exit fill records exchange_time exactly
        exch_exit = datetime(2026, 10, 19, 10, 15, 0, tzinfo=timezone.utc)
        arrival_exit = datetime(2026, 10, 19, 10, 15, 0, 450000, tzinfo=timezone.utc)
        q_exit = OptionQuoteSnapshot(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=exch_exit,
            received_wall_clock_utc=arrival_exit,
            exchange_time_status="VALID",
            best_bid=Decimal("130.00"),
            best_ask=Decimal("131.00"),
            quote_status="VALID",
        )
        sig_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            trigger_rule_name="EXIT_TARGET",
            trigger_rationale="Target",
            snapshot_reference_id="snap-skew-exit",
        )
        self.engine.clock = lambda: arrival_exit
        evt_exit = self.engine.process_signal(
            sig_exit,
            q_exit,
            execution_wall_time=None,
        )
        self.assertEqual(evt_exit.event_type, "POSITION_CLOSED")
        self.assertEqual(evt_exit.timestamp, exch_exit)
        self.assertNotEqual(evt_exit.timestamp, arrival_exit)

        trade.refresh_from_db()
        self.assertEqual(trade.exit_timestamp, exch_exit)
        self.assertNotEqual(trade.exit_timestamp, arrival_exit)
        self.assertEqual(trade.friction_breakdown["effective_schedule_date"], "2026-04-01")

        # Restore default test clock
        self.engine.clock = lambda: self.now_utc


class QuoteFreshnessGuardTestCase(TestCase):
    """
    Focused regression test suite for Phase 22D Quote-Freshness Safety.
    Verifies dynamic quote age recalculation at the execution decision boundary,
    rejection of stale, future, missing, and timezone-naive timestamps,
    and symmetrical entry and exit gating with open exposure preservation.
    """

    def setUp(self):
        self.fee_calc = StatutoryFeeCalculator()
        self.now_utc = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
        self.engine = PaperExecutionEngine(
            fee_calculator=self.fee_calc,
            clock=lambda: self.now_utc,
        )
        self.expiry = date(2026, 10, 22)

        self.signal_buy = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-FRESH-01",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=3001,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="BUY_TO_OPEN",
            suggested_lot_count=1,
            limit_price_hint=Decimal("100.00"),
            trigger_rule_name="ORB_TEST",
            trigger_rationale="Freshness test buy",
            snapshot_reference_id="snap-fresh-buy",
        )

        self.signal_exit = OptionSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id="STRAT-FRESH-01",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY26OCT24500CE",
            instrument_token=3001,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            action="EXIT_TARGET",
            suggested_lot_count=1,
            trigger_rule_name="TARGET_TEST",
            trigger_rationale="Freshness test exit",
            snapshot_reference_id="snap-fresh-exit",
        )

    def _create_quote(self, **kwargs) -> OptionQuoteSnapshot:
        defaults = {
            "instrument_token": 3001,
            "tradingsymbol": "NIFTY26OCT24500CE",
            "exchange_timestamp_utc": self.now_utc,
            "received_wall_clock_utc": self.now_utc,
            "exchange_time_status": "VALID",
            "best_bid": Decimal("100.00"),
            "best_ask": Decimal("101.00"),
            "bid_quantity_l1": 500,
            "ask_quantity_l1": 500,
            "quote_status": "VALID",
            "is_stale": False,
            "is_locked": False,
            "is_crossed": False,
            "is_execution_eligible": True,
        }
        defaults.update(kwargs)
        return OptionQuoteSnapshot.objects.create(**defaults)

    def test_fresh_quote_at_exact_threshold_boundary(self):
        """Verifies boundary: age <= 3.0s passes; age > 3.0s is rejected."""
        # 1. Quote age exactly 0.0s -> passes
        q_0s = self._create_quote(exchange_timestamp_utc=self.now_utc)
        sig1 = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt1 = self.engine.process_signal(sig1, q_0s)
        self.assertEqual(evt1.event_type, "ORDER_FILLED")

        # Clean active trade to test next boundary
        self.engine.active_trades.clear()
        PaperTradeLedger.objects.all().delete()

        # 2. Quote age exactly 3.0s -> passes (documented inclusive boundary)
        q_3s = self._create_quote(exchange_timestamp_utc=self.now_utc - timedelta(seconds=3))
        sig2 = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt2 = self.engine.process_signal(sig2, q_3s)
        self.assertEqual(evt2.event_type, "ORDER_FILLED")

        self.engine.active_trades.clear()
        PaperTradeLedger.objects.all().delete()

        # 3. Quote age 3.001s (> 3.0s) -> rejected
        q_3001s = self._create_quote(exchange_timestamp_utc=self.now_utc - timedelta(milliseconds=3001))
        sig3 = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt3 = self.engine.process_signal(sig3, q_3001s)
        self.assertEqual(evt3.event_type, "ORDER_REJECTED")
        self.assertEqual(evt3.message, "REJECTED_STALE_QUOTE")

    def test_quote_aging_after_ingestion_rejection(self):
        """
        Verifies Finding A: A quote whose persisted is_stale flag is False is
        re-evaluated and rejected when decision clock evaluates it as > 3.0s old.
        """
        q_aged = self._create_quote(
            exchange_timestamp_utc=self.now_utc - timedelta(seconds=10),
            is_stale=False,  # Persisted flag at ingestion time was False!
            quote_status="VALID",
        )
        sig = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt = self.engine.process_signal(sig, q_aged)

        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "REJECTED_STALE_QUOTE")

        # Verify DB ledger record: rejected, no fills, no fees, no P&L
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig.signal_id))
        self.assertEqual(trade.status, "REJECTED")
        self.assertEqual(trade.entry_fill_price, Decimal("0.00"))
        self.assertEqual(trade.total_frictions, Decimal("0.00"))
        self.assertIsNone(trade.gross_pnl)
        self.assertIsNone(trade.net_pnl)

    def test_future_exchange_timestamp_rejected(self):
        """Verifies quotes with exchange timestamps in the future are rejected."""
        q_future = self._create_quote(
            exchange_timestamp_utc=self.now_utc + timedelta(seconds=5),
        )
        sig = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt = self.engine.process_signal(sig, q_future)

        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "REJECTED_FUTURE_TIMESTAMP")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig.signal_id))
        self.assertEqual(trade.status, "REJECTED")
        self.assertEqual(trade.rejection_reason, "REJECTED_FUTURE_TIMESTAMP")

    def test_timezone_naive_exchange_timestamp_rejected(self):
        """Verifies quotes with timezone-naive timestamps fail closed as REJECTED_TIMEZONE_AMBIGUOUS."""
        naive_dt = datetime(2026, 10, 19, 10, 0, 0)  # tzinfo=None
        q_naive = OptionQuoteSnapshot(
            instrument_token=3001,
            tradingsymbol="NIFTY26OCT24500CE",
            exchange_timestamp_utc=naive_dt,
            received_wall_clock_utc=self.now_utc,
            exchange_time_status="VALID",
            best_bid=Decimal("100.00"),
            best_ask=Decimal("101.00"),
            quote_status="VALID",
        )
        sig = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt = self.engine.process_signal(sig, q_naive)

        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "REJECTED_TIMEZONE_AMBIGUOUS")

    def test_stale_exit_rejected_preserves_unresolved_exposure(self):
        """
        Verifies Finding B: Exit path applies full quote freshness guard.
        A stale quote on exit transitions the trade to PENDING_LIQUIDITY,
        records REJECTED_STALE_QUOTE, preserves unresolved exposure, and charges ZERO fees/P&L.
        """
        # 1. Establish open trade
        q_fresh = self._create_quote(exchange_timestamp_utc=self.now_utc)
        sig_buy = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt_buy = self.engine.process_signal(sig_buy, q_fresh)
        self.assertEqual(evt_buy.event_type, "ORDER_FILLED")

        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig_buy.signal_id))
        self.assertEqual(trade.status, "OPEN")

        # 2. Attempt exit with stale quote (age = 8 seconds, persisted is_stale=False)
        q_stale_exit = self._create_quote(
            exchange_timestamp_utc=self.now_utc - timedelta(seconds=8),
            is_stale=False,
            quote_status="VALID",
            best_bid=Decimal("110.00"),
            best_ask=Decimal("111.00"),
        )
        sig_exit = self.signal_exit.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt_exit = self.engine.process_signal(sig_exit, q_stale_exit)

        self.assertEqual(evt_exit.event_type, "ORDER_REJECTED")
        self.assertEqual(evt_exit.message, "REJECTED_STALE_QUOTE")
        self.assertIsNone(evt_exit.fill_price)
        self.assertEqual(evt_exit.fill_quantity, 0)

        # 3. Verify exposure is preserved in PENDING_LIQUIDITY
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "REJECTED_STALE_QUOTE")
        self.assertEqual(trade.exit_trigger_reason, "EXIT_TARGET")
        self.assertIsNone(trade.exit_timestamp)
        self.assertIsNone(trade.exit_fill_price)
        self.assertIsNone(trade.gross_pnl)
        self.assertIsNone(trade.net_pnl)
        self.assertEqual(trade.total_frictions, Decimal("0.00"))

        # In-memory tracking remains active
        trade_key = f"{sig_exit.strategy_id}:{sig_exit.tradingsymbol}"
        self.assertIn(trade_key, self.engine.active_trades)

    def test_exit_microstructure_gates_preserve_position_and_zero_frictions(self):
        """Verifies locked, crossed, and wide-spread quotes on exit reject and preserve exposure."""
        # 1. Establish open trade
        q_fresh = self._create_quote(exchange_timestamp_utc=self.now_utc)
        sig_buy = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        self.engine.process_signal(sig_buy, q_fresh)
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig_buy.signal_id))

        # Locked quote on exit
        q_locked = self._create_quote(
            exchange_timestamp_utc=self.now_utc,
            best_bid=Decimal("105.00"),
            best_ask=Decimal("105.00"),
            is_locked=True,
            quote_status="LOCKED",
        )
        sig_exit1 = self.signal_exit.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt1 = self.engine.process_signal(sig_exit1, q_locked)
        self.assertEqual(evt1.event_type, "ORDER_REJECTED")
        self.assertEqual(evt1.message, "REJECTED_LOCKED_QUOTE")
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "REJECTED_LOCKED_QUOTE")
        self.assertIsNone(trade.net_pnl)

        # Crossed quote on exit
        q_crossed = self._create_quote(
            exchange_timestamp_utc=self.now_utc,
            best_bid=Decimal("110.00"),
            best_ask=Decimal("105.00"),
            is_crossed=True,
            quote_status="CROSSED",
        )
        sig_exit2 = self.signal_exit.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt2 = self.engine.process_signal(sig_exit2, q_crossed)
        self.assertEqual(evt2.event_type, "ORDER_REJECTED")
        self.assertEqual(evt2.message, "REJECTED_CROSSED_BOOK")
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "REJECTED_CROSSED_BOOK")
        self.assertIsNone(trade.net_pnl)

        # Wide spread quote on exit (>2.5%)
        q_wide = self._create_quote(
            exchange_timestamp_utc=self.now_utc,
            best_bid=Decimal("100.00"),
            best_ask=Decimal("104.00"),  # 4% spread
        )
        sig_exit3 = self.signal_exit.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt3 = self.engine.process_signal(sig_exit3, q_wide)
        self.assertEqual(evt3.event_type, "ORDER_REJECTED")
        self.assertEqual(evt3.message, "REJECTED_EXCESSIVE_SPREAD")
        trade.refresh_from_db()
        self.assertEqual(trade.status, "PENDING_LIQUIDITY")
        self.assertEqual(trade.rejection_reason, "REJECTED_EXCESSIVE_SPREAD")
        self.assertIsNone(trade.net_pnl)
        self.assertEqual(trade.total_frictions, Decimal("0.00"))

    def test_public_process_signal_disallows_validation_time_bypass(self):
        """Verifies public process_signal() strictly disallows caller-supplied validation_time."""
        q_fresh = self._create_quote(exchange_timestamp_utc=self.now_utc)
        sig = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})

        # Calling with validation_time must raise TypeError
        with self.assertRaises(TypeError):
            self.engine.process_signal(
                sig,
                q_fresh,
                validation_time=self.now_utc,  # type: ignore[call-arg]
            )

    def test_stale_quote_cannot_bypass_engine_trusted_clock(self):
        """
        Verifies that an old quote is strictly rejected against the engine's trusted clock.
        Because public process_signal() cannot accept validation_time, callers cannot
        forge decision time to make stale quotes appear fresh.
        """
        # Quote is 15 seconds old relative to engine's trusted clock (now_utc)
        q_old = self._create_quote(
            exchange_timestamp_utc=self.now_utc - timedelta(seconds=15),
            is_stale=False,
            quote_status="VALID",
        )
        sig = self.signal_buy.model_copy(update={"signal_id": str(uuid.uuid4())})
        evt = self.engine.process_signal(sig, q_old)

        self.assertEqual(evt.event_type, "ORDER_REJECTED")
        self.assertEqual(evt.message, "REJECTED_STALE_QUOTE")
        self.assertIsNone(evt.fill_price)
        self.assertEqual(evt.fill_quantity, 0)

        # Database record confirmed rejected with zero fill, zero fees, zero PnL
        trade = PaperTradeLedger.objects.get(signal_id=uuid.UUID(sig.signal_id))
        self.assertEqual(trade.status, "REJECTED")
        self.assertEqual(trade.entry_fill_price, Decimal("0.00"))
        self.assertEqual(trade.total_frictions, Decimal("0.00"))
        self.assertIsNone(trade.gross_pnl)
        self.assertIsNone(trade.net_pnl)




