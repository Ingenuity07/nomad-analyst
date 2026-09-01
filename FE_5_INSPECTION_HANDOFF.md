# FE-5 INSPECTION HANDOFF — STOCK DETAIL & CHARTING TERMINAL

**Status:** TECHNICAL INSPECTION COMPLETE ✅  
**Date:** September 1, 2026  
**Action:** READ-ONLY AUDIT (NO CODE MODIFIED)

---

## 1. Executive Summary

This handoff details the findings of the technical inspection regarding Stock APIs, historical OHLCV data, technical indicators, fundamental statements, news, corporate events, AI research linkage, and charting library options for the future **FE-5 Stock Detail & Interactive Charting Terminal** (`/stocks/:symbol`).

---

## 2. Core Inspection Answers

### Q1: Exact stock APIs currently available
- `GET /api/v1/stocks/search/?q=...` -> Autocomplete instrument lookup
- `GET /api/v1/stocks/{symbol}/` -> Stock summary, latest snapshot, active recommendation, and opportunity summary
- `GET /api/v1/stocks/{symbol}/ohlcv/?timeframe=1d&limit=500` -> Candlestick series with open, high, low, close, volume
- `GET /api/v1/stocks/{symbol}/technicals/?timeframe=1d&as_of=...` -> Trend, momentum, volatility, and volume indicators
- `GET /api/v1/stocks/{symbol}/fundamentals/` -> Audited Income Statements, Balance Sheets, Cash Flows, and derived ratios
- `GET /api/v1/stocks/{symbol}/news/?page=...` -> Stock news feed
- `GET /api/v1/stocks/{symbol}/events/?page=...` -> Corporate disclosures & filings
- `POST /api/v1/chat/` -> LLM research on stock context

### Q2: Exact chart data currently available
- OHLCV candlestick series (`timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`) supporting `1d`, `5m`, `15m`, `1h` with date filtering (`start_date`, `end_date`) and limit parameters (up to 1000 bars).

### Q3: Technical / Fundamental / News capabilities
- **Technicals:** SMA (20, 50, 200), EMA (20, 50, 200), RSI (14), MACD (12, 26, 9), ATR (14), Volume SMA (20).
- **Fundamentals:** 10-period Annual & Quarterly Income Statements, Balance Sheets, Cash Flows, YoY revenue/PAT/EPS growth, margins, ROE, ROCE, Debt/Equity, CFO/PAT, and P/E.
- **News & Disclosures:** Paginated regulatory announcements, company filings, and news items.

### Q4: Charting-library recommendation
- **TradingView Lightweight Charts (`lightweight-charts` v4)**
- Free & open-source (Apache 2.0 license), canvas-based financial charting engine optimized for candlestick series, volume histograms, moving averages, and crosshair snapping.

### Q5: Point-In-Time (PIT) status
- `OHLCVBar` and `TechnicalFeature` support PIT filtering via `as_of` parameters.
- `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement` are organized by `fiscal_year` and `period_end` date.

### Q6: Data freshness status
- Provided via `MarketSnapshot.timestamp` (LTP quote), `OHLCVBar.timestamp` (latest bar), and `TechnicalFeature.timestamp` (latest calculations).

### Q7: Whether backend work blocks FE-5
- **NO BACKEND WORK BLOCKS FE-5.** All 8 required REST endpoints are fully implemented and verified in the Django backend.

### Q8: Recommended FE-5 architecture
- Tabbed research layout (`/stocks/:symbol`) with header metric strip, interactive canvas candlestick chart, independent TanStack Query tab panels (Technicals, Fundamentals, Valuation, News & Events, Signals), and AI research trigger.

---

## 3. Exact Next Step

**Technical inspection complete. Awaiting user instruction before implementing FE-5.**
