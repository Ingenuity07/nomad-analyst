"""
signal_engine.py — Core deterministic signal generation engine for Module 8.

Responsibilities:
  1. Load market context, sector context, technical features (PIT-safe, batched)
  2. Apply market regime gate and sector gate
  3. Run setup detectors and select best-matching setup
  4. Calculate entry, stop (structural/ATR), target
  5. Compute risk/reward and reject if below minimum threshold
  6. Compute multi-dimensional confidence (LOW/MEDIUM/HIGH)
  7. Return a RecommendationDraft dataclass (NOT persisted here)

The LLM never touches this module.
Intraday signals require intraday timeframe data — daily data NEVER simulates intraday.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

import numpy as np
import talib

from django.utils import timezone as django_timezone
from django.db.models import Max, Q

from market.signal_enums import (
    SignalDirection, SignalHorizon, SetupType, ConfidenceLevel,
    RecommendationStatus, EntryType, StopMethod, TargetMethod,
    MIN_RISK_REWARD, CONFIDENCE_WEIGHTS, REGIME_GATE_RULES, CONFIDENCE_THRESHOLD
)
from market.services.setup_detectors import (
    run_all_detectors, SetupResult, detect_breakdown
)

logger = logging.getLogger(__name__)

_INTRADAY_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "60m", "2h", "4h"}


# ─── Output dataclass ─────────────────────────────────────────────────────────

@dataclass
class RecommendationDraft:
    """
    Fully computed recommendation ready for persistence.
    All numeric fields are deterministic — none are LLM-generated.
    """
    instrument_id: str
    horizon: str
    signal: str
    setup_type: str
    as_of: datetime

    # Entry
    entry_type: str
    entry_price: Optional[float]
    entry_condition: str

    # Stop
    stop_price: Optional[float]
    stop_method: str
    invalidation_reason: str

    # Target
    target_price: Optional[float]
    target_method: str

    # R:R
    risk: Optional[float]
    reward: Optional[float]
    risk_reward_ratio: Optional[float]

    # Confidence
    confidence: str
    confidence_components: Dict[str, Any]

    # Context
    market_context: Dict[str, Any]
    sector_context: Dict[str, Any]

    # Explanatory
    supporting_factors: List[str]
    risk_factors: List[str]
    setup_details: Dict[str, Any]
    data_quality: Dict[str, Any]

    status: str = RecommendationStatus.ACTIVE.value
    calculation_version: int = 1


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _s(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safe float conversion."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _parse_as_of(as_of: Any) -> datetime:
    from django.utils import timezone as tz
    if not as_of:
        return tz.now()
    if isinstance(as_of, str):
        dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        return tz.make_aware(dt, timezone.utc) if tz.is_naive(dt) else dt
    if isinstance(as_of, datetime):
        return tz.make_aware(as_of, timezone.utc) if tz.is_naive(as_of) else as_of
    raise ValueError(f"Unsupported as_of: {type(as_of)}")


def _compute_atr_from_features(tf: Dict[str, Any]) -> Optional[float]:
    return _s(tf.get("ATR_14"))


def _entry_from_setup(setup: SetupResult, close: float, tf: Dict[str, Any]) -> tuple:
    """
    Returns (entry_type, entry_price, entry_condition) specific to the setup.
    """
    close_f = _s(close, close)

    if setup.setup_type == SetupType.BREAKOUT:
        r_high = _s(tf.get("rolling_high_20"))
        if r_high:
            entry_price = round(r_high * 1.005, 2)  # Just above 20-day high
            return (
                EntryType.BREAKOUT_CONFIRMATION.value,
                entry_price,
                f"Enter only if price sustains above {entry_price:.2f} (0.5% above 20-day high {r_high:.2f}) on close"
            )

    elif setup.setup_type == SetupType.PULLBACK:
        sma20 = _s(tf.get("SMA_20"))
        sma50 = _s(tf.get("SMA_50"))
        support = sma50 or sma20
        if support:
            return (
                EntryType.SUPPORT_RETEST.value,
                round(close_f, 2),
                f"Enter near support at {support:.2f} (SMA zone). Confirm intraday stabilisation."
            )

    elif setup.setup_type == SetupType.MOMENTUM:
        return (
            EntryType.MOMENTUM_CONFIRMATION.value,
            round(close_f, 2),
            f"Enter at market price {close_f:.2f} on momentum confirmation (volume > 1.2x avg)"
        )

    elif setup.setup_type in (SetupType.BREAKDOWN,):
        r_low = _s(tf.get("rolling_low_20"))
        if r_low:
            entry_price = round(r_low * 0.995, 2)
            return (
                EntryType.BREAKOUT_CONFIRMATION.value,
                entry_price,
                f"Enter short only if price sustains below {entry_price:.2f} (breakdown confirmation)"
            )

    elif setup.setup_type == SetupType.RECOVERY_REVERSAL:
        return (
            EntryType.SUPPORT_RETEST.value,
            round(close_f, 2),
            f"Enter near current price {close_f:.2f} at oversold support. Wait for green candle confirmation."
        )

    # Default: current market price
    return (
        EntryType.CURRENT_MARKET_PRICE.value,
        round(close_f, 2),
        f"Enter at current market price {close_f:.2f}"
    )


def _stop_from_setup(
    setup: SetupResult, entry_price: float, close: float, tf: Dict[str, Any], direction: str
) -> tuple:
    """
    Returns (stop_price, stop_method, invalidation_reason).
    Priority: structural → ATR-based → percentage fallback.
    """
    atr = _compute_atr_from_features(tf)

    if setup.setup_type in (SetupType.BREAKOUT, SetupType.MOMENTUM, SetupType.TREND_CONTINUATION):
        sma50 = _s(tf.get("SMA_50"))
        r_low = _s(tf.get("rolling_low_20"))
        structural = sma50 or r_low
        if structural and structural < entry_price:
            return (
                round(structural * 0.99, 2),
                StopMethod.STRUCTURAL.value,
                f"Setup invalidated if price closes below structural support {structural:.2f} (SMA-50/20-day low)"
            )

    elif setup.setup_type == SetupType.PULLBACK:
        r_low = _s(tf.get("rolling_low_20"))
        if r_low and r_low < entry_price:
            return (
                round(r_low * 0.99, 2),
                StopMethod.SWING_HIGH_LOW.value,
                f"Setup invalidated if price closes below recent swing low {r_low:.2f}"
            )

    elif setup.setup_type == SetupType.BREAKDOWN:
        r_high = _s(tf.get("rolling_high_20"))
        if r_high and r_high > entry_price:
            return (
                round(r_high * 1.01, 2),
                StopMethod.STRUCTURAL.value,
                f"Short invalidated if price reclaims above {r_high:.2f}"
            )

    elif setup.setup_type == SetupType.RECOVERY_REVERSAL:
        r_low = _s(tf.get("rolling_low_20"))
        if r_low:
            return (
                round(r_low * 0.985, 2),
                StopMethod.SWING_HIGH_LOW.value,
                f"Reversal invalidated if price makes new lower low below {r_low:.2f}"
            )

    # ATR-based fallback
    if atr:
        multiplier = 1.5
        if direction == SignalDirection.BUY.value:
            stop = round(entry_price - multiplier * atr, 2)
            return (
                stop,
                StopMethod.ATR_BASED.value,
                f"Stop at {stop:.2f} = entry {entry_price:.2f} - {multiplier}x ATR({atr:.2f})"
            )
        else:
            stop = round(entry_price + multiplier * atr, 2)
            return (
                stop,
                StopMethod.ATR_BASED.value,
                f"Stop at {stop:.2f} = entry {entry_price:.2f} + {multiplier}x ATR({atr:.2f})"
            )

    # Last resort percentage fallback
    pct = 0.04  # 4%
    if direction == SignalDirection.BUY.value:
        stop = round(entry_price * (1 - pct), 2)
        return (stop, StopMethod.PERCENTAGE_FALLBACK.value, f"Fallback 4% stop below entry")
    else:
        stop = round(entry_price * (1 + pct), 2)
        return (stop, StopMethod.PERCENTAGE_FALLBACK.value, f"Fallback 4% stop above entry (short)")


def _target_from_setup(
    setup: SetupResult, entry_price: float, stop_price: float, tf: Dict[str, Any],
    direction: str, min_rr: float
) -> tuple:
    """
    Returns (target_price, target_method).
    Priority: resistance/measured_move → ATR multiple → R:R derived.
    """
    atr = _compute_atr_from_features(tf)
    r_high = _s(tf.get("rolling_high_20"))

    risk = abs(entry_price - stop_price) if stop_price is not None else None

    if setup.setup_type == SetupType.BREAKOUT and r_high:
        # Measured move: project the recent range above breakout
        r_low = _s(tf.get("rolling_low_20"))
        if r_low and r_high > r_low:
            measured_move = r_high - r_low
            target = round(entry_price + measured_move, 2)
            return (target, TargetMethod.MEASURED_MOVE.value)

    elif setup.setup_type == SetupType.BREAKDOWN:
        r_low = _s(tf.get("rolling_low_20"))
        if r_low and r_high:
            measured_move = r_high - r_low
            target = round(entry_price - measured_move, 2)
            return (target, TargetMethod.MEASURED_MOVE.value)

    # ATR-based target
    if atr:
        multiplier = max(min_rr * 1.5, 2.0)
        if direction == SignalDirection.BUY.value:
            target = round(entry_price + multiplier * atr, 2)
        else:
            target = round(entry_price - multiplier * atr, 2)
        return (target, TargetMethod.ATR_MULTIPLE.value)

    # R:R derived target
    if risk:
        if direction == SignalDirection.BUY.value:
            target = round(entry_price + min_rr * risk, 2)
        else:
            target = round(entry_price - min_rr * risk, 2)
        return (target, TargetMethod.RISK_REWARD_DERIVED.value)

    return (None, TargetMethod.RISK_REWARD_DERIVED.value)


def _compute_confidence(
    best_setup: SetupResult,
    market_context: Dict[str, Any],
    sector_context: Dict[str, Any],
    fundamental_data: Dict[str, Any],
    news_events: List[Any],
    tf: Dict[str, Any],
    direction: str
) -> tuple:
    """
    Returns (confidence_level, confidence_components_dict, adjusted_score).

    Confidence is derived from 5 dimensions with defined weights.
    It does NOT claim probability of profit.
    """
    components = {}

    # 1. Technical confirmation (from setup score)
    tech_raw = best_setup.score
    components["technical_confirmation"] = {
        "score": round(tech_raw, 1),
        "weight": CONFIDENCE_WEIGHTS["technical_confirmation"],
        "note": f"Setup '{best_setup.setup_type.value}' scored {tech_raw:.0f}/100"
    }

    # 2. Market alignment (regime gate)
    mkt_score = 50.0  # Neutral baseline
    nifty_trend = "sideways"
    if market_context.get("index_regimes"):
        nifty_trend = market_context["index_regimes"].get("^NSEI", {}).get("trend", "sideways")

    if direction == SignalDirection.BUY.value:
        if nifty_trend == "bullish":
            mkt_score += REGIME_GATE_RULES["BULLISH_BUY_BOOST"]
        elif nifty_trend == "bearish":
            mkt_score += REGIME_GATE_RULES["BEARISH_BUY_PENALTY"]

    # High volatility check
    volatility = market_context.get("index_regimes", {}).get("^NSEI", {}).get("volatility", "normal")
    if volatility == "high":
        mkt_score += REGIME_GATE_RULES["HIGH_VOL_PENALTY"]

    mkt_score = max(0.0, min(100.0, mkt_score))
    components["market_alignment"] = {
        "score": round(mkt_score, 1),
        "weight": CONFIDENCE_WEIGHTS["market_alignment"],
        "note": f"Nifty trend={nifty_trend}, volatility={volatility}"
    }

    # 3. Sector alignment
    sec_score = 50.0
    sector_tier = sector_context.get("tier", "neutral")
    sector_momentum = sector_context.get("momentum_state", "stable")

    if direction == SignalDirection.BUY.value:
        if sector_tier == "strongest":
            sec_score += REGIME_GATE_RULES["STRONG_SECTOR_BOOST"] + 15.0
        elif sector_tier == "weakest":
            sec_score += REGIME_GATE_RULES["WEAK_SECTOR_PENALTY"]
        elif sector_momentum == "improving":
            sec_score += 10.0
        elif sector_momentum == "deteriorating":
            sec_score += REGIME_GATE_RULES["WEAK_SECTOR_PENALTY"]

    sec_score = max(0.0, min(100.0, sec_score))
    components["sector_alignment"] = {
        "score": round(sec_score, 1),
        "weight": CONFIDENCE_WEIGHTS["sector_alignment"],
        "note": f"Sector tier={sector_tier}, momentum={sector_momentum}"
    }

    # 4. Fundamental support
    fun_score = 50.0  # Neutral if no fundamentals
    if fundamental_data:
        roe = _s(fundamental_data.get("return_on_equity"))
        de = _s(fundamental_data.get("debt_equity"))
        rev_g = _s(fundamental_data.get("revenue_growth_yoy"))

        good_count = 0
        if roe is not None and roe > 0.12:
            good_count += 1
        if de is not None and de < 1.0:
            good_count += 1
        if rev_g is not None and rev_g > 0.05:
            good_count += 1

        fun_score = min(100.0, 40.0 + good_count * 20.0)

    components["fundamental_support"] = {
        "score": round(fun_score, 1),
        "weight": CONFIDENCE_WEIGHTS["fundamental_support"],
        "note": "Based on ROE, Debt/Equity, Revenue Growth"
    }

    # 5. News/event support
    news_score = 60.0  # Neutral
    if news_events:
        pos = any(any(w in str(e.get("headline", "")).lower()
                      for w in ("rise", "order", "growth", "profit", "dividend"))
                  for e in news_events)
        neg = any(any(w in str(e.get("headline", "")).lower()
                      for w in ("drop", "loss", "penalty", "fall", "investigation"))
                  for e in news_events)
        if pos:
            news_score = 85.0
        if neg:
            news_score = 30.0

    components["news_support"] = {
        "score": round(news_score, 1),
        "weight": CONFIDENCE_WEIGHTS["news_support"],
        "note": f"{len(news_events)} recent events evaluated"
    }

    # Weighted total
    total = sum(
        v["score"] * v["weight"]
        for v in components.values()
    )

    if total >= CONFIDENCE_THRESHOLD[ConfidenceLevel.HIGH]:
        level = ConfidenceLevel.HIGH.value
    elif total >= CONFIDENCE_THRESHOLD[ConfidenceLevel.MEDIUM]:
        level = ConfidenceLevel.MEDIUM.value
    else:
        level = ConfidenceLevel.LOW.value

    components["overall"] = {"score": round(total, 1), "level": level}
    return level, components, total


# ─── Main Signal Engine class ──────────────────────────────────────────────────

class SignalEngine:
    """
    Deterministic signal generation service.

    Usage:
        engine = SignalEngine()
        draft = engine.generate_recommendation(instrument, SignalHorizon.DELIVERY_SWING, as_of)
    """

    def __init__(self):
        pass

    def _parse_as_of_internal(self, as_of: Any) -> datetime:
        """Public wrapper for the module-level _parse_as_of helper."""
        return _parse_as_of(as_of)

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_recommendation(
        self,
        instrument,  # Instrument model instance
        horizon: str,
        as_of: Any = None
    ) -> RecommendationDraft:
        """
        Generate a fully deterministic recommendation for a single instrument.
        Returns a RecommendationDraft (NOT persisted).
        """
        from market.models import (
            OHLCVBar, TechnicalFeature, DerivedFundamentalMetric,
            IncomeStatement, NewsItem, CorporateDisclosure, MarketContextSnapshot
        )

        dt_as_of = _parse_as_of(as_of)
        horizon_enum = SignalHorizon(horizon)

        # ── Intraday gate (Module 9) ──────────────────────────────────────────
        # The gate is now delegated to IntradayReadinessService, which checks:
        #   1. Supported timeframe
        #   2. Minimum bar count (per timeframe)
        #   3. Data quality (HEALTHY or INCOMPLETE — not STALE/UNAVAILABLE)
        #   4. Critical data gaps within tolerance
        #   5. Technical features exist for the timeframe
        # The default timeframe for intraday signals is 5m.
        if horizon_enum == SignalHorizon.INTRADAY:
            from market.services.intraday_readiness import IntradayReadinessService
            intraday_timeframe = "5m"   # Default intraday resolution
            readiness = IntradayReadinessService().check_readiness(
                instrument, intraday_timeframe, as_of=dt_as_of
            )
            if not readiness.is_ready:
                return self._not_ready_draft(
                    instrument, horizon, dt_as_of,
                    f"INTRADAY NOT_READY [{intraday_timeframe}]: {readiness.reason}"
                )

        # ── Load technical features (PIT-safe) ───────────────────────────────
        timeframe = "1d" if horizon_enum != SignalHorizon.INTRADAY else "5m"

        # Use order_by('instrument') to satisfy Django's requirement for ordered
        # querysets when using .first() after annotation.
        latest_tf_ts_row = TechnicalFeature.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__lte=dt_as_of
        ).order_by('instrument').values('instrument').annotate(max_ts=Max('timestamp')).first()

        tf_dict: Dict[str, Any] = {}
        if latest_tf_ts_row:
            tf_records = TechnicalFeature.objects.filter(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=latest_tf_ts_row["max_ts"]
            )
            tf_dict = {r.name: (_s(r.value) if r.value is not None else None) for r in tf_records}

        # ── Load latest daily bar (for close price) ───────────────────────────
        latest_bar = OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe="1d",
            timestamp__lte=dt_as_of
        ).order_by('-timestamp').first()

        if not latest_bar:
            return self._insufficient_draft(
                instrument, horizon, dt_as_of, "No OHLCV bar available",
                {"status": "MISSING", "missing_fields": ["latest_bar"]}
            )

        close = float(latest_bar.close)

        # Staleness check
        if (dt_as_of - latest_bar.timestamp) > timedelta(days=5):
            return self._insufficient_draft(
                instrument, horizon, dt_as_of,
                f"Latest bar is {(dt_as_of - latest_bar.timestamp).days} days old (stale)",
                {"status": "STALE", "missing_fields": ["fresh_bar"]}
            )

        # ── Data quality assessment ───────────────────────────────────────────
        data_quality = self._assess_data_quality(tf_dict, latest_bar, dt_as_of)

        if data_quality["status"] == "INSUFFICIENT_MARKET_DATA":
            return self._insufficient_draft(
                instrument, horizon, dt_as_of, "Insufficient technical features",
                data_quality
            )

        # ── Market context (PIT-safe) ─────────────────────────────────────────
        mkt_snapshot = MarketContextSnapshot.objects.filter(
            as_of__lte=dt_as_of
        ).order_by('-as_of').first()

        market_context: Dict[str, Any] = {}
        if mkt_snapshot:
            market_context = {
                "index_regimes": mkt_snapshot.index_regimes or {},
                "breadth": mkt_snapshot.breadth or {},
            }

        # ── Sector context ────────────────────────────────────────────────────
        sector_context: Dict[str, Any] = {}
        sector_name = instrument.company.sector if instrument.company else None
        if mkt_snapshot and mkt_snapshot.sector_rankings and sector_name:
            for sec_item in mkt_snapshot.sector_rankings:
                if sec_item.get("sector") == sector_name:
                    sector_context = sec_item
                    break

        # ── Fundamental data (strict PIT-safe using filing_date) ──────────────
        company = instrument.company
        fundamental_data: Dict[str, Any] = {}
        if company:
            visible_stmts = IncomeStatement.objects.filter(
                company=company,
                period_type="ANNUAL",
                filing_date__lte=dt_as_of.date()
            ).values_list('period_string', flat=True)

            if visible_stmts:
                metrics = DerivedFundamentalMetric.objects.filter(
                    company=company,
                    period_type="ANNUAL",
                    period_string__in=list(visible_stmts)
                )
                best = {}
                for m in metrics:
                    if m.name not in best or m.period_string > best[m.name]["period"]:
                        best[m.name] = {"value": _s(m.value), "period": m.period_string}
                fundamental_data = {k: v["value"] for k, v in best.items()}

        # ── News events (PIT-safe, last 14 days) ──────────────────────────────
        start_news = dt_as_of - timedelta(days=14)
        news_events = []
        if company:
            news_items = list(NewsItem.objects.filter(
                company=company,
                published_at__range=(start_news, dt_as_of)
            ).values("headline", "published_at", "event_type"))
            disclosures = list(CorporateDisclosure.objects.filter(
                company=company,
                published_at__range=(start_news, dt_as_of)
            ).values("headline", "published_at", "category"))
            news_events = news_items + disclosures

        # ── Run setup detectors ───────────────────────────────────────────────
        all_results = run_all_detectors(tf_dict, close)

        # Pick best detected setup; if none, fall back to highest-scoring
        best = all_results[0] if all_results else None
        if best is None or not best.detected:
            # No setup detected — check for NO_ACTION
            return self._no_action_draft(
                instrument, horizon, dt_as_of,
                "No qualifying setup detected from current technical configuration",
                tf_dict, market_context, sector_context,
                data_quality, all_results
            )

        # ── Determine direction ───────────────────────────────────────────────
        if best.setup_type in (SetupType.BREAKDOWN,):
            direction = SignalDirection.SELL.value
        else:
            direction = SignalDirection.BUY.value

        # ── Entry, Stop, Target ───────────────────────────────────────────────
        entry_type, entry_price, entry_condition = _entry_from_setup(best, close, tf_dict)
        stop_price, stop_method, invalidation_reason = _stop_from_setup(
            best, entry_price, close, tf_dict, direction
        )

        min_rr = MIN_RISK_REWARD.get(horizon_enum, 1.5)
        target_price, target_method = _target_from_setup(
            best, entry_price, stop_price, tf_dict, direction, min_rr
        )

        # ── Risk / Reward ─────────────────────────────────────────────────────
        risk = reward = rr_ratio = None
        rr_rejected = False
        if entry_price is not None and stop_price is not None and target_price is not None:
            if direction == SignalDirection.BUY.value:
                risk = abs(entry_price - stop_price)
                reward = abs(target_price - entry_price)
            else:
                risk = abs(stop_price - entry_price)
                reward = abs(entry_price - target_price)

            if risk > 0:
                rr_ratio = round(reward / risk, 2)
                if rr_ratio < min_rr:
                    rr_rejected = True

        if rr_rejected:
            return self._no_action_draft(
                instrument, horizon, dt_as_of,
                f"Setup detected ({best.setup_type.value}) but R:R={rr_ratio:.2f} < minimum {min_rr}. Rejected.",
                tf_dict, market_context, sector_context,
                data_quality, all_results
            )

        # ── Confidence ────────────────────────────────────────────────────────
        confidence_level, confidence_components, _ = _compute_confidence(
            best, market_context, sector_context,
            fundamental_data, news_events, tf_dict, direction
        )

        # ── Build supporting / risk factors ───────────────────────────────────
        supporting_factors = list(best.conditions_met)
        risk_factors = list(best.conditions_failed)

        # Add regime/sector factors
        nifty_trend = market_context.get("index_regimes", {}).get("^NSEI", {}).get("trend", "sideways")
        if direction == SignalDirection.BUY.value and nifty_trend == "bullish":
            supporting_factors.append("Market regime is bullish — aligns with BUY direction")
        elif direction == SignalDirection.BUY.value and nifty_trend == "bearish":
            risk_factors.append("Market regime is bearish — headwind for BUY setup")

        sector_tier = sector_context.get("tier", "neutral")
        if sector_tier == "strongest":
            supporting_factors.append(f"Sector '{sector_name}' is a top-performing sector")
        elif sector_tier == "weakest":
            risk_factors.append(f"Sector '{sector_name}' is underperforming — adds risk")

        return RecommendationDraft(
            instrument_id=str(instrument.id),
            horizon=horizon,
            signal=direction,
            setup_type=best.setup_type.value,
            as_of=dt_as_of,
            entry_type=entry_type,
            entry_price=entry_price,
            entry_condition=entry_condition,
            stop_price=stop_price,
            stop_method=stop_method,
            invalidation_reason=invalidation_reason,
            target_price=target_price,
            target_method=target_method,
            risk=round(risk, 2) if risk is not None else None,
            reward=round(reward, 2) if reward is not None else None,
            risk_reward_ratio=rr_ratio,
            confidence=confidence_level,
            confidence_components=confidence_components,
            market_context=market_context,
            sector_context=sector_context,
            supporting_factors=supporting_factors,
            risk_factors=risk_factors,
            setup_details=best.as_dict(),
            data_quality=data_quality,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _assess_data_quality(self, tf: Dict[str, Any], bar, dt_as_of: datetime) -> Dict[str, Any]:
        missing = []
        status = "COMPLETE"

        if not bar:
            return {"status": "INSUFFICIENT_MARKET_DATA", "missing_fields": ["latest_bar"]}

        for key in ("RSI_14", "SMA_50", "SMA_200", "ATR_14"):
            if tf.get(key) is None:
                missing.append(key)

        if missing:
            status = "PARTIAL"

        return {
            "status": status,
            "missing_fields": missing,
            "bar_timestamp": bar.timestamp.isoformat(),
            "staleness_days": (dt_as_of - bar.timestamp).days
        }

    def _not_ready_draft(self, inst, horizon, dt_as_of, reason) -> RecommendationDraft:
        return RecommendationDraft(
            instrument_id=str(inst.id),
            horizon=horizon,
            signal=SignalDirection.NOT_READY.value,
            setup_type=SetupType.NONE.value,
            as_of=dt_as_of,
            entry_type=EntryType.CURRENT_MARKET_PRICE.value,
            entry_price=None, entry_condition=reason,
            stop_price=None, stop_method=StopMethod.PERCENTAGE_FALLBACK.value,
            invalidation_reason=reason,
            target_price=None, target_method=TargetMethod.RISK_REWARD_DERIVED.value,
            risk=None, reward=None, risk_reward_ratio=None,
            confidence=ConfidenceLevel.LOW.value,
            confidence_components={},
            market_context={}, sector_context={},
            supporting_factors=[], risk_factors=[reason],
            setup_details={}, data_quality={"status": "NOT_READY"},
            status=RecommendationStatus.CANCELLED.value,
        )

    def _insufficient_draft(self, inst, horizon, dt_as_of, reason, dq) -> RecommendationDraft:
        return RecommendationDraft(
            instrument_id=str(inst.id),
            horizon=horizon,
            signal=SignalDirection.INSUFFICIENT_DATA.value,
            setup_type=SetupType.NONE.value,
            as_of=dt_as_of,
            entry_type=EntryType.CURRENT_MARKET_PRICE.value,
            entry_price=None, entry_condition=reason,
            stop_price=None, stop_method=StopMethod.PERCENTAGE_FALLBACK.value,
            invalidation_reason=reason,
            target_price=None, target_method=TargetMethod.RISK_REWARD_DERIVED.value,
            risk=None, reward=None, risk_reward_ratio=None,
            confidence=ConfidenceLevel.LOW.value,
            confidence_components={},
            market_context={}, sector_context={},
            supporting_factors=[], risk_factors=[reason],
            setup_details={}, data_quality=dq,
            status=RecommendationStatus.CANCELLED.value,
        )

    def _no_action_draft(self, inst, horizon, dt_as_of, reason, tf, mkt, sec, dq, all_results) -> RecommendationDraft:
        return RecommendationDraft(
            instrument_id=str(inst.id),
            horizon=horizon,
            signal=SignalDirection.NO_ACTION.value,
            setup_type=SetupType.NONE.value,
            as_of=dt_as_of,
            entry_type=EntryType.CURRENT_MARKET_PRICE.value,
            entry_price=None, entry_condition=reason,
            stop_price=None, stop_method=StopMethod.PERCENTAGE_FALLBACK.value,
            invalidation_reason=reason,
            target_price=None, target_method=TargetMethod.RISK_REWARD_DERIVED.value,
            risk=None, reward=None, risk_reward_ratio=None,
            confidence=ConfidenceLevel.LOW.value,
            confidence_components={},
            market_context=mkt, sector_context=sec,
            supporting_factors=[],
            risk_factors=[reason],
            setup_details={"evaluated_setups": [r.as_dict() for r in all_results]},
            data_quality=dq,
            status=RecommendationStatus.CANCELLED.value,
        )
