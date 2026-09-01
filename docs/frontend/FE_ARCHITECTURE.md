# Nomad Analyst — Frontend Architecture & Technical Specification

**Version:** 1.0.0 (FE-0 Foundation)  
**Date:** September 1, 2026  
**Status:** Implementation-Ready Architecture  
**Target Backend:** `nomad-analyst` (Django 6.0 REST & Channels Backend, Modules 0–11)

---

## 1. Executive Summary & Design Philosophy

Nomad Analyst is an institutional-grade stock intelligence and quantitative research platform for the Indian equity markets (NSE/BSE). The frontend is designed as a **high-density, professional financial terminal** that bridges deterministic quantitative engines (market context, technical indicators, financial ratio modeling, intraday momentum setups, walk-forward backtesting) with grounded, evidence-backed LLM equity research.

### Core Architectural Principles:
1. **Fact-Grounded Presentation:** The UI never hallucinates or fabricates metrics. Missing or stale data is explicitly labeled (`STALE_DATA`, `INSUFFICIENT_DATA`, `UNAVAILABLE_HISTORICAL`).
2. **Backend Domain Authority:** All quantitative calculations, indicator algorithms, setup detections, R:R math, opportunity scoring, and PIT safety logic reside strictly in the Django backend. The frontend is responsible for presentation, charting, filtering, navigation, and local UI state.
3. **Information Density without Clutter:** Clean, dark-mode terminal aesthetics, tabular data alignment, high-contrast monospace numerical data, and structured visual cards. No casino-like animations or misleading "guaranteed profit" indicators.
4. **Resilient Data Fetching:** Seamless blend of smart cached REST queries (`stale-while-revalidate`), background interval polling during active market sessions, and low-latency WebSocket event streaming for live signal changes and research agent progress.

---

## 2. Frontend Technology Stack

| Layer | Chosen Technology | Version / Spec | Rationale & Selection Criteria |
|---|---|---|---|
| **Core Framework** | **React** | 19.0+ | Modern component model, concurrent rendering, optimized reconciliation for streaming tables and charts. |
| **Language** | **TypeScript** | 5.7+ | Strict end-to-end typing matching backend Pydantic & DRF response schemas. Zero `any` policy for financial metrics. |
| **Build & Dev Tooling** | **Vite** | 6.0+ | Sub-second Hot Module Replacement (HMR), tree-shaking, lightweight ESM production bundle without Webpack overhead. |
| **Client Routing** | **React Router** | 7.1+ | Declarative layout-based nested routing, URL search param synchronization for filters, tabs, and timeframes. |
| **Styling & Design System** | **Vanilla CSS + CSS Custom Properties** | CSS3 / Tokens | Maximum flexibility, zero runtime CSS-in-JS performance penalty, institutional dark-theme tokens, full design control without Tailwind utility bloat. |
| **Icons** | **Lucide React** | 0.468+ | Clean, lightweight SVG icon suite for financial and status indicators. |
| **Financial Charting** | **TradingView Lightweight Charts** | 4.2+ | Industry-standard 60fps canvas-based candlestick rendering, multi-pane indicators (Volume, RSI, MACD), custom price lines (Entry, Stop, Target) and marker overlays. |
| **State & Cache Management** | **Custom Query Hook Layer (SWR Pattern)** | In-house TypeScript | Zero-dependency, lightweight cache with automatic deduplication, background revalidation, interval polling, and cache invalidation. |
| **Real-Time Client** | **Native WebSocket Manager** | Browser Standard | Auto-reconnect with exponential backoff, heartbeat/ping-pong, integrating with Django Channels (`ws://...`). |
| **Schema Validation** | **Zod** | 3.24+ | Runtime validation of backend JSON payloads, preventing UI crashes from malformed responses. |
| **Testing** | **Vitest + React Testing Library** | Latest | Unit and component integration tests for financial tables, formatters, and signal badges. |

---

