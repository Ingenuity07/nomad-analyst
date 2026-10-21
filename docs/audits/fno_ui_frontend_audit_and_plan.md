# Nomad Analyst — Existing Frontend Audit & F&O UI Integration Plan

**Document Path:** `docs/audits/fno_ui_frontend_audit_and_plan.md`  
**Date:** 2026-10-21T16:30:00+05:30  
**Audit Type:** Read-Only Architectural Inspection & UI Integration Planning  
**Execution Status:** Completed (No code or backend modifications performed)  

---

## 1. Executive Summary

Nomad Analyst features an institutional-grade financial terminal frontend built with **React 19**, **TypeScript 5.7**, **React Router v7**, **TanStack React Query v5**, and **TradingView Lightweight Charts v4**. The UI strictly adheres to a minimalist, low-fatigue dark terminal design system governed by CSS custom properties ([docs/frontend/DESIGN_SYSTEM.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/frontend/DESIGN_SYSTEM.md)) without Tailwind or CSS-in-JS overhead.

While the backend F&O data pipeline, quote freshness gating, bar aggregation, strategy execution engine (`STRAT-ORB-15M`), and statutory fee model are fully implemented and verified in PostgreSQL (`nomad_analyst`), **zero F&O REST endpoints or frontend UI components currently exist**. 

This audit provides:
1. Complete architectural inventory of the existing frontend.
2. Gap analysis between existing equity APIs and F&O data contracts.
3. Recommended navigation structure: a dedicated, top-level `/fno` workspace with 4 tabbed panels.
4. Phased implementation plan with strict acceptance criteria and Vitest/DRF test specifications.

---

## 2. Existing Frontend Architecture & UI Inventory

### 2.1 Technology Stack & Tooling
* **Core Framework:** React 19.0.0 (`react`, `react-dom`)
* **Routing:** React Router DOM 7.1.1 (`BrowserRouter`, nested `<Routes>`, lazy loading with `Suspense`)
* **State & Query Cache:** `@tanstack/react-query` v5.62.8 + in-house `queryClient` ([frontend/src/lib/queryClient.ts](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/lib/queryClient.ts))
* **Financial Charting:** `lightweight-charts` v4.2.1 (TradingView canvas engine)
* **Styling & Tokens:** Vanilla CSS + CSS Custom Properties ([frontend/src/styles/tokens.css](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/styles/tokens.css)). Zero runtime CSS-in-JS; no Tailwind.
* **Icons:** `lucide-react` v0.468.0
* **Testing:** `vitest` v2.1.8 + `@testing-library/react` v16.1.0 + `jsdom` v25.0.1
* **Build Tool:** Vite 6.0.5 with Hot Module Replacement (HMR)

### 2.2 Navigation Hierarchy & Route Tree
The application shell ([frontend/src/components/layout/AppShell.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/layout/AppShell.tsx)) provides a persistent 240px sidebar ([frontend/src/components/layout/Sidebar.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/layout/Sidebar.tsx)) and a 52px top header strip ([frontend/src/components/layout/TopHeader.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/layout/TopHeader.tsx)).

```text
/ (AppShell Root)
├── /market                    → Market Overview (Macro indices, market regime, breadth, sector grid)
├── /market-intelligence       → Market & Sector Intelligence (Relative strength, sector rotation)
├── /sectors                   → Alias redirect to /market-intelligence
├── /intraday                  → Intraday Scanner (Live stock setups: ORB, VWAP Reclaim, Trend, Mean Reversion)
├── /delivery                  → Opportunities (Ranked 6-dimension delivery & swing setups)
├── /stocks                    → Stocks Directory (Stock search & universe listing)
│   └── /stocks/:symbol        → Unified Stock Detail (TradingView chart, technicals, fundamentals, news)
├── /fundamentals              → Financial Statements & Ratio Modeling
├── /recommendations           → Historical & Active Trade Recommendations
├── /research                  → AI Equity Research Studio (Evidence-backed LLM agent reports)
├── /backtests                 → Quantitative Strategy Backtesting Laboratory
├── /watchlist                 → User Monitored Symbol Watchlists
├── /alerts                    → Command Center (Trigger logs, notifications)
└── /design-system             → Design System Token & Component Showcase (DEV)
```

