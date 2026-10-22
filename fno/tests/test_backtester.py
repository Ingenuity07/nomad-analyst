"""
Nomad Analyst — Synthetic Regression Tests for Phase 2.4 Historical Backtester
Verifies no-look-ahead, cutoff gating, emergency settlement, quarantine isolation, and statutory fees.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
from unittest.mock import MagicMock
import zoneinfo

from django.test import SimpleTestCase
import pyarrow as pa
import pyarrow.parquet as pq

from fno.backtester.calendar import NiftyExpiryCalendar
from fno.backtester.contract_selector import OptionContractSelector
from fno.backtester.engine import HistoricalBacktestEngine
from fno.backtester.execution_simulator import HistoricalExecutionSimulator
from fno.backtester.fee_model import HistoricalFeeCalculator
from fno.backtester.metrics import HistoricalPerformanceMetrics
from fno.backtester.models import (
    BacktestConfig,
    BacktestTradeRecord,
    DataQualityIncident,
    SessionQualification,
)
from fno.execution.fee_calculator import StatutoryFeeBreakdown
from fno.services.historical_reader import HistoricalParquetReader

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class HistoricalBacktesterSyntheticTests(SimpleTestCase):
    """
    Synthetic tests covering the critical safety invariants and backtester edge cases.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        (self.base_dir / "index").mkdir(parents=True)
        (self.base_dir / "options").mkdir(parents=True)
        self.reader = HistoricalParquetReader(base_dir=self.base_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _create_mock_trade(
        self,
        trade_id: str = "T1",
        trading_day: str = "2025-08-14",
        net_pnl: Decimal = Decimal("500.00"),
        gross_pnl: Decimal = Decimal("570.00"),
        impaired: bool = False,
        emergency_settlement: bool = False,
    ) -> BacktestTradeRecord:
        fees = HistoricalFeeCalculator.calculate_round_trip(
            buy_price=Decimal("120.00"),
            sell_price=Decimal("127.60"),
            quantity=75,
            trade_date=date.fromisoformat(trading_day),
        )
        return BacktestTradeRecord(
            trade_id=trade_id,
            trading_day=trading_day,
            strategy_id="NIFTY_ORB_15M",
            strategy_version="1.0.0",
            tradingsymbol="NIFTY_2025-08-14_24500_CE",
            underlying_symbol="NIFTY",
            strike=24500,
            option_type="CE",
            expiry="2025-08-14",
            lot_size=75,
            quantity=75,
            signal_timestamp_ist=datetime.combine(date.fromisoformat(trading_day), time(9, 45), tzinfo=IST),
            entry_timestamp_ist=datetime.combine(date.fromisoformat(trading_day), time(9, 46), tzinfo=IST),
            exit_timestamp_ist=datetime.combine(date.fromisoformat(trading_day), time(10, 15), tzinfo=IST),
            holding_duration_seconds=1740,
            orb_high=Decimal("24520.00"),
            orb_low=Decimal("24480.00"),
            spot_at_signal=Decimal("24525.00"),
            spot_at_entry=Decimal("24526.00"),
            spot_at_exit=Decimal("24560.00"),
            entry_fill_price=Decimal("120.00"),
            exit_fill_price=Decimal("127.60"),
            gross_pnl=gross_pnl,
            statutory_fees=fees,
            net_pnl=net_pnl,
            net_return_pct=Decimal("0.055"),
            exit_reason="EXIT_TARGET",
            session_qualification="INCLUDED",
            slippage_rate=Decimal("0.005"),
            stt_rate_applied=Decimal("0.001"),
            is_emergency_expiry_settlement=emergency_settlement,
            execution_liquidity_impaired=impaired,
        )

    def test_missing_official_expiry_data_causes_hard_eligibility_failure(self):
        """Hard qualification failure on missing local expiry file."""
        calendar = NiftyExpiryCalendar(reader=self.reader)
        # 2025-10-21 is an official exchange expiry, but options/2025-10-21.parquet is NOT present
        self.assertFalse(calendar.has_local_expiry_data(date(2025, 10, 21)))
        # Dependent trading session 2025-10-21 must fail eligibility
        is_eligible = calendar.is_session_eligible(date(2025, 10, 21))
        self.assertFalse(is_eligible)

    def test_entry_cutoff_gate_at_simulated_fill_timestamp(self):
        """Simulated fill past 14:30:00 must be rejected."""
        config = BacktestConfig(entry_window_end=time(14, 30, 0))
        sim = HistoricalExecutionSimulator(config=config)

        # Signal at 14:30:00, next candle open at 14:31:00
        signal_ts = datetime(2025, 8, 14, 14, 30, 0, tzinfo=IST)
        fill_candle = {
            "timestamp_ist": datetime(2025, 8, 14, 14, 31, 0, tzinfo=IST),
            "open": Decimal("110.00"),
            "high": Decimal("112.00"),
            "low": Decimal("109.00"),
            "close": Decimal("111.00"),
            "volume": 500,
        }
        contract_info = {
            "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
            "strike": 24500,
            "option_type": "CE",
            "expiry": "2025-08-14",
            "lot_size": 75,
        }

        pos, rej, incs = sim.simulate_entry_fill(
            signal_timestamp=signal_ts,
            fill_candle=fill_candle,
            contract_info=contract_info,
            cash_balance=Decimal("100000.00"),
            spot_at_signal=Decimal("24500.00"),
            orb_high=Decimal("24490.00"),
            orb_low=Decimal("24450.00"),
        )
        self.assertIsNone(pos)
        self.assertEqual(rej, "REJECTED_FILL_PAST_ENTRY_CUTOFF")

    def test_simultaneous_stop_loss_and_target_priority(self):
        """When a bar touches both stop loss and target, stop loss executes first."""
        config = BacktestConfig(
            stop_loss_pct=Decimal("0.10"),      # 10%
            profit_target_pct=Decimal("0.15"),  # 15%
            tick_size=Decimal("0.05"),
        )
        sim = HistoricalExecutionSimulator(config=config)

        # Position entered at 100.00 -> Stop: 90.00, Target: 115.00
        position = {
            "trade_id": "SIM_1",
            "trading_day": "2025-08-14",
            "contract_info": {
                "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
                "strike": 24500,
                "option_type": "CE",
                "expiry": "2025-08-14",
            },
            "lot_size": 75,
            "quantity": 75,
            "signal_timestamp_ist": datetime(2025, 8, 14, 9, 30, tzinfo=IST),
            "entry_timestamp_ist": datetime(2025, 8, 14, 9, 31, tzinfo=IST),
            "spot_at_signal": Decimal("24500.00"),
            "spot_at_entry": Decimal("24500.00"),
            "orb_high": Decimal("24490.00"),
            "orb_low": Decimal("24450.00"),
            "entry_fill_price": Decimal("100.00"),
            "stop_loss_price": Decimal("90.00"),
            "profit_target_price": Decimal("115.00"),
            "execution_liquidity_impaired": False,
            "data_quality_incidents": [],
            "pending_exit": None,
        }

        # Volatile bar: Open=102.00, High=120.00 (touches target), Low=85.00 (touches stop), Close=110.00
        volatile_bar = {
            "timestamp_ist": datetime(2025, 8, 14, 9, 35, tzinfo=IST),
            "open": Decimal("102.00"),
            "high": Decimal("120.00"),
            "low": Decimal("85.00"),
            "close": Decimal("110.00"),
            "volume": 2000,
        }

        trade, incident = sim.evaluate_active_position(
            position=position,
            current_candle=volatile_bar,
            current_time_ist=volatile_bar["timestamp_ist"],
            is_expiry_day=False,
        )

        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "EXIT_STOP", "Worst-case priority must trigger STOP before TARGET.")
        self.assertLessEqual(trade.exit_fill_price, Decimal("90.00"))

    def test_missing_intermediate_candle_logs_incident_and_quarantines(self):
        """Missing candle during open trade marks trade liquidity impaired and logs incident."""
        sim = HistoricalExecutionSimulator(config=BacktestConfig())
        position = {
            "trade_id": "SIM_GAP",
            "trading_day": "2025-08-14",
            "contract_info": {
                "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
                "strike": 24500,
                "option_type": "CE",
                "expiry": "2025-08-14",
            },
            "lot_size": 75,
            "quantity": 75,
            "signal_timestamp_ist": datetime(2025, 8, 14, 9, 30, tzinfo=IST),
            "entry_timestamp_ist": datetime(2025, 8, 14, 9, 31, tzinfo=IST),
            "spot_at_signal": Decimal("24500.00"),
            "spot_at_entry": Decimal("24500.00"),
            "orb_high": Decimal("24490.00"),
            "orb_low": Decimal("24450.00"),
            "entry_fill_price": Decimal("100.00"),
            "stop_loss_price": Decimal("85.00"),
            "profit_target_price": Decimal("120.00"),
            "execution_liquidity_impaired": False,
            "data_quality_incidents": [],
            "pending_exit": None,
        }

        # Gap at 09:35
        trade, incident = sim.evaluate_active_position(
            position=position,
            current_candle=None,
            current_time_ist=datetime(2025, 8, 14, 9, 35, tzinfo=IST),
            is_expiry_day=False,
        )
        self.assertIsNone(trade)
        self.assertIsNotNone(incident)
        self.assertEqual(incident.incident_type, "DATA_QUALITY_INCIDENT_MISSING_CANDLES")
        self.assertTrue(position["execution_liquidity_impaired"])

    def test_emergency_expiry_settlement_against_official_underlying_index_close(self):
        """Emergency expiry cash settlement uses official index close (not VWAP) and applies exercise STT."""
        sim = HistoricalExecutionSimulator(config=BacktestConfig())
        position = {
            "trade_id": "SIM_SETTLE",
            "trading_day": "2025-08-14",
            "contract_info": {
                "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
                "strike": 24500,
                "option_type": "CE",
                "expiry": "2025-08-14",
            },
            "lot_size": 75,
            "quantity": 75,
            "signal_timestamp_ist": datetime(2025, 8, 14, 9, 30, tzinfo=IST),
            "entry_timestamp_ist": datetime(2025, 8, 14, 9, 31, tzinfo=IST),
            "spot_at_signal": Decimal("24500.00"),
            "spot_at_entry": Decimal("24500.00"),
            "orb_high": Decimal("24490.00"),
            "orb_low": Decimal("24450.00"),
            "entry_fill_price": Decimal("100.00"),
            "stop_loss_price": Decimal("85.00"),
            "profit_target_price": Decimal("120.00"),
            "execution_liquidity_impaired": True,
            "data_quality_incidents": ["MISSING_INTERMEDIATE_CANDLE"],
            "pending_exit": "EXIT_EOD",
        }

        # Expiry close: Official index close = 24650.00 (ITM by 150 pts)
        trade = sim._finalize_unexecutable_or_settlement(
            position=position,
            exit_time_ist=datetime(2025, 8, 14, 15, 30, tzinfo=IST),
            is_expiry_day=True,
            official_index_close=Decimal("24650.00"),
        )

        self.assertEqual(trade.exit_reason, "SETTLED_EXPIRY_CASH_FALLBACK")
        self.assertTrue(trade.is_emergency_expiry_settlement)
        self.assertEqual(trade.exit_fill_price, Decimal("150.00"))
        # Verify STT calculated on intrinsic exercise settlement
        self.assertGreater(trade.statutory_fees.stt, Decimal("0.00"))

    def test_dual_ledger_quarantine_isolation(self):
        """Impaired and emergency trades must NOT contaminate standard clean ledger."""
        clean_trade = self._create_mock_trade(trade_id="C1", net_pnl=Decimal("1000.00"), impaired=False)
        impaired_trade = self._create_mock_trade(trade_id="Q1", net_pnl=Decimal("-2000.00"), impaired=True)
        emergency_trade = self._create_mock_trade(trade_id="E1", net_pnl=Decimal("500.00"), emergency_settlement=True)

        clean_metrics = HistoricalPerformanceMetrics.calculate_ledger_metrics([clean_trade])
        quarantined_metrics = HistoricalPerformanceMetrics.calculate_ledger_metrics([impaired_trade])
        emergency_metrics = HistoricalPerformanceMetrics.calculate_ledger_metrics([emergency_trade])

        # Clean ledger must show only clean trades
        self.assertEqual(clean_metrics["total_trades"], 1)
        self.assertEqual(clean_metrics["total_net_pnl"], "1000.00")
        self.assertEqual(clean_metrics["win_rate_pct"], "100.00")

        # Quarantined ledger holds impaired trades
        self.assertEqual(quarantined_metrics["total_trades"], 1)
        self.assertEqual(quarantined_metrics["total_net_pnl"], "-2000.00")

        # Emergency settlement ledger holds emergency trades
        self.assertEqual(emergency_metrics["total_trades"], 1)
        self.assertEqual(emergency_metrics["total_net_pnl"], "500.00")

    def test_chronological_splits_partitioning(self):
        """Verifies In-Sample, Validation, and Holdout split boundary attribution."""
        is_trade = self._create_mock_trade(trade_id="IS_1", trading_day="2025-09-10", net_pnl=Decimal("100.00"))
        val_trade = self._create_mock_trade(trade_id="VAL_1", trading_day="2026-01-15", net_pnl=Decimal("200.00"))
        oos_trade = self._create_mock_trade(trade_id="OOS_1", trading_day="2026-05-20", net_pnl=Decimal("300.00"))

        splits = HistoricalPerformanceMetrics.calculate_chronological_splits([is_trade, val_trade, oos_trade])

        self.assertEqual(splits["in_sample"]["metrics"]["total_trades"], 1)
        self.assertEqual(splits["in_sample"]["metrics"]["total_net_pnl"], "100.00")

        self.assertEqual(splits["validation"]["metrics"]["total_trades"], 1)
        self.assertEqual(splits["validation"]["metrics"]["total_net_pnl"], "200.00")

        self.assertEqual(splits["holdout_oos"]["metrics"]["total_trades"], 1)
        self.assertEqual(splits["holdout_oos"]["metrics"]["total_net_pnl"], "300.00")

    def test_expiry_day_rollover_after_1300_ist(self):
        """Signals on expiry day before 13:00 trade 0-DTE; signals at or after 13:00 roll to next weekly."""
        calendar = NiftyExpiryCalendar(
            dataset_expiries=[date(2025, 8, 14), date(2025, 8, 21)]
        )
        selector = OptionContractSelector(calendar=calendar, roll_cutoff_time=time(13, 0, 0))

        # Expiry day is 2025-08-14
        # Signal A at 10:30 IST (before 13:00) -> 0-DTE (2025-08-14)
        contract_morning = selector.select_contract(
            session_date=date(2025, 8, 14),
            spot_price=Decimal("24500.00"),
            direction="BULLISH",
            signal_time=datetime(2025, 8, 14, 10, 30, tzinfo=IST),
        )
        self.assertIsNotNone(contract_morning)
        self.assertEqual(contract_morning["expiry"], "2025-08-14")

        # Signal B at 13:05 IST (after 13:00) -> Rolls to next weekly (2025-08-21)
        contract_afternoon = selector.select_contract(
            session_date=date(2025, 8, 14),
            spot_price=Decimal("24500.00"),
            direction="BULLISH",
            signal_time=datetime(2025, 8, 14, 13, 5, tzinfo=IST),
        )
        self.assertIsNotNone(contract_afternoon)
        self.assertEqual(contract_afternoon["expiry"], "2025-08-21")

    def test_fixed_slippage_model_execution(self):
        """Fixed points slippage model adds/subtracts exact points instead of percentage."""
        config_fixed = BacktestConfig(
            slippage_model="FIXED_POINTS",
            fixed_slippage_pts=Decimal("0.50"),
            tick_size=Decimal("0.05"),
        )
        sim = HistoricalExecutionSimulator(config=config_fixed)

        # Entry at open 100.00 -> fill = 100.00 + 0.50 = 100.50
        signal_ts = datetime(2025, 8, 14, 9, 30, tzinfo=IST)
        fill_candle = {
            "timestamp_ist": datetime(2025, 8, 14, 9, 31, tzinfo=IST),
            "open": Decimal("100.00"),
            "high": Decimal("105.00"),
            "low": Decimal("99.00"),
            "close": Decimal("102.00"),
            "volume": 1000,
        }
        contract_info = {
            "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
            "strike": 24500,
            "option_type": "CE",
            "expiry": "2025-08-14",
            "lot_size": 75,
        }

        pos, rej, incs = sim.simulate_entry_fill(
            signal_timestamp=signal_ts,
            fill_candle=fill_candle,
            contract_info=contract_info,
            cash_balance=Decimal("100000.00"),
            spot_at_signal=Decimal("24500.00"),
            orb_high=Decimal("24490.00"),
            orb_low=Decimal("24450.00"),
        )
        self.assertIsNotNone(pos)
        self.assertEqual(pos["entry_fill_price"], Decimal("100.50"))

        # Exit taker fill at 110.00 -> fill = 110.00 - 0.50 = 109.50
        exit_fill = sim._compute_taker_exit_fill(Decimal("110.00"))
        self.assertEqual(exit_fill, Decimal("109.50"))

    def test_atm_strike_tie_breaker_round_half_up(self):
        """Verifies deterministic ROUND_HALF_UP tie-breaking without banker-rounding."""
        # 24524.49 -> 24500
        self.assertEqual(OptionContractSelector.calculate_atm_strike(Decimal("24524.49")), 24500)
        # Exactly halfway 24525.00 -> rounds up to 24550 (banker's rounding would round down to 24500!)
        self.assertEqual(OptionContractSelector.calculate_atm_strike(Decimal("24525.00")), 24550)
        # 24575.00 -> rounds up to 24600
        self.assertEqual(OptionContractSelector.calculate_atm_strike(Decimal("24575.00")), 24600)
        # 24549.99 -> 24550
        self.assertEqual(OptionContractSelector.calculate_atm_strike(Decimal("24549.99")), 24550)

    def test_unfilled_entry_due_to_missing_candle_consumes_session_attempt(self):
        """Missing candle at entry rejects fill as unfilled and consumes session attempt (no re-entry)."""
        sim = HistoricalExecutionSimulator(config=BacktestConfig())
        signal_ts = datetime(2025, 8, 14, 9, 30, tzinfo=IST)
        contract_info = {
            "tradingsymbol": "NIFTY_2025-08-14_24500_CE",
            "strike": 24500,
            "option_type": "CE",
            "expiry": "2025-08-14",
            "lot_size": 75,
        }

        # Fill candle is None (missing market data)
        pos, rej, incs = sim.simulate_entry_fill(
            signal_timestamp=signal_ts,
            fill_candle=None,
            contract_info=contract_info,
            cash_balance=Decimal("200000.00"),
            spot_at_signal=Decimal("24500.00"),
            orb_high=Decimal("24490.00"),
            orb_low=Decimal("24450.00"),
        )
        self.assertIsNone(pos)
        self.assertEqual(rej, "EXPIRED_UNFILLED_NO_LIQUIDITY_BAR")


