# Nomad Analyst — FE-5 Stock Detail & Charting Technical Inspection

**Date:** September 1, 2026  
**Target Workspace:** FE-5 Stock Detail & Interactive Charting Terminal (`/stocks/:symbol`)  
**Status:** READ-ONLY INSPECTION COMPLETE (NO CODE MODIFICATIONS)

---

## 1. Executive Summary

This inspection evaluates the backend models, services, REST APIs, technical features, fundamental statements, news, corporate events, AI research linkage, and charting library options required for the upcoming **FE-5 Stock Detail & Interactive Terminal** (`/stocks/:symbol`).

All necessary backend REST presentation endpoints exist under `/api/v1/stocks/`, `/api/v1/opportunities/`, and `/api/v1/recommendations/`. **There are NO backend blockers preventing FE-5 implementation.**

---

## 2. Stock REST API Inventory

| Endpoint | Method | Parameters | Serializer / Response | Backend Provider / Table | Status |
|---|---|---|---|---|---|
| `GET /api/v1/stocks/search/` | `GET` | `q` (string) | `InstrumentSearchSerializer` (`id`, `symbol`, `company_name`, `sector`) | `Instrument`, `Company` | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/` | `GET` | `symbol` (path) | `InstrumentSerializer`, `MarketSnapshotSerializer`, `StockRecommendationSerializer`, `StockOpportunitySnapshotSerializer` | `Instrument`, `MarketSnapshot`, `StockRecommendation`, `StockOpportunitySnapshot` | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/ohlcv/` | `GET` | `timeframe` (`1d`, `5m`, `15m`, `1h`), `start_date`, `end_date`, `limit` (max 1000) | `OHLCVBarSerializer` (`timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`) | `OHLCVBar` (Unique on `[instrument, timeframe, timestamp]`) | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/technicals/` | `GET` | `timeframe` (`1d`), `as_of` (ISO8601) | Dictionary of indicators (`SMA_20/50/200`, `EMA_20/50/200`, `RSI_14`, `MACD`, `ATR_14`) | `TechnicalFeature` | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/fundamentals/` | `GET` | `symbol` (path) | Audited statements (`income_statement`, `balance_sheet`, `cash_flow`) + `metrics` | `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`, `DerivedFundamentalMetric` | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/news/` | `GET` | `page`, `page_size` | `NewsItemSerializer` (`headline`, `summary`, `source`, `published_at`, `url`) | `NewsItem` | `IMPLEMENTED` |
| `GET /api/v1/stocks/{symbol}/events/` | `GET` | `page`, `page_size` | `CorporateDisclosureSerializer` (`headline`, `category`, `published_at`, `details`) | `CorporateDisclosure` | `IMPLEMENTED` |
| `POST /api/v1/chat/` | `POST` | `{ query, conversation_id }` | Agent analysis report with tool call evidence | `chat/agents/` (Module 5) | `IMPLEMENTED` |

---

## 3. Stock Identity Model

- **Canonical URL Identifier:** `symbol` (e.g. `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`).
- **Exchange:** Default `NSE`.
- **Database Model:**
  - `Company`: Holds legal identity, name, ISIN, Sector, Industry, Sub-industry, Description, Website.
  - `Instrument`: Holds ticker `symbol`, `exchange`, `instrument_type` (`EQUITY`, `ETF`, `INDEX`), `lot_size`, `currency` (`INR`).

---

## 4. Historical OHLCV & Chart Data Contract

- **Supported Timeframes:** `1d` (Daily historical up to years), `5m`, `15m`, `1h` (Intraday backfill).
- **Date Ranges Supported:** `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `3Y`, `5Y`, `MAX`.
- **Payload Schema:**
  ```json
  {
    "symbol": "RELIANCE",
    "exchange": "NSE",
    "timeframe": "1d",
    "bars_count": 250,
    "bars": [
      {
        "timeframe": "1d",
        "timestamp": "2026-08-20T00:00:00Z",
        "open": "2950.00",
        "high": "2985.00",
        "low": "2940.00",
        "close": "2975.50",
        "volume": 4520100,
        "source": "yfinance"
      }
    ]
  }
  ```

---

## 5. Technical & Fundamental Indicator Capabilities

### Technical Indicators (Module 2):
- **Trend:** `SMA_20`, `SMA_50`, `SMA_200`, `EMA_20`, `EMA_50`, `EMA_200`.
- **Momentum:** `RSI_14`, `MACD_line`, `MACD_signal`, `MACD_hist`.
- **Volatility & Volume:** `ATR_14`, `volume_sma_20`, `daily_return`.

### Fundamental Metrics & Statements (Module 3):
- **Statements:** 10-period Annual & Quarterly Income Statements, Balance Sheets, and Cash Flow Statements.
- **Ratios Computed:** `revenue_growth_yoy`, `ebitda_growth_yoy`, `pat_growth_yoy`, `eps_growth_yoy`, `ebitda_margin`, `net_margin`, `return_on_equity` (ROE), `return_on_capital_employed` (ROCE), `debt_equity`, `fcf_margin`, `pe_ratio`.

---

## 6. Recommended Charting Library

**Recommendation:** **TradingView Lightweight Charts (`lightweight-charts` v4)**
- **Why:** High-performance HTML5 Canvas rendering built expressly for financial candlestick, bar, volume, and overlay series. Zero DOM bloat, native responsive time-scales, smooth zooming/panning, and strict TypeScript types.
- **Licensing:** Apache 2.0 (100% free and open-source).

---

## 7. Recommended Information Architecture for `/stocks/:symbol`

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Header: Symbol | Company Name | Sector | LTP | 1D Change | DataStatus (LIVE)           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Timeframe / Range Switcher: [ 1D | 1W | 1M | 3M | 6M | 1Y | 5Y ] [ Overlays: SMA/EMA ]│
│ Interactive Candlestick + Volume Chart (Lightweight Charts)                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Tab Navigation:                                                                        │
│ [ Technicals ] [ Fundamentals ] [ Valuation ] [ News & Events ] [ Strategy Signals ]   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Active Tab Content Panels (Independent Query Loading):                                 │
│ • Technicals: Indicator Matrix (RSI, Moving Averages, MACD, Trend State)               │
│ • Fundamentals: Financial Statements Table (Income, Balance Sheet, Cash Flow, ROE)     │
│ • Valuation: PE, PB, Margins, Debt/Equity vs Sector Benchmarks                         │
│ • News & Events: Timeline of corporate filings and news items                          │
│ • Strategy Signals: Active Opportunity score and Recommendation Order history          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ AI Research Console Deep Link: "Ask Nomad Analyst AI about {symbol} →"                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