### 2.3 Page-by-Page Inventory
| Route | Page Component | Functional Purpose & Key Features |
|---|---|---|
| `/market` | [MarketPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/MarketPage.tsx) | Live macro dashboard (Nifty 50, Bank Nifty, S&P 500, USD/INR, Crude, Gold), AD breadth ratio, trend regime badge. |
| `/intraday` | [IntradayPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/IntradayPage.tsx) | Cash equity intraday setups (5m/15m ORB, VWAP), constituent table, filter toolbar, SignalDetailDrawer. |
| `/delivery` | [DeliveryPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/DeliveryPage.tsx) | Ranked 6-dimension swing scoring table (Technical, Fundamental, Sector, Context, News, Liquidity). |
| `/stocks/:symbol` | [StockDetailPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/StockDetailPage.tsx) | Multi-pane TradingView canvas chart, technical indicators, financial statement tables, peer analysis. |
| `/research` | [ResearchPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/ResearchPage.tsx) | AI research console with real-time tool execution trace, driver/risk analysis, contradiction detection. |
| `/backtests` | [BacktestsPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/BacktestsPage.tsx) | Walk-forward quantitative backtesting runner, equity curve chart, Sharpe ratio, drawdowns. |
| `/watchlist` | [WatchlistPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/WatchlistPage.tsx) | Custom user watchlists with real-time price updates and quick navigation to stock details. |
| `/alerts` | [AlertsPage.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/AlertsPage.tsx) | Real-time command center, trigger logs, filterable alert notifications. |
| `/design-system`| [DesignSystemShowcase.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/pages/DesignSystemShowcase.tsx) | Token visualizer, button/badge/table styles, typography scale. |

### 2.4 Shared Component Primitives
Located in [frontend/src/components/ui/](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/):
* **Tables:** [Table.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Table.tsx) — High-density financial table with monospace numbers (`font-feature-settings: 'tnum'`), sortable headers, and hover highlights.
* **Cards & Containers:** [Card.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Card.tsx), [PageContainer.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/layout/PageContainer.tsx) — Institutional dark containers (`--bg-surface`, `--border-subtle`).
* **Status Badges:** [Badge.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Badge.tsx), [DataStatus.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/DataStatus.tsx) — Semantic color tags (`LIVE`, `STALE`, `FAIL_CLOSED`, `OPEN`, `REJECTED`).
* **Navigation Controls:** [Tabs.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Tabs.tsx) — Underlined and pill tab selectors with active border indicators.
* **Metrics:** [Metric.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Metric.tsx) — Monospace numerical values with directional delta indicators and subtext labels.
* **Feedback States:** [Skeleton.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/Skeleton.tsx), [ErrorState.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/ErrorState.tsx), [EmptyState.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/ui/EmptyState.tsx).

