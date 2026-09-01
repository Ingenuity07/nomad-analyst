# Nomad Analyst — FE-1 Application Shell & Foundation

**Version:** 1.0.0 (FE-1 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (12/12 Vitest Tests + 229/229 Django Tests)  
**Location:** `frontend/`

---

## 1. Executive Summary

FE-1 establishes the complete frontend application shell, design system foundation, type-safe API client, TanStack Query configuration, WebSocket abstraction, and declarative routing for Nomad Analyst.

### Technologies Implemented:
- **Core:** React 19 (`^19.0.0`), TypeScript (`~5.7.2`), Vite 6 (`^6.0.5`)
- **Routing:** React Router v7 (`^7.1.1`)
- **State & Caching:** TanStack Query v5 (`^5.62.8`)
- **Styling:** CSS3 Custom Properties Design Tokens (`tokens.css`, `reset.css`, `global.css`)
- **Icons:** Lucide React (`^0.468.0`)
- **Testing:** Vitest 2 + React Testing Library + jsdom

---

## 2. Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/              # MarketSessionIndicator, ISTClock
│   │   ├── layout/              # AppShell, Sidebar, TopHeader, PageContainer
│   │   └── ui/                  # Button, Badge, Card, Table, Input, Select, Tabs, Tooltip, Modal, Skeleton, EmptyState, ErrorState, DataStatus, Metric, Timestamp
│   ├── hooks/                   # useMarketOverview, useStock, useOpportunities, useRecommendations, useIntraday, useBacktests, useResearch, useWebSocket
│   ├── lib/
│   │   ├── api/                 # client.ts (central fetch wrapper), endpoints.ts, types.ts
│   │   ├── websocket/           # client.ts, types.ts
│   │   └── queryClient.ts       # TanStack Query client configuration
│   ├── pages/                   # MarketPageShell, IntradayPageShell, DeliveryPageShell, StocksPageShell, StockDetailPageShell, RecommendationsPageShell, ResearchPageShell, BacktestsPageShell, WatchlistPageShell, DesignSystemShowcase
│   ├── styles/                  # tokens.css, reset.css, global.css
│   ├── test/                    # apiClient.test.ts, uiPrimitives.test.tsx, marketSession.test.tsx, routing.test.tsx, setup.ts
│   ├── App.tsx                  # Root QueryClientProvider + BrowserRouter layout
│   └── main.tsx                 # DOM Entry Point
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## 3. Route Table

| URL Path | Workspace Shell Component | Status | Next Feature Module |
|---|---|---|---|
| `/` | Redirects to `/market` | Complete | — |
| `/market` | `MarketPageShell` | Complete | **FE-2** Market Overview |
| `/intraday` | `IntradayPageShell` | Complete | **FE-4** Intraday Scanner |
| `/delivery` | `DeliveryPageShell` | Complete | **FE-3** Delivery Opportunities |
| `/stocks` | `StocksPageShell` | Complete | **FE-5** Stock Detail |
| `/stocks/:symbol` | `StockDetailPageShell` | Complete | **FE-5** Stock Detail |
| `/recommendations` | `RecommendationsPageShell` | Complete | **FE-6** Recommendations & Outcomes |
| `/research` | `ResearchPageShell` | Complete | **FE-8** AI Intelligence |
| `/backtests` | `BacktestsPageShell` | Complete | **FE-7** Backtesting Lab |
| `/watchlist` | `WatchlistPageShell` | Complete | **FE-9** Watchlist |
| `/design-system` | `DesignSystemShowcase` | Complete | Internal Living Showcase |

---

## 4. API Client & Error Handling Architecture

The central API client (`frontend/src/lib/api/client.ts`) guarantees:
1. **Typed Requests:** Complete TypeScript generics matching backend Pydantic models (`lib/api/types.ts`).
2. **Canonical Error Envelope Normalization:** Maps `{ error: { code, message, details, timestamp } }` into standard `ApiError` instances.
3. **Timeout & Abort Controller:** 15-second default timeout with automatic cleanup.
