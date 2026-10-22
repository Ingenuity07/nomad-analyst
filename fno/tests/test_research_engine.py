"""
Nomad Analyst — Phase 3.1 Research Engine & ORB Baseline Regression Tests
Verifies bit-for-bit trade-level equivalence between MultiStrategyBacktestEngine
evaluating NiftyOrbStrategyPlugin and the authoritative Phase 2.4.2 baseline report.
"""

from decimal import Decimal
import json
from pathlib import Path
from unittest import TestCase

from django.test import SimpleTestCase

from fno.backtester.models import BacktestConfig
from fno.research.engine import MultiStrategyBacktestEngine
from fno.research.interfaces import (
    BaseStrategyConfig,
    ExecutionOutcomeType,
    SessionContext,
    SignalDirection,
    StrategySignal,
)
from fno.research.strategies.orb_15m import NiftyOrbStrategyPlugin, OrbStrategyConfig


class StrategyInterfaceContractTests(TestCase):
    """Verifies that strategy interfaces and signals behave as specified."""

    def test_strategy_signal_immutability(self):
        from datetime import datetime, time
        import zoneinfo

        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        sig = StrategySignal(
            signal_id="SIG-TEST-001",
            strategy_id="STRAT-TEST",
            signal_timestamp_ist=datetime(2025, 10, 1, 9, 35, tzinfo=ist),
            direction=SignalDirection.BUY_CE,
            index_spot_price=Decimal("25100.50"),
            stop_loss_pct=Decimal("0.15"),
            profit_target_pct=Decimal("0.20"),
            max_holding_minutes=45,
            entry_cutoff_time=time(14, 30),
            trigger_reason="Test Trigger",
        )
        self.assertEqual(sig.signal_id, "SIG-TEST-001")
        self.assertEqual(sig.direction, SignalDirection.BUY_CE)
        with self.assertRaises(Exception):
            sig.direction = SignalDirection.BUY_PE  # Immutable dataclass

    def test_orb_strategy_config_encapsulation(self):
        config = OrbStrategyConfig(
            min_orb_range_pts=Decimal("20.00"),
            max_orb_range_pts=Decimal("120.00"),
        )
        self.assertEqual(config.strategy_id, "STRAT-ORB-15M")
        self.assertEqual(config.min_orb_range_pts, Decimal("20.00"))
        self.assertEqual(config.max_orb_range_pts, Decimal("120.00"))


