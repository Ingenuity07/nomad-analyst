# FE-0 HANDOFF — FRONTEND ARCHITECTURE & API CONTRACT

**Status:** ARCHITECTURE & API CONTRACT COMPLETE ✅  
**Base Backend Commit:** `4acb1f5` (`fix: resolve backend integration issues`)  
**Backend Status:** Validated Modules 0–11 (100% Passing Tests, Live Data Verified)  
**Deliverable Type:** Architecture, Design Specification & API Contract (Zero Frontend Code Written)

---

## 1. Chosen Frontend Technology Stack

| Layer | Selected Technology | Version | Rationale |
|---|---|---|---|
| **Core Framework** | **React** | `19.0.0` | Industry-standard UI component model, concurrent rendering, virtual DOM efficiency for financial tables and streaming grids. |
| **Language** | **TypeScript** | `~5.7.2` | Strict compile-time typing matching backend Pydantic models. Zero `any` policy for financial data. |
| **Build & Tooling** | **Vite** | `^6.0.5` | Instant HMR, native ES modules, lightweight optimized bundle output matching `nomad-prospecting-frontend`. |
| **Client Routing** | **React Router** | `^7.1.1` | Nested declarative layout routing with URL query param synchronization for timeframes, filters, and tabs. |
| **Styling & Tokens** | **Vanilla CSS + Design Tokens** | CSS3 | Zero-runtime penalty, custom CSS variables for dark-mode institutional terminal palette. No Tailwind utility bloat. |
| **Icons** | **Lucide React** | `^0.468.0` | Comprehensive financial, navigation, and status indicator SVGs. |
| **Financial Charting** | **TradingView Lightweight Charts** | `^4.2.0` | 60fps canvas candlestick engine, multi-pane indicator synchronization (Volume, RSI, MACD), setup price level lines. |
| **Data Fetching & Cache** | **Custom SWR / Query Hook Layer** | In-house TS | Lightweight `stale-while-revalidate` cache, deduplication, auto-retry, background polling during market hours. |
| **Real-Time Client** | **Native WebSocket Manager** | Browser API | Auto-reconnect, exponential backoff, heartbeat ping/pong connecting to Django Channels (`/ws/market/`). |
| **Schema Validation** | **Zod** | `^3.24.0` | Runtime validation of incoming backend JSON envelopes. |
| **Testing** | **Vitest + Testing Library** | Latest | Fast unit and component tests for financial formatters, tables, and signal cards. |

---

## 2. Frontend Folder Structure & Organization

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/                # Static assets, logos
│   ├── components/            # Reusable UI components
│   │   ├── common/            # Button, Card, Badge, Table, Modal, Shimmer, Tabs
│   │   ├── charts/            # TradingView Candlestick, Volume, RSI, MACD panes
│   │   ├── layout/            # Shell, Sidebar, Header, MarketSessionClock
│   │   ├── market/            # IndexStrip, BreadthBar, SectorMatrix, MacroNews
│   │   ├── intraday/          # IntradaySignalCard, SetupMeter, QualityWidget
│   │   ├── delivery/          # OpportunityTable, ScoreBreakdownMeter, SetupDrawer
│   │   ├── stocks/            # StockHeader, TechnicalsMatrix, FinancialStatements, PeerList
│   │   ├── research/          # QueryConsole, ToolTraceTimeline, StructuredReportCard
│   │   └── backtest/          # ConfigForm, PerformanceScorecard, SlicesTable, TradeLog
│   ├── hooks/                 # Custom React hooks
│   │   ├── useMarketOverview.ts
│   │   ├── useStockDetail.ts
│   │   ├── useIntradaySignals.ts
│   │   ├── useOpportunities.ts
│   │   ├── useBacktest.ts
│   │   ├── useAIResearch.ts
│   │   ├── useWebSocket.ts
│   │   └── useIntervalPoll.ts
│   ├── services/              # API clients & network layer
│   │   ├── api.ts             # Base fetch wrapper with error handling & CSRF
│   │   ├── marketService.ts   # /api/market/ endpoints
│   │   ├── stockService.ts    # /api/stocks/ endpoints
│   │   ├── oppService.ts      # /api/opportunities/ endpoints
│   │   ├── recService.ts      # /api/recommendations/ endpoints
│   │   ├── backtestService.ts # /api/backtests/ endpoints
│   │   └── researchService.ts # /api/research/ endpoints
│   ├── types/                 # Canonical TypeScript interfaces
│   │   ├── market.ts          # MarketOverview, IndexQuote, Breadth, SectorRanking
│   │   ├── stock.ts           # StockQuote, OHLCVBar, TechnicalIndicators, Statements
│   │   ├── signal.ts          # Recommendation, IntradaySignal, SetupType, Confidence
│   │   ├── backtest.ts        # BacktestConfig, PerformanceReport, PerformanceSlice
│   │   ├── research.ts        # ResearchRequest, ResearchReport, EvidenceTrace
│   │   └── api.ts             # PaginatedResponse, ApiError, DataFreshness
│   ├── utils/                 # Pure helper functions
│   │   ├── formatters.ts      # Currency (INR Crores/Lakhs), Percentages, Decimals
│   │   ├── dateUtils.ts       # IST / UTC conversion, Market Session countdown
│   │   └── mathUtils.ts       # Risk/Reward math, R-multiple display
│   ├── styles/                # Global styling & design tokens
│   │   ├── tokens.css         # CSS custom properties (colors, typography, spacing)
│   │   ├── reset.css          # Modern CSS reset
│   │   └── global.css         # Typography, layout, scrollbar, table defaults
│   ├── routes/                # Page route views
│   │   ├── MarketOverviewPage.tsx
│   │   ├── IntradayPage.tsx
│   │   ├── DeliveryOpportunitiesPage.tsx
│   │   ├── StockDetailPage.tsx
│   │   ├── AIResearchPage.tsx
│   │   ├── BacktestingPage.tsx
│   │   ├── WatchlistPage.tsx
│   │   └── AlertsPage.tsx
│   ├── App.tsx                # Layout wrapper & route definitions
│   └── main.tsx               # DOM entry point
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## 3. Client Routing Table

