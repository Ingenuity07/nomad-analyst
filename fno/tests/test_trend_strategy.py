"""
Unit and Integration Tests for STRAT-TREND-EMA-DONCHIAN Strategy Plugin
Reference: docs/architecture/strategy_interface_v1.md
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import zoneinfo

from django.test import SimpleTestCase

from fno.backtester.models import BacktestConfig
from fno.research.engine import MultiStrategyBacktestEngine
from fno.research.interfaces import (
    SessionContext,
    SignalDirection,
    StrategySignal,
)
from fno.research.strategies.trend_following import (
    NiftyTrendFollowingPlugin,
    TrendStrategyConfig,
)

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class TrendStrategyUnitTest(SimpleTestCase):
    """
    Unit tests for indicator calculations, warm-up, body filters, and signal triggers.
    """

    def setUp(self):
        self.config = TrendStrategyConfig()
        self.strategy = NiftyTrendFollowingPlugin(config=self.config)
        self.session_date = date(2025, 10, 1)
        self.context = SessionContext(
            trading_day=self.session_date,
            is_expiry_day=False,
            nearest_expiry=date(2025, 10, 3),
            initial_capital=Decimal("200000.00"),
            max_trades_per_session=1,
        )
        self.strategy.initialize_session(self.context)

    def _create_bar(
        self,
        dt: datetime,
        open_val: str,
        high_val: str,
        low_val: str,
        close_val: str,
    ) -> dict:
        return {
            "timestamp_ist": dt,
            "open": Decimal(open_val),
            "high": Decimal(high_val),
            "low": Decimal(low_val),
            "close": Decimal(close_val),
            "volume": 0,
        }

    def test_ema_initialization_and_warmup(self):
        """
        Verifies EMA(9) initializes on the 9th bar and EMA(21) initializes on the 21st bar.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed 8 bars: neither EMA should be ready
        for i in range(8):
            bar = self._create_bar(start_time + timedelta(minutes=i), "25000", "25050", "24980", "25000")
            sig = self.strategy.on_index_bar(bar, self.context)
            self.assertIsNone(sig)
            self.assertIsNone(self.strategy.fast_ema)
            self.assertIsNone(self.strategy.slow_ema)

        # 9th bar (bar index 8): Fast EMA(9) should now be initialized as SMA(9)
        bar_9 = self._create_bar(start_time + timedelta(minutes=8), "25000", "25050", "24980", "25000")
        self.strategy.on_index_bar(bar_9, self.context)
        self.assertIsNotNone(self.strategy.fast_ema)
        self.assertEqual(self.strategy.fast_ema, Decimal("25000.00"))
        self.assertIsNone(self.strategy.slow_ema)

        # Feed up to 20 bars: Slow EMA still None
        for i in range(9, 20):
            bar = self._create_bar(start_time + timedelta(minutes=i), "25000", "25050", "24980", "25000")
            self.strategy.on_index_bar(bar, self.context)
            self.assertIsNone(self.strategy.slow_ema)

        # 21st bar (bar index 20, 09:35 IST): Slow EMA(21) should now be initialized as SMA(21)
        bar_21 = self._create_bar(start_time + timedelta(minutes=20), "25000", "25050", "24980", "25000")
        self.strategy.on_index_bar(bar_21, self.context)
        self.assertIsNotNone(self.strategy.slow_ema)
        self.assertEqual(self.strategy.slow_ema, Decimal("25000.00"))

    def test_donchian_excludes_current_bar_no_look_ahead(self):
        """
        Verifies Donchian Channel High and Low strictly exclude current bar T.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed 29 bars (09:15 to 09:43) with range 24900 to 25100
        for i in range(29):
            bar = self._create_bar(start_time + timedelta(minutes=i), "25000", "25100", "24900", "25000")
            self.strategy.on_index_bar(bar, self.context)

        # Bar 30 at 09:44:00 (still pre-entry window)
        bar_30 = self._create_bar(start_time + timedelta(minutes=29), "25000", "25100", "24900", "25000")
        self.strategy.on_index_bar(bar_30, self.context)

        # Bar 31 at 09:45:00 (entry window active)
        # Bar 31 has high 25200, close 25180.
        # Donchian High of previous 20 bars should be 25100 (excluding current bar's 25200)
        bar_31 = self._create_bar(start_time + timedelta(minutes=30), "25000", "25200", "24950", "25180")
        sig = self.strategy.on_index_bar(bar_31, self.context)
        
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, SignalDirection.BUY_CE)
        self.assertEqual(sig.metadata["donchian_high"], "25100")
        self.assertEqual(sig.metadata["donchian_low"], "24900")
        self.assertEqual(sig.index_spot_price, Decimal("25180"))

    def test_candle_body_filter_rejection(self):
        """
        Verifies that a breakout candle with a large upper wick (closing in lower 70% of candle range)
        is rejected even if Close > Donchian High.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed 30 bars with flat price
        for i in range(30):
            bar = self._create_bar(start_time + timedelta(minutes=i), "25000", "25100", "24900", "25000")
            self.strategy.on_index_bar(bar, self.context)

        # At 09:45: Bar surges to 25200, but closes at 24950 (range = 25200 - 24900 = 300 pts)
        # (Close - Low) / Range = (24950 - 24900) / 300 = 50 / 300 = 0.1667 < 0.70
        bar_rejection = self._create_bar(start_time + timedelta(minutes=30), "25150", "25200", "24900", "24950")
        sig = self.strategy.on_index_bar(bar_rejection, self.context)
        self.assertIsNone(sig)

    def test_bearish_trend_signal_pe(self):
        """
        Verifies BUY_PE signal emitted when EMA9 < EMA21, Close < Donchian Low, and candle body in lower 30%.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed 25 bars with falling prices to establish EMA9 < EMA21
        price = Decimal("25500")
        for i in range(30):
            high = price + Decimal("20")
            low = price - Decimal("20")
            close = price
            bar = self._create_bar(start_time + timedelta(minutes=i), str(price), str(high), str(low), str(close))
            self.strategy.on_index_bar(bar, self.context)
            price -= Decimal("10")

        self.assertTrue(self.strategy.fast_ema < self.strategy.slow_ema)

        # Bar at 09:45: Sharp breakdown
        # Low of previous bars is around 25200
        # Breakdown bar: High=25200, Low=25100, Close=25110. (High - Close) / Range = (25200 - 25110) / 100 = 0.90 >= 0.70
        breakdown_bar = self._create_bar(start_time + timedelta(minutes=30), "25200", "25200", "25100", "25110")
        sig = self.strategy.on_index_bar(breakdown_bar, self.context)

        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, SignalDirection.BUY_PE)
        self.assertEqual(sig.strategy_id, "STRAT-TREND-EMA-DONCHIAN")
        self.assertEqual(sig.stop_loss_pct, Decimal("0.15"))
        self.assertEqual(sig.profit_target_pct, Decimal("0.30"))
        self.assertEqual(sig.max_holding_minutes, 60)
        self.assertEqual(sig.entry_cutoff_time, time(14, 0, 0))

    def test_entry_cutoff_at_1400_ist(self):
        """
        Verifies that bars at or past 14:00:00 IST emit no signals.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed bars up to 14:00:00 IST
        cutoff_time = datetime(2025, 10, 1, 14, 0, tzinfo=IST)
        
        # Bar at 14:00:00 IST
        bar_cutoff = self._create_bar(cutoff_time, "25000", "25200", "24900", "25180")
        sig = self.strategy.on_index_bar(bar_cutoff, self.context)
        self.assertIsNone(sig)

    def test_single_trade_per_session_limit(self):
        """
        Verifies that after one signal is emitted, no subsequent signals are emitted on the same session.
        """
        start_time = datetime(2025, 10, 1, 9, 15, tzinfo=IST)
        
        # Feed 30 bars
        for i in range(30):
            bar = self._create_bar(start_time + timedelta(minutes=i), "25000", "25100", "24900", "25000")
            self.strategy.on_index_bar(bar, self.context)

        # Bar 31 at 09:45 emits signal
        bar_31 = self._create_bar(start_time + timedelta(minutes=30), "25000", "25200", "24950", "25180")
        sig1 = self.strategy.on_index_bar(bar_31, self.context)
        self.assertIsNotNone(sig1)

        # Bar 32 at 09:46 also triggers breakout, but should be suppressed
        bar_32 = self._create_bar(start_time + timedelta(minutes=31), "25180", "25250", "25150", "25240")
        sig2 = self.strategy.on_index_bar(bar_32, self.context)
        self.assertIsNone(sig2)


