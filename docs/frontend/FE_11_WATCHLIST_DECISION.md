# FE-11 Watchlist & Decision Workspace Documentation

## Overview

The **Watchlist & Decision Workspace** (`/watchlist`) provides a personalized, client-persisted environment for monitoring curated equity baskets, tracking real-time trade signals and discovery opportunities, assigning personal decision states (`WATCHING`, `CONSIDERING`, `RESEARCHING`, `HOLDING`), recording investment theses, and seamlessly navigating across Nomad Analyst terminals.

---

## Architecture & Storage Model

Because the backend Django service currently has no persistent user authentication or database `Watchlist` / `Portfolio` models, FE-11 relies on **versioned browser `localStorage`** (`nomad_analyst_watchlists_v1`) for state isolation and persistence.

### Local Storage Schema (`WatchlistStore`):
```typescript
export type DecisionStatus = 'WATCHING' | 'CONSIDERING' | 'RESEARCHING' | 'HOLDING';

export interface WatchlistItem {
  symbol: string;
  decisionStatus: DecisionStatus;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Watchlist {
  id: string;
  name: string;
  symbols: WatchlistItem[];
  createdAt: string;
  updatedAt: string;
}

export interface WatchlistStore {
  version: number;
  activeWatchlistId: string;
  watchlists: Watchlist[];
}
```

---

## Workspace Layout & User Experience

```
---------------------------------------------------------------------------------------------------
FE-11: WATCHLIST & DECISION WORKSPACE (/watchlist)
---------------------------------------------------------------------------------------------------

1. WATCHLIST MANAGEMENT STRIP
   - Multi-Watchlist Tabs ("Core Watchlist", "+ New Watchlist", Rename, Delete).
   - Quick Add Symbol with Autocomplete Search (via GET /api/v1/stocks/search/) and duplicate prevention.

2. WATCHLIST SUMMARY STRIP (WatchlistSummaryStrip)
   - Tracked Stocks count in active list.
   - Day Breadth: Advancing vs Declining count.
   - Active Signals: Count of actionable BUY/SELL setups matching watched stocks.
   - Average Opportunity Score across the basket.

3. MONITORED DECISION MATRIX (MonitoredDecisionTable)
   - View Modes: Table View 📋 vs Cards View 🗂️.
   - Columns: Symbol, Company/Sector, Latest Close, 1D Change %, Strategy Signal (BUY/SELL), Opp Score (/100), Decision State Badge, Quick Action Buttons.
   - 1-Click Actions:
     - 📈 Stock Terminal (/stocks/:symbol)
     - 🤖 AI Research (/research?symbol=:symbol)
     - ✕ Remove from list

4. WATCHED STOCK DETAIL DOSSIER (WatchedStockDetailDrawer)
   - Interactive modal on row click:
     - Company identity, sector, latest closing price, and day change %.
     - Personal Decision State Selector (WATCHING, CONSIDERING, RESEARCHING, HOLDING).
     - Personal Investment Thesis Notes (Editable text area with Save & Cancel).
     - Matched Strategy Setup: Entry, Stop Loss, Target, R:R ratio, Confidence.
     - Matched Opportunity: Score and primary drivers.
     - Direct Links: Stock Terminal, Company Fundamentals, AI Research.

5. PORTFOLIO & BROKER BOUNDARY (PortfolioBoundaryCard)
   - Informational disclaimer explaining local browser persistence and marking live broker sync and P&L portfolio tracking as planned backend features (FUTURE).
---------------------------------------------------------------------------------------------------
```

---

## Backend APIs Consumed

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `GET /api/v1/stocks/search/?q={query}` | `GET` | Autocomplete equity search for adding stocks to watchlists. |
| `GET /api/v1/stocks/{symbol}/` | `GET` | Live price snapshot, company details, and exchange information. |
| `GET /api/v1/recommendations/?status=ACTIVE` | `GET` | Active strategy setups matched by symbol against watched items. |
| `GET /api/v1/opportunities/` | `GET` | Delivery opportunities scored and matched by symbol. |
| `GET /api/v1/stocks/{symbol}/technicals/` | `GET` | Technical indicators (RSI, SMA50, SMA200, volatility). |

---

## Scope Boundaries & Future Capabilities

### IMPLEMENTED:
- Client-side multi-watchlist manager (Create, Rename, Delete, Switch).
- Autocomplete search with duplicate symbol prevention.
- Summary metrics aggregated over active watched basket.
- Monitored decision matrix with Table and Card views.
- Personal decision states (`WATCHING`, `CONSIDERING`, `RESEARCHING`, `HOLDING`).
- Editable personal investment thesis notes persisted in browser.
- Real-time cross-referencing with active strategy recommendations and opportunity scores.
- 1-click cross-workspace navigation to Stock Terminal (FE-5), Fundamentals (FE-9), AI Research (FE-8), and Delivery (FE-3).

### NOT IMPLEMENTED / FUTURE:
- Backend `UserWatchlist` and `WatchlistItem` database tables (awaits user auth layer).
- Portfolio holding / position management (quantity, cost basis, realized/unrealized P&L).
- Broker integrations (Zerodha Kite, Upstox, Groww, Angel One).
- Live transaction order execution or automated trade journaling.
