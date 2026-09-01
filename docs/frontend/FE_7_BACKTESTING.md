# FE-7 Backtesting Lab Workspace Specification

## 1. Route & Overview
- **Route**: `/backtests`
- **Purpose**: Walk-forward strategy simulation laboratory allowing traders and analysts to simulate strategy setups deterministically across historical date windows, inspect statistical performance metrics, understand methodological biases & data quality limitations, and review past simulation runs.

---

## 2. Component Architecture
```
frontend/src/features/backtesting/
├── components/
│   ├── BacktestConfigForm.tsx       # Universe, horizon, timeframe, dates, cost mode, ambiguity policy
│   ├── BacktestSummaryKPIs.tsx      # Win rate, Expectancy (R), Profit Factor, Max Drawdown (R), execution ratio
│   ├── BacktestBiasDisclosures.tsx  # Point-in-time enforcement & survivorship bias disclosures
│   ├── BacktestBreakdownTables.tsx  # Tabular breakdown by Setup Type and Signal Direction
│   ├── HistoricalBacktestsTable.tsx # Paginated historical simulation runs with status badges
│   └── BacktestDetailDrawer.tsx     # Full inspection drawer for selected historical backtest runs
```

---

## 3. Key Features & Visual Design Rules

### A. Execution Model
- Synchronous walk-forward execution via `POST /api/v1/backtests/run/`.
- Clear button loading spinner and disabled state during simulation computation (`▶ Running Walk-Forward Simulation...`).
- Graceful validation error surfacing via `<ErrorState />` if invalid parameters or empty universe date windows are provided.

### B. Statistical & Financial Integrity
- **Expectancy & R-multiples**: Rendered authoritative from backend `result` payload (e.g. `+1.35 R`, `-2.45 R`).
- **Null Safety**: When sample count is insufficient for win rate or expectancy calculation, displays `'Insufficient Sample'` or `'—'` without falsifying zeros.
- **No Client Calculations**: All win rates, profit factors, drawdowns, and expectancy metrics are computed exclusively on the backend.

### C. Bias & Methodological Disclosures
- Prominently displays point-in-time and data limitations (survivorship bias from fixed universe membership, historical fundamental lag).
- Sits above the detailed breakdown tables so analysts always see data assumptions in context.

### D. Historical Runs & Inspector Drawer
- Paginated table showing all previous simulations (`GET /api/v1/backtests/?page=...`).
- Deep-dive slide-over drawer displaying exact parameters (brokerage, STT, slippage, ambiguity policy, start/end dates), summary KPIs, bias warnings, and breakdown tables.

---

## 4. Verification & Testing
- **10 Unit Test Suites** passing (36 tests in total).
- Comprehensive coverage for:
  1. Configuration form rendering and default inputs.
  2. Walk-forward simulation execution and KPI strip / bias disclosures / breakdown tables rendering.
  3. Historical backtest run pagination and detail drawer inspection.
  4. Validation failure handling and error state recovery.
