# NOMAD ANALYST — PHASE 15A: REAL DATA READINESS & POPULATION AUDIT

## 1. Executive Summary & Architectural Preservation
Nomad Analyst is a fully integrated equity intelligence platform comprising 11 backend domain modules, 29 REST API endpoints, and 13 frontend workspace phases. The platform was successfully built and verified using an initial seeded universe (`RELIANCE`, `TCS`, `INFY`, `TEST1`).

This Phase 15A Audit evaluates the exact readiness of the existing system to ingest, process, and maintain real market data for the **NIFTY 50 universe** without modifying any core analytical algorithms, Django models, database schemas, or frontend API contracts.

```
                    NOMAD ANALYST (NIFTY 50 ENGINE)
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
        MARKET CONTEXT                        STOCK INTELLIGENCE
              │                                       │
       ┌──────┼──────┐                         ┌──────┼──────────┐
       │      │      │                         │      │          │
     Regime Breadth Sectors                  Price Technical Fundamentals
       │      │      │                         │      │          │
       └──────┴──────┘                         └──────┴──────────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  ▼
                         OPPORTUNITY ENGINE
                                  │
                                  ▼
                        RECOMMENDATION ENGINE
                                  │
                          ┌───────┴───────┐
                          ▼               ▼
                      DELIVERY        INTRADAY
                          │               │
                          └───────┬───────┘
                                  ▼
                             AI RESEARCH
                                  │
                                  ▼
                              DECISION
                                  │
                       ┌──────────┴──────────┐
                       ▼                     ▼
                   WATCHLIST              ALERTS
                       │
                       ▼
                    OUTCOMES
                       │
                       ▼
                   BACKTESTING
```

**Verdict**: **READY TO IMPLEMENT DATA FOUNDATION (Verdict A)**.  
The current data architecture already possesses the necessary models, uniqueness constraints, PIT timestamp fields, and provider abstractions to support the full NIFTY 50 universe.

---

## 2. Existing Data Model Inventory