| URL Path | Route Component | Purpose |
|---|---|---|
| `/` or `/market` | `MarketOverviewPage` | Macro Indices, Market Regime, Breadth Bar, Sector Matrix, News |
| `/intraday` | `IntradayPage` | Live 5m/15m actionable signals, ORB/VWAP setup cards, Session clock |
| `/delivery` | `DeliveryOpportunitiesPage`| Ranked 6D Opportunity Discovery Table, Swing trade setups |
| `/stocks/:symbol`| `StockDetailPage` | Full Stock Terminal (TradingView Chart, Technicals, Fundamentals, News) |
| `/research` | `AIResearchPage` | Natural-language stock research console with live tool execution traces |
| `/backtesting` | `BacktestingPage` | Walk-forward quantitative backtest runner and performance metrics |
| `/watchlist` | `WatchlistPage` | Custom symbol lists with live price updates and sparklines |
| `/alerts` | `AlertsPage` | Real-time signal triggers and system notifications |

---

## 4. API Inventory & Classification

### 4.1 Existing Backend APIs (Currently Registered in Django URLs)
- `GET /api/providers/` — List LLM provider health status (from `llm.urls`).
- `GET /api/analytics/` — Prompt run and latency analytics (from `llm.urls`).
- `GET /api/conversations/` — List chat conversations (from `chat.urls`).
- `POST /api/chat/` — Legacy chat execution endpoint (from `chat.urls`).

### 4.2 Required New APIs (Backend Domain Services Exist — REST Views to be Added in Django)
1. `GET /api/market/overview/` — Aggregated market snapshot (indices, regime, breadth, sectors, macro cues).
2. `GET /api/market/indices/` — Real-time quotes for benchmark indices (`^NSEI`, `^NSEBANK`).
3. `GET /api/market/regime/` — Trend regime and breadth metrics.
4. `GET /api/market/sectors/` — Sector relative strength and momentum tiers.
5. `GET /api/stocks/search/?q={query}` — Instant symbol search / autocomplete.
6. `GET /api/stocks/{symbol}/` — Stock summary, company metadata, and quote.
7. `GET /api/stocks/{symbol}/ohlcv/?timeframe=1d` — Candlestick bar history for charting.
8. `GET /api/stocks/{symbol}/technicals/?timeframe=1d` — 20 calculated technical indicators.
9. `GET /api/stocks/{symbol}/fundamentals/` — Consolidated Income, Balance Sheet, Cash Flow + Ratios.
10. `GET /api/stocks/{symbol}/news/` — Company news items and corporate announcements.
11. `GET /api/opportunities/?universe=NIFTY50&horizon=DELIVERY_SWING` — 6-dimension scored opportunities.
12. `GET /api/recommendations/?horizon=DELIVERY_SWING&status=ACTIVE` — Active trade setups.
13. `GET /api/recommendations/{id}/` — Single recommendation detail.
14. `GET /api/intraday/signals/?timeframe=5m` — Live session intraday recommendations.
15. `GET /api/intraday/{symbol}/readiness/` — Intraday warmup and quality health check.
16. `POST /api/backtests/run/` — Execute a walk-forward backtest simulation.
17. `GET /api/backtests/` — List historical backtest runs.
18. `GET /api/backtests/{run_id}/` — Backtest performance report and trade outcomes.
19. `GET /api/strategy-performance/` — Aggregated outcome metrics across completed recommendations.
20. `POST /api/research/query/` — Execute an on-demand AI stock research task.
21. `WS /ws/market/` — Live quote and signal event broadcast channel.

