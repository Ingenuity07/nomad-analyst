# Nomad Analyst — FE-4 Intraday Scanner & Real-Time Signals Documentation

**Version:** 1.0.0 (FE-4 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (23/23 Vitest Tests + 229/229 Django Tests)  
**Route:** `/intraday`

---

## 1. Executive Summary

FE-4 delivers the production-ready **Intraday Scanner & Real-Time Signals Workspace** (`/intraday`). It connects directly to the Module 10 Intraday Strategy Signal Engine and Module 9 Intraday Data Ingestion Infrastructure via BE-API-1 REST endpoints.

Using **TanStack Query 15-second polling** during active Indian equity market hours (09:15–15:30 IST) and automatically pausing polling when the session is closed, the workspace presents live intraday setups without fake WebSockets or unverified client calculations.

---

## 2. Component Architecture

```
frontend/src/
├── features/intraday/components/
│   ├── IntradayFilterToolbar.tsx        # Timeframe (5m/15m/1h), Setup, Direction, Status & Symbol filters
│   ├── IntradaySummaryStrip.tsx         # Active count, Triggered count, IST Session Window & 15s Polling state
│   ├── IntradaySignalTable.tsx          # Multi-column table with entry, stop, Target 1, Target 2, R:R & DQ buttons
│   ├── SignalDetailDrawer.tsx           # Execution parameters, structural stop, invalidation notes & terminal link
│   └── IntradayDataQualityModal.tsx     # On-demand modal inspecting bar counts, gaps, and readiness grades
├── pages/
│   └── IntradayPage.tsx                 # Root workspace orchestrator with polling lifecycle & reset handlers
└── test/
    └── intradayPage.test.tsx            # Vitest test suite (4 tests, all passing)
```

---

## 3. Consumed REST APIs & Polling Configuration

| Endpoint | Method | Query Parameters | Polling Strategy | Purpose |
|---|---|---|---|---|
| `GET /api/v1/intraday/overview/` | `GET` | None | 15s interval during market hours | Session window, elapsed/remaining minutes, active/triggered signal totals |
| `GET /api/v1/intraday/recommendations/` | `GET` | `timeframe`, `setup_type`, `signal`, `status`, `page`, `page_size` | 15s interval during market hours | Live intraday signal candidates, entry prices, stops, targets, and R:R |
| `GET /api/v1/intraday/data-quality/` | `GET` | `symbol`, `timeframe` | On-demand (when DQ button clicked) | 1-click readiness evaluation & data quality grade |

---

## 4. Supported Strategy Setups & Lifecycle Semantics

- **Timeframes:** `5m` (primary), `15m` (intermediate), `1h` (structural trend).
- **Setups:** `ORB_BREAKOUT` (Opening Range Breakout), `VWAP_RECLAIM` (Institutional VWAP Reversal), `TREND_CONTINUATION` (EMA Alignment), `MEAN_REVERSION` (Statistical Pullback).
- **Lifecycle Progression:** `ACTIVE` (armed waiting entry) → `TRIGGERED` (in execution) → `TARGET_HIT` / `STOPPED` / `EXPIRED` (market close at 15:30 IST).
- **Data Quality Grading:** Evaluated against Module 9 readiness checks before signal generation.