| Model Name | Primary Key | Key Relationships | Required Fields | Optional / Nullable Fields | PIT & Timestamp Fields | Constraints & Indexes |
|---|---|---|---|---|---|---|
| `Company` | UUID | Related to `instruments`, `income_statements`, `balance_sheets`, `cash_flows`, `news_items` | `name`, `is_active` | `legal_name`, `short_name`, `isin`, `sector`, `industry`, `sub_industry`, `description`, `website` | `created_at`, `updated_at` | Unique ISIN; Indexed by PK |
| `Instrument` | UUID | `company` (FK CASCADE), `ohlcv_bars`, `snapshots`, `technical_features`, `recommendations` | `company`, `symbol`, `exchange`, `instrument_type`, `currency`, `lot_size`, `is_active` | `isin` | `created_at`, `updated_at` | Unique `symbol`; Indexed by exchange/active |
| `MarketSnapshot` | UUID | `instrument` (FK CASCADE) | `instrument`, `timestamp`, `source` | `open`, `high`, `low`, `close`, `volume`, `previous_close`, `change`, `change_percent`, `source_timestamp` | `timestamp`, `source_timestamp`, `created_at` | Indexes: `[instrument, timestamp]`, `[timestamp]` |
| `OHLCVBar` | UUID | `instrument` (FK CASCADE) | `instrument`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `source` | None | `timestamp` (Bar Open UTC), `created_at` | `UniqueConstraint(instrument, timeframe, timestamp)`; Indexes: `[instrument, timeframe, timestamp]`, `[timestamp]` |
| `TechnicalFeature` | UUID | `instrument` (FK CASCADE) | `instrument`, `timeframe`, `timestamp`, `name`, `parameters`, `param_key` | `value` | `timestamp` (Source Bar Open), `created_at` | `UniqueConstraint(instrument, timeframe, name, param_key, timestamp)` |
| `RawFundamentalData`| UUID | `company` (FK CASCADE) | `company`, `source`, `fiscal_period`, `reporting_type`, `raw_payload`, `status` | `source_url` | `retrieved_at` (Provenance Anchor) | Index: `[company, reporting_type, fiscal_period]` |
| `IncomeStatement` | UUID | `company` (FK CASCADE) | `company`, `fiscal_year`, `period_type`, `period_string` | `period_start`, `period_end`, `filing_date`, `revenue`, `expenses`, `ebitda`, `ebit`, `depreciation`, `interest`, `pbt`, `tax`, `pat`, `eps` | `period_end`, `filing_date` (PIT), `created_at` | `UniqueConstraint(company, period_type, period_string)`; Index: `fiscal_year` |
| `BalanceSheetStatement`| UUID | `company` (FK CASCADE) | `company`, `fiscal_year`, `period_type`, `period_string` | `period_start`, `period_end`, `filing_date`, `equity_capital`, `reserves`, `borrowings`, `other_liabilities`, `total_liabilities`, `fixed_assets`, `cwip`, `investments`, `other_assets`, `total_assets` | `period_end`, `filing_date` (PIT), `created_at` | `UniqueConstraint(company, period_type, period_string)`; Index: `fiscal_year` |
| `CashFlowStatement`| UUID | `company` (FK CASCADE) | `company`, `fiscal_year`, `period_type`, `period_string` | `period_start`, `period_end`, `filing_date`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `free_cash_flow` | `period_end`, `filing_date` (PIT), `created_at` | `UniqueConstraint(company, period_type, period_string)`; Index: `fiscal_year` |
| `DerivedFundamentalMetric`| UUID | `company` (FK CASCADE) | `company`, `period_type`, `period_string`, `name` | `value` | `created_at` | `UniqueConstraint(company, period_type, period_string, name)` |
| `CorporateEvent` | UUID | `company` (FK CASCADE) | `company`, `event_type`, `details` | `announcement_date`, `ex_date` | `announcement_date`, `ex_date`, `created_at` | Index: `[company, event_type, ex_date]` |
| `NewsItem` | UUID | `company` (FK nullable), `instrument` (FK nullable) | `headline`, `source`, `published_at`, `event_type`, `raw_metadata`, `content_hash` | `company`, `instrument`, `summary`, `source_id`, `url` | `published_at` (PIT), `ingested_at` | `UniqueConstraint(content_hash)`; Indexes: `[company, published_at]`, `[published_at]`, `[event_type]` |
| `CorporateDisclosure`| UUID | `company` (FK CASCADE) | `company`, `headline`, `category`, `source`, `announcement_id`, `published_at`, `details`, `content_hash` | `url` | `published_at` (PIT), `ingested_at` | `UniqueConstraint(content_hash)`; Indexes: `[company, published_at]`, `[published_at]` |
| `MarketContextSnapshot`| UUID | None (Macro level) | `as_of`, `universe`, `calculations_version`, `index_regimes`, `breadth`, `sector_rankings`, `global_cues`, `cross_market_features`, `macro_events`, `data_quality` | None | `as_of` (PIT Anchor), `created_at` | Index: `[as_of, universe]` |
| `Universe` & `UniverseMembership` | UUID | `universe` (FK), `instrument` (FK) | `name`, `universe`, `instrument`, `added_at`, `is_active` | `description`, `removed_at` | `added_at`, `removed_at` | `unique_together(universe, instrument, is_active)` |
| `StockOpportunitySnapshot`| UUID | `instrument` (FK CASCADE) | `instrument`, `as_of`, `universe`, `horizon`, `opportunity_type`, `component_scores`, `final_opportunity_score`, `supporting_features`, `risks`, `data_quality` | None | `as_of` (PIT Anchor), `created_at` | Indexes: `[as_of, universe, horizon]`, `[instrument, as_of]` |
| `StockRecommendation` | UUID | `instrument` (FK CASCADE), `outcomes` | `instrument`, `horizon`, `signal`, `setup_type`, `as_of`, `entry_type`, `entry_condition`, `stop_method`, `invalidation_reason`, `target_method`, `confidence`, `status` | `entry_price`, `stop_price`, `target_price`, `risk`, `reward`, `risk_reward_ratio`, `status_updated_at`, `llm_explanation`, `timeframe`, `target_2_price`, `target_2_method`, `session_window`, `strategy_version`, `expires_at` | `as_of` (PIT Anchor), `generated_at`, `status_updated_at`, `expires_at` | Indexes: `[instrument, as_of]`, `[horizon, signal, status]`, `[as_of, status]`, `[instrument, horizon, status, expires_at]` |
| `RecommendationOutcome`| UUID | `recommendation` (FK CASCADE) | `recommendation`, `evaluation_version`, `entry_triggered`, `ambiguous_intrabar`, `bars_evaluated` | `entry_timestamp`, `actual_entry_price`, `exit_reason`, `exit_timestamp`, `actual_exit_price`, `gross_pnl_absolute`, `gross_pnl_percent`, `cost_absolute`, `net_pnl_absolute`, `net_pnl_percent`, `risk_amount`, `r_multiple`, `target_hit`, `stop_hit`, `max_favorable_excursion`, `max_adverse_excursion`, `holding_duration_bars`, `holding_duration_seconds`, `data_quality_warnings` | `entry_timestamp`, `exit_timestamp`, `evaluated_at` | `UniqueConstraint(recommendation, evaluation_version)`; Indexes: `[recommendation, evaluation_version]`, `[exit_reason]`, `[evaluated_at]` |
| `BacktestRun` | UUID | None (Strategy run) | `run_id`, `config`, `status`, `universe_name`, `timeframe`, `horizon`, `start_date`, `end_date`, `strategy_version` | `completed_at`, `result`, `error_message` | `started_at`, `completed_at`, `start_date`, `end_date` | Unique `run_id`; Indexes: `[status]`, `[universe_name, timeframe, horizon]`, `[started_at]` |

