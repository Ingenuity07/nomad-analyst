# FE-7 INSPECTION HANDOFF — BACKTESTING LAB WORKSPACE

**Status:** TECHNICAL INSPECTION COMPLETE ✅  
**Date:** September 1, 2026  
**Action:** READ-ONLY AUDIT (NO CODE MODIFIED)

---

## 1. Executive Summary

This handoff details the findings of the technical inspection regarding the walk-forward backtesting engine, configuration schemas, transaction cost modeling, Point-In-Time safety guarantees, performance aggregations, and REST APIs for the future **FE-7 Backtesting Lab Workspace** (`/backtests`).

---

## 2. Core Inspection Answers

### Q1: Exact backtest APIs available
- `GET /api/v1/backtests/?page=...` -> Paginated list of historical backtest runs.
- `GET /api/v1/backtests/{run_id}/` -> Full backtest run detail including configuration parameters and complete `result` performance report dictionary.
- `POST /api/v1/backtests/run/` -> Executes a backtest simulation and returns the created `BacktestRun` record (status `201 Created`).

### Q2: Actual engine architecture
- `BacktestRunner` performs a deterministic walk-forward simulation across instruments in the specified universe.
- Uses identical strategy signal logic as live recommendations with bar-by-bar entry and exit evaluation (`EntryEvaluator`, `ExitEvaluator`, `PnLCalculator`, `MFEMAECalculator`).
- Compiles a complete `PerformanceReport` through `StrategyPerformanceService`.

### Q3: Actual configurable parameters
- `universe_name` (`NIFTY50`, `NIFTY_NEXT50`, `NIFTY_MIDCAP50`, `CUSTOM_UNIV`)
- `timeframe` (`1d`, `5m`, `15m`, `1h`)
- `horizon` (`DELIVERY_SWING`, `INTRADAY`, `LONG_TERM`)
- `start_date` and `end_date` (inclusive YYYY-MM-DD date range)
- `cost_mode` (`NO_COST`, `REALISTIC`, `CUSTOM`)
- `brokerage_pct`, `stt_pct`, `slippage_bps`
- `ambiguity_policy` (`CONSERVATIVE`, `OPTIMISTIC`, `EXCLUDE`)

### Q4: Execution / cost assumptions
- Symmetrical transaction costs (brokerage % + STT % + slippage bps) applied on entry and exit legs.
- Stop vs Target collision in the same OHLC bar handled according to `ambiguity_policy` (default `CONSERVATIVE`: stop hit).

### Q5: Point-In-Time (PIT) / look-ahead status
- **OHLCV Data:** Strictly PIT-safe; future price bars are excluded at every walk-forward step.
- **Biases Disclosed:** Survivorship bias (fixed current universe membership) and missing historical fundamentals/news are explicitly tracked and returned in `data_quality_warnings`.

### Q6: Actual metrics / results available
- `total_signals`, `triggered`, `wins`, `losses`, `win_rate` (null if < 10 trades), `trigger_rate`, `avg_return_pct`, `median_return_pct`, `avg_r`, `median_r`, `expectancy` (null if < 30 trades), `profit_factor`, `max_drawdown_r`, `avg_holding_bars`, dimension breakdowns (`by_setup_type`, `by_direction`, `by_sector`, `by_regime`), and `statistical_warnings`.

### Q7: Async / job status
- `POST /api/v1/backtests/run/` executes synchronously and persists the `BacktestRun` record with status `COMPLETE` or `FAILED`.

### Q8: Reproducibility / versioning status
- Every `BacktestRun` snapshots the exact `config` dictionary, `strategy_version`, `start_date`, and `end_date`.

### Q9: Whether backend work blocks FE-7
- **NO BACKEND WORK BLOCKS FE-7.** All 3 REST endpoints are fully implemented and verified.

### Q10: Recommended FE-7 information architecture
- Backtest Configuration Form card (Universe, Horizon, Timeframe, Date Range, Cost Mode, Ambiguity Policy, Run button).
- Summary KPI Metric Strip (Win Rate %, Expectancy R, Profit Factor, Max Drawdown in R, Total Trades).
- Dual-Tab layout:
  - **Performance Overview & Slices:** Setup Type breakdown table, Direction breakdown, statistical warnings, and PIT bias disclosures.
  - **Historical Backtest Runs:** Paginated table of past runs with run IDs, date ranges, win rates, and inspection actions.

---

## 3. Exact Next Step

**Technical inspection complete. Awaiting user instruction before implementing FE-7.**