## 3. Product Information Architecture & Page Map

The frontend application is structured into 8 distinct workspace areas accessible via the global application sidebar / top navigation:

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                                NOMAD ANALYST SHELL                                         │
├──────────────┬─────────────────────────────────────────────────────────────────────────────┤
│ GLOBAL NAV   │  [Market Overview]  [Intraday]  [Delivery/Swing]  [AI Research]  [Backtest] │
│ IST CLOCK    │  Session Status: REGULAR (Closes in 02:45:12)  | Breadth: Bullish (+1.42)   │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ SIDEBAR      │ ACTIVE VIEW CONTAINER                                                       │
│              │                                                                             │
│ • Overview   │  1. /market          → Macro Indices, Breadth, Sector Tiers, News Feed     │
│ • Intraday   │  2. /intraday        → Live 5m/15m Signals (ORB, VWAP, Trend), Gating      │
│ • Delivery   │  3. /delivery        → Ranked 6-Dimension Opportunity Grid & Setups        │
│ • Stocks     │  4. /stocks/:symbol  → Master Stock Detail (Chart, Quant, Funds, News, AI) │
│ • Research   │  5. /research        → Multi-Stock Evidence-Backed Research Agent Studio   │
│ • Backtest   │  6. /backtesting     → Walk-Forward Historical Strategy Testing & Metrics  │
│ • Watchlist  │  7. /watchlist       → User Custom Monitored Symbols                       │
│ • Alerts     │  8. /alerts          → Real-time Trigger & Notification Log                │
└──────────────┴─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Workspace Views

### 1. `/market` — Market Overview
- **Benchmark Header:** Live price cards for NIFTY 50 (`^NSEI`), BANK NIFTY (`^NSEBANK`), SENSEX (`^BSESN`), S&P 500 (`^GSPC`), USD/INR (`USDINR=X`), Crude Oil (`CL=F`), Gold (`GC=F`), US 10Y Yield (`^TNX`).
- **Market Regime Card:** Primary trend regime badge (`BULLISH_TRENDING`, `BEARISH_TRENDING`, `RANGE_BOUND`, `HIGH_VOLATILITY`), moving average trend alignment, ATR volatility tier.
- **Advance/Decline Breadth Bar:** Live advancing vs declining count, AD Ratio, Market Participation %, Net New 52W Highs/Lows.
- **Sector Momentum Matrix:** Ranked sector grid (Leading, Improving, Weakening, Lagging) with 1D/1W/1M momentum delta.
- **Macro & Corporate News Feed:** Chronological headline stream with source attribution, sentiment tag, and related company chips.

### 2. `/intraday` — Live Intraday Intelligence
- **Market Session Banner:** Current IST time, trading phase (`PRE_OPEN`, `REGULAR`, `POST_CLOSE`), market open countdown, holiday alerts.
- **Active Setup Scanner Grid:** Live cards for actionable intraday recommendations (`BUY` / `SELL`), displaying:
  - Ticker Symbol & Exchange (`RELIANCE:NSE`)
  - Setup Type (`ORB_BREAKOUT`, `VWAP_RECLAIM`, `TREND_CONTINUATION`, `MEAN_REVERSION`)
  - Execution Timeframe (`5m` / `15m`)
  - Entry Price, Stop-Loss Price, Target 1, Target 2 (with risk/reward ratio e.g. `1:2.4`)
  - Confidence Level (`HIGH`, `MEDIUM`, `LOW`)
  - Session Window & Expiry Countdown (`Expires at 15:15 IST`)
  - Real-time Status Badge (`ACTIVE`, `ENTRY_TRIGGERED`, `TARGET_HIT`, `STOP_HIT`, `EXPIRED`)
- **Intraday Quality Health Panel:** Warmup candle count, missing bar detection, and volume liquidity status.