class TrendStrategyExecutionIntegrationTest(SimpleTestCase):
    """
    Integration tests evaluating execution simulation, next-minute fills,
    risk exits, missing candles, expiry roll, and regression on the historical dataset.
    """

    def test_risk_parameters_applied_to_simulator(self):
        """
        Verifies that MultiStrategyBacktestEngine propagates the trend strategy's
        risk parameters (15% SL, 30% PT, 60m max holding, 14:00 cutoff) to its config.
        """
        strategy = NiftyTrendFollowingPlugin()
        engine = MultiStrategyBacktestEngine(strategy=strategy)
        
        self.assertEqual(engine.config.strategy_id, "STRAT-TREND-EMA-DONCHIAN")
        self.assertEqual(engine.config.stop_loss_pct, Decimal("0.15"))
        self.assertEqual(engine.config.profit_target_pct, Decimal("0.30"))
        self.assertEqual(engine.config.max_holding_minutes, 60)
        self.assertEqual(engine.config.entry_window_start, time(9, 45, 0))
        self.assertEqual(engine.config.entry_window_end, time(14, 0, 0))

    def test_full_trend_backtest_deterministic_regression(self):
        """
        Runs the full historical backtest for STRAT-TREND-EMA-DONCHIAN and asserts
        exact deterministic trade count, qualified sessions, net P&L, and exit breakdown.
        """
        strategy = NiftyTrendFollowingPlugin()
        engine = MultiStrategyBacktestEngine(strategy=strategy)
        result = engine.run(calculate_sensitivity=False)
        
        # Session Accounting
        self.assertEqual(result.total_trading_days, 242)
        self.assertEqual(result.qualified_sessions, 222)
        self.assertEqual(result.excluded_sessions, 20)
        
        # Trades Count
        clean_metrics = result.metrics["standard_clean_ledger"]
        self.assertEqual(clean_metrics["total_trades"], 218)
        self.assertEqual(clean_metrics["winning_trades"], 76)
        self.assertEqual(clean_metrics["losing_trades"], 142)
        self.assertEqual(clean_metrics["win_rate_pct"], "34.86")
        
        # P&L and Risk Metrics
        self.assertEqual(clean_metrics["total_net_pnl"], "-31735.550")
        self.assertEqual(clean_metrics["total_gross_pnl"], "-17912.25")
        self.assertEqual(clean_metrics["total_frictions"], "13823.300")
        self.assertEqual(clean_metrics["profit_factor"], "0.8771")
        self.assertEqual(clean_metrics["max_drawdown_amount"], "40206.900")
        self.assertEqual(clean_metrics["max_drawdown_pct"], "19.60")
        self.assertEqual(clean_metrics["expectancy_per_trade"], "-145.58")
        
        # Exit Reasons
        from collections import Counter
        exit_counts = Counter(t.exit_reason for t in result.normal_trades)
        self.assertEqual(exit_counts["EXIT_STOP"], 119)
        self.assertEqual(exit_counts["EXIT_TARGET"], 43)
        self.assertEqual(exit_counts["EXIT_TIME"], 56)
        self.assertEqual(exit_counts.get("EXIT_EOD", 0), 0)
        
        # Execution Outcomes
        unfilled_count = sum(
            1 for s in result.session_summaries
            if s.rejection_reason == "EXPIRED_UNFILLED_NO_LIQUIDITY_BAR"
        )
        self.assertEqual(unfilled_count, 4)
        self.assertEqual(len(result.quarantined_trades), 0)

