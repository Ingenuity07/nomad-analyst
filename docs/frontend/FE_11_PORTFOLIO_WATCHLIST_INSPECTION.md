# FE-11 Portfolio / Watchlist & Decision Workspace — Technical Inspection Report

## Executive Summary

This document provides a comprehensive, read-only technical inspection of the backend and frontend systems for **FE-11: Portfolio / Watchlist & Decision Workspace**.

The inspection establishes that:
1. **Watchlists, Portfolios, Positions, and Transactions** are **MISSING** from the backend Django database models and REST API.
2. **Broker integrations** (Zerodha, Upstox, Groww, Angel One) are **MISSING** from the codebase.
3. **User Authentication & Object-Level Ownership** are **MISSING** on the backend API layer (endpoints operate with `AllowAny` permissions).
4. **FE-11 MVP can be implemented cleanly as a Watchlist & Decision Workspace** leveraging client-side `localStorage` for watchlist management, decision notes, and custom baskets, while integrating live quotes, active recommendations (`StockRecommendation`), discovery opportunities (`StockOpportunitySnapshot`), and stock terminal / AI research handoffs.

---

## 1. Watchlist API & Model Audit

| Entity / Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **Backend `Watchlist` Model** | **MISSING** | No `Watchlist` table exists in Django ORM. |
| **Backend `WatchlistItem` Model** | **MISSING** | No `WatchlistItem` table exists in Django ORM. |
| **Watchlist CRUD Endpoints** | **MISSING** | No `/api/v1/watchlists/` endpoint exists in Django REST framework. |
| **Client-Side Watchlist Persistence** | **IMPLEMENTED** | `localStorage` persistence can store multiple custom watchlists, symbols, and user notes. |
| **Stock Data for Watchlists** | **IMPLEMENTED** | `GET /api/v1/stocks/{symbol}/`, `GET /api/v1/stocks/search/`, `GET /api/v1/stocks/{symbol}/technicals/` provide live quotes, changes, and technical bias. |

---

## 2. Portfolio, Holdings & Transaction Audit

| Entity / Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **`Portfolio` Model** | **MISSING** | No portfolio container model in database. |
| **`Holding` / `Position` Model** | **MISSING** | No positions table (quantity, buy price, invested value, market value). |
| **`Transaction` / `Trade` Model** | **MISSING** | No transaction logging (buy/sell orders, STT, brokerage, taxes). |
| **Portfolio Valuation / P&L Engine** | **MISSING** | No realized/unrealized P&L or cost-basis calculations in backend. |
| **Broker Integration** | **MISSING** | No Zerodha Kite, Upstox, Angel One, or Groww API clients exist. |
| **Portfolio Risk / Allocation** | **MISSING** | No asset allocation or sector concentration calculations exist in backend. |

---

## 3. User Authentication & Security

- **Authentication**: The backend does not implement JWT, OAuth, or Session-based user accounts; `REST_FRAMEWORK` uses `AllowAny`.
- **User Isolation**: Because watchlists in FE-11 will use `localStorage`, user data is isolated to the local browser client without cross-user data leakage.
- **Backend User Model**: Django's default `auth_user` table exists in migrations but is not connected to financial models.

---

## 4. Decision Context & Research Integration

- **Active Recommendations**: `GET /api/v1/recommendations/` returns active swing/positional setups (`signal`, `setup_type`, `entry_price`, `stop_price`, `target_price`, `confidence`, `risk_reward_ratio`).
- **Opportunity Snapshots**: `GET /api/v1/opportunities/` returns discovery scores and setup drivers.
- **AI Research Dossiers**: `POST /api/v1/research/` can be launched directly for any watched stock via `/research?symbol={symbol}`.
- **Audited Fundamentals**: Direct 1-click navigation to `/fundamentals?symbol={symbol}`.
- **Stock Terminal**: Direct 1-click navigation to `/stocks/{symbol}`.

---

## 5. Stale Data, Market Price Source & PIT

- **Price Source**: `MarketSnapshot` provides `close`, `change`, `change_percent`, and `timestamp`.
- **Trading Hours**: `MarketSessionInfo` classifies session windows (`OPENING`, `MORNING`, `MIDDAY`, `AFTERNOON`, `CLOSING`, `OUTSIDE`).
- **Stale Price Behavior**: During market-closed hours or non-trading intervals, last recorded snapshot prices are used with `DataStatus` indicating `HISTORICAL_PIT` or `STALE`.

---

## 6. Recommended FE-11 Workspace Architecture

```
---------------------------------------------------------------------------------------------------
FE-11: WATCHLIST & DECISION WORKSPACE (/watchlist)
---------------------------------------------------------------------------------------------------

1. WATCHLIST MANAGER & TAB STRIP
   - Multi-Watchlist Tabs: "Core High-Conviction", "Momentum Breakouts", "Fundamental Value", "+ New List"
   - Quick Add Symbol Autocomplete Search (via GET /api/v1/stocks/search/)
   - Manage List (Rename, Delete, Reorder)

2. WATCHLIST SUMMARY & DECISION STATS STRIP
   - Total Tracked Symbols Count, Advancing / Declining Ratio in Watchlist
   - Active Recommendation Signals Count (BUY / SELL setups active)
   - Average Opportunity Score across watched basket

3. MONITORED DECISION MATRIX (Table View & Card View Toggle)
   - Columns: Symbol, Company Name, Sector, Latest Close, 1D Change %, Signal/Setup Badge, Opportunity Score, User Decision Tag (WATCHING, CONSIDERING, RESEARCHING), Quick Actions.
   - 1-Click Navigation:
     - 📈 Stock Terminal (/stocks/:symbol)
     - 🏛️ Fundamentals (/fundamentals?symbol=:symbol)
     - 🤖 AI Research (/research?symbol=:symbol)
     - 💡 Setup Detail (/recommendations)

4. WATCHED STOCK DETAIL DRAWER (Interactive on Row Click)
   - Quote snapshot & mini technical indicators (RSI, SMA50, SMA200)
   - Active recommendation trade setup details (Entry, Stop Loss, Target, R:R)
   - User Decision Thesis Notes (editable text area persisted to localStorage)
   - User Decision Status Selector (WATCHING, CONSIDERING, RESEARCHING, HOLDING)

5. PORTFOLIO & BROKER CAPABILITIES BOUNDARY
   - Restrained note indicating Live Broker Sync (Zerodha/Upstox) and P&L Tracking are FUTURE backend capabilities.
---------------------------------------------------------------------------------------------------
```

---

## 7. Backend Gap Classification for FE-11

- **P0 (Blocks FE-11 MVP)**: **ZERO (0 Blockers)**. Client-side `localStorage` watchlist state combined with existing backend APIs (`/api/v1/stocks/{symbol}/`, `/api/v1/recommendations/`, `/api/v1/opportunities/`, `/api/v1/stocks/search/`) provides a complete, institutional watchlist and decision-tracking experience.
- **P1 (Important Enhancements)**:
  - Add backend `UserWatchlist` and `WatchlistItem` database models and REST endpoints when multi-device user auth is introduced.
- **P2 / FUTURE**:
  - `PortfolioHolding`, `Position`, `Transaction` models and P&L computation engine.
  - Broker OAuth integrations (Zerodha Kite, Upstox, Groww, Angel One).
  - Portfolio-level risk analytics (VaR, beta, sector concentration).