### 3. `/delivery` — Delivery & Swing Opportunities
- **Universe Filter Toolbar:** Select Universe (`NIFTY50`, `NIFTY_NEXT_50`, `NIFTY_MIDCAP_100`), Horizon (`DELIVERY_SWING`, `LONG_TERM`), Sector filter.
- **Ranked Opportunity Discovery Table:**
  - Symbol & Company Name
  - Overall Opportunity Score (0 to 100 with visual meter)
  - Opportunity Archetype (`MOMENTUM_BREAKOUT`, `PULLBACK_SUPPORT`, `VALUE_RECOVERY`, `EARNINGS_ACCELERATION`, `TRENDING`)
  - 6-Dimension Score Breakdown Mini-Bars: Technical (25%), Fundamental (25%), Sector (15%), Market Context (15%), News (10%), Liquidity (10%)
  - Deterministic Recommendation Signal (`BUY`, `NO_ACTION`, `INSUFFICIENT_DATA`)
  - Primary Pros & Risk Highlights
- **Active Recommendation Drawer:** Inspect full trade setup details, entry trigger conditions, stop-loss invalidation level, and target projection.

### 4. `/stocks/:symbol` — Unified Stock Detail Workspace
- **Header Strip:** Symbol, Company Name, Sector/Industry, Live Price, 1D Absolute & % Change, Day High/Low, 52-Week High/Low, Volume, Data Freshness Timestamp.
- **Main Chart Panel:** Full TradingView Lightweight Charts canvas with timeframe selector (`5m`, `15m`, `1h`, `1d`, `1w`), indicator toggles (SMA 20/50/200, EMA 9/21, VWAP, Bollinger Bands), sub-panes (Volume, RSI 14, MACD), and active recommendation price lines (Entry, Stop, Target).
- **Tabbed Workspace:**
  1. *Technicals:* Key indicator summary, trend regime, support/resistance levels, distance from 52W high/low, ATR volatility.
  2. *Fundamentals:* Audited financial statement viewer (Annual & Quarterly tables for Income Statement, Balance Sheet, Cash Flow), and derived ratios (ROE, ROCE, Debt/Equity, Operating Margin, EPS Growth, PE, PB).
  3. *Sector & Peers:* Sector rank, relative strength vs Nifty 50, peer valuation comparison.
  4. *News & Disclosures:* Company-specific news articles, corporate announcements, filings.
  5. *Recommendations & Outcomes:* Active and historical signals for this stock, win/loss history, R-multiples.
  6. *AI Research:* On-demand trigger for instant LLM equity research on this symbol.

### 5. `/research` — AI Stock Research Studio
- **Research Query Console:** Natural-language question input, symbol selector, research depth toggle (`QUICK`, `STANDARD`, `DEEP`), and optional Point-in-Time (`as_of`) historical date selector.
- **Live Tool Execution Timeline:** Real-time visual trace showing agent reasoning and tool executions (`get_market_quote` → `get_technical_features` → `get_fundamentals` → `get_stock_opportunity` → `get_recommendation`).
- **Structured Research Report Viewer:**
  - Executive Summary & Company Profile
  - Market Snapshot & Pricing Action
  - Technical Structure & Indicator Alignment
  - Fundamental Financial Health & Statement Trends
  - News & Material Events Analysis
  - Grounded Positive Drivers (`positive_factors`) & Risk Drivers (`risks`)
  - Signal Contradictions & Missing Unknowns (`contradictions`, `unknowns`)
  - Exact Source & Tool Evidence Traces (`evidence`)

