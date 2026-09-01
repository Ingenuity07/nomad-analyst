# Nomad Analyst — FE-6 Recommendations & Outcome Tracking Documentation

**Version:** 1.0.0 (FE-6 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (32/32 Vitest Tests + 229/229 Django Tests)  
**Route:** `/recommendations`

---

## 1. Executive Summary

FE-6 delivers the **Trade Recommendations & Outcome Attribution Workspace** (`/recommendations`), enabling users to inspect live active signals, review historical trade evaluations, and analyze strategy performance without performing any client-side financial calculations or mock estimations.

Key capabilities:
1. **Audited Strategy Performance Strip:** Displays live backend-computed metrics (`Win Rate %`, `Average Expectancy in R`, `Sample Size in Trades`, `Wins/Losses`) with an explicit **Small Sample Warning (`is_small_sample = true`)** for samples under 30 trades.
2. **Multi-Parameter Filter Toolbar:** Full support for `Horizon` (`DELIVERY_SWING`, `INTRADAY`, `LONG_TERM`), `Signal` (`BUY`, `SELL`), `Setup Pattern` (`BREAKOUT`, `PULLBACK`, `MOMENTUM`, `ORB_BREAKOUT`, etc.), `Lifecycle Status`, `Confidence`, and ticker search with instant reset.
3. **Dual-Tab Table Layout:**
   - **Active Signals Tab:** Multi-column view of armed (`ACTIVE`) and actively managed (`TRIGGERED`) trade signals with Entry Level, Stop Loss, Target 1, and Risk/Reward ratio.
   - **Historical Outcomes Tab:** Complete view of closed trades with Actual Entry/Exit prices, Net P&L % (post-cost), R-Multiple (`+1.85 R`), MFE / MAE (%), Holding Duration in bars, and Exit Reason.
4. **Recommendation Detail Drawer:** In-depth trade inspection exposing planned execution levels, supporting technical/fundamental factors, structural risks, realized trade outcome card, and quick navigation to `/stocks/:symbol`.

---

## 2. Component Architecture

```
frontend/src/
├── features/recommendations/components/
│   ├── StrategyPerformanceStrip.tsx      # Strategy selector, Win Rate %, Avg R, Sample Size & Small Sample Alert
│   ├── RecommendationFilterToolbar.tsx   # Horizon, Signal, Setup, Status, Confidence, and Search filters
│   ├── ActiveSignalsTable.tsx             # Data table for ACTIVE & TRIGGERED recommendations with R:R
│   ├── HistoricalOutcomesTable.tsx        # Data table for evaluated trades with Net PnL, R-Multiple, MFE/MAE
│   └── RecommendationDetailDrawer.tsx     # Inspection drawer for planned levels, supporting factors & outcome
├── pages/
│   └── RecommendationsPage.tsx            # Main workspace coordinator with pagination & error isolation
└── test/
    └── recommendationsPage.test.tsx       # Vitest test suite (4 tests, all passing)
```

---

## 3. Consumed REST APIs & Query Strategy

| Endpoint | Method | Parameters | Cache / Stale Strategy | Purpose |
|---|---|---|---|---|
| `GET /api/v1/strategies/{strategy}/performance/` | `GET` | `strategy` (`DELIVERY_SWING`, `INTRADAY`) | 5-minute stale time | Aggregated win rate, expectancy, and small sample flag |
| `GET /api/v1/recommendations/` | `GET` | `horizon`, `signal`, `setup_type`, `status`, `confidence`, `page` | 30-second stale time | Paginated list of active/armed recommendations |
| `GET /api/v1/recommendations/{id}/` | `GET` | `id` (UUID) | 2-minute stale time | Detail of an individual recommendation |
| `GET /api/v1/outcomes/` | `GET` | `signal`, `setup_type`, `exit_reason`, `page` | 2-minute stale time | Paginated historical outcome evaluations |
| `GET /api/v1/recommendations/{id}/outcome/` | `GET` | `id` (UUID) | 5-minute stale time | Outcome metrics attached to an individual trade |
