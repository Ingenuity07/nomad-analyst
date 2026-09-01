# FE-10 Market Intelligence & Sector Analysis Documentation

## Overview

The **Market Intelligence & Sector Analysis Workspace** (`/market-intelligence`, alias `/sectors`) provides institutional analytical depth across Indian macro regimes, internal market breadth participation, sector relative momentum leaderboards, constituent equities exploration, and global cross-market sensitivities.

---

## Workspace Architecture & Routing

- **Primary Route**: `/market-intelligence`
- **Routing Alias**: `/sectors`
- **Complementary Roles**:
  - `FE-2` (`/market`): High-level market overview dashboard.
  - `FE-10` (`/market-intelligence`): Deep sector momentum leaderboards, constituent drill-down, sector-filtered delivery opportunities, breadth participation metrics, and global cues.
  - `FE-3` (`/delivery`): Multi-factor delivery opportunities scanner.
  - `FE-4` (`/intraday`): Real-time intraday scanner gated by market regime.
  - `FE-5` (`/stocks/:symbol`): Single-stock price action and charting terminal.
  - `FE-6` (`/recommendations`): Actionable recommendations tagged with market context.
  - `FE-8` (`/research`): AI intelligence laboratory for multi-tool equity and sector research.
  - `FE-9` (`/fundamentals`): Multi-year company balance sheet and financial statements.

---

## Core Components & Layout

```
---------------------------------------------------------------------------------------------------
FE-10: MARKET INTELLIGENCE & SECTOR ANALYSIS WORKSPACE (/market-intelligence)
---------------------------------------------------------------------------------------------------

1. BENCHMARK REGIME BAR (BenchmarkRegimeBar)
   - Quotes for Nifty 50 (^NSEI), Bank Nifty (^NSEBANK), Sensex (^BSESN).
   - Live Trend Badges: BULLISH / BEARISH / SIDEWAYS.
   - SMA200 Position, Trading Session Window Clock, and Data Freshness.

2. MARKET BREADTH & PARTICIPATION (MarketBreadthCard)
   - Advance / Decline Progress Bar (Advances vs Declines vs Unchanged).
   - Breadth Metrics: A/D Ratio, % Above SMA20, % Above SMA50, % Above SMA200, 52W Highs/Lows.
   - Breadth Regime Status: STRONG / NEUTRAL / WEAK.

3. GLOBAL CUES & SENSITIVITIES (GlobalCuesSensitivities)
   - S&P 500, Nasdaq, Dow Jones, CBOE VIX, USD/INR, Crude Oil, Gold, US 10Y Yield.
   - 20-Day Rolling Pearson Correlation with Nifty 50 and Macro Event Disclosures.

4. SECTOR MOMENTUM LEADERBOARD (SectorMomentumLeaderboard)
   - Ranked Table: Rank, Sector, 1D Return %, vs Nifty %, Average RSI, Volatility, Tier (Strongest/Weakest), Momentum Delta (Improving/Deteriorating/Stable).
   - Visual 1D Sector Performance Spread Pills.
   - Interactive row clicking activates the sector deep-dive panel below.

5. SELECTED SECTOR DRILL-DOWN (SelectedSectorDetail)
   - Action Button: "🤖 Synthesize Sector Thesis in AI Laboratory" → /research?question=...
   - Tab 1: Constituent Equities Table (Symbol, Company Name, Exchange, Terminal / Fundamentals links).
   - Tab 2: Sector Delivery Opportunities (Setup Type, Score, Primary Drivers, View Setup link).

6. THEME ROADMAP & BOUNDARY INDICATOR (ThemeRoadmapCard)
   - Restrained note identifying Theme factor models and 4-quadrant RRG curves as FUTURE capabilities.
---------------------------------------------------------------------------------------------------
```

---

## API Endpoints Consumed

| Endpoint | Method | Response Payload | Description |
| :--- | :--- | :--- | :--- |
| `GET /api/v1/market/overview/` | `GET` | `MarketOverviewResponse` | Aggregated market session, indices, breadth, sector rankings, global cues, and news. |
| `GET /api/v1/market/indices/` | `GET` | `{ indices: MarketIndexItem[], as_of: string }` | Benchmark index quotes, trend regime, and SMA200 position. |
| `GET /api/v1/market/breadth/` | `GET` | `{ universe: string, breadth: MarketBreadth, as_of: string }` | Advances, declines, A/D ratio, participation above SMA20/50/200, 52W extremes. |
| `GET /api/v1/market/sectors/` | `GET` | `{ sector_rankings: SectorRanking[], as_of: string }` | Ranked sector momentum tiers, 1D returns, relative strength, and momentum deltas. |
| `GET /api/v1/market/global/` | `GET` | `{ global_cues: CrossMarketCues, as_of: string }` | Global market cues (S&P 500, USD/INR, Crude, Gold) and rolling correlations. |
| `GET /api/v1/stocks/?sector={sector}` | `GET` | `PaginatedResponse<StockSummary>` | Paginated constituent equities belonging to the selected sector. |
| `GET /api/v1/opportunities/?sector={sector}` | `GET` | `PaginatedResponse<StockOpportunitySnapshot>` | Scored delivery swing opportunities in the selected sector. |

---

## Point-in-Time (PIT) & Lookahead Handling

- `MarketContextService` accepts `as_of` parameter and computes technical indicators and breadth strictly on historical price bars prior to `as_of`.
- `MarketContextSnapshot` persists immutable snapshots for backtesting and historical replay.

---

## Scope Boundaries & Future Capabilities

### IMPLEMENTED:
- Deterministic market regime detection (Trend, Volatility, Momentum, Breadth).
- Benchmark index quotes and SMA200 relationship.
- Internal market breadth and SMA participation metrics.
- Sector relative momentum leaderboard and 1D performance spread.
- Interactive sector constituent drill-down and sector-filtered delivery opportunities.
- Global cues and macroeconomic central bank event disclosures.
- Direct handoffs to FE-5 (Stock Terminal), FE-9 (Fundamentals), FE-3 (Delivery Opportunities), FE-8 (AI Research).

### NOT IMPLEMENTED / FUTURE:
- Thematic basket classification engine (e.g. AI, Defence, EV, Renewables).
- Formal 4-quadrant Relative Rotation Graph (RRG) coordinates (JdK RS-Ratio & RS-Momentum).
- Multi-period sector historical return series (1W, 1M, 3M, 6M, 1Y).
- Dedicated historical regime transitions endpoint.