### 2.5 Data-Fetching & Real-Time Patterns
* **REST Queries:** Centralized API client in [frontend/src/lib/api/client.ts](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/lib/api/client.ts) (`apiClient.get()`, `apiClient.post()`), wrapped in React Query hooks with 5s–30s `refetchInterval` polling during market hours.
* **WebSocket Integration:** [frontend/src/lib/websocket/client.ts](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/lib/websocket/client.ts) manages native WebSocket connections to `/ws/intraday/` with automatic exponential backoff reconnects and status broadcasting.
* **Error Boundaries:** Universal [ErrorBoundary.tsx](file:///Users/shivamsingh/personal/nomad-analyst/frontend/src/components/common/ErrorBoundary.tsx) wraps the app shell and individual page bodies to isolate component-level failures.

---

## 3. Existing F&O Backend Contract Inventory & Gap Analysis

The backend data contracts in `fno/` were compared against existing REST endpoints in `market/urls.py` and `frontend/src/lib/api/endpoints.ts`:

| Data Domain | Required UI Information | Current Backend Availability | Classification | Gap & Required Backend Addition |
|---|---|---|---|---|
| **1. NIFTY Spot Context** | Nifty 50 spot price, direction, regime, last update time | `GET /api/v1/intraday/market-context/` returns `nifty_spot`, `direction`, `regime` | **Available** | None; existing contract is complete. |
| **2. ATM Strike Chain** | Calculated ATM strike, active CE/PE tokens, strike step (50 pts), expiry dates | Computed in memory by `DesiredOptionUniverse` (`fno/services/desired_universe.py`) | **Unavailable** | Need `GET /api/v1/fno/chain/` exposing current ATM and subscribed contracts. |
| **3. Option Feed Health** | Ingestion status, active token count, quote freshness age, feed latency | Daemon logs and heartbeat telemetry track active tokens and quote age | **Unavailable** | Need `GET /api/v1/fno/health/` returning quote freshness & token status. |
| **4. Option Bars (1m OHLCV)** | 1m candlestick data for active CE/PE strikes (Open, High, Low, Close, Volume, OI) | Stored in PostgreSQL table `fno_option_ohlcv_bars` (`OptionOHLCVBar` model) | **Unavailable** | Need `GET /api/v1/fno/bars/?symbol=...&timeframe=1m` for chart rendering. |
| **5. Opening Range Status** | 15-bar completion count (N/15), High/Low levels, established boolean, session date | Tracked in `NiftyOrbBreakoutStrategy` state and persisted spot bars | **Unavailable** | Need `GET /api/v1/fno/strategy/` returning range bounds & completion counter. |
| **6. Strategy Evaluations** | Total evaluation count, signal decisions, quote gate rejections, rejection reasons | Logged in daemon telemetry and persisted as `status="REJECTED"` in ledger | **Unavailable** | Need `GET /api/v1/fno/evaluations/` exposing recent signals and rejection audit logs. |
| **7. Paper Positions & Ledger** | Active open trades, fill price, slippage, lot size, entry timestamp, live unrealized P&L | Stored in PostgreSQL table `fno_paper_trade_ledger` (`PaperTradeLedger` model) | **Unavailable** | Need `GET /api/v1/fno/trades/` returning open positions and historical trades. |
| **8. Frictions & Statistics** | Statutory charges breakdown (STT, Exchange 0.03553%, GST, SEBI), net P&L, win rate | Calculated by `StatutoryFeeCalculator` and command `report_paper_session` | **Unavailable** | Need `GET /api/v1/fno/performance/` aggregating session trade stats. |
| **9. Diagnostics & Data Quality**| Partial bar counts, missing bars, disconnect events, ticker daemon health | Parsed by `fno/services/log_parsers.py` and stored with `is_partial=True` | **Unavailable** | Need `GET /api/v1/fno/diagnostics/` exposing partial bar metrics. |

---

## 4. Proposed F&O UI Integration Architecture

### 4.1 Navigation Recommendation: Dedicated Top-Level `/fno` Workspace

```
Global Sidebar:
  📊 Market Overview       (/market)
  🌐 Market & Sectors       (/market-intelligence)
  ⚡ Intraday Scanner       (/intraday)          ← Cash Equities
  🎯 Opportunities          (/delivery)
  📈 Stocks & Research      (/stocks)
  ⚡ F&O Laboratory         (/fno)               ← NEW: Derivatives Terminal (Tag: BETA / LIVE)
  🏛️ Fundamentals          (/fundamentals)
  💡 Recommendations        (/recommendations)
  🤖 AI Intelligence        (/research)
  🧪 Backtesting Lab        (/backtests)
  ⭐ Watchlists             (/watchlist)
  🚨 Command Center         (/alerts)
```

#### Rationale & Trade-Off Analysis:
1. **Separation of Derivatives from Cash Equities:** Cash equities (`/intraday`) focus on multi-stock scanning across 50 Nifty constituents with 6-dimension scores. Merging options chains, strike ladders, expiration dates, Greeks, and paper trading ledger into `/intraday` creates unmanageable visual density and violates the terminal's editorial restraint.
2. **Compact Navigation Footprint:** Using a single top-level route `/fno` with an internal tab bar maintains sidebar elegance without cluttering the 240px navigation strip.
3. **Consistency with Design System:** Directly reuses existing design tokens, `Tabs`, `Table`, `Badge`, `Metric`, and `Card` components without custom CSS bloat.

---

### 4.2 Proposed Page Layout: `/fno` (4 Tabbed Workspaces)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ F&O DERIVATIVES TERMINAL — NIFTY OPTIONS & STRATEGY LAB                                    │
│ Underlying: NIFTY 50 (24,520.10 ▲ +0.45%) | ATM: 24,500 | Range: ESTABLISHED (24,570/24,422)│
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Tab 1: Live Monitor ]  [ Tab 2: Strategy (ORB-15M) ]  [ Tab 3: Paper Trading ]  [ Tab 4: Diagnostics ] │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Tab 1: Live Monitor & Option Chain
* **NIFTY Spot Header Card:** Spot price, day change, trend regime badge (`BULLISH_TRENDING`), and feed delay indicator.
* **Active Subscribed Strikes Ladder:** Compact tabular grid displaying the active dynamic universe:
  - Strike Price, Expiry Date (`2026-10-27`)
  - CE Column: Bid/Ask, Spread %, Volume, OI, Quote Age (Freshness Badge: `< 0.5s` Emerald)
  - PE Column: Bid/Ask, Spread %, Volume, OI, Quote Age
