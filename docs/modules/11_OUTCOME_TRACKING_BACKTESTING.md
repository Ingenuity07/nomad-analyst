# Module 11 — Recommendation Outcome Tracking & Backtesting Foundation

## Objective

Build the research and evaluation foundation required to determine whether
Nomad Analyst's recommendations actually work in practice.

Module 10 generates genuinely intraday-aware recommendations.
Module 11 now measures:

- Whether the entry price was triggered
- Whether the stop or target was hit — and which came first
- What happened in same-bar ambiguity
- When each event occurred and how many bars it took
- The resulting P&L, R-multiple, MFE, and MAE
- Aggregated strategy performance across any slice
- Full backtest runs over historical data

---

## Architecture

```
StockRecommendation (ACTIVE)
        │
        ▼
EntryEvaluator
  BUY:  triggered when bar.high >= entry_price
  SELL: triggered when bar.low  <= entry_price
        │
        ▼ (entry triggered)
ExitEvaluator
  BUY  target: bar.high >= target_price  → TARGET_HIT
  BUY  stop:   bar.low  <= stop_price    → STOP_HIT
  SELL target: bar.low  <= target_price  → TARGET_HIT
  SELL stop:   bar.high >= stop_price    → STOP_HIT
  Same bar:    both hit                  → AMBIGUOUS_INTRABAR
  Session end: bar.timestamp >= expires_at → EXPIRED_SESSION
  Kill-switch: bar count >= max_holding_bars → EXPIRED_MAX_DURATION
        │
        ▼
MFEMAECalculator  — per-bar running max/min excursion (pct from entry)
PnLCalculator     — gross/net P&L, R-multiple, with slippage & brokerage
        │
        ▼
RecommendationOutcomeService  — persists RecommendationOutcome (append-only)
                              — updates StockRecommendation.status
        │
        ▼
StrategyPerformanceService    — aggregates outcomes into PerformanceReport
        │
        ▼
BacktestRunner                — end-to-end pipeline over universe + date range
```

---

## Key Design Decisions

### PIT Safety
Never uses future bars. `evaluate_single()` receives bars pre-filtered by the
caller (always capped to `as_of`). Evaluators are pure functions.

### Same-Bar Ambiguity
Three policies when both stop and target are touched in one bar:
- `CONSERVATIVE` — stop wins; treat as loss (default)
- `OPTIMISTIC`   — target wins; treat as gain
- `EXCLUDE`      — record as AMBIGUOUS_INTRABAR, exclude from win/loss

### Historical Data Limitations
All outcomes include `data_quality_warnings`:
- `UNAVAILABLE_HISTORICAL_NEWS`
- `UNAVAILABLE_HISTORICAL_FUNDAMENTALS`

These must be communicated to users.

### Immutability
`RecommendationOutcome` is append-only.
Unique constraint: `(recommendation_id, evaluation_version)`.

### Statistical Guardrails
- `n < 10` triggered → `win_rate = None`, `SMALL_SAMPLE_WARNING`
- `n < 30` triggered → `expectancy = None`, `INSUFFICIENT_SAMPLE`

---

## Models

### RecommendationOutcome (market/models.py)

| Field | Type | Description |
|---|---|---|
| recommendation | FK | Parent recommendation |
| evaluation_version | int | Allows re-evaluation with new config |
| entry_triggered | bool | Whether entry was reached |
| exit_reason | str | TARGET_HIT / STOP_HIT / EXPIRED_SESSION / EXPIRED_MAX_DURATION / AMBIGUOUS_INTRABAR / NO_ENTRY |
| actual_entry_price | Decimal? | With slippage applied |
| actual_exit_price | Decimal? | Actual exit |
| holding_duration_bars | int? | Bars held |
| net_pnl_percent | Decimal? | Net P&L after costs |
| r_multiple | Decimal? | Net P&L / initial risk |
| max_favorable_excursion | Decimal? | MFE % from entry |
| max_adverse_excursion | Decimal? | MAE % from entry |
| ambiguous_intrabar | bool | Same-bar stop+target flag |
| cost_config_snapshot | JSON | Cost model at evaluation time |
| data_quality_warnings | JSON | Limitation flags |

### BacktestRun (market/models.py)

| Field | Type | Description |
|---|---|---|
| run_id | str | Unique identifier |
| config | JSON | Full BacktestConfig snapshot |
| status | str | PENDING / RUNNING / COMPLETE / FAILED |
| performance_report | JSON | Full PerformanceReport |
| data_quality_warnings | JSON | Aggregate DQ flags |

---

## Services

| File | Class / Function | Purpose |
|---|---|---|
| cost_model.py | CostConfig | NO_COST / REALISTIC config |
| cost_model.py | SlippageModel | Entry/exit slippage |
| outcome_engine.py | EntryEvaluator | Determines if entry triggered |
| outcome_engine.py | ExitEvaluator | Determines exit reason & price |
| outcome_engine.py | MFEMAECalculator | Max favorable/adverse excursion |
| outcome_engine.py | PnLCalculator | Gross/net P&L and R-multiple |
| outcome_service.py | RecommendationOutcomeService | Persistence + lifecycle |
| performance_metrics.py | StrategyPerformanceService | Aggregation + slices |
| backtest_runner.py | BacktestRunner | End-to-end backtest runner |
| backtest_config.py | BacktestConfig | Config dataclass (serialisable) |

---

## LLM Tools (read-only)

| Tool | Description |
|---|---|
| get_recommendation_outcome | Outcome for a single rec by UUID |
| get_strategy_performance | Aggregated metrics with filters |
| get_backtest_result | Backtest run results |

All registered in MarketResearchService.

LLM contract: read-only only. Always surface statistical_warnings and
data_quality_warnings. Do not present win_rate as a performance guarantee.

---

## Celery Task

`evaluate_recommendation_outcomes` — runs hourly, evaluates all expired ACTIVE
recommendations. Registered in migration 0020.

---

## Enums (market/signal_enums.py)

```python
class ExitReason(str, Enum):
    TARGET_HIT           = "TARGET_HIT"
    STOP_HIT             = "STOP_HIT"
    EXPIRED_SESSION      = "EXPIRED_SESSION"
    EXPIRED_MAX_DURATION = "EXPIRED_MAX_DURATION"
    AMBIGUOUS_INTRABAR   = "AMBIGUOUS_INTRABAR"
    NO_ENTRY             = "NO_ENTRY"

class AmbiguityPolicy(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    OPTIMISTIC   = "OPTIMISTIC"
    EXCLUDE      = "EXCLUDE"
```

---

## Migrations

| Migration | Description |
|---|---|
| 0019_recommendation_outcome_backtest_run | Models |
| 0020_bootstrap_outcome_evaluation_task | Celery beat task |

---

## Tests — OutcomeTrackingTests (65 tests)

Areas: EntryEvaluator, ExitEvaluator, same-bar ambiguity, session expiry,
max-duration kill-switch, MFE/MAE, P&L, R-multiple, cost model, performance
metrics, statistical warnings, dimension slices, model constraints, lifecycle,
idempotency, PIT safety, historical data warnings, enum completeness, daily rec
regression.

---

## Constraints Honoured

- No VectorBT / Backtrader / Zipline / QuantConnect / ML frameworks
- Transaction costs never assumed zero (NO_COST must be explicit)
- Historical data marked UNAVAILABLE, not simulated
- Outcome records are immutable (append-only by unique constraint)
- Strategy parameters unchanged by outcome evaluation
- PIT safety enforced by architecture (pure functions over pre-filtered bars)
