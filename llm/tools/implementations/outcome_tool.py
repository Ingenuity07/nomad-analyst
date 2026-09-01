"""
outcome_tool.py — Read-only LLM tools for recommendation outcomes & backtesting (Module 11).

3 tools:
  1. get_recommendation_outcome   — full outcome for one recommendation
  2. get_strategy_performance     — performance slice by setup/timeframe/direction/regime
  3. get_backtest_result          — full backtest result by run_id

LLM CONSTRAINTS (enforced by read-only design):
  - LLM may read all outcome fields and summarise results.
  - LLM may NOT alter historical outcomes, alter strategy parameters, or claim
    statistical significance from small samples.
  - LLM MUST acknowledge statistical_warnings in every performance response.
  - LLM MUST NOT convert win_rate into guaranteed future probability of profit.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_recommendation_outcome(
    recommendation_id: str,
    evaluation_version: int = 1,
) -> Dict[str, Any]:
    """
    Retrieve the full outcome record for a recommendation.

    Args:
        recommendation_id:   UUID of the StockRecommendation.
        evaluation_version:  Evaluation version to retrieve (default: 1).

    Returns:
        dict with full outcome fields, or error if not found.
    """
    from market.models import RecommendationOutcome, StockRecommendation

    try:
        rec = StockRecommendation.objects.get(id=recommendation_id)
    except StockRecommendation.DoesNotExist:
        return {"error": f"Recommendation {recommendation_id} not found."}
    except Exception as exc:
        return {"error": str(exc)}

    try:
        outcome = RecommendationOutcome.objects.get(
            recommendation=rec,
            evaluation_version=evaluation_version,
        )
    except RecommendationOutcome.DoesNotExist:
        return {
            "recommendation_id": str(rec.id),
            "symbol": rec.instrument.symbol,
            "signal": rec.signal,
            "status": rec.status,
            "outcome": None,
            "message": (
                f"No outcome recorded yet for evaluation_version={evaluation_version}. "
                f"The recommendation is still {rec.status}."
            ),
        }

    return {
        "recommendation_id": str(rec.id),
        "symbol": rec.instrument.symbol,
        "horizon": rec.horizon,
        "signal": rec.signal,
        "setup_type": rec.setup_type,
        "confidence": rec.confidence,
        "as_of": rec.as_of.isoformat(),
        "entry_price": float(rec.entry_price) if rec.entry_price else None,
        "stop_price": float(rec.stop_price) if rec.stop_price else None,
        "target_price": float(rec.target_price) if rec.target_price else None,
        "recommendation_status": rec.status,
        "outcome": {
            "id": str(outcome.id),
            "evaluation_version": outcome.evaluation_version,
            "evaluated_at": outcome.evaluated_at.isoformat(),
            "entry_triggered": outcome.entry_triggered,
            "entry_timestamp": outcome.entry_timestamp.isoformat() if outcome.entry_timestamp else None,
            "actual_entry_price": float(outcome.actual_entry_price) if outcome.actual_entry_price else None,
            "exit_reason": outcome.exit_reason,
            "exit_timestamp": outcome.exit_timestamp.isoformat() if outcome.exit_timestamp else None,
            "actual_exit_price": float(outcome.actual_exit_price) if outcome.actual_exit_price else None,
            "gross_pnl_absolute": float(outcome.gross_pnl_absolute) if outcome.gross_pnl_absolute is not None else None,
            "gross_pnl_percent": float(outcome.gross_pnl_percent) if outcome.gross_pnl_percent is not None else None,
            "cost_absolute": float(outcome.cost_absolute) if outcome.cost_absolute is not None else None,
            "net_pnl_absolute": float(outcome.net_pnl_absolute) if outcome.net_pnl_absolute is not None else None,
            "net_pnl_percent": float(outcome.net_pnl_percent) if outcome.net_pnl_percent is not None else None,
            "risk_amount": float(outcome.risk_amount) if outcome.risk_amount is not None else None,
            "r_multiple": float(outcome.r_multiple) if outcome.r_multiple is not None else None,
            "target_hit": outcome.target_hit,
            "stop_hit": outcome.stop_hit,
            "ambiguous_intrabar": outcome.ambiguous_intrabar,
            "max_favorable_excursion": float(outcome.max_favorable_excursion) if outcome.max_favorable_excursion is not None else None,
            "max_adverse_excursion": float(outcome.max_adverse_excursion) if outcome.max_adverse_excursion is not None else None,
            "holding_duration_bars": outcome.holding_duration_bars,
            "holding_duration_seconds": outcome.holding_duration_seconds,
            "bars_evaluated": outcome.bars_evaluated,
            "data_quality_warnings": outcome.data_quality_warnings,
        },
    }


def get_strategy_performance(
    setup_type: Optional[str] = None,
    timeframe: Optional[str] = None,
    direction: Optional[str] = None,
    horizon: Optional[str] = None,
    strategy_version: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Retrieve aggregated strategy performance metrics from outcome records.

    Performance is computed from RecommendationOutcome records matching the
    specified filters. Always returns statistical_warnings — the LLM must
    acknowledge these in any response.

    Args:
        setup_type:       Filter by setup type (e.g. 'OPENING_RANGE_BREAKOUT').
        timeframe:        Filter by timeframe (e.g. '5m').
        direction:        Filter by signal direction ('BUY' or 'SELL').
        horizon:          Filter by horizon ('INTRADAY', 'DELIVERY_SWING', etc.).
        strategy_version: Filter by strategy config version.
        start_date:       ISO date string (inclusive).
        end_date:         ISO date string (inclusive).
        limit:            Max outcomes to include (default: 500).

    Returns:
        dict with performance metrics, dimension slices, and statistical_warnings.

    LLM WARNING: win_rate is a historical frequency, NOT a probability of future profit.
    NEVER interpret statistical_warnings as minor — they indicate limited sample size.
    """
    from datetime import date
    from market.models import RecommendationOutcome, StockRecommendation
    from market.services.performance_metrics import StrategyPerformanceService

    qs = RecommendationOutcome.objects.select_related(
        "recommendation", "recommendation__instrument"
    ).order_by("evaluated_at")

    # Apply filters via related recommendation fields
    rec_filter: Dict[str, Any] = {}
    if setup_type:
        rec_filter["recommendation__setup_type"] = setup_type
    if timeframe:
        rec_filter["recommendation__timeframe"] = timeframe
    if direction:
        rec_filter["recommendation__signal"] = direction
    if horizon:
        rec_filter["recommendation__horizon"] = horizon
    if strategy_version:
        rec_filter["recommendation__strategy_version"] = strategy_version
    if start_date:
        try:
            rec_filter["recommendation__as_of__date__gte"] = date.fromisoformat(start_date)
        except ValueError:
            return {"error": f"Invalid start_date format: {start_date}. Use YYYY-MM-DD."}
    if end_date:
        try:
            rec_filter["recommendation__as_of__date__lte"] = date.fromisoformat(end_date)
        except ValueError:
            return {"error": f"Invalid end_date format: {end_date}. Use YYYY-MM-DD."}

    if rec_filter:
        qs = qs.filter(**rec_filter)

    qs = qs[:limit]
    outcomes = list(qs)

    if not outcomes:
        return {
            "total_outcomes": 0,
            "message": "No outcomes found for the specified filters.",
            "statistical_warnings": [
                "SMALL_SAMPLE_WARNING: zero outcomes found. No statistics can be computed."
            ],
        }

    svc = StrategyPerformanceService()
    s_date = date.fromisoformat(start_date) if start_date else None
    e_date = date.fromisoformat(end_date) if end_date else None

    report = svc.compute(
        outcomes=outcomes,
        strategy_version=strategy_version,
        start_date=s_date,
        end_date=e_date,
    )

    return {
        "filters_applied": {
            "setup_type": setup_type,
            "timeframe": timeframe,
            "direction": direction,
            "horizon": horizon,
            "strategy_version": strategy_version,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        },
        "performance": report.to_dict(),
        "llm_disclaimer": (
            "win_rate is a historical frequency computed from past trades. "
            "It is NOT a guarantee of future returns. "
            "Always check statistical_warnings before interpreting these results."
        ),
    }