* **TradingView Mini-Chart:** Dual candlestick chart for active CE and PE contracts with volume sub-panes.

#### Tab 2: Strategy Monitor (`STRAT-ORB-15M`)
* **Opening Range Progress Widget:**
  - Visual 15-segment progress bar showing bar formation between 09:15 and 09:30 IST.
  - Locked Range Bounds: High (`24,570.00`), Low (`24,422.00`), Range Width (`148 pts`).
  - Readiness Status Badge: `FORMING (8/15)` Amber or `LOCKED (15/15)` Emerald or `FAIL_CLOSED` Crimson.
* **Evaluation & Decision Stream:**
  - Real-time counter of evaluated snapshots (`Evals: 132`).
  - Recent Decision Stream: Timestamp, Strike, Trigger Rule, Decision (`ACCEPTED` / `REJECTED`), and Rejection Reason chip (`REJECTED_MAX_CONCURRENT_POSITIONS`, `REJECTED_STALE_QUOTE`, `REJECTED_EXCESSIVE_SPREAD`).

#### Tab 3: Paper Trading Ledger & Performance
* **Active Open Position Banner:**
  - Tradingsymbol, Option Type (`CE`), Quantity (`65`), Entry Time, Fill Price, Current LTP, Unrealized P&L, Slippage Incurred.
* **Completed Session Trades Table:**
  - Trade ID, Contract, Entry/Exit Fill Prices, Gross P&L, Total Statutory Frictions (STT, Exchange Fee 0.03553%, GST, SEBI), Net P&L.
* **Statistical Performance Strip:**
  - Win Rate %, Profit Factor, Expectancy per trade, Maximum Drawdown, Cumulative Net P&L.

#### Tab 4: Data Quality & System Diagnostics
* **Feed Health & Connectivity Card:**
  - Kite WebSocket status (`CONNECTED`), PostgreSQL pool status, Redis status, uptime counter.
* **1-Minute Bar Aggregator Health:**
  - Total bars persisted today, Partial bars count & percentage, missing bars detected.
* **Daemon Reconnect Audit Log:**
  - Chronological table of reconnect events, socket disconnect codes, and active bar flush records.

---

## 5. Phased Implementation Plan

### Phase 1: Backend API Presentation Layer (`fno/api/`)
* **Objective:** Expose existing models and in-memory strategy state via secure, read-only Django REST Framework endpoints.
* **Endpoints to implement:**
  - `GET /api/v1/fno/overview/` (Underlying spot, ATM strike, strategy state, range bounds)
  - `GET /api/v1/fno/chain/` (Active option quote snapshots, freshness, bid/ask)
  - `GET /api/v1/fno/trades/` (PaperTradeLedger records, P&L, fee breakdown)
  - `GET /api/v1/fno/diagnostics/` (Option bar counts, partial bar ratio, feed health)
* **Acceptance Criteria:**
  - All endpoints return strict typed JSON conforming to DRF Spectacular OpenAPI schema.
  - Zero mock or fabricated market values; endpoints read directly from database and daemon cache.
  - Read-only operations; no order placement or ledger mutation from GET requests.