### 6. `/backtesting` — Quantitative Strategy Backtest Laboratory
- **Configuration Panel:** Strategy selection, Setup type, Execution Timeframe (`5m`, `15m`, `1h`, `1d`), Universe selection, Historical Date Range (`start_date` to `end_date`), Cost Model (`NO_COST`, `REALISTIC_NSE_EQUITY`, `REALISTIC_NSE_INTRADAY`), Ambiguity Resolution Policy (`CONSERVATIVE`, `OPTIMISTIC`, `EXCLUDE`).
- **Execution Controls:** Run Backtest button with progress state (PENDING → RUNNING → COMPLETE / FAILED).
- **Executive Performance Scorecard:**
  - Total Signals Generated, Triggered Count, Untriggered Count
  - Win Rate % (with statistical small-sample warning if `n < 10`)
  - Average Return %, Median Return %, Standard Deviation
  - Average R-Multiple, Expectancy, Profit Factor
  - Peak-to-Trough Drawdown (in R)
  - Average & Median Holding Duration (in bars/days)
- **Dimensional Performance Breakdown Tabs:**
  - By Setup Type (e.g. ORB vs VWAP vs Momentum)
  - By Timeframe (`5m` vs `15m` vs `1d`)
  - By Direction (`BUY` vs `SELL`)
  - By Market Regime (`BULLISH` vs `BEARISH` vs `SIDEWAYS`)
  - By Industry Sector
- **Trade Log Table:** Complete list of simulated trades with Entry Bar, Exit Bar, Actual Entry/Exit Price, Slippage Incurred, Gross/Net PnL, R-Multiple, MFE %, MAE %, Exit Reason (`TARGET_HIT`, `STOP_HIT`, `EXPIRED_SESSION`, `AMBIGUOUS_INTRABAR`).
- **Data Quality & Audit Notice:** Explicit disclaimers highlighting limitations (e.g. historical fundamentals/news non-reconstructibility).

### 7. `/watchlist` — Custom Watchlists
- Tabbed multi-watchlist organizer with real-time price cards, 1D sparkline mini-charts, quick opportunity scores, active recommendation indicators, and 1-click navigation to Stock Detail.

### 8. `/alerts` — Live Signal & System Notifications
- Stream of system triggers (e.g. "RELIANCE 5m ORB Entry Triggered @ ₹1,309.0", "HDFCBANK Target 1 Hit @ ₹1,680.0", "Market Context Regime shifted to HIGH_VOLATILITY").

---

## 4. Key User Journeys

### User Journey A: Morning Market Open Workflow (08:45 – 09:30 IST)
1. **Pre-Open Context Check:** User opens `/market` at 08:50 IST to inspect global market overnight cues (S&P 500, US 10Y, Crude Oil, GIFT Nifty proxy) and review the calculated market regime.
2. **Opportunity Scan Review:** User navigates to `/delivery` to review top-ranked swing opportunities calculated by the overnight batch pipeline.
3. **Setup Selection:** User inspects top candidates (e.g. `RELIANCE` with Score 87.0), examines the 6-dimension breakdown, and reviews deterministic entry/stop levels.
4. **Intraday Transition:** At 09:15 IST (market open), user switches to `/intraday` to monitor Opening Range Breakout (ORB) formations across the Nifty 50 universe during the first 15-minute window.

### User Journey B: Active Intraday Session Workflow (09:30 – 15:15 IST)
1. **Live Signal Monitoring:** User keeps `/intraday` open. The live signal grid updates as 5m candles close.
2. **Signal Notification:** A new `BUY` card appears: `TCS [5m VWAP_RECLAIM] Entry: ₹4,150.0, Stop: ₹4,120.0, Target 1: ₹4,210.0, R:R: 1:2.0, Confidence: HIGH`.
3. **Deep Dive Verification:** User clicks the card to open the quick stock drawer, viewing the 5m candlestick chart with VWAP overlay and active setup lines.
4. **Lifecycle Tracking:** User monitors the trade status as it transitions from `ACTIVE` → `ENTRY_TRIGGERED` → `TARGET_HIT` with exact execution timestamps.