---

## 3. Data Requirement Matrix by Nomad Capability

| Nomad Capability | Required Data | Existing Model | Required Fields | Current Population | Missing for NIFTY 50 |
|---|---|---|---|---|---|
| **Market Context** | Benchmark Index bars, Breadth, Sector Momentum, Global Cues | `MarketContextSnapshot`, `OHLCVBar`, `TechnicalFeature` | `^NSEI`, `^NSEBANK`, Sector index OHLCV, Advances/Declines | 3 Snapshots | Daily EOD bar ingestion for all 50 constituent stocks + Sector Indices |
| **Stock Intelligence** | 1-Year Daily OHLCV, Technical Indicator Tree, Corporate Metadata | `Company`, `Instrument`, `OHLCVBar`, `TechnicalFeature` | `open`, `high`, `low`, `close`, `volume`, SMA-20/50/200, RSI-14, MACD | 4 Symbols (272 bars each) | Ingestion for remaining 46 NIFTY 50 symbols |
| **Opportunity Engine** | Multi-factor quantitative scoring (Technicals, Fundamentals, Sector, Market) | `StockOpportunitySnapshot` | `final_opportunity_score`, `component_scores`, `supporting_features` | 2 Snapshots | Daily automated execution over all 50 NIFTY universe members |
| **Recommendation Engine**| Deterministic setups (Breakouts, Retests), Structural Stops, Targets, R:R | `StockRecommendation` | `entry_price`, `stop_price`, `target_price`, `risk_reward_ratio`, `status` | 3 Recommendations | Daily recommendation generation over all 50 NIFTY symbols |
| **Delivery Opportunities**| Daily delivery setups, volume confirmation, liquidity filters | `StockOpportunitySnapshot`, `StockRecommendation` | `horizon='DELIVERY_SWING'`, `setup_type`, `volume >= 50000` | Populated for 4 stocks | Ingestion of remaining 46 symbols |
| **Intraday Scanner** | 5m candlestick bars, Opening Range, VWAP, Session Windows | `OHLCVBar(timeframe='5m')`, `TechnicalFeature` | `open`, `high`, `low`, `close`, `volume`, `timestamp` | 0 bars (Properly reports insufficient bars) | Live 5m streaming feed (Kite Connect / TrueData) |
| **AI Research** | Multi-tool evidence extraction, 3-statement financials, Technicals | `MarketResearchService`, `IncomeStatement`, `BalanceSheetStatement`, `NewsItem` | Audited financial statements, ratios, technical features | Fully functional for seeded stocks | Population of financial statements for remaining 46 symbols |
| **Watchlist** | Live price snapshots, symbol registration | `Instrument`, `MarketSnapshot`, `localStorage` | `symbol`, `price`, `change_percent` | Fully operational | Active registry of all 50 NIFTY symbols |
| **Command Center Alerts**| Continuous price & condition evaluation against REST feeds | `Instrument`, `StockOpportunitySnapshot`, `StockRecommendation` | `price`, `status`, `final_opportunity_score` | Fully operational | 50 NIFTY universe active feed |
| **Outcome Tracking** | Post-trade lifecycle bar-by-bar evaluation, Net P&L, R-multiples | `RecommendationOutcome`, `OHLCVBar` | `actual_entry_price`, `actual_exit_price`, `net_pnl_percent`, `r_multiple` | Engine verified; 0 live outcomes | Daily bar progression for active recommendations |
| **Backtesting Lab** | Multi-year historical OHLCV, Universe definition | `BacktestRun`, `Universe`, `OHLCVBar` | `OHLCVBar` (2–5 years of historical daily bars) | 4 completed runs | 2–5 years historical daily OHLCV for all 50 symbols |