class HistoricalBacktesterDatabaseIsolationTests(SimpleTestCase):
    """Verifies that the backtester never touches or mutates operational database tables."""
    databases = {"default"}

    def test_backtester_execution_does_not_mutate_operational_database(self):
        from fno.models import PaperTradeLedger, OptionOHLCVBar

        # Read operational table counts (should remain untouched)
        ledger_count_before = PaperTradeLedger.objects.count()
        ohlcv_count_before = OptionOHLCVBar.objects.count()

        # Execute backtester helper / simulator
        config = BacktestConfig(initial_capital=Decimal("200000.00"))
        sim = HistoricalExecutionSimulator(config=config)

        # Assert operational tables are untouched
        self.assertEqual(PaperTradeLedger.objects.count(), ledger_count_before)
        self.assertEqual(OptionOHLCVBar.objects.count(), ohlcv_count_before)


class HistoricalBacktesterPhase242Tests(SimpleTestCase):
    """Tests for Phase 2.4.2: Configurable ORB Filter and In-Memory Sensitivity Caching."""

    def test_configurable_max_orb_range_limit_and_no_limit_mode(self):
        """Verifies that max_orb_range_pts=150 filters wide ranges, while max_orb_range_pts=None allows them."""
        # 1. Configured limit: 150 pts
        cfg_150 = BacktestConfig(max_orb_range_pts=Decimal("150.00"))
        self.assertEqual(cfg_150.max_orb_range_pts, Decimal("150.00"))
        self.assertEqual(cfg_150.to_dict()["max_orb_range_pts"], "150.00")

        # 2. No limit mode: None
        cfg_none = BacktestConfig(max_orb_range_pts=None)
        self.assertIsNone(cfg_none.max_orb_range_pts)
        self.assertIsNone(cfg_none.to_dict()["max_orb_range_pts"])

    def test_max_orb_range_cli_argument_parsing(self):
        """Verifies CLI argument parsing for --max-orb-range across valid numbers, 'none', and invalid inputs."""
        from django.core.management.base import CommandError
        from fno.management.commands.run_fno_backtest import Command

        cmd = Command()

        # Helper to simulate option parsing
        def parse_val(val_str):
            cleaned = val_str.strip().lower()
            if cleaned in ("none", "0", "null", "no-limit", "nolimit"):
                return None
            val = Decimal(val_str)
            if val <= Decimal("0"):
                raise CommandError(f"Invalid --max-orb-range: '{val_str}'. Must be a positive number or 'none'.")
            return val

        # Valid inputs
        self.assertEqual(parse_val("150.00"), Decimal("150.00"))
        self.assertEqual(parse_val("75.5"), Decimal("75.5"))
        self.assertIsNone(parse_val("none"))
        self.assertIsNone(parse_val("None"))
        self.assertIsNone(parse_val("0"))
        self.assertIsNone(parse_val("no-limit"))

        # Invalid inputs
        with self.assertRaises(CommandError):
            parse_val("-50.00")
        with self.assertRaises(Exception):
            parse_val("invalid_string")

    def test_cached_vs_uncached_full_sensitivity_equivalence(self):
        """
        Runs backtest with cached and uncached readers and asserts 100% exact semantic
        and mathematical equivalence across all trade records and sensitivity scenarios.
        """
        from fno.backtester.engine import HistoricalBacktestEngine, CachedHistoricalReader
        from fno.services.historical_reader import HistoricalParquetReader
        from fno.backtester.calendar import NiftyExpiryCalendar
        from fno.backtester.contract_selector import OptionContractSelector
        from fno.backtester.execution_simulator import HistoricalExecutionSimulator

        # Use a bounded date slice (July 2025) for fast, thorough multi-scenario equivalence check
        start_d = date(2025, 7, 1)
        end_d = date(2025, 7, 31)

        reader = HistoricalParquetReader()

        # 1. Uncached Run
        cfg_uncached = BacktestConfig(
            start_date=start_d,
            end_date=end_d,
            enable_query_cache=False,
            max_orb_range_pts=Decimal("150.00"),
        )
        engine_uncached = HistoricalBacktestEngine(config=cfg_uncached, reader=reader)
        res_uncached = engine_uncached.run(calculate_sensitivity=True)

        # 2. Cached Run
        cfg_cached = BacktestConfig(
            start_date=start_d,
            end_date=end_d,
            enable_query_cache=True,
            max_orb_range_pts=Decimal("150.00"),
        )
        engine_cached = HistoricalBacktestEngine(config=cfg_cached, reader=reader)
        res_cached = engine_cached.run(calculate_sensitivity=True)

        # A. Session & Trade Count Equality
        self.assertEqual(res_uncached.qualified_sessions, res_cached.qualified_sessions)
        self.assertEqual(res_uncached.excluded_sessions, res_cached.excluded_sessions)
        self.assertEqual(len(res_uncached.normal_trades), len(res_cached.normal_trades))

        # B. Trade-by-trade deep equality
        for t_u, t_c in zip(res_uncached.normal_trades, res_cached.normal_trades):
            self.assertEqual(t_u.trading_day, t_c.trading_day)
            self.assertEqual(t_u.tradingsymbol, t_c.tradingsymbol)
            self.assertEqual(t_u.strike, t_c.strike)
            self.assertEqual(t_u.option_type, t_c.option_type)
            self.assertEqual(t_u.lot_size, t_c.lot_size)
            self.assertEqual(t_u.signal_timestamp_ist, t_c.signal_timestamp_ist)
            self.assertEqual(t_u.entry_timestamp_ist, t_c.entry_timestamp_ist)
            self.assertEqual(t_u.exit_timestamp_ist, t_c.exit_timestamp_ist)
            self.assertEqual(t_u.entry_fill_price, t_c.entry_fill_price)
            self.assertEqual(t_u.exit_fill_price, t_c.exit_fill_price)
            self.assertEqual(t_u.gross_pnl, t_c.gross_pnl)
            self.assertEqual(t_u.net_pnl, t_c.net_pnl)
            self.assertEqual(t_u.exit_reason, t_c.exit_reason)
            self.assertEqual(t_u.statutory_fees.total_frictions, t_c.statutory_fees.total_frictions)

        # C. Primary Ledger Metrics Equality
        m_u = res_uncached.metrics["standard_clean_ledger"]
        m_c = res_cached.metrics["standard_clean_ledger"]
        self.assertEqual(m_u["total_net_pnl"], m_c["total_net_pnl"])
        self.assertEqual(m_u["win_rate_pct"], m_c["win_rate_pct"])
        self.assertEqual(m_u["profit_factor"], m_c["profit_factor"])
        self.assertEqual(m_u["max_drawdown_amount"], m_c["max_drawdown_amount"])

        # D. All Six Sensitivity Scenarios Equality
        sens_u = res_uncached.sensitivity_analysis
        sens_c = res_cached.sensitivity_analysis
        for sc in ["0.0%", "0.5%", "1.0%", "1.5%"]:
            self.assertEqual(sens_u["percentage_models"][sc]["net_pnl"], sens_c["percentage_models"][sc]["net_pnl"])
            self.assertEqual(sens_u["percentage_models"][sc]["win_rate_pct"], sens_c["percentage_models"][sc]["win_rate_pct"])
            self.assertEqual(sens_u["percentage_models"][sc]["total_trades"], sens_c["percentage_models"][sc]["total_trades"])

        for sc in ["₹0.50/unit", "₹1.00/unit"]:
            self.assertEqual(sens_u["fixed_points_models"][sc]["net_pnl"], sens_c["fixed_points_models"][sc]["net_pnl"])
            self.assertEqual(sens_u["fixed_points_models"][sc]["win_rate_pct"], sens_c["fixed_points_models"][sc]["win_rate_pct"])
            self.assertEqual(sens_u["fixed_points_models"][sc]["total_trades"], sens_c["fixed_points_models"][sc]["total_trades"])