---

## 5. Real-Time & Charting Strategies

### Real-Time Strategy:
- **Hybrid Approach:**
  - Fast REST with `stale-while-revalidate` + 15s/30s background interval polling during active NSE market hours (09:15–15:30 IST) for price quotes, breadth, and candlestick data.
  - Native WebSocket (`/ws/market/`) for instantaneous broadcast of actionable signal generation (`SIGNAL_GENERATED`), lifecycle transitions (`ENTRY_TRIGGERED`, `TARGET_HIT`, `STOP_HIT`, `EXPIRED`), and live AI research agent tool progress streams.

### Charting Strategy:
- **Engine:** TradingView Lightweight Charts (v4.2+).
- **Features:** Candlesticks, Volume Histogram, Overlays (SMA 20/50/200, EMA 9/21, VWAP, Bollinger Bands), Oscillators (RSI 14, MACD), Setup Price Levels (Horizontal dashed lines for Entry, Stop Loss, Target 1, Target 2), and execution arrow markers.
- **Data Flow:** All indicator math is pre-calculated by backend `TechnicalFeatureEngine` or computed deterministically from backend bars.

---

## 6. Frontend Implementation Phases

- **FE-1: Application Shell & Design System** — Vite React structure, layout, dark-mode CSS tokens, client router, IST session clock, UI atom library.
- **FE-2: Market Overview Workspace** — Macro index ticker strip, market regime, breadth bar, sector momentum matrix, news feed.
- **FE-3: Stock Detail Workspace** — TradingView candlestick canvas, indicators matrix, multi-period financial statements, news timeline.
- **FE-4: Delivery & Swing Opportunities** — Ranked opportunity discovery grid, 6-dimension score meters, trade setup drawers.
- **FE-5: Live Intraday Intelligence** — Live 5m signal cards, R:R meters, session countdown, intraday data quality widget.
- **FE-6: AI Stock Research Studio** — Research console, depth toggles, live tool execution trace timeline, structured report cards.
- **FE-7: Quantitative Backtesting Laboratory** — Walk-forward config form, performance scorecard, dimensional slices, trade log.
- **FE-8: Watchlists & System Alerts** — Custom symbol organizer, signal trigger notification stream.
- **FE-9: Performance, Accessibility & Hardening** — Global `Cmd+K` symbol search, keyboard navigation, Lighthouse optimization.

---

## 7. Prioritized Missing Backend Capabilities

| Priority | Missing Capability | Impact on Frontend | Required Action |
|---|---|---|---|
| **P0** | DRF REST Views & Serializers for `market` app (`market/views.py`, `market/urls.py`) | Frontend cannot fetch market/stock/opp/rec data via REST | Expose DRF viewsets wrapping existing backend services |
| **P0** | Backtest & Research Trigger REST Endpoints | Frontend cannot trigger backtests or research queries | Add `BacktestRunAPIView` and `StockResearchAPIView` |
| **P1** | Stock Symbol Search Endpoint (`/api/stocks/search/`) | Quick search (`Cmd+K`) needs fast symbol autocomplete | Add filtered queryset view over `Instrument` |
| **P2** | Watchlist Persistence Model in Database | Watchlists will rely on `localStorage` until DB model exists | Add `UserWatchlist` model in future module |
| **P3** | User Custom Alert Notification Webhooks | Alerts will be in-app UI notifications only | Add webhook delivery in future module |

---

## 8. Exact Next Step

**Awaiting user instruction to begin FE-1 (Application Shell, Design System, Router & Layout).**  
No code changes were made in this design phase. All documentation is committed and implementation-ready.