class ResearchEngineOrbRegressionTests(TestCase):
    """
    Authoritative regression suite verifying that MultiStrategyBacktestEngine
    with NiftyOrbStrategyPlugin reproduces the Phase 2.4.2 baseline bit-for-bit.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report_path = Path("docs/audits/fno_backtest_report_orb15m.json")
        if not cls.report_path.exists():
            raise FileNotFoundError(f"Baseline report missing at {cls.report_path}")
        with open(cls.report_path, "r") as f:
            cls.saved_report = json.load(f)

        # Run MultiStrategyBacktestEngine with identical config
        orb_config = OrbStrategyConfig(
            max_orb_range_pts=Decimal("150.00"),
            min_orb_range_pts=Decimal("15.00"),
            stop_loss_pct=Decimal("0.15"),
            profit_target_pct=Decimal("0.20"),
            max_holding_minutes=45,
        )
        plugin = NiftyOrbStrategyPlugin(config=orb_config)
        cls.engine = MultiStrategyBacktestEngine(
            strategy=plugin,
            config=BacktestConfig(
                max_orb_range_pts=Decimal("150.00"),
                enable_query_cache=True,
            ),
        )
        cls.result = cls.engine.run(calculate_sensitivity=True)

    def test_session_accounting_equivalence(self):
        """Verifies total trading days, qualified sessions, and excluded sessions."""
        self.assertEqual(self.result.total_trading_days, 242)
        self.assertEqual(self.result.qualified_sessions, 204)
        self.assertEqual(self.result.excluded_sessions, 38)

        # Check exclusion breakdown
        exclusions = [s for s in self.result.session_summaries if s.qualification != "QUALIFIED_FULL_SESSION"]
        self.assertEqual(len(exclusions), 38)

        missing_expiry = [s for s in exclusions if s.qualification == "EXCLUDED_MISSING_EXPIRY_DATA"]
        self.assertEqual(len(missing_expiry), 19)

        wide_orb = [s for s in exclusions if s.qualification == "EXCLUDED_RANGE_TOO_WIDE"]
        self.assertEqual(len(wide_orb), 18)

        data_gap = [s for s in exclusions if s.qualification == "EXCLUDED_DATA_GAP"]
        self.assertEqual(len(data_gap), 1)

    def test_execution_resolution_breakdown(self):
        """
        Verifies execution outcome counts:
        - 200 Clean Executed Trades
        - 0 Quarantined Trades
        - 4 Unfilled Entry Attempts (EXPIRED_UNFILLED_NO_LIQUIDITY_BAR)
        - 0 Rejected Attempts
        - 0 No Signal Days (every qualified day had a breakout)
        """
        self.assertEqual(len(self.result.normal_trades), 200)
        self.assertEqual(len(self.result.quarantined_trades), 0)

        # 4 Unfilled Entry Attempts
        unfilled = [
            s for s in self.result.session_summaries
            if s.qualification == "QUALIFIED_FULL_SESSION" and s.breakout_detected and not s.trade_executed
        ]
        self.assertEqual(len(unfilled), 4)
        unfilled_dates = {s.trading_day for s in unfilled}
        expected_unfilled_dates = {"2026-06-04", "2026-06-05", "2026-06-08", "2026-06-09"}
        self.assertEqual(unfilled_dates, expected_unfilled_dates)
        for s in unfilled:
            self.assertEqual(s.rejection_reason, "EXPIRED_UNFILLED_NO_LIQUIDITY_BAR")

    def test_headline_financial_metrics_equivalence(self):
        """Verifies Net P&L, Profit Factor, Drawdown, and Win Rate at baseline 0.5% slippage."""
        metrics = self.result.metrics["standard_clean_ledger"]
        saved_metrics = self.saved_report["metrics"]["standard_clean_ledger"]

        self.assertEqual(metrics["total_trades"], 200)
        self.assertEqual(metrics["winning_trades"], 82)
        self.assertEqual(metrics["losing_trades"], 118)
        self.assertEqual(metrics["win_rate_pct"], "41.00")
        self.assertEqual(metrics["total_net_pnl"], "-42080.740")
        self.assertEqual(metrics["profit_factor"], "0.7714")
        self.assertEqual(metrics["total_gross_pnl"], "-29562.25")
        self.assertEqual(metrics["total_frictions"], "12518.490")
        self.assertEqual(metrics["max_drawdown_amount"], "42256.820")
        self.assertEqual(metrics["max_drawdown_pct"], "21.13")
        self.assertEqual(metrics["expectancy_per_trade"], "-210.40")

        # Compare directly against saved report values
        for key in ["total_trades", "winning_trades", "losing_trades", "win_rate_pct",
                    "total_net_pnl", "profit_factor", "total_gross_pnl", "total_frictions",
                    "max_drawdown_amount", "max_drawdown_pct", "expectancy_per_trade"]:
            self.assertEqual(metrics[key], saved_metrics[key], f"Mismatch in metric {key}")

    def test_trade_level_bit_for_bit_equivalence(self):
        """Verifies every single executed trade matches the saved report."""
        saved_trades = self.saved_report["normal_trades"]
        self.assertEqual(len(self.result.normal_trades), len(saved_trades))

        for idx, (res_t, saved_t) in enumerate(zip(self.result.normal_trades, saved_trades)):
            self.assertEqual(res_t.trading_day, saved_t["trading_day"], f"Trade {idx} date mismatch")
            self.assertEqual(res_t.tradingsymbol, saved_t["tradingsymbol"], f"Trade {idx} symbol mismatch")
            self.assertEqual(res_t.strike, saved_t["strike"], f"Trade {idx} strike mismatch")
            self.assertEqual(res_t.option_type, saved_t["option_type"], f"Trade {idx} option_type mismatch")
            self.assertEqual(res_t.lot_size, saved_t["lot_size"], f"Trade {idx} lot_size mismatch")
            self.assertEqual(res_t.quantity, saved_t["quantity"], f"Trade {idx} quantity mismatch")
            self.assertEqual(res_t.signal_timestamp_ist.isoformat(), saved_t["signal_timestamp_ist"], f"Trade {idx} signal_timestamp mismatch")
            self.assertEqual(res_t.entry_timestamp_ist.isoformat(), saved_t["entry_timestamp_ist"], f"Trade {idx} entry_timestamp mismatch")
            self.assertEqual(res_t.exit_timestamp_ist.isoformat(), saved_t["exit_timestamp_ist"], f"Trade {idx} exit_timestamp mismatch")
            self.assertEqual(str(res_t.entry_fill_price), saved_t["entry_fill_price"], f"Trade {idx} entry_fill_price mismatch")
            self.assertEqual(str(res_t.exit_fill_price), saved_t["exit_fill_price"], f"Trade {idx} exit_fill_price mismatch")
            self.assertEqual(str(res_t.gross_pnl), saved_t["gross_pnl"], f"Trade {idx} gross_pnl mismatch")
            self.assertEqual(str(res_t.net_pnl), saved_t["net_pnl"], f"Trade {idx} net_pnl mismatch")
            self.assertEqual(res_t.exit_reason, saved_t["exit_reason"], f"Trade {idx} exit_reason mismatch")
            self.assertEqual(res_t.to_dict()["statutory_fees"], saved_t["statutory_fees"], f"Trade {idx} statutory fees mismatch")

    def test_slippage_sensitivity_grid_equivalence(self):
        """Verifies all six sensitivity scenarios match the saved report bit-for-bit."""
        saved_sens = self.saved_report["sensitivity_analysis"]
        res_sens = self.result.sensitivity_analysis

        # Check percentage models: 0.0%, 0.5%, 1.0%, 1.5%
        for label in ["0.0%", "0.5%", "1.0%", "1.5%"]:
            self.assertIn(label, res_sens["percentage_models"])
            res_item = res_sens["percentage_models"][label]
            saved_item = saved_sens["percentage_models"][label]
            self.assertEqual(res_item["total_trades"], saved_item["total_trades"])
            self.assertEqual(res_item["net_pnl"], saved_item["net_pnl"], f"Mismatch at percentage {label}")
            self.assertEqual(res_item["profit_factor"], saved_item["profit_factor"], f"PF mismatch at {label}")
            self.assertEqual(res_item["max_drawdown_amount"], saved_item["max_drawdown_amount"], f"DD mismatch at {label}")

        # Check fixed points models: ₹0.50/unit, ₹1.00/unit
        for label in ["₹0.50/unit", "₹1.00/unit"]:
            self.assertIn(label, res_sens["fixed_points_models"])
            res_item = res_sens["fixed_points_models"][label]
            saved_item = saved_sens["fixed_points_models"][label]
            self.assertEqual(res_item["total_trades"], saved_item["total_trades"])
            self.assertEqual(res_item["net_pnl"], saved_item["net_pnl"], f"Mismatch at fixed {label}")
            self.assertEqual(res_item["profit_factor"], saved_item["profit_factor"], f"PF mismatch at {label}")
            self.assertEqual(res_item["max_drawdown_amount"], saved_item["max_drawdown_amount"], f"DD mismatch at {label}")