---

## 4. NIFTY 50 Population Plan

### A. Universe Registry & Symbol Normalization
1. **Instrument Table**: Populate 50 rows in `Instrument` with `exchange='NSE'`, `instrument_type='EQUITY'`, `currency='INR'`, `is_active=True`.
2. **Company Table**: Populate 50 rows in `Company` with exact NSE short names, official company names, industry sectors (Energy, IT, Financial Services, Auto, FMCG, Pharma, Metals, etc.), and ISIN codes.
3. **Universe Table**: Create `Universe(name='NIFTY50', description='NIFTY 50 Index Universe', is_active=True)`.
4. **UniverseMembership Table**: Link all 50 `Instrument` records to `Universe('NIFTY50')` with `is_active=True`.

---

## 5. Daily Market Data Provider Assessment (yfinance)

### A. Format Mapping to Existing `OHLCVBar` Model
- `yfinance` returns historical daily data in pandas dataframe / JSON structure.
- **Mapping**:
  - `Date` / `Datetime` -> `timestamp` (normalized to UTC midnight for 1d bars: `YYYY-MM-DD 00:00:00+00:00`).
  - `Open` -> `Decimal(open)`
  - `High` -> `Decimal(high)`
  - `Low` -> `Decimal(low)`
  - `Close` -> `Decimal(close)`
  - `Volume` -> `int(volume)`
  - `source` -> `"yfinance"`
  - `timeframe` -> `"1d"`
- **Corporate Actions**: `yfinance` automatically handles split adjustments and dividend tracking via `.actions`.

### B. Provider Risk Assessment
- **Development & Internal Validation**: **LOW RISK / HIGH VALUE**. Ideal for seeding 2–5 years of clean daily OHLCV for 50 stocks with zero API subscription cost.
- **Commercial Production**: **MEDIUM RISK**. Potential rate-limiting or Yahoo API endpoint format shifts. For commercial scale, secondary failover to official NSE/BSE EOD bhavcopy parser or dedicated vendor API (TrueData/Kite) is recommended.

---

## 6. Live / Intraday Data Provider Assessment (Kite Connect)

### A. Expectations of Existing Intraday Architecture (`IntradayMarketDataService`)
- Timeframe: `5m` bars (`timeframe='5m'`).
- Expected fields: `timestamp` (IST session bar start in UTC), `open`, `high`, `low`, `close`, `volume`.
- Bar requirements: Minimum 100 5m bars (~4 trading sessions) for indicator warmup (Opening Range, 20-period EMA, VWAP, ATR).

### B. Kite Connect Ingestion Mapping
- **Kite Historical API**: `GET /instruments/historical/:instrument_token/5minute` returns `[[timestamp, open, high, low, close, volume], ...]`.
- **Transformation Pipeline**:
  ```
  Kite 5m Array 
  → Python dict 
  → timezone-aware UTC datetime 
  → OHLCVBar.objects.bulk_create(..., ignore_conflicts=True)
  → IntradaySignalEngine
  → StockRecommendation(horizon='INTRADAY')
  ```

---

## 7. Fundamentals Source Assessment

