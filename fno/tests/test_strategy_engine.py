"""
Unit tests for Generic Strategy Framework, SignalValidator, StrategyManager, and NiftyOrbBreakoutStrategy.
Reference: Phase 22C Specification
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
import zoneinfo
from django.test import SimpleTestCase

from fno.services.feature_engine import OptionFeatureSnapshot
from fno.strategies.base import BaseStrategy, OptionSignal, PaperTradeEvent
from fno.strategies.manager import StrategyManager
from fno.strategies.nifty_orb_breakout import NiftyOrbBreakoutStrategy
from fno.strategies.validator import SignalValidator

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class StrategyEngineTestCase(SimpleTestCase):
    def setUp(self):
        self.validator = SignalValidator()
        self.manager = StrategyManager(validator=self.validator)
        self.strategy = NiftyOrbBreakoutStrategy()
        self.manager.register_strategy(self.strategy)

        # Set 15m opening range for NIFTY: High = 24550, Low = 24450
        self.strategy.set_opening_range(high=Decimal("24550.00"), low=Decimal("24450.00"))

        # Valid mock feature snapshot at 10:15:00 IST (04:45:00 UTC)
        self.dt_valid_ist = datetime(2026, 10, 19, 10, 15, 0, tzinfo=IST)
        self.dt_valid_utc = self.dt_valid_ist.astimezone(timezone.utc)

        self.snapshot_ce = OptionFeatureSnapshot(
            snapshot_id="snap-ce-001",
            snapshot_version="1.3.0",
            engine_git_commit="test_commit",
            feature_set_id="DEFAULT_NIFTY_OPTS_V1",
            calculation_timestamp_utc=self.dt_valid_utc,
            received_wall_clock_utc=self.dt_valid_utc,
            timeframe="1m",
            exchange_time_status="VALID",
            is_quote_fresh=True,
            quote_age_seconds=Decimal("0.5"),
            underlying_symbol="^NSEI",
            underlying_spot_price=Decimal("24580.00"),  # Bullish breakout above 24550
            underlying_open=Decimal("24500.00"),
            underlying_high=Decimal("24585.00"),
            underlying_low=Decimal("24490.00"),
            underlying_close=Decimal("24580.00"),
            market_regime="TRENDING_BULLISH",
            tradingsymbol="NIFTY26OCT24550CE",
            instrument_token=1001,
            option_type="CE",
            strike_price=Decimal("24550.00"),
            expiry_date=date(2026, 10, 22),
            days_to_expiry=3,
            trading_sessions_to_expiry=Decimal("3.8"),
            atm_distance_points=Decimal("30.00"),
            moneyness_category="ATM",
            premium_open=Decimal("120.00"),
            premium_high=Decimal("135.00"),
            premium_low=Decimal("118.00"),
            premium_close=Decimal("130.00"),
            premium_bar_volume=5000,
            premium_session_volume=50000,
            best_bid=Decimal("129.50"),
            best_ask=Decimal("130.50"),
            mid_price=Decimal("130.00"),
            spread_absolute=Decimal("1.00"),
            spread_percentage=Decimal("0.0077"),  # 0.77% < 2.5%
            greeks_status="VALID",
            implied_volatility=Decimal("0.155"),
            delta=Decimal("0.53"),
            gamma=Decimal("0.0008"),
            theta=Decimal("-25.50"),
            vega=Decimal("12.00"),
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_partial_bar=False,
            is_valid_for_signal=True,
        )

    def test_bullish_orb_breakout_signal_generation(self):
        """Verifies that bullish breakout produces a valid OptionSignal."""
        signals = self.manager.process_feature_snapshot(self.snapshot_ce)
        self.assertEqual(len(signals), 1)
        sig = signals[0]

        self.assertEqual(sig.strategy_id, "STRAT-ORB-15M")
        self.assertEqual(sig.action, "BUY_TO_OPEN")
        self.assertEqual(sig.tradingsymbol, "NIFTY26OCT24550CE")
        self.assertEqual(sig.trigger_rule_name, "ORB_BULLISH_CE_BREAKOUT")
        self.assertLess(sig.stop_loss_premium, Decimal("130.50"))
        self.assertGreater(sig.profit_target_premium, Decimal("130.50"))

    def test_disabled_strategy_generates_no_signals(self):
        """Verifies enable/disable controls."""
        self.strategy.disable()
        self.assertFalse(self.strategy.is_enabled)

        signals = self.manager.process_feature_snapshot(self.snapshot_ce)
        self.assertEqual(len(signals), 0)

        self.strategy.enable()
        self.assertTrue(self.strategy.is_enabled)
        signals2 = self.manager.process_feature_snapshot(self.snapshot_ce)
        self.assertEqual(len(signals2), 1)

    def test_signal_rejection_on_stale_quote(self):
        """Verifies validator rejects signals if snapshot is stale."""
        stale_snap = self.snapshot_ce.model_copy(update={
            "is_stale": True,
            "quote_age_seconds": Decimal("4.2"),
            "is_valid_for_signal": False,
        })
        signals = self.manager.process_feature_snapshot(stale_snap)
        self.assertEqual(len(signals), 0)

        # Check rejection in manager's audit log
        self.assertTrue(any(a.status == "REJECTED" and a.rejection_code == "REJECTED_STALE_QUOTE" for a in self.manager.audit_log))

    def test_signal_rejection_on_crossed_or_locked_quotes(self):
        """Verifies validator rejects crossed books."""
        crossed_snap = self.snapshot_ce.model_copy(update={
            "is_crossed": True,
            "best_bid": Decimal("135.00"),
            "best_ask": Decimal("130.00"),
            "is_valid_for_signal": False,
        })
        signals = self.manager.process_feature_snapshot(crossed_snap)
        self.assertEqual(len(signals), 0)
        self.assertTrue(any(a.status == "REJECTED" and a.rejection_code == "REJECTED_CROSSED_BOOK" for a in self.manager.audit_log))

    def test_signal_rejection_on_excessive_spread(self):
        """Verifies validator rejects spreads > 2.5%."""
        wide_snap = self.snapshot_ce.model_copy(update={
            "best_bid": Decimal("100.00"),
            "best_ask": Decimal("104.00"),  # 4% spread
            "spread_percentage": Decimal("0.04"),
            "is_valid_for_signal": False,
        })
        signals = self.manager.process_feature_snapshot(wide_snap)
        self.assertEqual(len(signals), 0)
        self.assertTrue(any(a.status == "REJECTED" and a.rejection_code == "REJECTED_EXCESSIVE_SPREAD" for a in self.manager.audit_log))

    def test_strategy_lifecycle_trade_events_and_exit(self):
        """Verifies position tracking on ORDER_FILLED and subsequent profit target EXIT_TARGET."""
        signals = self.manager.process_feature_snapshot(self.snapshot_ce)
        self.assertEqual(len(signals), 1)
        sig = signals[0]

        # Simulate fill event
        fill_event = PaperTradeEvent(
            event_id="evt-1",
            event_type="ORDER_FILLED",
            strategy_id="STRAT-ORB-15M",
            signal_id=sig.signal_id,
            tradingsymbol=sig.tradingsymbol,
            fill_price=Decimal("131.00"),
            fill_quantity=65,
            slippage=Decimal("0.50"),
            timestamp=self.dt_valid_utc,
        )
        self.manager.broadcast_trade_event(fill_event)
        self.assertIsNotNone(self.strategy.active_position)

        # Snapshot where price reached profit target (+20% of 131 = 157.2) -> Bid = 160.00
        target_snap = self.snapshot_ce.model_copy(update={
            "best_bid": Decimal("160.00"),
            "best_ask": Decimal("161.00"),
            "premium_close": Decimal("160.00"),
        })

        exit_signals = self.manager.process_feature_snapshot(target_snap)
        self.assertEqual(len(exit_signals), 1)
        self.assertEqual(exit_signals[0].action, "EXIT_TARGET")
