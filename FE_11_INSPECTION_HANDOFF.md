# FE-11 Portfolio / Watchlist & Decision Workspace — Technical Inspection Handoff

## 1. Executive Status

- **Status**: **INSPECTION COMPLETE (READ-ONLY)**
- **Date**: September 1, 2026
- **Workspace Route**: `/watchlist`
- **Backend P0 Blockers**: **ZERO (0 P0 Blockers)** for a client-side persisted Watchlist & Decision Workspace consuming existing live stock, recommendation, and opportunity APIs.

---

## 2. Implemented vs Missing Backend Capabilities

| Capability | Status | Technical Details |
| :--- | :--- | :--- |
| **Backend Watchlist Model** | **MISSING** | No database model or REST endpoint exists on Django backend. |
| **Client-Side Watchlist Persistence** | **IMPLEMENTED** | `localStorage` provides robust multi-watchlist storage, user notes, and decision tags without backend dependency. |
| **Stock Quotes & Details** | **IMPLEMENTED** | `GET /api/v1/stocks/{symbol}/` and `GET /api/v1/stocks/search/` provide quotes, sector, ISIN, and active signals. |
| **Active Recommendations** | **IMPLEMENTED** | `GET /api/v1/recommendations/` returns active trade setups (entry, stop loss, target, R:R). |
| **Opportunities Scoring** | **IMPLEMENTED** | `GET /api/v1/opportunities/` returns discovery scores and setup drivers. |
| **Portfolio & Position Tracking** | **MISSING** | No `Holding`, `Position`, or `Transaction` models exist in database. |
| **Broker Integration** | **MISSING** | No Zerodha, Upstox, Groww, or Angel One API clients exist. |
| **Portfolio P&L & Allocation** | **MISSING** | No realized/unrealized P&L or cost-basis calculations in backend. |
| **User Authentication / Isolation** | **MISSING** | Backend API operates with `AllowAny` permissions; client-side isolation is enforced via browser `localStorage`. |

---

## 3. Relationship with Other Workspaces

- **FE-5 Stock Detail (`/stocks/:symbol`)**: 1-click navigation to inspect live candlestick charts and technical indicators.
- **FE-9 Company Fundamentals (`/fundamentals?symbol=:symbol`)**: 1-click navigation to inspect balance sheets and audited ratios.
- **FE-8 AI Research (`/research?symbol=:symbol`)**: 1-click action to launch deep AI equity research.
- **FE-6 Recommendations (`/recommendations`)**: Direct cross-reference for actionable trade setups.
- **FE-3 Delivery Opportunities (`/delivery`)**: Direct cross-reference for swing setups.

---

## 4. Recommended FE-11 Workspace Layout

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

## 5. Artifact & Documentation Locations

- **Full Inspection Report**: [docs/frontend/FE_11_PORTFOLIO_WATCHLIST_INSPECTION.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/frontend/FE_11_PORTFOLIO_WATCHLIST_INSPECTION.md)
- **Inspection Handoff Document**: [FE_11_INSPECTION_HANDOFF.md](file:///Users/shivamsingh/personal/nomad-analyst/FE_11_INSPECTION_HANDOFF.md)
