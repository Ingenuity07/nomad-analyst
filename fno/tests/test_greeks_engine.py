"""
Unit tests for GreeksEngine: Black-Scholes formulas, Brent IV inversion, and boundary conditions.
Reference: Phase 22B Specification
"""

from datetime import date, datetime, time
from decimal import Decimal
import zoneinfo
from django.test import SimpleTestCase

from fno.services.greeks_engine import GreeksConfig, GreeksEngine, GreeksResult

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class GreeksEngineTestCase(SimpleTestCase):
    def setUp(self):
        self.config = GreeksConfig(
            risk_free_rate=0.065,
            dividend_yield=0.012,
            trading_days_per_year=252.0,
            annual_theta_divisor=252.0,
            model_version="BRENT_BSM_V1",
        )
        self.engine = GreeksEngine(config=self.config)
        self.current_dt = datetime(2026, 10, 19, 10, 0, tzinfo=IST)
        self.expiry_date = date(2026, 10, 22)

    def test_time_to_expiry_calculation(self):
        """Verifies session-based and calendar-based time to expiry calculation."""
        res = self.engine.calculate_time_to_expiry(self.current_dt, self.expiry_date)
        self.assertFalse(res.is_expired)
        self.assertEqual(res.calendar_days, 3)
        self.assertGreater(res.years_to_expiry, 0.0)
        self.assertGreater(res.trading_sessions_to_expiry, Decimal("3.0"))

    def test_time_to_expiry_expired_boundary(self):
        """Verifies that timestamp on or after 15:30 IST on expiry day is marked expired."""
        expired_dt = datetime(2026, 10, 22, 15, 30, 0, tzinfo=IST)
        res = self.engine.calculate_time_to_expiry(expired_dt, self.expiry_date)
        self.assertTrue(res.is_expired)
        self.assertEqual(res.years_to_expiry, 0.0)
        self.assertEqual(res.trading_sessions_to_expiry, Decimal("0.0"))

    def test_black_scholes_pricing_and_put_call_parity(self):
        """Verifies Black-Scholes pricing matches Put-Call parity."""
        S = 24500.0
        K = 24500.0
        T = 0.05
        sigma = 0.16
        r = 0.065
        q = 0.012

        call_price = self.engine.black_scholes_price(S, K, T, sigma, "CE", r=r, q=q)
        put_price = self.engine.black_scholes_price(S, K, T, sigma, "PE", r=r, q=q)

        import math
        lhs = call_price - put_price
        rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        self.assertAlmostEqual(lhs, rhs, places=4)

    def test_greeks_analytical_signs(self):
        """Verifies standard Greek properties: Call Delta > 0, Put Delta < 0, Gamma > 0, Vega > 0."""
        S = 24500.0
        K = 24500.0
        T = 0.05
        sigma = 0.15

        c_delta, c_gamma, c_theta, c_vega = self.engine.calculate_greeks(S, K, T, sigma, "CE")
        p_delta, p_gamma, p_theta, p_vega = self.engine.calculate_greeks(S, K, T, sigma, "PE")

        self.assertGreater(c_delta, 0.0)
        self.assertLess(c_delta, 1.0)
        self.assertLess(p_delta, 0.0)
        self.assertGreater(p_delta, -1.0)

        # Gamma and Vega are identical for call and put
        self.assertAlmostEqual(c_gamma, p_gamma, places=6)
        self.assertGreater(c_gamma, 0.0)
        self.assertAlmostEqual(c_vega, p_vega, places=4)
        self.assertGreater(c_vega, 0.0)

        # Theta is negative (decay)
        self.assertLess(c_theta, 0.0)
        self.assertLess(p_theta, 0.0)

    def test_brent_iv_inversion_accuracy(self):
        """Verifies Brent's method inverts market price back to exact input volatility."""
        S = 24500.0
        K = 24600.0
        tte_res = self.engine.calculate_time_to_expiry(self.current_dt, self.expiry_date)
        T = tte_res.years_to_expiry
        expected_vol = 0.185

        for opt_type in ["CE", "PE"]:
            theoretical_price = self.engine.black_scholes_price(S, K, T, expected_vol, opt_type)
            result = self.engine.calculate_option_intelligence(
                market_price=theoretical_price,
                spot_price=S,
                strike_price=K,
                current_dt=self.current_dt,
                expiry_date=self.expiry_date,
                option_type=opt_type,
                best_bid=theoretical_price - 1.0,
                best_ask=theoretical_price + 1.0,
                pricing_source="QUOTE_MIDPOINT",
            )
            self.assertEqual(result.status, "VALID")
            self.assertIsNone(result.failure_reason)
            self.assertEqual(result.pricing_source, "QUOTE_MIDPOINT")
            self.assertAlmostEqual(float(result.implied_volatility), expected_vol, places=4)
            self.assertIsNotNone(result.delta)
            self.assertIsNotNone(result.gamma)
            self.assertIsNotNone(result.theta)
            self.assertIsNotNone(result.vega)

    def test_arbitrage_violation_below_intrinsic(self):
        """Verifies that an option price below intrinsic returns BELOW_INTRINSIC and null Greeks."""
        S = 25000.0
        K = 24000.0  # Deep ITM Call, intrinsic ~ 1000
        market_price = 800.0  # Severe arbitrage violation

        result = self.engine.calculate_option_intelligence(
            market_price=market_price,
            spot_price=S,
            strike_price=K,
            current_dt=self.current_dt,
            expiry_date=self.expiry_date,
            option_type="CE",
            best_bid=790.0,
            best_ask=810.0,
        )
        self.assertEqual(result.status, "CALCULATION_FAILED")
        self.assertEqual(result.failure_reason, "BELOW_INTRINSIC")
        self.assertIsNone(result.implied_volatility)
        self.assertIsNone(result.delta)
        self.assertIsNone(result.gamma)

    def test_zero_bid_and_zero_price_quote_handling(self):
        """Verifies that zero bid quotes return ZERO_BID failure status without fabricating Greeks."""
        result = self.engine.calculate_option_intelligence(
            market_price=10.0,
            spot_price=24500.0,
            strike_price=25500.0,
            current_dt=self.current_dt,
            expiry_date=self.expiry_date,
            option_type="CE",
            best_bid=0.0,  # Zero bid
            best_ask=10.0,
        )
        self.assertEqual(result.status, "CALCULATION_FAILED")
        self.assertEqual(result.failure_reason, "ZERO_BID")
        self.assertIsNone(result.implied_volatility)
        self.assertIsNone(result.delta)

        # Zero market price
        result_zero_price = self.engine.calculate_option_intelligence(
            market_price=0.0,
            spot_price=24500.0,
            strike_price=24500.0,
            current_dt=self.current_dt,
            expiry_date=self.expiry_date,
            option_type="CE",
        )
        self.assertEqual(result_zero_price.status, "CALCULATION_FAILED")
        self.assertIn(result_zero_price.failure_reason, ["ZERO_PRICE", "INVALID_INPUTS"])

    def test_unbracketed_and_numerical_failure(self):
        """Verifies unbracketed volatility / extreme prices return appropriate failure reasons."""
        S = 24500.0
        K = 24500.0
        # Price exceeding upper bound (S * exp(-qT))
        result_above = self.engine.calculate_option_intelligence(
            market_price=25000.0,  # Impossible call premium > spot
            spot_price=S,
            strike_price=K,
            current_dt=self.current_dt,
            expiry_date=self.expiry_date,
            option_type="CE",
        )
        self.assertEqual(result_above.status, "CALCULATION_FAILED")
        self.assertEqual(result_above.failure_reason, "ABOVE_MAX_BOUND")

    def test_expired_option_intelligence(self):
        """Verifies that an expired option returns EXPIRED failure status."""
        expired_dt = datetime(2026, 10, 22, 16, 0, tzinfo=IST)
        result = self.engine.calculate_option_intelligence(
            market_price=50.0,
            spot_price=24500.0,
            strike_price=24500.0,
            current_dt=expired_dt,
            expiry_date=self.expiry_date,
            option_type="CE",
        )
        self.assertEqual(result.status, "CALCULATION_FAILED")
        self.assertEqual(result.failure_reason, "EXPIRED")
        self.assertIsNone(result.implied_volatility)

    def test_greeks_config_versioned_assumptions(self):
        """Verifies custom GreeksConfig assumptions propagate to calculations."""
        custom_config = GreeksConfig(
            risk_free_rate=0.07,
            dividend_yield=0.015,
            trading_days_per_year=250.0,
            annual_theta_divisor=250.0,
            model_version="CUSTOM_TEST_V2",
        )
        custom_engine = GreeksEngine(config=custom_config)
        self.assertEqual(custom_engine.risk_free_rate, 0.07)
        self.assertEqual(custom_engine.dividend_yield, 0.015)
        self.assertEqual(custom_engine.config.model_version, "CUSTOM_TEST_V2")
