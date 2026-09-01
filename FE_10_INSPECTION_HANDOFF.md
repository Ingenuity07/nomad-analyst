# FE-10 Market Intelligence / Sector & Theme Workspace — Technical Inspection Handoff

## 1. Executive Status

- **Status**: **INSPECTION COMPLETE (READ-ONLY)**
- **Date**: September 1, 2026
- **Workspace Route**: `/market-intelligence` or `/sectors`
- **Backend P0 Blockers**: **ZERO (0 P0 Blockers)** for Market Regime, Breadth, Sector Momentum Leaderboard, Sector Constituents, and Global Cues.

---

## 2. Implemented vs Missing Backend Capabilities

| Capability | Status | Technical Details |
| :--- | :--- | :--- |
| **Market Overview Snapshot** | **IMPLEMENTED** | `GET /api/v1/market/overview/` returns aggregated context: session, breadth, index regimes, sector rankings, global cues, news. |
| **Benchmark Indices** | **IMPLEMENTED** | Quotes, changes, regime status, and SMA200 position for `^NSEI` (Nifty 50), `^NSEBANK` (Bank Nifty), `^BSESN` (Sensex). |
| **Market Regime Detection** | **IMPLEMENTED** | Deterministic trend (`bullish`, `bearish`, `sideways`), volatility (`low`, `normal`, `high`, `extreme`), momentum (`positive`, `negative`, `neutral`). |
| **Market Breadth & Internals** | **IMPLEMENTED** | `GET /api/v1/market/breadth/` returns Advances/Declines, A/D ratio, participation above SMA20/50/200, 52W Highs/Lows, and breadth regime. |
| **Sector Momentum Leaderboard** | **IMPLEMENTED** | `GET /api/v1/market/sectors/` returns ranked sectors with 1D return, relative vs Nifty, average RSI, volatility, tier (`strongest`/`weakest`), and momentum state (`improving`/`deteriorating`). |
| **Sector Constituent Stocks** | **IMPLEMENTED** | `GET /api/v1/stocks/?sector={sector}` returns paginated equities belonging to the requested sector. |
| **Sector Opportunities** | **IMPLEMENTED** | `GET /api/v1/opportunities/?sector={sector}` returns scored delivery swing opportunities in the sector. |
| **Global Cues & Correlations** | **IMPLEMENTED** | `GET /api/v1/market/global/` returns S&P 500, Nasdaq, Dow Jones, CBOE VIX, USD/INR, Crude Oil, Gold, US 10Y Yield + 20D rolling correlations. |
| **Macro Economic Events** | **IMPLEMENTED** | Filters disclosures/news matching RBI, FOMC, inflation, CPI, GDP, interest rates. |
| **Themes Infrastructure** | **MISSING** | No Theme model, no theme-to-stock mapping table, and no theme performance calculation engine exist in backend. |
| **4-Quadrant RRG Rotation Trajectories** | **PARTIAL** | 1D relative return and 5D momentum delta exist; formal JdK RS-Ratio / RS-Momentum vector coordinates are MISSING. |
| **Multi-Period Sector Returns** | **MISSING** | 1W, 1M, 3M, 6M, 1Y sector return series are not exposed by the current endpoint. |
| **Historical Regime API** | **MISSING** | Persisted in `MarketContextSnapshot` DB, but endpoint (`/market/regime/history/`) is unexposed. |

---

## 3. Point-in-Time (PIT) & Lookahead Safety

- **Market Context**: `MarketContextService` accepts `as_of` parameter and computes technical indicators and breadth strictly on historical bars prior to `as_of`.
- **Snapshots**: Persisted in `MarketContextSnapshot` table with immutable `as_of` timestamp.
- **Sector Mappings**: Relational via `Company.sector`.

---

## 4. Relationship with Other Workspaces

- **FE-2 Market Overview (`/market`)**: Provides high-level daily dashboard. FE-10 provides the deep sector-by-sector and constituent breakdown.
- **FE-3 Delivery Opportunities (`/delivery`)**: Deep link to sector opportunities (`/delivery?sector=...`).
- **FE-4 Intraday Scanner (`/intraday`)**: Uses market regime gating for real-time breakout setups.
- **FE-5 Stock Detail (`/stocks/:symbol`)**: Deep dive into individual constituent equities.
- **FE-6 Recommendations (`/recommendations`)**: Displays setups tagged with sector and market regime.
- **FE-8 AI Research (`/research`)**: Action button to synthesize sector thesis in AI laboratory (`/research?question=Analyze+Technology+sector+outlook`).
- **FE-9 Company Fundamentals (`/fundamentals`)**: Link to company balance sheet and financial statement explorer.

---

## 5. Recommended FE-10 Workspace Layout

```
---------------------------------------------------------------------------------------------------
FE-10: MARKET INTELLIGENCE & SECTOR ANALYSIS WORKSPACE
---------------------------------------------------------------------------------------------------

1. MARKET REGIME & BENCHMARK INDEX BAR
   - Nifty 50, Bank Nifty, Sensex Quotes & Regime Badges (Bullish/Bearish/Sideways, Volatility, Momentum)
   - Live Market Trading Session Window & Data Freshness Indicator

2. MARKET BREADTH & INTERNAL PARTICIPATION
   - Advance/Decline Ratio & Participation Gauges (% Above SMA20, SMA50, SMA200)
   - 52-Week Highs vs Lows Breakdown & Breadth Regime (Strong / Neutral / Weak)

3. SECTOR MOMENTUM & RELATIVE STRENGTH LEADERBOARD
   - Ranked Sectors Table: Rank, Sector Name, 1D Return %, Relative Return vs Nifty, RSI, Volatility, Tier, Momentum State
   - Visual Sector Momentum Bar Chart (Top Performers vs Laggards)
   - Sector Filter / Selection to trigger Constituent & Opportunity Deep Dive

4. SELECTED SECTOR DEEP-DIVE PANEL (Interactive on Sector Click)
   - Sector Constituent Equities Table (Symbol, Price, Change %, RSI, Technical Bias)
   - Top Delivery Opportunities in Selected Sector (from FE-3)
   - "Synthesize Sector Thesis in AI Laboratory" → links to FE-8

5. GLOBAL CUES & CROSS-MARKET SENSITIVITIES
   - S&P 500, Nasdaq, Dow Jones, CBOE VIX, USD/INR, Crude Oil, Gold, US 10Y Yield
   - 20-Day Rolling Pearson Correlation with Nifty 50
   - Macro Economic Event Disclosures (RBI, Inflation, Policy)

6. THEMES & FUTURE ROADMAP INDICATOR
   - Structured note indicating Themes & RRG Trajectories remain FUTURE backend capabilities.
---------------------------------------------------------------------------------------------------
```

---

## 6. Artifact & Documentation Locations

- **Full Inspection Report**: [docs/frontend/FE_10_MARKET_INTELLIGENCE_INSPECTION.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/frontend/FE_10_MARKET_INTELLIGENCE_INSPECTION.md)
- **Handoff Document**: [FE_10_INSPECTION_HANDOFF.md](file:///Users/shivamsingh/personal/nomad-analyst/FE_10_INSPECTION_HANDOFF.md)