### A. FundamentalDataService Requirements
- Financial statements required:
  1. **IncomeStatement**: Annual and Quarterly (Revenue, Expenses, EBITDA, EBIT, PBT, Tax, PAT, EPS).
  2. **BalanceSheetStatement**: Annual (Equity Capital, Reserves, Borrowings, Total Liabilities, Fixed Assets, Investments, Total Assets).
  3. **CashFlowStatement**: Annual (Operating Cash Flow, Investing Cash Flow, Financing Cash Flow, Free Cash Flow).
  4. **DerivedFundamentalMetric**: Computed ratios (ROE, ROCE, Debt/Equity, Operating Margin, Asset Turnover).

### B. Source Viability for NIFTY 50
- **Primary Source (Structured XBRL & Filings)**: Official NSE corporate filings / XBRL repository or financial aggregator API.
- **Development Reference Source**: Screener.in consolidated financial HTML scraper (`ScreenerFundamentalProvider` in `market/providers/screener.py`), already mapped to `RawFundamentalData` for complete audit provenance.

---

## 8. News & Corporate Disclosures Assessment

### A. News & Disclosure Models
- `NewsItem`: Headline, summary, source, URL, published_at (PIT anchor), event_type (earnings, macro, contract, management), content_hash.
- `CorporateDisclosure`: Official exchange announcement, category (board meeting, dividend, quarterly result), announcement_id, published_at, details.

### B. Sourcing Strategy for NIFTY 50
- **Primary Evidence**: Official NSE Corporate Announcements RSS / API (`https://www.nseindia.com/api/corporate-announcements`).
- **Secondary News**: Yahoo Finance RSS feeds (`YahooRSSNewsProvider` in `market/providers/news_provider.py`), already implemented with deduplication hashing (`content_hash = SHA256(headline + published_at)`).
- **Discovery Fallback**: Search / RSS aggregator.

---

## 9. Company Reports & Filings (AI Research Pipeline)

### A. Document Ingestion Flow
```
Company IR / NSE Announcement (PDF / Web Filing)
  ↓
Text Extraction & Chunking (Section-level indexing)
  ↓
Evidence Extraction Tool (e.g. GetCompanyNewsTool / GetCompanyEventsTool)
  ↓
MarketResearchAgent (Synthesizes thesis, risks, contradictions)
  ↓
Evidence Drawer in UI (Displays verified timestamp & source document)
```

---

## 10. Data Provider Architecture & Seam Evaluation

### A. Existing Abstraction in `market/providers/base.py`
The platform already defines standard Python `Protocol` interfaces:
```python
class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> dict: ...
    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", start_date: datetime = None, end_date: datetime = None) -> dict: ...
```
- Adding a new vendor (e.g. `KiteMarketProvider` or `TrueDataMarketProvider`) requires **zero changes** to `TechnicalFeatureEngine`, `OpportunityDiscoveryService`, `RecommendationService`, or `StockResearchAgentService`.
- Providers only return raw dicts; normalizers convert them to standard domain models.

---

## 11. Data Freshness & Staleness Policy Matrix

| Data Family | Primary Source | Production Refresh Frequency | Acceptable Staleness Threshold | Timestamp Semantics | Historical Retention |
|---|---|---|---|---|---|
| **Real-Time Quotes** | Kite / Yahoo Chart | Every 30s during market hours | > 2 minutes = STALE | Quote arrival timestamp (UTC) | Rolling 30 days |
| **Intraday 5m Bars** | Kite / TrueData | Every 5 minutes (09:15–15:30 IST)| > 15 minutes = STALE | Bar open UTC timestamp | Rolling 60 days |
| **Daily OHLCV Bars** | yfinance / NSE Bhavcopy | Daily at 16:30 IST (EOD) | > 24 hours = STALE | Bar trading date (00:00 UTC) | 10+ Years (Permanent) |
| **Technical Indicators**| Internal Feature Engine | Daily EOD / 5m Intraday | Recomputed per new bar | Source bar open timestamp | Matches bar retention |
| **Financial Statements**| NSE XBRL / Screener | Quarterly upon earnings release| > 100 days without update | `filing_date` (PIT anchor) | 10+ Years (Permanent) |
| **Corporate Disclosures**| NSE Announcements RSS | Hourly | > 4 hours = STALE | `published_at` (Exchange stamp)| Permanent |
| **Market News** | Yahoo RSS / Press Feeds | Hourly | > 4 hours = STALE | `published_at` (Article stamp) | 1 Year |

