"""
Nomad Analyst — F&O Core Options Intelligence: OptionFeatureEngine & Schema
Reference: Phase 22B Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Constructs standardized, reproducible, immutable OptionFeatureSnapshot instances.
Consolidates 1-minute OHLCV+OI option bars, high-frequency quote snapshots,
underlying index context, breadth/regime context, and Black-Scholes Greeks.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
import subprocess
import time
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, Field

from fno.models import OptionOHLCVBar, OptionQuoteSnapshot
from fno.services.greeks_engine import GreeksConfig, GreeksEngine, GreeksResult


def get_git_commit() -> Optional[str]:
    """Retrieves current Git short commit hash for feature provenance."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=1,
        ).decode().strip()
        return commit
    except Exception:
        return "unknown"


CURRENT_GIT_COMMIT = get_git_commit()


class OptionFeatureSnapshot(BaseModel):
    """
    Standardized, reproducible feature contract emitted by the Core Intelligence Engine.
    Consumed by all independent strategy modules and paper execution engines.
    """
    model_config = {"arbitrary_types_allowed": True, "frozen": True}

    # 1. Provenance & Version Metadata
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    snapshot_version: str = "1.3.0"
    engine_git_commit: Optional[str] = CURRENT_GIT_COMMIT
    feature_set_id: str = "DEFAULT_NIFTY_OPTS_V1"
    calculation_timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeframe: str = "1m"

    # 2. Triple Timestamp & Independent Freshness Architecture
    exchange_timestamp_utc: Optional[datetime] = None
    last_trade_timestamp_utc: Optional[datetime] = None
    received_wall_clock_utc: datetime
    received_monotonic_ns: int = 0
    feed_latency_ms: Optional[int] = None
    quote_age_seconds: Optional[Decimal] = None
    last_trade_age_seconds: Optional[Decimal] = None
    pipeline_latency_ms: Decimal = Decimal("0.0")
    exchange_time_status: str = "VALID"
    is_quote_fresh: bool = False

    # 3. Underlying Index Price & Futures Volume Context
    underlying_symbol: str = "^NSEI"
    underlying_spot_price: Decimal
    underlying_open: Decimal
    underlying_high: Decimal
    underlying_low: Decimal
    underlying_close: Decimal
    underlying_futures_price: Optional[Decimal] = None
    underlying_futures_vwap: Optional[Decimal] = None
    underlying_futures_rvol_5m: Optional[Decimal] = None
    underlying_vwap_source: str = "UNAVAILABLE"

    # 4. Market Regime, Trend & Breadth Context
    market_regime: str = "SIDEWAYS_CHOP"
    trend_strength_adx: Optional[Decimal] = None
    advancers_count: int = 25
    decliners_count: int = 25
    advance_decline_ratio: Decimal = Decimal("1.00")
    india_vix_level: Decimal = Decimal("13.50")
    india_vix_daily_change_pct: Decimal = Decimal("0.00")

    # 5. Contract Specific Identifiers & Expiry
    tradingsymbol: str
    instrument_token: int
    option_type: str
    strike_price: Decimal
    expiry_date: date
    days_to_expiry: int
    trading_sessions_to_expiry: Decimal
    atm_distance_points: Decimal
    moneyness_category: str

    # 6. Premium Price & Bar Metrics
    premium_open: Decimal
    premium_high: Decimal
    premium_low: Decimal
    premium_close: Decimal
    premium_bar_volume: int
    premium_session_volume: int
    exchange_session_atp: Decimal = Decimal("0.00")
    nomad_candle_vwap: Optional[Decimal] = None

    # 7. Open Interest Metrics (With Explicit Heuristic Semantics)
    open_interest: Optional[int] = None
    oi_status: str = "UNPOPULATED"
    oi_change_1m: Optional[int] = None
    oi_change_session: Optional[int] = None
    oi_interpretation: Optional[str] = Field(
        default=None,
        description="Heuristic inference of open interest dynamics; NOT verified participant positioning."
    )

    # 8. Microstructure, Order Book & Liquidity Metrics
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    mid_price: Optional[Decimal] = None
    spread_absolute: Optional[Decimal] = None
    spread_percentage: Optional[Decimal] = None
    bid_depth_quantity_l1: Optional[int] = None
    ask_depth_quantity_l1: Optional[int] = None
    total_buy_quantity: Optional[int] = None
    total_sell_quantity: Optional[int] = None
    order_book_imbalance: Optional[Decimal] = None

    # 9. Analytics, Black-Scholes Greeks & Failure Handling
    greeks_status: str = "VALID"
    greeks_failure_reason: Optional[str] = None
    iv_pricing_source: str = "QUOTE_MIDPOINT"  # "QUOTE_MIDPOINT", "BAR_CLOSE_LTP", "UNAVAILABLE"
    iv_market_price: Optional[Decimal] = None
    implied_volatility: Optional[Decimal] = None
    delta: Optional[Decimal] = None
    gamma: Optional[Decimal] = None
    theta: Optional[Decimal] = None
    vega: Optional[Decimal] = None

    # 10. Data Quality & Integrity Flags
    quote_status: str = "VALID"
    is_stale: bool = False
    is_locked: bool = False
    is_crossed: bool = False
    is_partial_bar: bool = False
    is_valid_for_signal: bool = False