### Phase 2: Frontend API Client & React Query Hooks
* **Objective:** Define TypeScript types, register endpoints, and build query hooks in `frontend/src/`.
* **Files to create/modify:**
  - `frontend/src/lib/api/endpoints.ts`: Add `FNO_OVERVIEW`, `FNO_CHAIN`, `FNO_TRADES`, `FNO_DIAGNOSTICS`.
  - `frontend/src/lib/api/types.ts`: Define `FnoOverviewResponse`, `FnoOptionQuote`, `FnoPaperTrade`, `FnoDiagnostics`.
  - `frontend/src/hooks/useFnoData.ts`: Implement `useFnoOverview()`, `useFnoChain()`, `useFnoTrades()`, `useFnoDiagnostics()` with 2s–5s polling intervals.
* **Acceptance Criteria:**
  - Full TypeScript typing with zero `any` declarations.
  - Automatic background polling during market hours (09:15–15:30 IST); paused post-market.

### Phase 3: Frontend F&O Workspace (`/fno`)
* **Objective:** Build and wire the `/fno` route and tabbed components.
* **Files to create:**
  - `frontend/src/pages/FnoPage.tsx`
  - `frontend/src/features/fno/components/FnoLiveMonitorTab.tsx`
  - `frontend/src/features/fno/components/FnoStrategyTab.tsx`
  - `frontend/src/features/fno/components/FnoLedgerTab.tsx`
  - `frontend/src/features/fno/components/FnoDiagnosticsTab.tsx`
* **Sidebar Integration:**
  - Add `{ to: '/fno', label: 'F&O Laboratory', icon: '⚡', tag: 'BETA' }` to `NAV_ITEMS` in `Sidebar.tsx`.
  - Register route `/fno` in `App.tsx` with lazy loading.
* **Acceptance Criteria:**
  - Strictly reuses existing UI components (`Table`, `Card`, `Badge`, `Metric`, `Tabs`).
  - Numbers formatted using monospace tabular numerals (`font-feature-settings: 'tnum'`).
  - Handles loading (`Skeleton`), error (`ErrorState`), and empty states (`EmptyState`) gracefully.

### Phase 4: Integration Testing & Verification
* **Objective:** End-to-end unit and integration testing.
* **Tests to implement:**
  - DRF test cases in `fno/tests/test_fno_api.py` validating HTTP responses, status codes, and schema conformance.
  - Vitest test cases in `frontend/src/test/fnoPage.test.tsx` verifying tab navigation, metric rendering, and table formatting.
  - Number formatting regression checks ensuring string decimals from DRF are cast before `.toFixed()` calls.

---

## 6. Dependencies, Risks & Unresolved Questions

1. **Dependency: Running Ticker Daemon Cache Access:**  
   The F&O overview API needs real-time access to the strategy's in-memory opening range and active ATM strikes.  
   *Resolution:* Store active strategy status and range bounds in Redis/Django cache (`cache.set("fno_strategy_orb_state", ...)`), allowing web workers to query state instantly without locking the database.
2. **Risk: Frontend Decimal Parsing (Type Coercion):**  
   Django REST Framework serializes `DecimalField` as string (`"105.00"`). During the browser audit, an existing equity component encountered `item.entry_price.toFixed is not a function`.  
   *Resolution:* All F&O frontend components must parse decimal fields via `Number(val)` or a dedicated `formatCurrency()` helper before calling number methods.
3. **Open Decision: Real-Time WebSockets vs. Polling:**  
   For the initial iteration, high-frequency React Query polling (2s interval during market hours) provides extreme stability with zero WebSocket connection management complexity. WebSocket streaming (`ws/fno/`) can be introduced in a subsequent optimization phase.

---

## 7. Audit Evidence & Verified Execution Log

* **Browser Subagent Inspections:**
  - Navigated to `http://localhost:5173/market` (Screenshot saved: `market_page_1792580173127.png`)
  - Navigated to `http://localhost:5173/intraday` (Screenshot saved: `intraday_page_1792580185170.png`)
* **API Diagnostic Checks:**
  - `curl -I http://localhost:5173` → `HTTP/1.1 200 OK` (Vite 6 Dev Server alive)
  - `curl -I http://localhost:8000/api/v1/market/overview/` → `HTTP/1.1 200 OK` (Daphne/Django alive)
* **Git Status Baseline:**
  - Branch: `main` (Preserved all existing working-tree files; zero code committed or staged).
