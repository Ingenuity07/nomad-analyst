"""
intraday_tool.py — Read-only LLM tools for intraday recommendations (Module 10).

3 tools:
  1. get_intraday_recommendations  — list with filters
  2. get_intraday_recommendation   — full detail for one recommendation
  3. get_intraday_setups           — all detected setups (scores) for a symbol at as_of

LLM CONSTRAINTS (enforced by read-only design):
  - LLM may read all fields.
  - LLM may NOT modify: signal, entry_price, stop_price, target_price, confidence.
  - LLM may explain: why setup exists, market context, sector context,
    risks, contradictions, invalidation conditions.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_intraday_recommendations(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    setup_type: Optional[str] = None,
    direction: Optional[str] = None,
    confidence: Optional[str] = None,
    status: Optional[str] = None,
    session_window: Optional[str] = None,
    as_of: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Retrieve intraday recommendations with optional filters.

    Args:
        symbol:        Stock ticker symbol (e.g. 'RELIANCE').
        timeframe:     Timeframe filter (e.g. '5m', '15m').
        setup_type:    Setup type (e.g. 'OPENING_RANGE_BREAKOUT').
        direction:     Signal direction ('BUY' or 'SELL').
        confidence:    Confidence level ('HIGH', 'MEDIUM', 'LOW').
        status:        Recommendation status ('ACTIVE', 'EXPIRED', etc.).
        session_window: Session window filter ('MORNING', 'MIDDAY', etc.).
        as_of:         ISO datetime string to filter by as_of.
        limit:         Maximum number of records to return (max 50).

    Returns:
        dict with 'recommendations' list and 'count'.
    """
    from market.models import StockRecommendation, Instrument

    qs = StockRecommendation.objects.filter(horizon="INTRADAY").select_related("instrument")

    if symbol:
        try:
            inst = Instrument.objects.get(symbol=symbol.upper())
            qs = qs.filter(instrument=inst)
        except Instrument.DoesNotExist:
            return {"error": f"Instrument '{symbol}' not found.", "recommendations": [], "count": 0}

    if timeframe:
        qs = qs.filter(timeframe=timeframe)

    if setup_type:
        qs = qs.filter(setup_type=setup_type)

    if direction:
        qs = qs.filter(signal=direction.upper())

    if confidence:
        qs = qs.filter(confidence=confidence.upper())

    if status:
        qs = qs.filter(status=status.upper())

    if session_window:
        qs = qs.filter(session_window=session_window.upper())

    if as_of:
        try:
            dt = datetime.fromisoformat(as_of)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            qs = qs.filter(as_of__date=dt.date())
        except ValueError:
            return {"error": f"Invalid as_of format: '{as_of}'. Use ISO format.", "recommendations": [], "count": 0}

    limit = min(int(limit), 50)
    recs = qs.order_by("-generated_at")[:limit]

    data = []
    for r in recs:
        data.append({
            "id": str(r.id),
            "symbol": r.instrument.symbol,
            "horizon": r.horizon,
            "timeframe": r.timeframe,
            "signal": r.signal,
            "setup_type": r.setup_type,
            "confidence": r.confidence,
            "status": r.status,
            "session_window": r.session_window,
            "strategy_version": r.strategy_version,
            "entry_price": str(r.entry_price) if r.entry_price else None,
            "stop_price": str(r.stop_price) if r.stop_price else None,
            "target_price": str(r.target_price) if r.target_price else None,
            "target_2_price": str(r.target_2_price) if r.target_2_price else None,
            "risk_reward_ratio": str(r.risk_reward_ratio) if r.risk_reward_ratio else None,
            "as_of": r.as_of.isoformat(),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "generated_at": r.generated_at.isoformat(),
        })

    return {"recommendations": data, "count": len(data)}