### User Journey C: Comprehensive Stock Research Workflow
1. **Stock Search:** User uses global quick search (`Cmd+K` or search bar) and selects `INFY`.
2. **Technical & Fundamental Inspection:** On `/stocks/INFY`, user reviews moving average alignment, RSI momentum, 5-year revenue/EBITDA growth, and Debt/Equity safety.
3. **News & Disclosure Review:** User checks the news tab for recent quarterly earnings disclosures or management commentary.
4. **Trigger AI Research:** User clicks "Generate AI Research Report". The embedded research panel streams the tool execution trace in real time, producing a grounded, citation-backed intelligence report in ~5 seconds.

### User Journey D: Quantitative Strategy Validation Workflow
1. **Configure Backtest:** User navigates to `/backtesting` and sets parameters: Universe = `NIFTY50`, Timeframe = `1d`, Horizon = `DELIVERY_SWING`, Range = `Past 6 Months`, Cost Model = `REALISTIC_NSE_EQUITY`.
2. **Execute Walk-Forward:** User clicks "Run Walk-Forward Backtest".
3. **Analyze Robustness:** User inspects the aggregate Win Rate, Expectancy, and Max Drawdown, reviews the statistical sample size warnings, checks the Setup Type breakdown to see which strategy variant generated positive alpha, and inspects the MFE/MAE distribution.

---

## 5. Frontend / Backend Architecture & Boundary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React 19 + TypeScript)                      │
│                                                                                 │
│  UI Views & Layouts        Component Library       TradingView Lightweight      │
│  • Market Overview         • Terminal Tables       Charts Canvas Engine         │
│  • Intraday Grid           • Score Meters          • Candlestick Series         │
│  • Stock Workspace         • Signal Badges         • Volume Sub-pane            │
│  • Backtest Lab            • Status Banners        • Indicator Lines            │
│  • Research Studio         • Data Freshness Tag    • Setup Markers (Entry/SL/TP)│
│                                                                                 │
│  State & Network Layer                                                          │
│  • Custom SWR Query Cache (TTL, Stale-While-Revalidate, Window Focus Refetch)   │
│  • WebSocket Client (Auto-Reconnect, Heartbeat Ping/Pong, Event Dispatcher)     │
│  • Client-Side Filtering, Sorting, Pagination, Monospace Numerical Formatters  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ HTTP REST & WebSockets (JSON)
┌──────────────────────────────────────▼──────────────────────────────────────────┐
│                             BACKEND (Django 6.0 + DRF)                          │
│                                                                                 │
│  REST API Endpoints (/api/...)               Channels WebSockets (/ws/...)      │
│  • Market Overview & Regimes (/api/market/)  • Live Quote & Signal Broadcasts   │
│  • Stock Quotes & OHLCV (/api/stocks/)       • LLM Research Stream Events       │
│  • Opportunities & Setups (/api/opps/)                                          │
│  • Recommendations & Signals (/api/recs/)                                       │
│  • Backtest Walk-Forward (/api/backtests/)                                      │
│  • AI Research Agent (/api/research/)                                           │
│                                                                                 │
│  Core Domain Services (Modules 0–11)                                            │
│  • Technical Feature Engine (20 indicators)  • Screener & YFinance Providers    │
│  • Fundamental Metrics Engine (152 ratios)   • Deterministic Signal Engines     │
│  • Context & Breadth Calculator              • Outcome & Performance Evaluators │
│  • Intelligent Multi-LLM Router (Gemini)     • PIT-Safe Backtest Runner         │
│                                                                                 │
│  Database Layer                                                                 │
│  • PostgreSQL 16 (Primary Core Models)       • Redis 7 (Celery Broker & Cache)  │
│  • SQLite (Telemetry & Prompt Run Logs)                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Boundary Contract:
- **Backend Owns:** All calculation math, technical indicator formulas, financial statement parsing, scoring algorithms, opportunity ranking weights, strategy rules, risk/reward calculations, PIT enforcement, backtest simulations, and LLM tool execution.
- **Frontend Owns:** High-performance visualization, layout assembly, responsive viewport scaling, user interactions, local table search/filtering, chart pan/zoom rendering, tab switching, and honest display of data-quality states.

