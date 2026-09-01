# Nomad Analyst — FE-5 Stock Detail & Charting Terminal Documentation

**Version:** 1.0.0 (FE-5 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (28/28 Vitest Tests + 229/229 Django Tests)  
**Route:** `/stocks/:symbol`

---

## 1. Executive Summary

FE-5 delivers the **Stock Detail & Interactive Charting Terminal** (`/stocks/:symbol`), the central research workspace for individual Indian equities.

It combines a canvas-accelerated **TradingView Lightweight Charts v4** interactive candlestick and volume terminal with tabbed research panels covering:
- **Overview & Trade Signals:** Latest snapshot pricing, armed recommendation orders, and multi-factor opportunity rankings.
- **Technical Indicators:** Moving averages (SMA/EMA 20/50/200), RSI (14), MACD (12/26/9), ATR (14), and Volume SMA (20).
- **Audited Fundamentals:** Annual & Quarterly Income Statements, Balance Sheets, Cash Flow Statements, and derived ratios (ROE, ROCE, Debt/Equity, Net Margin, YoY Growth, P/E).
- **News & Filings:** Company news stream and official exchange corporate disclosures.
- **AI Research Synthesis:** Direct query submission to the Module 5 Agentic Research Orchestrator.

---

## 2. Component Architecture

```
frontend/src/
├── features/stockDetail/components/
│   ├── StockHeader.tsx            # Symbol, company name, sector, LTP, change & DataStatus
│   ├── StockChartCard.tsx         # TradingView Lightweight Charts v4 canvas candlestick + volume
│   ├── OverviewTab.tsx            # Key metrics, active recommendation signal & opportunity scoring
│   ├── TechnicalsTab.tsx          # Moving averages, momentum oscillators & volatility
│   ├── FundamentalsTab.tsx        # Income, Balance Sheet, Cash Flow tables & derived ratios
│   ├── NewsEventsTab.tsx          # Paginated company news feed and corporate disclosures
│   └── AIResearchTab.tsx          # Interactive LLM analysis with execution evidence citations
├── pages/
│   └── StockDetailPage.tsx       # Root workspace orchestrator with tab routing & error boundary
└── test/
    └── stockDetailPage.test.tsx  # Vitest test suite (5 tests, all passing)
```

---

## 3. Consumed REST APIs & Query Strategy

| Endpoint | Method | Timeframe / Params | Cache / Stale Strategy | Purpose |
|---|---|---|---|---|
| `GET /api/v1/stocks/{symbol}/` | `GET` | None | 30-second stale time | Primary stock summary, latest snapshot, active recommendation, and opportunity |
| `GET /api/v1/stocks/{symbol}/ohlcv/` | `GET` | `timeframe` (`1d`, `5m`, `15m`, `1h`), `limit` | 60-second stale time | Historical candlestick and volume series |
| `GET /api/v1/stocks/{symbol}/technicals/` | `GET` | `timeframe=1d` | 60-second stale time | Trend, momentum, volatility, and volume indicators |
| `GET /api/v1/stocks/{symbol}/fundamentals/` | `GET` | None | 5-minute stale time | Audited statements and derived financial ratios |
| `GET /api/v1/stocks/{symbol}/news/` | `GET` | `page_size=15` | 2-minute stale time | Company news feed |
| `GET /api/v1/stocks/{symbol}/events/` | `GET` | `page_size=15` | 2-minute stale time | Exchange announcements & corporate disclosures |
| `POST /api/v1/chat/` | `POST` | `{ query }` | On-demand (no cache) | Agentic AI qualitative investment thesis report |

---

## 4. Primary Chart Capabilities

- **Engine:** TradingView Lightweight Charts v4.2.1 (Apache 2.0).
- **Timeframe Switcher:** `5m`, `15m`, `1h`, `1D`, `1M`, `1Y`, `5Y`.
- **Canvas Acceleration:** WebGL/Canvas rendering handling thousands of bars with instant pan/zoom.
- **Crosshair Hover Tooltip:** Dynamic display of bar Open, High, Low, Close, and Volume in monospace typography.