class OptionFeatureEngine:
    """
    Core Options Intelligence snapshot generator.
    Deterministic, robust calculation of options features.
    """

    def __init__(
        self,
        greeks_engine: Optional[GreeksEngine] = None,
        feature_set_id: str = "DEFAULT_NIFTY_OPTS_V1",
    ):
        self.greeks_engine = greeks_engine or GreeksEngine()
        self.feature_set_id = feature_set_id

    def classify_moneyness(
        self,
        spot: Decimal,
        strike: Decimal,
        option_type: str,
    ) -> Tuple[Decimal, str]:
        """
        Determines ATM distance and moneyness category.
        ATM: within 50 index points.
        ITM: 50 to 200 points in the money.
        DEEP_ITM: > 200 points in the money.
        OTM: 50 to 200 points out of the money.
        DEEP_OTM: > 200 points out of the money.
        """
        diff = spot - strike
        opt = option_type.upper()

        if opt == "CE":
            if diff >= Decimal("200.0"):
                return diff, "DEEP_ITM"
            elif diff >= Decimal("50.0"):
                return diff, "ITM"
            elif diff <= Decimal("-200.0"):
                return diff, "DEEP_OTM"
            elif diff <= Decimal("-50.0"):
                return diff, "OTM"
            else:
                return diff, "ATM"
        else:  # PE
            pe_diff = strike - spot
            if pe_diff >= Decimal("200.0"):
                return diff, "DEEP_ITM"
            elif pe_diff >= Decimal("50.0"):
                return diff, "ITM"
            elif pe_diff <= Decimal("-200.0"):
                return diff, "DEEP_OTM"
            elif pe_diff <= Decimal("-50.0"):
                return diff, "OTM"
            else:
                return diff, "ATM"

    def interpret_oi(
        self,
        price_change: Decimal,
        oi_change: Optional[int],
    ) -> Optional[str]:
        """
        Heuristic inference of open interest dynamics.
        Note: This is an analytical rule based on price/OI deltas, NOT verified
        institutional participant positioning or certified exchange counterparty attribution.
        - Price Up & OI Up -> LONG_BUILDUP
        - Price Down & OI Up -> SHORT_BUILDUP
        - Price Down & OI Down -> LONG_UNWINDING
        - Price Up & OI Down -> SHORT_COVERING
        """
        if oi_change is None or oi_change == 0 or price_change == Decimal("0.0"):
            return None

        if price_change > Decimal("0.0") and oi_change > 0:
            return "LONG_BUILDUP"
        elif price_change < Decimal("0.0") and oi_change > 0:
            return "SHORT_BUILDUP"
        elif price_change < Decimal("0.0") and oi_change < 0:
            return "LONG_UNWINDING"
        elif price_change > Decimal("0.0") and oi_change < 0:
            return "SHORT_COVERING"
        return None

    def build_snapshot(
        self,
        bar: OptionOHLCVBar,
        quote: Optional[OptionQuoteSnapshot],
        underlying_spot: Decimal,
        underlying_ohlc: Optional[Dict[str, Decimal]] = None,
        futures_context: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        prev_bar: Optional[OptionOHLCVBar] = None,
        session_open_oi: Optional[int] = None,
        cumulative_session_volume: Optional[int] = None,
        calculation_time: Optional[datetime] = None,
    ) -> OptionFeatureSnapshot:
        """
        Assembles and computes an immutable OptionFeatureSnapshot.
        """
        start_monotonic = time.monotonic_ns()
        now_utc = calculation_time or datetime.now(timezone.utc)

        # 1. Timestamps & Quote Freshness
        if quote:
            rec_wall = quote.received_wall_clock_utc
            exch_ts = quote.exchange_timestamp_utc
            exch_status = quote.exchange_time_status
            quote_status = quote.quote_status
            is_stale = quote.is_stale
            is_locked = quote.is_locked
            is_crossed = quote.is_crossed

            best_bid = quote.best_bid
            best_ask = quote.best_ask
            bid_q1 = quote.bid_quantity_l1
            ask_q1 = quote.ask_quantity_l1

            if exch_ts and exch_status == "VALID":
                age_sec = Decimal(str(round((now_utc - exch_ts).total_seconds(), 3)))
                quote_age = max(Decimal("0.0"), age_sec)
                feed_lat_ms = int((rec_wall - exch_ts).total_seconds() * 1000)
                is_fresh = (quote_age <= Decimal("3.0"))
            else:
                quote_age = None
                feed_lat_ms = None
                is_fresh = False
        else:
            rec_wall = now_utc
            exch_ts = None
            exch_status = "FALLBACK_TO_RECEIVED"
            quote_status = "EMPTY_BOOK"
            is_stale = True
            is_locked = False
            is_crossed = False
            best_bid = None
            best_ask = None
            bid_q1 = None
            ask_q1 = None
            quote_age = None
            feed_lat_ms = None
            is_fresh = False

        # 2. Spreads & Microstructure
        mid_price = None
        spread_abs = None
        spread_pct = None
        ob_imbalance = None

        if best_bid is not None and best_ask is not None:
            spread_abs = best_ask - best_bid
            mid_price = (best_bid + best_ask) / Decimal("2.0")
            if best_bid > Decimal("0.0"):
                spread_pct = Decimal(str(round(float(spread_abs / best_bid), 6)))
            else:
                spread_pct = None

        if bid_q1 is not None and ask_q1 is not None:
            tot_depth = bid_q1 + ask_q1
            if tot_depth > 0:
                ob_imbalance = Decimal(str(round((bid_q1 - ask_q1) / tot_depth, 4)))

        # 3. Moneyness & Expiry
        atm_dist, moneyness = self.classify_moneyness(
            spot=underlying_spot,
            strike=bar.strike_price,
            option_type=bar.option_type,
        )

        tte = self.greeks_engine.calculate_time_to_expiry(
            current_dt=exch_ts or now_utc,
            expiry_date=bar.expiry_date,
        )

        # 4. Underlying OHLC & Futures Context
        u_ohlc = underlying_ohlc or {}
        u_open = u_ohlc.get("open", underlying_spot)
        u_high = u_ohlc.get("high", underlying_spot)
        u_low = u_ohlc.get("low", underlying_spot)
        u_close = u_ohlc.get("close", underlying_spot)

        fut_ctx = futures_context or {}
        fut_price = fut_ctx.get("futures_price")
        fut_vwap = fut_ctx.get("futures_vwap")
        fut_rvol = fut_ctx.get("futures_rvol_5m")
        fut_source = fut_ctx.get("vwap_source", "UNAVAILABLE")

        # 5. Market Regime & Breadth Context
        mkt_ctx = market_context or {}
        regime = mkt_ctx.get("regime", "SIDEWAYS_CHOP")
        adx = mkt_ctx.get("adx")
        adv = mkt_ctx.get("advancers", 25)
        dec = mkt_ctx.get("decliners", 25)
        ad_ratio = Decimal(str(round(adv / max(1, dec), 2)))
        vix_lvl = mkt_ctx.get("vix_level", Decimal("13.50"))
        vix_chg = mkt_ctx.get("vix_daily_change_pct", Decimal("0.00"))

        # 6. Open Interest Dynamics (Heuristic)
        oi_1m_delta = None
        if prev_bar and prev_bar.open_interest is not None and bar.open_interest is not None:
            oi_1m_delta = bar.open_interest - prev_bar.open_interest

        oi_session_delta = None
        if session_open_oi is not None and bar.open_interest is not None:
            oi_session_delta = bar.open_interest - session_open_oi

        price_diff = bar.close - bar.open
        oi_interp = self.interpret_oi(price_diff, oi_1m_delta)

        # 7. Exact Market Price Input Selection for IV Inversion
        # Precedence: Fresh quote midpoint is authoritative only when the book
        # is valid, fresh, sufficiently liquid (spread <= 2.5%, bid > 0), and unlocked/uncrossed.
        if quote:
            if is_stale or not is_fresh:
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="CALCULATION_FAILED",
                    failure_reason="STALE_QUOTE_PRICING",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            elif is_locked:
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="CALCULATION_FAILED",
                    failure_reason="LOCKED_BOOK",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            elif is_crossed:
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="CALCULATION_FAILED",
                    failure_reason="CROSSED_BOOK",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            elif best_bid is None or best_bid <= Decimal("0.0"):
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="CALCULATION_FAILED",
                    failure_reason="ZERO_BID",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            elif spread_pct is not None and spread_pct > Decimal("0.025"):
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="SKIPPED_ILLIQUID",
                    failure_reason="WIDE_SPREAD",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            elif mid_price is None or mid_price <= Decimal("0.0"):
                iv_pricing_source = "UNAVAILABLE"
                pricing_val = None
                greeks_res = GreeksResult(
                    status="CALCULATION_FAILED",
                    failure_reason="INVALID_PRICE",
                    pricing_source=iv_pricing_source,
                    implied_volatility=None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                )
            else:
                iv_pricing_source = "QUOTE_MIDPOINT"
                pricing_val = mid_price
                greeks_res = self.greeks_engine.calculate_option_intelligence(
                    market_price=float(pricing_val),
                    spot_price=float(underlying_spot),
                    strike_price=float(bar.strike_price),
                    current_dt=exch_ts or now_utc,
                    expiry_date=bar.expiry_date,
                    option_type=bar.option_type,
                    best_bid=float(best_bid) if best_bid is not None else None,
                    best_ask=float(best_ask) if best_ask is not None else None,
                    pricing_source=iv_pricing_source,
                )
        else:
            # Fallback to bar close only if quote book is empty/unpopulated
            iv_pricing_source = "BAR_CLOSE_LTP"
            pricing_val = bar.close
            greeks_res = self.greeks_engine.calculate_option_intelligence(
                market_price=float(pricing_val),
                spot_price=float(underlying_spot),
                strike_price=float(bar.strike_price),
                current_dt=exch_ts or now_utc,
                expiry_date=bar.expiry_date,
                option_type=bar.option_type,
                best_bid=float(best_bid) if best_bid is not None else None,
                best_ask=float(best_ask) if best_ask is not None else None,
                pricing_source=iv_pricing_source,
            )

        # 8. Signal Eligibility Gate
        is_signal_eligible = (
            not bar.is_partial_bar
            and quote is not None
            and not is_stale
            and is_fresh
            and not is_locked
            and not is_crossed
            and exch_status == "VALID"
            and quote_status == "VALID"
            and spread_pct is not None
            and spread_pct <= Decimal("0.025")
            and not tte.is_expired
            and greeks_res.status == "VALID"
        )

        # Monotonic pipeline latency
        end_monotonic = time.monotonic_ns()
        pipeline_ms = Decimal(str(round((end_monotonic - start_monotonic) / 1_000_000.0, 3)))

        return OptionFeatureSnapshot(
            snapshot_id=str(uuid.uuid4()),
            snapshot_version="1.3.0",
            engine_git_commit=CURRENT_GIT_COMMIT,
            feature_set_id=self.feature_set_id,
            calculation_timestamp_utc=now_utc,
            timeframe=bar.timeframe,
            exchange_timestamp_utc=exch_ts,
            last_trade_timestamp_utc=None,
            received_wall_clock_utc=rec_wall,
            received_monotonic_ns=start_monotonic,
            feed_latency_ms=feed_lat_ms,
            quote_age_seconds=quote_age,
            last_trade_age_seconds=None,
            pipeline_latency_ms=pipeline_ms,
            exchange_time_status=exch_status,
            is_quote_fresh=is_fresh,
            underlying_symbol=bar.underlying_symbol,
            underlying_spot_price=underlying_spot,
            underlying_open=u_open,
            underlying_high=u_high,
            underlying_low=u_low,
            underlying_close=u_close,
            underlying_futures_price=fut_price,
            underlying_futures_vwap=fut_vwap,
            underlying_futures_rvol_5m=fut_rvol,
            underlying_vwap_source=fut_source,
            market_regime=regime,
            trend_strength_adx=adx,
            advancers_count=adv,
            decliners_count=dec,
            advance_decline_ratio=ad_ratio,
            india_vix_level=vix_lvl,
            india_vix_daily_change_pct=vix_chg,
            tradingsymbol=bar.tradingsymbol,
            instrument_token=bar.instrument_token,
            option_type=bar.option_type,
            strike_price=bar.strike_price,
            expiry_date=bar.expiry_date,
            days_to_expiry=tte.calendar_days,
            trading_sessions_to_expiry=tte.trading_sessions_to_expiry,
            atm_distance_points=atm_dist,
            moneyness_category=moneyness,
            premium_open=bar.open,
            premium_high=bar.high,
            premium_low=bar.low,
            premium_close=bar.close,
            premium_bar_volume=bar.volume,
            premium_session_volume=cumulative_session_volume or bar.volume,
            exchange_session_atp=Decimal("0.00"),
            nomad_candle_vwap=bar.close,
            open_interest=bar.open_interest,
            oi_status=bar.oi_status,
            oi_change_1m=oi_1m_delta,
            oi_change_session=oi_session_delta,
            oi_interpretation=oi_interp,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
            spread_absolute=spread_abs,
            spread_percentage=spread_pct,
            bid_depth_quantity_l1=bid_q1,
            ask_depth_quantity_l1=ask_q1,
            total_buy_quantity=None,
            total_sell_quantity=None,
            order_book_imbalance=ob_imbalance,
            greeks_status=greeks_res.status,
            greeks_failure_reason=greeks_res.failure_reason,
            iv_pricing_source=iv_pricing_source,
            iv_market_price=pricing_val,
            implied_volatility=greeks_res.implied_volatility,
            delta=greeks_res.delta,
            gamma=greeks_res.gamma,
            theta=greeks_res.theta,
            vega=greeks_res.vega,
            quote_status=quote_status,
            is_stale=is_stale,
            is_locked=is_locked,
            is_crossed=is_crossed,
            is_partial_bar=bar.is_partial_bar,
            is_valid_for_signal=is_signal_eligible,
        )