def get_backtest_result(
    run_id: Optional[str] = None,
    universe_name: Optional[str] = None,
    timeframe: Optional[str] = None,
    horizon: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Retrieve backtest run results.

    Args:
        run_id:        Specific backtest run_id to retrieve.
        universe_name: Filter by universe name.
        timeframe:     Filter by timeframe.
        horizon:       Filter by horizon.
        limit:         Maximum runs to list (when run_id not specified).

    Returns:
        Full backtest result including configuration, performance metrics,
        and data quality warnings.

    LLM WARNING: Backtest results reflect HISTORICAL data. They cannot predict
    future performance. All data_quality_warnings must be communicated to the user.
    """
    from market.models import BacktestRun

    if run_id:
        try:
            bt = BacktestRun.objects.get(run_id=run_id)
            return _serialize_backtest_run(bt, full=True)
        except BacktestRun.DoesNotExist:
            return {"error": f"BacktestRun '{run_id}' not found."}

    # List recent runs
    qs = BacktestRun.objects.all()
    if universe_name:
        qs = qs.filter(universe_name=universe_name)
    if timeframe:
        qs = qs.filter(timeframe=timeframe)
    if horizon:
        qs = qs.filter(horizon=horizon)

    runs = list(qs.order_by("-started_at")[:limit])

    return {
        "count": len(runs),
        "runs": [_serialize_backtest_run(bt, full=False) for bt in runs],
        "llm_disclaimer": (
            "Backtest results are computed on historical data only. "
            "All data_quality_warnings document limitations such as "
            "unavailable historical fundamentals or news."
        ),
    }


def _serialize_backtest_run(bt: "BacktestRun", full: bool = True) -> dict:
    base = {
        "run_id": bt.run_id,
        "status": bt.status,
        "universe_name": bt.universe_name,
        "timeframe": bt.timeframe,
        "horizon": bt.horizon,
        "start_date": bt.start_date.isoformat(),
        "end_date": bt.end_date.isoformat(),
        "strategy_version": bt.strategy_version,
        "started_at": bt.started_at.isoformat(),
        "completed_at": bt.completed_at.isoformat() if bt.completed_at else None,
        "data_quality_warnings": bt.data_quality_warnings,
    }
    if full:
        base["config"] = bt.config
        base["result"] = bt.result
        base["error_message"] = bt.error_message
    return base
