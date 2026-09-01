# Nomad Analyst — FE-7 Backtesting Lab Technical Inspection

**Date:** September 1, 2026  
**Target Workspace:** FE-7 Backtesting Lab Workspace (`/backtests`)  
**Status:** READ-ONLY INSPECTION COMPLETE (NO CODE MODIFICATIONS)

---

## 1. Executive Summary

This inspection evaluates the backend backtesting engine (Module 11 `BacktestRunner`), configuration schemas (`BacktestConfig`), transaction cost models (`CostConfig`), Point-In-Time (PIT) safety guarantees, performance aggregations (`PerformanceReport`), REST APIs, and serializer schemas required for the future **FE-7 Backtesting Lab Workspace** (`/backtests`).

All required backend REST endpoints under `/api/v1/backtests/` (`GET /api/v1/backtests/`, `GET /api/v1/backtests/{run_id}/`, `POST /api/v1/backtests/run/`) exist and have passed comprehensive testing. **There are NO backend blockers preventing FE-7 implementation.**

---

## 2. Backtesting REST API Inventory

| Endpoint | Method | Parameters / Request Body | Serializer / Response | Backend Provider / Model | Status |
|---|---|---|---|---|---|
| `GET /api/v1/backtests/` | `GET` | `page`, `page_size` | `BacktestRunSerializer` (list of historical backtest runs with `run_id`, `status`, `universe_name`, `timeframe`, `horizon`, `start_date`, `end_date`, `result`) | `BacktestRun` (Module 11) | `IMPLEMENTED` |
| `GET /api/v1/backtests/{run_id}/` | `GET` | `run_id` (string slug) | `BacktestRunSerializer` (full run detail, `config`, `result` dictionary, `data_quality_warnings`, `error_message`) | `BacktestRun` (Module 11) | `IMPLEMENTED` |
| `POST /api/v1/backtests/run/` | `POST` | `{ universe_name, timeframe, horizon, start_date, end_date, cost_mode, brokerage_pct, stt_pct, slippage_bps, ambiguity_policy }` | `BacktestRunSerializer` (status `201 Created` with completed `BacktestRun` instance) | `BacktestRunner().run(config)` | `IMPLEMENTED` |

---

## 3. Backtest Engine Architecture & Execution Flow

1. **Deterministic Walk-Forward Engine (`BacktestRunner`):**
   - Step-by-step chronological bar evaluation across all active members of the specified universe.
   - At each historical `as_of` timestamp, only bars prior to `as_of` are visible to signal detectors (`min_bars_required: 30`).
   - Generates `BacktestSignalRecord` using identical Module 8 / Module 10 strategy logic.
2. **Outcome Evaluation:**
   - Evaluates trade entry triggers (`EntryEvaluator`) and exit thresholds (`ExitEvaluator`) bar-by-bar.
   - Computes gross P&L, transaction costs (`CostConfig`), net P&L, R-multiples, MFE %, and MAE %.
3. **Performance Aggregation (`StrategyPerformanceService`):**
   - Builds `PerformanceReport` serialized directly into `BacktestRun.result`.

---

## 4. Configurable Parameters & Defaults

| Parameter | Type | Allowed Values / Constraints | Default |
|---|---|---|---|
| `universe_name` | string | `NIFTY50`, `NIFTY_NEXT50`, `NIFTY_MIDCAP50`, `CUSTOM_UNIV` | `NIFTY50` |
| `timeframe` | string | `1d`, `5m`, `15m`, `1h` | `1d` |
| `horizon` | string | `DELIVERY_SWING`, `INTRADAY`, `LONG_TERM` | `DELIVERY_SWING` |
| `start_date` | YYYY-MM-DD | Historical start date | Required |
| `end_date` | YYYY-MM-DD | Historical end date | Required |
| `cost_mode` | string | `NO_COST`, `REALISTIC`, `CUSTOM` | `REALISTIC` |
| `brokerage_pct` | float | Per leg percentage (e.g. `0.03%`) | `0.03` |
| `stt_pct` | float | Securities Transaction Tax (e.g. `0.025%` delivery / `0.01%` intraday) | `0.1` / `0.025` |
| `slippage_bps` | float | Slippage in basis points per leg (e.g. `5.0 bps`) | `5.0` |
| `ambiguity_policy`| string | `CONSERVATIVE` (stop wins), `OPTIMISTIC` (target wins), `EXCLUDE` | `CONSERVATIVE` |

---

## 5. Returned Performance Metrics & Statistical Integrity

`PerformanceReport` returns:
- **Trade Counts:** `total_signals`, `triggered`, `untriggered`, `wins`, `losses`, `ambiguous`, `expired_no_entry`, `expired_after_entry`.
- **Performance Rates:** `win_rate` (null if triggered < 10), `trigger_rate`.
- **Return Distributions:** `avg_return_pct`, `median_return_pct`, `std_return_pct`.
- **R-Multiples & Expectancy:** `avg_r`, `median_r`, `expectancy` (null if < 30 trades), `profit_factor`.
- **Drawdown & Duration:** `max_drawdown_r`, `avg_holding_bars`, `median_holding_bars`.
- **Attribution Slices:** `by_setup_type`, `by_timeframe`, `by_direction`, `by_regime`, `by_sector`.
- **Quality & Statistical Disclaimers:** `statistical_warnings` (e.g. small sample warnings) and `data_quality_warnings` (historical fundamentals/news limitations).

---

## 6. Point-In-Time (PIT) Guarantees & Known Limitations

- **OHLCV Data:** Strictly PIT-safe; future bars are sliced out at every step.
- **Survivorship Bias Disclaimer:** The engine uses current universe membership as a proxy for historical universe membership (explicitly surfaced in `data_quality_warnings`).
- **Fundamental & News Bias Disclaimer:** Historical fundamentals and news are not backfilled point-in-time for all historical dates.

---

## 7. Recommended FE-7 Information Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Header: Title | Active Run Status | DataStatus (LIVE)                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Configuration Form Card:                                                               │
│ • Universe • Horizon • Timeframe • Date Range (Start/End) • Cost Mode & Assumptions     │
│ • Ambiguity Policy • [ ▶ Run Backtest Simulation ]                                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Summary KPI Metric Strip (When Run Selected):                                          │
│ [ Win Rate % ] [ Expectancy (R) ] [ Profit Factor ] [ Max Drawdown (R) ] [ Total Trades]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Tab Navigation:                                                                        │
│ [ Performance Overview & Slices ]  [ Dimension Attribution ]  [ Historical Backtest Runs]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Tab 1: Performance Overview & Dimension Slices                                         │
│ • Setup Type Breakdown Table (Setup, Signals, Triggered, Win Rate %, Avg R, P.F.)       │
│ • Direction Breakdown (BUY vs SELL)                                                    │
│ • Statistical Warnings & PIT Disclaimers Box                                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Tab 2: Historical Backtest Runs Table                                                  │
│ • Run ID • Universe • Date Range • Horizon • Win Rate • Avg R • Status • View Results   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