---

## 6. Financial Charting Architecture

### Engine: TradingView Lightweight Charts (v4.2+)
- **Why Selected:** Purpose-built for financial trading applications, 60fps hardware-accelerated canvas rendering, sub-100KB footprint, zero dependencies, native support for multi-pane synchronization, crosshairs, tooltips, price lines, and marker overlays.

### Chart Component Structure:
1. **Primary Candlestick Pane:**
   - Real OHLCV bars (`time`, `open`, `high`, `low`, `close`)
   - Candle Colors: Up `#10B981` (Emerald Green), Down `#EF4444` (Crimson Red), Border/Wick match body
   - Technical Overlays (Toggable):
     - SMA 20 (Blue `#3B82F6`), SMA 50 (Orange `#F59E0B`), SMA 200 (Purple `#8B5CF6`)
     - EMA 9 (Cyan `#06B6D4`), EMA 21 (Pink `#EC4899`)
     - VWAP (Yellow `#EAB308`)
     - Bollinger Bands (Upper/Lower `#6B7280`, Fill `#1F2937` with 0.1 opacity)
   - Setup Price Level Lines:
     - Entry Price: Horizontal dashed line (`#3B82F6` Cyan/Blue) with badge `ENTRY: ₹1,309.0`
     - Stop Loss: Horizontal dashed line (`#EF4444` Red) with badge `STOP: ₹1,280.0`
     - Target 1: Horizontal dashed line (`#10B981` Green) with badge `TP1: ₹1,360.0`
     - Target 2: Horizontal dashed line (`#059669` Dark Green) with badge `TP2: ₹1,410.0`
   - Trade Markers: Visual arrow markers at bar timestamps indicating `BUY_TRIGGERED`, `TARGET_HIT`, `STOP_HIT`.
2. **Volume Sub-Pane (Bottom 20%):**
   - Histogram series aligned with candlestick timestamps.
   - Bar color matches candle direction (Up/Down) with 0.5 opacity.
   - 20-period Volume Moving Average line overlay.
3. **Oscillator Sub-Panes (Optional Toggles):**
   - RSI (14) Pane with 30 (Oversold), 50 (Midline), 70 (Overbought) reference lines.
   - MACD (12, 26, 9) Pane with MACD line, Signal line, and zero-centered histogram.

---

## 7. Real-Time & Polling Architecture