---

## 12. Point-In-Time (PIT) Safety Matrix

| Ingestion Event | Data Timestamp | Availability / Ingestion Timestamp | PIT Rule Enforced |
|---|---|---|---|
| **Quarterly P&L Filing** | Period End: `2025-12-31` | Filing Date: `2026-02-10` | Fundamental indicators (ROE, PE, PAT growth) prior to `2026-02-10` MUST use Q2 (previous) filing. Never backfill prior to filing date. |
| **Daily OHLCV Bar** | Bar Date: `2026-09-01` | Ingested: `2026-09-01 16:30:00` | Backtest on `2026-09-01` cannot access `close` price until market session end. |
| **Corporate Event (Dividend)**| Ex-Date: `2026-08-15` | Announced: `2026-07-20` | Signal engine only knows dividend event on or after `2026-07-20`. |

---

## 13. Minimum Viable NIFTY 50 Real Dataset

### A. MUST HAVE (Required for Full System Operation)
1. **50 NIFTY Instruments & Companies** with industry sectors and ISIN codes.
2. **2 Years of Daily OHLCV Bars** (Jan 2024 to Present) for all 50 stocks + `^NSEI` (NIFTY 50 index) + `^NSEBANK` (NIFTY Bank index).
3. **Calculated Technical Features** (SMA-20/50/200, RSI-14, MACD, ATR-14, Bollinger Bands) for all 50 stocks over the 2-year window.
4. **3 Years of Financial Statements** (Income Statement, Balance Sheet, Cash Flow) for all 50 stocks.
5. **Market Context Snapshots** (Daily macro regime, advance/decline breadth, sector momentum tiers).

### B. SHOULD HAVE (Recommended for Enhanced Research & Intraday)
1. **60 Days of 5m Intraday OHLCV Bars** for all 50 stocks.
2. **Recent 90 Days of Corporate Disclosures & News Items** for all 50 stocks.
3. **Active Daily Opportunity & Recommendation Generation** scheduled EOD.

### C. NICE TO HAVE (Future Expansion)
1. 10 years of historical daily bars for deep multi-cycle backtesting.
2. Full text PDF indexing of earnings call transcripts.

---

## 14. Exact Step-by-Step Implementation Sequence

```
STEP 1: Populate NIFTY 50 Universe Registry
  └── Script creates 50 Company + 50 Instrument + 1 Universe + 50 UniverseMembership records.

STEP 2: Ingest 2 Years Historical Daily OHLCV
  └── YFinanceProvider fetches 2024–2026 1d bars for 50 stocks + 2 benchmark indices.

STEP 3: Run Feature Engine & Market Context Generator
  └── TechnicalFeatureEngine computes all indicators; MarketContextService creates initial regime snapshots.

STEP 4: Ingest 3-Year Audited Financial Statements
  └── Ingests balance sheets, income statements, cash flows, and derived ratios for 50 companies.

STEP 5: Execute Initial Opportunity & Recommendation Scans
  └── OpportunityDiscoveryService & RecommendationService generate baseline ranked setups.

STEP 6: Ingest Corporate News & Announcements
  └── YahooRSSNewsProvider & NSE disclosures ingest recent news with deduplication hashes.

STEP 7: (Optional) Connect Intraday 5m Backfill & Live Stream
  └── Populates rolling 5m bars during active market hours.
```

---

## 15. Invariant Architecture Boundaries (What Must NOT Change)
1. **Zero Database Schema Migrations Required**: All models in `market/models.py` already accommodate 100% of required fields.
2. **Zero Analytical Algorithm Rewrites**: `SignalEngine`, `OpportunityDiscoveryService`, `TechnicalFeatureEngine`, `IntradaySignalEngine`, and `OutcomeEngine` remain identical.
3. **Zero Frontend API Contract Alterations**: All 29 REST endpoints in `market/urls.py` and `frontend/src/lib/api/types.ts` remain 100% stable.
4. **Strict Calculation Ownership**: All financial and technical metrics remain exclusively calculated on the backend.
5. **Zero Client-Side Calculation Violation**: Frontend remains strictly a presentation and interaction layer.
