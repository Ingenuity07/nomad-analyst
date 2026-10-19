"""
Nomad Analyst — F&O Core Options Intelligence: Black-Scholes & Greeks Engine
Reference: Phase 22B Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Pure, deterministic implementation of:
1. Black-Scholes-Merton option pricing with continuous dividend yield (Merton 1973).
2. Analytical Black-Scholes Greeks: Delta, Gamma, Theta (daily decay), Vega (1% vol change).
3. Robust Brent-Dekker hybrid numerical solver for Implied Volatility (IV) inversion.
4. Indian market session-aware time-to-expiry (252 trading-day convention, 15:30 IST close).
5. Explicit versioned configuration: risk-free rate, dividend yield, theta divisor conventions.
6. Explicit failure modes: no fabricated Greeks, no silent substitution of zero.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Optional, Tuple
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")

# Standard Indian Market Defaults
DEFAULT_RISK_FREE_RATE = 0.065   # 6.5% 91-day T-Bill annualized yield
DEFAULT_DIVIDEND_YIELD = 0.012   # 1.2% NIFTY continuous dividend yield
TRADING_DAYS_PER_YEAR = 252.0
MINUTES_PER_TRADING_SESSION = 375.0  # 09:15 to 15:30 IST = 6.25 hours = 375 mins
EXPIRY_CLOSE_TIME = time(15, 30, 0)
MIN_IV_BOUND = 0.001             # 0.1% volatility
MAX_IV_BOUND = 5.000             # 500% volatility
MAX_BRENT_ITERATIONS = 50
BRENT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class GreeksConfig:
    """Explicit, versioned configuration assumptions for options pricing and Greeks."""
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD
    trading_days_per_year: float = TRADING_DAYS_PER_YEAR
    annual_theta_divisor: float = TRADING_DAYS_PER_YEAR  # 252.0 trading-day convention
    model_version: str = "BRENT_BSM_V1"
    min_iv_bound: float = MIN_IV_BOUND
    max_iv_bound: float = MAX_IV_BOUND
    max_brent_iterations: int = MAX_BRENT_ITERATIONS
    brent_tolerance: float = BRENT_TOLERANCE


@dataclass(frozen=True)
class TimeToExpiryResult:
    calendar_days: int
    trading_sessions_to_expiry: Decimal
    years_to_expiry: float
    is_expired: bool


@dataclass(frozen=True)
class GreeksResult:
    status: str  # "VALID", "CALCULATION_FAILED", "SKIPPED_ILLIQUID"
    failure_reason: Optional[str]  # "BELOW_INTRINSIC", "ABOVE_MAX_BOUND", "NON_CONVERGENT", "ZERO_BID", "ZERO_PRICE", "EXPIRED", "INVALID_INPUTS", None
    pricing_source: str            # "QUOTE_MIDPOINT", "BAR_CLOSE_LTP", "UNAVAILABLE"
    implied_volatility: Optional[Decimal]
    delta: Optional[Decimal]
    gamma: Optional[Decimal]
    theta: Optional[Decimal]
    vega: Optional[Decimal]


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function N(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function n(x)."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


class GreeksEngine:
    """
    Deterministic Black-Scholes Greeks calculator and IV inversion engine.
    """

    def __init__(
        self,
        config: Optional[GreeksConfig] = None,
        risk_free_rate: Optional[float] = None,
        dividend_yield: Optional[float] = None,
        trading_days_per_year: Optional[float] = None,
    ):
        base_config = config or GreeksConfig()
        r = risk_free_rate if risk_free_rate is not None else base_config.risk_free_rate
        q = dividend_yield if dividend_yield is not None else base_config.dividend_yield
        t_days = trading_days_per_year if trading_days_per_year is not None else base_config.trading_days_per_year

        self.config = GreeksConfig(
            risk_free_rate=r,
            dividend_yield=q,
            trading_days_per_year=t_days,
            annual_theta_divisor=base_config.annual_theta_divisor,
            model_version=base_config.model_version,
            min_iv_bound=base_config.min_iv_bound,
            max_iv_bound=base_config.max_iv_bound,
            max_brent_iterations=base_config.max_brent_iterations,
            brent_tolerance=base_config.brent_tolerance,
        )
        self.risk_free_rate = self.config.risk_free_rate
        self.dividend_yield = self.config.dividend_yield
        self.trading_days_per_year = self.config.trading_days_per_year

    def calculate_time_to_expiry(
        self,
        current_dt: datetime,
        expiry_date: date,
    ) -> TimeToExpiryResult:
        """
        Calculates calendar days, fractional trading sessions, and annualized T.
        Converts inputs to IST zone (Asia/Kolkata).
        Market close on expiry day is strictly 15:30:00 IST.
        """
        if current_dt.tzinfo is None:
            current_dt_ist = current_dt.replace(tzinfo=UTC).astimezone(IST)
        else:
            current_dt_ist = current_dt.astimezone(IST)

        expiry_dt_ist = datetime.combine(expiry_date, EXPIRY_CLOSE_TIME, tzinfo=IST)

        if current_dt_ist >= expiry_dt_ist:
            cal_days = (expiry_date - current_dt_ist.date()).days
            return TimeToExpiryResult(
                calendar_days=max(0, cal_days),
                trading_sessions_to_expiry=Decimal("0.0"),
                years_to_expiry=0.0,
                is_expired=True,
            )

        cal_days = (expiry_date - current_dt_ist.date()).days

        market_open_today = datetime.combine(current_dt_ist.date(), time(9, 15, 0), tzinfo=IST)
        market_close_today = datetime.combine(current_dt_ist.date(), time(15, 30, 0), tzinfo=IST)

        if current_dt_ist < market_open_today:
            today_fraction = 1.0
        elif current_dt_ist > market_close_today:
            today_fraction = 0.0
        else:
            remaining_seconds = (market_close_today - current_dt_ist).total_seconds()
            today_fraction = max(0.0, min(1.0, remaining_seconds / (MINUTES_PER_TRADING_SESSION * 60.0)))

        current_curr = current_dt_ist.date()
        full_business_days = 0
        from datetime import timedelta
        check_date = current_curr + timedelta(days=1)
        while check_date < expiry_date:
            if check_date.weekday() < 5:  # Monday to Friday
                full_business_days += 1
            check_date += timedelta(days=1)

        if current_dt_ist.date() == expiry_date:
            total_sessions = today_fraction
        else:
            total_sessions = today_fraction + full_business_days + 1.0

        years_to_expiry = max(0.0, total_sessions / self.trading_days_per_year)
        sessions_decimal = Decimal(str(round(total_sessions, 4)))

        return TimeToExpiryResult(
            calendar_days=cal_days,
            trading_sessions_to_expiry=sessions_decimal,
            years_to_expiry=years_to_expiry,
            is_expired=False,
        )

    def black_scholes_price(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str,
        r: Optional[float] = None,
        q: Optional[float] = None,
    ) -> float:
        """
        Black-Scholes-Merton option price for European options with continuous dividend yield.
        """
        if S <= 0.0 or K <= 0.0 or sigma <= 0.0:
            return 0.0
        if T <= 0.0:
            if option_type.upper() == "CE":
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)

        r = self.risk_free_rate if r is None else r
        q = self.dividend_yield if q is None else q

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        if option_type.upper() == "CE":
            return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        else:
            return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)

    def calculate_greeks(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str,
        r: Optional[float] = None,
        q: Optional[float] = None,
    ) -> Tuple[float, float, float, float]:
        """
        Calculates analytical Greeks: (Delta, Gamma, Theta_daily, Vega_1pct).
        Theta is expressed as 1-day decay in INR (using configured annual_theta_divisor, default 252).
        Vega is expressed as change in price per 1% (0.01) change in volatility.
        """
        r = self.risk_free_rate if r is None else r
        q = self.dividend_yield if q is None else q

        if S <= 0.0 or K <= 0.0 or sigma <= 0.0 or T <= 0.0:
            return 0.0, 0.0, 0.0, 0.0

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        pdf_d1 = _norm_pdf(d1)
        exp_qT = math.exp(-q * T)
        exp_rT = math.exp(-r * T)

        # Gamma (identical for Call and Put)
        gamma = (exp_qT * pdf_d1) / (S * sigma * sqrt_T)

        # Vega (per 1% = 0.01 change in volatility)
        vega_1pct = (S * exp_qT * pdf_d1 * sqrt_T) * 0.01

        if option_type.upper() == "CE":
            delta = exp_qT * _norm_cdf(d1)
            theta_annual = (
                -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
                + q * S * exp_qT * _norm_cdf(d1)
                - r * K * exp_rT * _norm_cdf(d2)
            )
        else:
            delta = exp_qT * (_norm_cdf(d1) - 1.0)
            theta_annual = (
                -(S * exp_qT * pdf_d1 * sigma) / (2.0 * sqrt_T)
                - q * S * exp_qT * _norm_cdf(-d1)
                + r * K * exp_rT * _norm_cdf(-d2)
            )

        theta_daily = theta_annual / self.config.annual_theta_divisor
        return delta, gamma, theta_daily, vega_1pct

    def invert_implied_volatility(
        self,
        market_price: float,
        S: float,
        K: float,
        T: float,
        option_type: str,
        r: Optional[float] = None,
        q: Optional[float] = None,
        max_iterations: Optional[int] = None,
        tolerance: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Inverts Black-Scholes formula using a Brent-Dekker hybrid root finder.
        Returns: (implied_volatility, failure_reason)
        """
        r = self.risk_free_rate if r is None else r
        q = self.dividend_yield if q is None else q
        max_iter = max_iterations or self.config.max_brent_iterations
        tol = tolerance or self.config.brent_tolerance

        if market_price <= 0.0:
            return None, "ZERO_PRICE"
        if S <= 0.0 or K <= 0.0:
            return None, "INVALID_INPUTS"
        if T <= 0.0:
            return None, "EXPIRED"

        # Calculate theoretical intrinsic value bounds
        exp_qT = math.exp(-q * T)
        exp_rT = math.exp(-r * T)
        if option_type.upper() == "CE":
            intrinsic = max(0.0, S * exp_qT - K * exp_rT)
            upper_bound_price = S * exp_qT
        else:
            intrinsic = max(0.0, K * exp_rT - S * exp_qT)
            upper_bound_price = K * exp_rT

        # Arbitrage check: market price cannot be less than intrinsic value
        if market_price <= intrinsic:
            return None, "BELOW_INTRINSIC"

        if market_price >= upper_bound_price:
            return None, "ABOVE_MAX_BOUND"

        def f(sigma: float) -> float:
            return self.black_scholes_price(S, K, T, sigma, option_type, r=r, q=q) - market_price

        a = self.config.min_iv_bound
        b = self.config.max_iv_bound
        fa = f(a)
        fb = f(b)

        if fa * fb > 0.0:
            if fa > 0.0:
                return None, "BELOW_INTRINSIC"
            else:
                return None, "NON_CONVERGENT"

        if abs(fa) < abs(fb):
            a, b = b, a
            fa, fb = fb, fa

        c = a
        fc = fa
        mflag = True
        d = 0.0

        for _ in range(max_iter):
            if abs(fb) < tol:
                return b, None
            if abs(b - a) < tol:
                return b, None

            if fa != fc and fb != fc:
                s = (
                    a * fb * fc / ((fa - fb) * (fa - fc))
                    + b * fa * fc / ((fb - fa) * (fb - fc))
                    + c * fa * fb / ((fc - fa) * (fc - fb))
                )
            else:
                s = b - fb * (b - a) / (fb - fa)

            cond1 = not ((3.0 * a + b) / 4.0 <= s <= b or b <= s <= (3.0 * a + b) / 4.0)
            cond2 = mflag and abs(s - b) >= (abs(b - c) / 2.0)
            cond3 = (not mflag) and abs(s - b) >= (abs(c - d) / 2.0)
            cond4 = mflag and abs(b - c) < tol
            cond5 = (not mflag) and abs(c - d) < tol

            if cond1 or cond2 or cond3 or cond4 or cond5:
                s = (a + b) / 2.0
                mflag = True
            else:
                mflag = False

            fs = f(s)
            d = c
            c = b
            fc = fb

            if fa * fs < 0.0:
                b = s
                fb = fs
            else:
                a = s
                fa = fs

            if abs(fa) < abs(fb):
                a, b = b, a
                fa, fb = fb, fa

        return None, "NON_CONVERGENT"

    def calculate_option_intelligence(
        self,
        market_price: float,
        spot_price: float,
        strike_price: float,
        current_dt: datetime,
        expiry_date: date,
        option_type: str,
        best_bid: Optional[float] = None,
        best_ask: Optional[float] = None,
        pricing_source: str = "QUOTE_MIDPOINT",
        r: Optional[float] = None,
        q: Optional[float] = None,
    ) -> GreeksResult:
        """
        Orchestrates full IV inversion and analytical Greeks generation.
        Strictly returns explicit failure statuses when inputs or convergence fail.
        """
        if best_bid is not None and best_bid <= 0.0:
            return GreeksResult(
                status="CALCULATION_FAILED",
                failure_reason="ZERO_BID",
                pricing_source=pricing_source,
                implied_volatility=None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )

        tte = self.calculate_time_to_expiry(current_dt, expiry_date)
        if tte.is_expired or tte.years_to_expiry <= 0.0:
            return GreeksResult(
                status="CALCULATION_FAILED",
                failure_reason="EXPIRED",
                pricing_source=pricing_source,
                implied_volatility=None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )

        if spot_price <= 0.0 or strike_price <= 0.0 or market_price <= 0.0:
            return GreeksResult(
                status="CALCULATION_FAILED",
                failure_reason="INVALID_INPUTS",
                pricing_source=pricing_source,
                implied_volatility=None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )

        iv, fail_reason = self.invert_implied_volatility(
            market_price=market_price,
            S=spot_price,
            K=strike_price,
            T=tte.years_to_expiry,
            option_type=option_type,
            r=r,
            q=q,
        )

        if iv is None:
            return GreeksResult(
                status="CALCULATION_FAILED",
                failure_reason=fail_reason,
                pricing_source=pricing_source,
                implied_volatility=None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )

        delta, gamma, theta, vega = self.calculate_greeks(
            S=spot_price,
            K=strike_price,
            T=tte.years_to_expiry,
            sigma=iv,
            option_type=option_type,
            r=r,
            q=q,
        )

        return GreeksResult(
            status="VALID",
            failure_reason=None,
            pricing_source=pricing_source,
            implied_volatility=Decimal(str(round(iv, 6))),
            delta=Decimal(str(round(delta, 4))),
            gamma=Decimal(str(round(gamma, 6))),
            theta=Decimal(str(round(theta, 4))),
            vega=Decimal(str(round(vega, 4))),
        )
