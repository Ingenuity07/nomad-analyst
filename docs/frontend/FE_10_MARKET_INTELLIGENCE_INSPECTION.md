# FE-10 Market Intelligence / Sector & Theme Workspace — Technical Inspection Report

## Executive Summary

This document provides a comprehensive, read-only technical inspection of the backend and frontend systems for **FE-10: Market Intelligence / Sector & Theme Workspace**.

The inspection establishes that the backend (Module 6 & Module 7) provides robust, deterministic market regime classification, market breadth participation analytics, benchmark index monitoring, ranked sector momentum leaderboards, cross-market global cues, and macro event tracking. However, **Themes** (e.g. AI, Defence, EV, Renewables) and **4-Quadrant RRG Sector Rotation Trajectories** are **MISSING** or **PARTIAL** in the codebase.

---

## 1. Market API Audit

| Endpoint | Method | Parameters | Status | Response Schema / Data Source | Freshness & PIT |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /api/v1/market/overview/` | `GET` | `universe`, `as_of` | **IMPLEMENTED** | Aggregated dashboard: `market_session`, `breadth`, `index_regimes`, `sector_rankings`, `cross_market_cues`, `fii_dii_flow`, `recent_news`, `data_freshness`. | PIT-safe via `as_of`. Stale after session closes. |
| `GET /api/v1/market/indices/` | `GET` | `as_of` | **IMPLEMENTED** | Quotes, changes, regime status, and SMA200 trend for `^NSEI`, `^NSEBANK`, `^BSESN`. | Live or historical point-in-time. |
| `GET /api/v1/market/regime/` | `GET` | `as_of` | **IMPLEMENTED** | Benchmark index regimes (`trend`, `volatility`, `momentum`) and `breadth_regime`. | Deterministic indicators on-the-fly or persisted snapshot. |
| `GET /api/v1/market/breadth/` | `GET` | `universe`, `as_of` | **IMPLEMENTED** | Advances/Declines, A/D ratio, participation above SMA20/50/200, 52W Highs/Lows, coverage. | On-the-fly calculation from active equities. |
| `GET /api/v1/market/sectors/` | `GET` | `as_of` | **IMPLEMENTED** | Ranked sector leaderboard with 1D average returns, relative vs Nifty, RSI, volatility, tier, and momentum state. | Calculated from constituent equity bars. |
| `GET /api/v1/market/global/` | `GET` | `as_of` | **IMPLEMENTED** | Global cues: S&P 500, Nasdaq, Dow Jones, CBOE VIX, USD/INR, Crude Oil, Gold, US 10Y Yield with staleness flag. | Sourced from global instrument bars. |
| `GET /api/v1/stocks/?sector={sector}` | `GET` | `sector`, `page`, `page_size` | **IMPLEMENTED** | Paginated constituent equities belonging to the requested sector. | Relational database `Company.sector`. |
| `GET /api/v1/opportunities/?sector={sector}` | `GET` | `sector`, `horizon` | **IMPLEMENTED** | Scored delivery opportunities filtered by sector. | Discovery engine (`OpportunityDiscoveryService`). |
| `GET /api/v1/market/themes/` | `GET` | — | **MISSING** | Curated or algorithmic market themes list. | No Theme table in database. |
| `GET /api/v1/market/regime/history/` | `GET` | — | **MISSING** | Historical regime transition timeline endpoint. | Data exists in `MarketContextSnapshot` DB, but endpoint is unexposed. |

---

## 2. Benchmark Index Capabilities

- **Available Benchmark Indices**:
  - `^NSEI`: NIFTY 50
  - `^NSEBANK`: BANK NIFTY
  - `^BSESN`: SENSEX
- **Metrics Available**:
  - Current Close Price, Absolute Day Change, Percentage Day Change.
  - Trend Regime: `bullish`, `bearish`, `sideways` (Close vs SMA200 and SMA50 vs SMA200).
  - Volatility Regime: `low`, `normal`, `high`, `extreme` (Rolling 20-day daily return std dev vs historical percentiles).
  - Momentum: `positive`, `negative`, `neutral` (RSI14 and MACD signal cross).
  - Trend Slope & SMA200 position.

---

## 3. Market Breadth & Internal Health

- **Deterministic Breadth Metrics**:
  - `advancing`: Number of stocks with positive 1D return.
  - `declining`: Number of stocks with negative 1D return.
  - `unchanged`: Number of stocks with 0% 1D return.
  - `advance_decline_ratio`: `advancing / max(1, declining)`.
  - `breadth_regime`: `strong` (>70% stocks above SMA50), `neutral` (30%–70%), `weak` (<30%).
  - `participation`:
    - `pct_above_sma20`: % of universe above 20-day SMA.
    - `pct_above_sma50`: % of universe above 50-day SMA.
    - `pct_above_sma200`: % of universe above 200-day SMA.
  - `new_highs_count`: Stocks within 0.5% of 252-day high.
  - `new_lows_count`: Stocks within 0.5% of 252-day low.
  - `coverage`: Total universe size, active coverage size, coverage ratio, missing symbols list.
- **Ownership**: All breadth calculations are performed strictly on the backend via `MarketContextService.calculate_market_breadth`.

---

## 4. Market Regime Detection Engine

- **Regime Classification**:
  - *Trend*: Bullish (Price > SMA200 & SMA50 > SMA200), Bearish (Price < SMA200 & SMA50 < SMA200), Sideways.
  - *Volatility*: Evaluated against rolling 30-day historical percentiles (`low` < p25, `normal` p25-p75, `high` p75-p95, `extreme` > p95).
  - *Momentum*: Positive (RSI > 55 & MACD > signal), Negative (RSI < 45 & MACD < signal), Neutral.
- **Integration**:
  - `OpportunityDiscoveryService` gates setups based on market regime (e.g. illiquid or high volatility limits).
  - `StockRecommendation` records the exact `market_context` and regime at the time of signal generation.

---

## 5. Volatility & Global Assets

- **India VIX**: Not ingested as an individual Indian ticker; system uses `^VIX` (CBOE VIX) as global volatility benchmark.
- **Realized Volatility**: `vol20` (20-day rolling standard deviation of daily returns) is computed for all instruments.
- **Global Assets Tracked**:
  - `^GSPC` (S&P 500), `^IXIC` (Nasdaq), `^DJI` (Dow Jones), `^VIX` (CBOE VIX).
  - `USDINR=X` (USD/INR Exchange Rate).
  - `CL=F` (Crude Oil Futures), `GC=F` (Gold Futures).
  - `^TNX` (US 10-Yr Treasury Yield).
- **Cross-Market Features**: 20-day Pearson rolling correlations between Nifty 50 and S&P 500, USD/INR, and Crude Oil.

---

## 6. Sector Infrastructure & Performance

- **Sector Entity**: `Company.sector` (e.g. Technology, Financial Services, Energy, Automobile, Healthcare, Consumer Goods, Metals, etc.).
- **Constituent Mapping**: `Company (1) ── (N) Instrument`.
- **Sector Leaderboard (`MarketContextService.calculate_sector_performance`)**:
  - `average_return`: 1D average return of constituent equities.
  - `relative_return_vs_nifty`: Sector return minus Nifty 50 return.
  - `average_rsi`: Average RSI14 across sector stocks.
  - `average_volatility`: Average 20-day volatility.
  - `momentum_state`: `improving` (1D avg return - 5D return > +1.5%), `deteriorating` (delta < -1.5%), `stable`.
  - `rank`: Sorted 1 to N.
  - `tier`: `strongest` (top quartile), `weakest` (bottom quartile), `neutral`.
- **Multi-Period Sector Returns**: 1W, 1M, 3M, 6M, 1Y sector return series are **MISSING** in the backend endpoint.

---

## 7. Sector Rotation Assessment

- **Current Status**: **PARTIAL**.
- **Supported**: Relative strength vs Nifty, RSI, momentum delta over 5 days (`improving` vs `deteriorating`), and tier ranking.
- **Missing**: True 4-quadrant RRG (Relative Rotation Graph) framework with JdK RS-Ratio and RS-Momentum vector coordinates and historical trail curves.

---

## 8. Theme Infrastructure Status

- **Status**: **MISSING**.
- **Findings**:
  - No `Theme` model exists in Django ORM.
  - No theme-to-stock mapping table (`ThemeMembership`) exists.
  - No theme return or momentum calculation engine exists.
  - LLM in Module 5 can discuss qualitative themes in research memos using news and company context, but no structured quantitative theme analytics engine is present.

---

## 9. News, Macro & Corporate Events

- **Market News (`NewsItem`)**: Corporate news feed with headline, summary, source, and published timestamp.
- **Exchange Disclosures (`CorporateDisclosure`)**: Regulatory announcements from NSE/BSE.
- **Macro Keyword Event Scanner**: Filters news and disclosures matching RBI, FOMC, inflation, CPI, GDP, interest rate keywords.

---

## 10. Cross-Workspace Touchpoints

- **FE-2 Market Overview (`/market`)**: Provides the initial dashboard snapshot. FE-10 will expand this into a deep sector, constituent, and cross-asset intelligence terminal.
- **FE-3 Delivery Opportunities (`/delivery`)**: Filter opportunities by sector (`/delivery?sector=...`).
- **FE-4 Intraday Scanner (`/intraday`)**: Displays intraday breakout setups under the current market regime.
- **FE-5 Stock Detail (`/stocks/:symbol`)**: Deep dive into individual constituent equities.
- **FE-6 Recommendations (`/recommendations`)**: Inspect active recommendations tagged with sector and market regime context.
- **FE-8 AI Research (`/research`)**: Launch AI research with pre-populated sector queries (`/research?question=Analyze+Technology+sector+outlook`).
- **FE-9 Company Fundamentals (`/fundamentals`)**: Link to company balance sheet and financial statement explorer.

---

## 11. Point-in-Time (PIT) & Lookahead Safety

- `MarketContextService.get_market_context(as_of=...)` calculates all regime, breadth, and sector metrics strictly using historical price bars up to `as_of`.
- `MarketContextSnapshot` persists historical records with immutable `as_of` timestamps.
- Stock sector mappings are relational via `Company.sector`. While sector reclassifications are rare in Indian markets, historical sector changes are not stored in a temporal versioning table.

---

## 12. Recommended FE-10 Workspace Architecture

```
---------------------------------------------------------------------------------------------------
FE-10: MARKET INTELLIGENCE & SECTOR ANALYSIS WORKSPACE (/market-intelligence or /sectors)
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

## 13. Backend Gap Classification for FE-10

- **P0 (Blocks FE-10 MVP)**: **ZERO (0 Blockers)**. Existing endpoints (`GET /api/v1/market/overview/`, `GET /api/v1/market/regime/`, `GET /api/v1/market/breadth/`, `GET /api/v1/market/sectors/`, `GET /api/v1/stocks/?sector=...`, `GET /api/v1/opportunities/?sector=...`) provide all data required for market regime, breadth, sector leaderboards, and constituent exploration.
- **P1 (Important Enhancements)**:
  - Add multi-period sector returns (1W, 1M, 3M, 6M, 1Y) to `MarketSectorsAPIView`.
  - Expose historical regime transitions timeline endpoint (`GET /api/v1/market/regime/history/`).
- **P2 (Secondary Enhancements)**:
  - Add JdK RS-Ratio / RS-Momentum coordinates for 4-quadrant RRG sector rotation.
- **FUTURE**:
  - Theme entity model, theme-to-stock mapping, and theme performance tracking engine.
