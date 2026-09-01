# FE-7 Backtesting Lab Workspace — Handoff

## Summary of Implementation

FE-7 provides a professional historical strategy simulation laboratory (`/backtests`) connecting directly to the Module 7 Strategy Engine & Backtester.

---

## Deliverables & Components

1. **Backtest Configuration Form (`BacktestConfigForm.tsx`)**:
   - Universe (`NIFTY50`, `NIFTY_NEXT50`, `NIFTY_MIDCAP50`, `CUSTOM_UNIV`).
   - Strategy Horizon (`DELIVERY_SWING`, `POSITIONAL`, `INTRADAY_MOMENTUM`).
   - Bar Timeframe (`1d`, `1h`, `15m`, `5m`).
   - Simulation Date Window (`start_date`, `end_date`).
   - Execution Cost Model (`REALISTIC` [0.03% Brokerage, 0.025% STT, 5 bps slippage], `NO_COST`, `CUSTOM` with progressive disclosure inputs).
   - Ambiguity Policy (`CONSERVATIVE`, `OPTIMISTIC`, `EXCLUDE`).

2. **Simulation Summary KPIs (`BacktestSummaryKPIs.tsx`)**:
   - Win Rate with total Wins/Losses.
   - Expectancy (R-multiple) per signal.
   - Profit Factor (Gross Wins / Gross Losses).
   - Max Drawdown (Peak-to-trough in R-multiple).
   - Trade Execution Count (`triggered / total_signals`).
   - Explicit null-safety: displays `'Insufficient Sample'` or `'—'` if sample count is below statistical thresholds.

3. **Point-In-Time & Data Quality Bias Disclosures (`BacktestBiasDisclosures.tsx`)**:
   - Highlights methodological assumptions (survivorship bias from current universe membership, historical fundamental availability).

4. **Dimensional Breakdown Tables (`BacktestBreakdownTables.tsx`)**:
   - Tabular performance slices by Pattern / Setup (`BREAKOUT`, `MEAN_REVERSION`, etc.).
   - Tabular performance slices by Signal Direction (`BUY`, `SELL`).

5. **Historical Simulations Table & Inspector Drawer (`HistoricalBacktestsTable.tsx`, `BacktestDetailDrawer.tsx`)**:
   - Paginated historical runs table with status badges (`COMPLETE`, `FAILED`, `RUNNING`).
   - Slide-over drawer providing full inspection into past simulation parameters, KPIs, biases, and breakdown tables.

---

## Verification Summary
- **Frontend Unit Tests**: 10 test suites (36 tests) passing.
- **Frontend Build**: TypeScript check & Vite production bundle compiled cleanly.
- **Backend Tests**: 229 Django tests passing (`python manage.py test market`).
