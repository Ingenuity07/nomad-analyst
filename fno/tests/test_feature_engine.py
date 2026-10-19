"""
Unit tests for OptionFeatureEngine & OptionFeatureSnapshot schema.
Reference: Phase 22B Specification
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from django.test import TestCase

from fno.models import OptionOHLCVBar, OptionQuoteSnapshot
from fno.services.feature_engine import OptionFeatureEngine, OptionFeatureSnapshot
from fno.services.greeks_engine import GreeksEngine


class FeatureEngineTestCase(TestCase):
    def setUp(self):
        self.feature_engine = OptionFeatureEngine()
        self.expiry = date(2026, 10, 22)
        self.ts = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)

        self.bar = OptionOHLCVBar.objects.create(
            instrument_token=123456,
            tradingsymbol="NIFTY26O2224500CE",
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=self.expiry,
            timeframe="1m",
            timestamp=self.ts,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("152.00"),
            volume=500,
            open_interest=25000,
            oi_status="VALID",
            is_partial_bar=False,
        )

        self.quote = OptionQuoteSnapshot.objects.create(
            instrument_token=123456,
            tradingsymbol="NIFTY26O2224500CE",
            exchange_timestamp_utc=self.ts,
            received_wall_clock_utc=self.ts,
            exchange_time_status="VALID",
            best_bid=Decimal("151.50"),
            best_ask=Decimal("152.50"),
            bid_quantity_l1=150,
            ask_quantity_l1=200,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

    def test_moneyness_classification(self):
        """Verifies moneyness categorisation across ATM, ITM, DEEP_ITM, OTM, and DEEP_OTM."""
        engine = self.feature_engine
        spot = Decimal("24500.00")

        # CE
        _, cat_atm = engine.classify_moneyness(spot, Decimal("24500.00"), "CE")
        self.assertEqual(cat_atm, "ATM")
        _, cat_itm = engine.classify_moneyness(spot, Decimal("24400.00"), "CE")
        self.assertEqual(cat_itm, "ITM")
        _, cat_deep_itm = engine.classify_moneyness(spot, Decimal("24200.00"), "CE")
        self.assertEqual(cat_deep_itm, "DEEP_ITM")
        _, cat_otm = engine.classify_moneyness(spot, Decimal("24600.00"), "CE")
        self.assertEqual(cat_otm, "OTM")
        _, cat_deep_otm = engine.classify_moneyness(spot, Decimal("24800.00"), "CE")
        self.assertEqual(cat_deep_otm, "DEEP_OTM")

        # PE
        _, p_itm = engine.classify_moneyness(spot, Decimal("24600.00"), "PE")
        self.assertEqual(p_itm, "ITM")
        _, p_otm = engine.classify_moneyness(spot, Decimal("24400.00"), "PE")
        self.assertEqual(p_otm, "OTM")

    def test_oi_interpretation_heuristic(self):
        """Verifies open interest build-up and unwinding interpretations as analytical heuristics."""
        engine = self.feature_engine
        self.assertEqual(engine.interpret_oi(Decimal("5.0"), 1000), "LONG_BUILDUP")
        self.assertEqual(engine.interpret_oi(Decimal("-5.0"), 1000), "SHORT_BUILDUP")
        self.assertEqual(engine.interpret_oi(Decimal("-5.0"), -1000), "LONG_UNWINDING")
        self.assertEqual(engine.interpret_oi(Decimal("5.0"), -1000), "SHORT_COVERING")
        self.assertIsNone(engine.interpret_oi(Decimal("0.0"), 1000))

    def test_build_valid_feature_snapshot(self):
        """Verifies successful generation of a complete, valid OptionFeatureSnapshot with midpoint pricing."""
        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )

        self.assertIsInstance(snapshot, OptionFeatureSnapshot)
        self.assertEqual(snapshot.snapshot_version, "1.3.0")
        self.assertEqual(snapshot.tradingsymbol, "NIFTY26O2224500CE")
        self.assertEqual(snapshot.underlying_spot_price, Decimal("24500.00"))
        self.assertEqual(snapshot.moneyness_category, "ATM")
        self.assertEqual(snapshot.greeks_status, "VALID")
        self.assertEqual(snapshot.iv_pricing_source, "QUOTE_MIDPOINT")
        self.assertEqual(snapshot.iv_market_price, Decimal("152.00"))  # (151.50 + 152.50) / 2
        self.assertIsNotNone(snapshot.implied_volatility)
        self.assertIsNotNone(snapshot.delta)
        self.assertTrue(snapshot.is_quote_fresh)
        self.assertTrue(snapshot.is_valid_for_signal)

    def test_stale_ltp_with_fresh_book(self):
        """Verifies that when bar close (LTP) is unrepresentative, fresh quote midpoint is prioritized."""
        # Bar close reflects old trade price of 100.00, but fresh quote is 151.50 / 152.50
        self.bar.close = Decimal("100.00")
        self.bar.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        # Midpoint from fresh quote book is used for IV inversion, NOT stale bar close!
        self.assertEqual(snapshot.iv_pricing_source, "QUOTE_MIDPOINT")
        self.assertEqual(snapshot.iv_market_price, Decimal("152.00"))
        self.assertEqual(snapshot.greeks_status, "VALID")

    def test_stale_quote_book_fails_iv_calculation(self):
        """Verifies that a stale quote book explicitly fails IV inversion rather than fabricating Greeks."""
        self.quote.is_stale = True
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertEqual(snapshot.greeks_status, "CALCULATION_FAILED")
        self.assertEqual(snapshot.greeks_failure_reason, "STALE_QUOTE_PRICING")
        self.assertEqual(snapshot.iv_pricing_source, "UNAVAILABLE")
        self.assertIsNone(snapshot.implied_volatility)
        self.assertIsNone(snapshot.delta)
        self.assertFalse(snapshot.is_valid_for_signal)

    def test_signal_ineligible_on_partial_bar(self):
        """Verifies that a partial bar (e.g. from network disconnect) fails is_valid_for_signal."""
        self.bar.is_partial_bar = True
        self.bar.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)

    def test_signal_ineligible_on_stale_or_crossed_quote(self):
        """Verifies that stale or crossed quote states invalidate signal generation."""
        self.quote.is_crossed = True
        self.quote.best_bid = Decimal("155.00")
        self.quote.best_ask = Decimal("150.00")
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)

    def test_signal_ineligible_on_excessive_spread(self):
        """Verifies that spreads > 2.5% invalidate signal generation and skip IV inversion."""
        self.quote.best_bid = Decimal("100.00")
        self.quote.best_ask = Decimal("105.00")  # 5% spread
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)
        self.assertGreater(snapshot.spread_percentage, Decimal("0.025"))
        self.assertEqual(snapshot.greeks_status, "SKIPPED_ILLIQUID")
        self.assertEqual(snapshot.greeks_failure_reason, "WIDE_SPREAD")
        self.assertEqual(snapshot.iv_pricing_source, "UNAVAILABLE")

    def test_zero_bid_quote_fails_iv_and_signal(self):
        """Verifies that zero-bid quotes fail IV calculation and invalidate signal generation."""
        self.quote.best_bid = Decimal("0.00")
        self.quote.best_ask = Decimal("5.00")
        self.quote.quote_status = "ZERO_BID"
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)
        self.assertEqual(snapshot.greeks_status, "CALCULATION_FAILED")
        self.assertEqual(snapshot.greeks_failure_reason, "ZERO_BID")
        self.assertIsNone(snapshot.implied_volatility)

    def test_locked_book_fails_iv_and_signal(self):
        """Verifies that locked books (bid == ask) fail IV calculation and invalidate signals."""
        self.quote.is_locked = True
        self.quote.best_bid = Decimal("150.00")
        self.quote.best_ask = Decimal("150.00")
        self.quote.quote_status = "LOCKED"
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)
        self.assertEqual(snapshot.greeks_status, "CALCULATION_FAILED")
        self.assertEqual(snapshot.greeks_failure_reason, "LOCKED_BOOK")

    def test_crossed_book_fails_iv_and_signal(self):
        """Verifies that crossed books (bid > ask) fail IV calculation and invalidate signals."""
        self.quote.is_crossed = True
        self.quote.best_bid = Decimal("155.00")
        self.quote.best_ask = Decimal("150.00")
        self.quote.quote_status = "CROSSED"
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)
        self.assertEqual(snapshot.greeks_status, "CALCULATION_FAILED")
        self.assertEqual(snapshot.greeks_failure_reason, "CROSSED_BOOK")

    def test_invalid_negative_price_fails_iv_and_signal(self):
        """Verifies that invalid prices fail IV calculation and invalidate signals."""
        self.quote.best_bid = Decimal("-5.00")
        self.quote.best_ask = Decimal("-1.00")
        self.quote.save()

        snapshot = self.feature_engine.build_snapshot(
            bar=self.bar,
            quote=self.quote,
            underlying_spot=Decimal("24500.00"),
            calculation_time=self.ts,
        )
        self.assertFalse(snapshot.is_valid_for_signal)
        self.assertEqual(snapshot.greeks_status, "CALCULATION_FAILED")