def get_intraday_recommendation(
    recommendation_id: Optional[str] = None,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve full detail for a single intraday recommendation.

    Provide either recommendation_id (UUID) or symbol (returns latest active).

    Returns:
        Full recommendation dict including setup_details, confidence_components,
        supporting_factors, risk_factors, intraday indicators, OR range context.
    """
    from market.models import StockRecommendation, Instrument

    if recommendation_id:
        try:
            r = StockRecommendation.objects.select_related("instrument").get(
                id=recommendation_id, horizon="INTRADAY"
            )
        except StockRecommendation.DoesNotExist:
            return {"error": f"Intraday recommendation '{recommendation_id}' not found."}
    elif symbol:
        try:
            inst = Instrument.objects.get(symbol=symbol.upper())
        except Instrument.DoesNotExist:
            return {"error": f"Instrument '{symbol}' not found."}
        r = (StockRecommendation.objects
             .filter(instrument=inst, horizon="INTRADAY", status="ACTIVE")
             .order_by("-generated_at").first())
        if not r:
            return {"error": f"No active intraday recommendation for '{symbol}'."}
    else:
        return {"error": "Provide either recommendation_id or symbol."}

    return {
        "id": str(r.id),
        "symbol": r.instrument.symbol,
        "horizon": r.horizon,
        "timeframe": r.timeframe,
        "signal": r.signal,
        "setup_type": r.setup_type,
        "confidence": r.confidence,
        "confidence_components": r.confidence_components,
        "status": r.status,
        "session_window": r.session_window,
        "strategy_version": r.strategy_version,
        "entry_type": r.entry_type,
        "entry_price": str(r.entry_price) if r.entry_price else None,
        "entry_condition": r.entry_condition,
        "stop_price": str(r.stop_price) if r.stop_price else None,
        "stop_method": r.stop_method,
        "invalidation_reason": r.invalidation_reason,
        "target_price": str(r.target_price) if r.target_price else None,
        "target_method": r.target_method,
        "target_2_price": str(r.target_2_price) if r.target_2_price else None,
        "target_2_method": r.target_2_method,
        "risk": str(r.risk) if r.risk else None,
        "reward": str(r.reward) if r.reward else None,
        "risk_reward_ratio": str(r.risk_reward_ratio) if r.risk_reward_ratio else None,
        "supporting_factors": r.supporting_factors,
        "risk_factors": r.risk_factors,
        "setup_details": r.setup_details,
        "market_context": r.market_context,
        "sector_context": r.sector_context,
        "data_quality": r.data_quality,
        "as_of": r.as_of.isoformat(),
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "generated_at": r.generated_at.isoformat(),
        "llm_explanation": r.llm_explanation,
    }


def get_intraday_setups(
    symbol: str,
    timeframe: str = "5m",
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run intraday setup detectors for a symbol and return all scored setups.

    This is a diagnostic/research tool — useful for understanding
    which setups are forming, their scores, and why they did/did not fire.

    Does NOT persist any recommendation. Read-only analysis.

    Args:
        symbol:    Stock ticker symbol.
        timeframe: '5m' or '15m'.
        as_of:     ISO datetime string (defaults to now).

    Returns:
        dict with 'setups' (list of scored detector results) and 'context'
        (session window, indicators, OR range).
    """
    from market.models import Instrument, OHLCVBar
    from market.services.intraday_indicators import compute_intraday_indicators
    from market.services.opening_range import compute_opening_range
    from market.services.intraday_session import classify_session
    from market.services.intraday_detectors import run_intraday_detectors
    from market.services.market_session import IndianMarketSession
    from market.intraday_strategy_config import MIN_BARS_FOR_ANALYSIS

    IST = IndianMarketSession.IST

    try:
        inst = Instrument.objects.get(symbol=symbol.upper())
    except Instrument.DoesNotExist:
        return {"error": f"Instrument '{symbol}' not found."}

    if as_of:
        try:
            dt = datetime.fromisoformat(as_of)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return {"error": f"Invalid as_of: '{as_of}'."}
    else:
        from django.utils import timezone as tz
        dt = tz.now()

    dt_ist = dt.astimezone(IST)
    session_date = dt_ist.date()

    bars = list(OHLCVBar.objects.filter(
        instrument=inst, timeframe=timeframe, timestamp__lte=dt
    ).order_by("-timestamp")[:200])
    bars.reverse()

    min_bars = MIN_BARS_FOR_ANALYSIS.get(timeframe, 30)
    if len(bars) < min_bars:
        return {
            "error": f"Insufficient intraday bars ({len(bars)} loaded, {min_bars} needed).",
            "symbol": symbol, "timeframe": timeframe,
        }

    ind = compute_intraday_indicators(bars, session_date)
    or_range = compute_opening_range(bars, session_date, timeframe)
    sw = classify_session(dt)

    prev_close = float(bars[-2].close) if len(bars) >= 2 else None

    all_results = run_intraday_detectors(
        ind=ind,
        or_range=or_range,
        bars=bars,
        session_window=sw.window,
        prev_bar_close=prev_close,
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "as_of": dt.isoformat(),
        "session_window": sw.window,
        "minutes_elapsed": sw.minutes_elapsed,
        "minutes_remaining": sw.minutes_remaining,
        "context": {
            "indicators": ind.as_dict(),
            "opening_range": {
                "high": or_range.high, "low": or_range.low,
                "range_pct": or_range.range_pct, "is_complete": or_range.is_complete,
            } if or_range else None,
        },
        "setups": [
            {
                "setup_type": r.setup_type.value,
                "detected": r.detected,
                "score": round(r.score, 1),
                "conditions_met": r.conditions_met,
                "conditions_failed": r.conditions_failed,
                "relevant_values": r.relevant_values,
            }
            for r in all_results
        ],
        "detected_count": sum(1 for r in all_results if r.detected),
        "total_evaluated": len(all_results),
    }