To achieve low-latency responsiveness without unnecessary connection overhead, Nomad Analyst uses a **hybrid real-time strategy**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REAL-TIME HYBRID STRATEGY                          │
├──────────────────────┬─────────────────────────────┬────────────────────────┤
│ WORKSPACE / DATA     │ TRANSPORT MECHANISM         │ FREQUENCY / TRIGGER    │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ Market Indices       │ Interval Polling / SWR      │ Every 30s during Mkt   │
│ Market Breadth       │ Interval Polling / SWR      │ Every 60s during Mkt   │
│ Intraday 5m Candles  │ Interval Polling / SWR      │ Every 15s during Mkt   │
│ Intraday Signals     │ WebSocket (`/ws/market/`)   │ Event-driven (Instant) │
│ Stock Quote Header   │ Interval Polling / SWR      │ Every 10s during Mkt   │
│ Stock Fundamentals   │ Cached REST (SWR)           │ On Mount / 1 hour TTL  │
│ AI Research Progress │ WebSocket (`/ws/research/`) │ Event-driven streaming │
│ Backtest Status      │ Interval Polling (500ms)    │ Active while RUNNING   │
└──────────────────────┴─────────────────────────────┴────────────────────────┘
```

### WebSocket Protocol Specification (`/ws/market/`):
- **Client Handshake:** Connects via standard WebSocket with query token.
- **Heartbeat:** Client sends `{"type": "ping"}` every 30 seconds; server responds `{"type": "pong"}`.
- **Event Types Broadcast by Backend:**
  1. `SIGNAL_GENERATED` — New recommendation produced by intraday signal engine.
  2. `SIGNAL_STATUS_UPDATED` — State change on existing signal (`ENTRY_TRIGGERED`, `TARGET_HIT`, `STOP_HIT`, `EXPIRED`).
  3. `REGIME_CHANGED` — Market context trend regime shift detected.
  4. `MARKET_SESSION_EVENT` — Market open, close, or pre-open state transition.

---

## 8. Data State Management & UI Integrity

Financial decision-making requires absolute transparency regarding data freshness. Nomad Analyst implements a **strict 6-state UI model**:

| State | Visual Indicator | UI Behavior |
|---|---|---|
| **1. LIVE / FRESH** | Green dot + `LIVE` badge + timestamp | Normal full-fidelity rendering. |
| **2. STALE DATA** | Amber warning dot + `STALE (5m ago)` tag | Content remains visible but dimmed; subtle banner informs user of delayed provider updates. |
| **3. PARTIAL DATA** | Yellow badge + `PARTIAL` + field list | Displays available fields; missing metrics display `—` with tooltip explaining missing feature. |
| **4. UNAVAILABLE** | Gray badge + `UNAVAILABLE` | Clear message explaining that data provider does not supply this metric (e.g. historical news). |
| **5. LOADING** | Shimmer skeleton matching final layout | Preserves layout structure; prevents content jumping. |
| **6. ERROR** | Red outline + Retry button | Actionable error message with one-click reload button. |

---

## 9. Design System & Financial Terminal Aesthetics

The application uses an institutional dark-theme design system built with CSS Custom Properties:

```css
:root {
  /* Surface & Background Palette */
  --bg-primary: #0B0E14;      /* Deep obsidian terminal canvas */
  --bg-secondary: #111722;    /* Card & container surface */
  --bg-tertiary: #182232;     /* Elevated surfaces, hover states */
  --border-subtle: #1F2C3F;   /* Subtle structural dividers */
  --border-strong: #2D3F5A;   /* Active / focused borders */

  /* Text & Contrast Hierarchy */
  --text-primary: #F8FAFC;    /* High-contrast headers & values */
  --text-secondary: #94A3B8;  /* Field labels & descriptions */
  --text-muted: #64748B;      /* Timestamps, disclaimers, metadata */

  /* Semantic Financial Accents */
  --bullish: #10B981;         /* Green: Gains, BUY signals, Target Hit */
  --bullish-bg: rgba(16, 185, 129, 0.12);
  --bearish: #EF4444;         /* Red: Losses, SELL signals, Stop Hit */
  --bearish-bg: rgba(239, 68, 68, 0.12);
  --neutral-blue: #3B82F6;    /* Blue: Entry levels, active focus */
  --neutral-blue-bg: rgba(59, 130, 246, 0.12);
  --warning-amber: #F59E0B;   /* Amber: Stale data, small sample alerts */
  --warning-amber-bg: rgba(245, 158, 11, 0.12);

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Roboto Mono', monospace; /* Used for ALL prices, numbers, percentages */

  /* Spacing & Layout */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}
```

---

## 10. Frontend Security & Production Standards

1. **Zero Client Secrets:** No third-party API keys (Yahoo Finance, Screener.in, Google Gemini, Groq, etc.) ever exist in frontend bundles. All provider queries route through Django backend endpoints.
2. **Authentication & Authorization:** Standard Session / Token authentication with CSRF protection on state-modifying requests (`POST /api/backtests/run/`, `POST /api/research/query/`).
3. **Safe Number Parsing:** All monetary and percentage amounts are formatted using strict utility functions that handle `null`, `undefined`, and `NaN` without breaking the DOM.
4. **Accessible Semantics:** Non-color-only status badges (every green/red badge is accompanied by an explicit text label and icon e.g. `▲ +2.51%` / `▼ -1.20%` / `BUY` / `SELL`).
