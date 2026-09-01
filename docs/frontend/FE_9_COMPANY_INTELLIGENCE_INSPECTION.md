# FE-9 Company Fundamentals & Document Intelligence — Technical Inspection Report

## Executive Summary

This document provides a comprehensive, read-only technical inspection of the backend and frontend systems for **FE-9: Company Fundamentals & Document Intelligence Workspace**.

The inspection establishes that while structured financial statements (`IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`), derived fundamental metrics, and exchange regulatory disclosures (`CorporateDisclosure`) are **IMPLEMENTED** in the relational database, unstructured document intelligence (PDF Annual Reports, Investor Presentations, Earnings Transcripts, Vector Search, and Document RAG) is **MISSING** from the codebase.

---

## 1. Company & Fundamental API Audit

| Endpoint | Method | Status | Serializer | Models / Tables | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /api/v1/stocks/{symbol}/` | `GET` | **IMPLEMENTED** | `StockDetailAPIView` / `InstrumentSerializer` | `Instrument`, `Company`, `MarketSnapshot`, `StockRecommendation`, `StockOpportunitySnapshot` | Company identity, profile, sector, industry, active signal, and snapshot quote. |
| `GET /api/v1/stocks/{symbol}/fundamentals/` | `GET` | **IMPLEMENTED** | `StockFundamentalsAPIView` / `IncomeStatementSerializer`, `BalanceSheetStatementSerializer`, `CashFlowStatementSerializer`, `DerivedFundamentalMetricSerializer` | `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`, `DerivedFundamentalMetric` | Multi-period historical statements (annual & quarterly) and derived ratios. |
| `GET /api/v1/stocks/{symbol}/events/` | `GET` | **IMPLEMENTED** | `StockDisclosuresAPIView` / `CorporateDisclosureSerializer` | `CorporateDisclosure` | Paginated exchange announcements, filings metadata, categories, and exchange URLs. |
| `GET /api/v1/stocks/{symbol}/news/` | `GET` | **IMPLEMENTED** | `StockNewsAPIView` / `NewsItemSerializer` | `NewsItem` | Paginated corporate news headlines with summaries and sentiment categories. |
| `GET /api/v1/stocks/search/` | `GET` | **IMPLEMENTED** | `StockSearchAPIView` / `InstrumentSearchSerializer` | `Instrument`, `Company` | Symbol and company name autocomplete search. |
| `GET /api/v1/stocks/{symbol}/documents/` | `GET` | **MISSING** | — | — | PDF document list / annual report repository endpoint. |
| `GET /api/v1/stocks/{symbol}/earnings/estimates/` | `GET` | **MISSING** | — | — | Consensus estimates and earnings surprises endpoint. |
| `GET /api/v1/stocks/{symbol}/peers/` | `GET` | **MISSING** | — | — | Peer comparison and sector valuation benchmark endpoint. |

---

## 2. Company Identity & Relationships

In `market/models.py`:
- **`Company`**:
  - `id`: UUID (Primary Key)
  - `name`: CharField (e.g. "Reliance Industries Limited")
  - `legal_name`: CharField
  - `short_name`: CharField (e.g. "RELIANCE")
  - `isin`: CharField (12 chars, unique)
  - `sector`: CharField (e.g. "Energy")
  - `industry`: CharField (e.g. "Oil & Gas Refining")
  - `sub_industry`: CharField
  - `description`: TextField
  - `website`: URLField
- **Relationships**:
  - `Company (1) ── (N) Instrument` (e.g. `RELIANCE:NSE`, `RELIANCE:BSE`).
  - `Instrument` links to `MarketSnapshot`, `OHLCVBar`, `TechnicalFeature`, `StockOpportunitySnapshot`, `StockRecommendation`.
  - `Company` links directly to `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`, `DerivedFundamentalMetric`, `CorporateEvent`, `CorporateDisclosure`, `RawFundamentalData`.

---

## 3. Financial Statements Availability

### Income Statement (`IncomeStatement`)
- **Fields**: `fiscal_year`, `period_type` (`ANNUAL` | `QUARTERLY`), `period_string`, `period_start`, `period_end`, `filing_date`, `revenue`, `expenses`, `ebitda`, `ebit`, `depreciation`, `interest`, `pbt`, `tax`, `pat`, `eps`.
- **History**: Up to 10 historical annual periods and recent quarterly periods per company.
- **Source**: Ingested via Screener provider (`screener.in`) and normalized.

### Balance Sheet (`BalanceSheetStatement`)
- **Fields**: `fiscal_year`, `period_type`, `period_string`, `period_start`, `period_end`, `filing_date`, `equity_capital`, `reserves`, `borrowings`, `other_liabilities`, `total_liabilities`, `fixed_assets`, `cwip`, `investments`, `other_assets`, `total_assets`.
- **History**: Multi-year annual balance sheets.

### Cash Flow Statement (`CashFlowStatement`)
- **Fields**: `fiscal_year`, `period_type`, `period_string`, `period_start`, `period_end`, `filing_date`, `operating_cash_flow` (CFO), `investing_cash_flow` (CFI), `financing_cash_flow` (CFF), `free_cash_flow` (FCF).

---

## 4. Fundamental Ratios & Growth Metrics

Computed deterministically on the backend via `FundamentalMetricService` (`market/services/fundamental_service.py`):
- **Growth Metrics**:
  - `revenue_growth_yoy`: YoY % change in revenue.
  - `ebitda_growth_yoy`: YoY % change in EBITDA.
  - `pat_growth_yoy`: YoY % change in Profit After Tax.
  - `eps_growth_yoy`: YoY % change in EPS.
- **Profitability & Margins**:
  - `ebitda_margin`: `ebitda / revenue`
  - `ebit_margin`: `ebit / revenue`
  - `net_margin`: `pat / revenue`
  - `fcf_margin`: `free_cash_flow / revenue`
- **Return & Leverage**:
  - `return_on_equity` (ROE): `pat / (equity_capital + reserves)`
  - `return_on_capital_employed` (ROCE): `ebit / (equity + borrowings)`
  - `debt_equity`: `borrowings / equity`
  - `cfo_pat`: `operating_cash_flow / pat`
- **Valuation**:
  - `pe_ratio`: `price / eps`
- **Missing Metrics in Backend**: P/B (book value), EV/EBITDA, EV/Sales, PEG Ratio, Dividend Yield (not stored as standalone columns in `DerivedFundamentalMetric`).

---

## 5. Point-in-Time (PIT) Safety & Availability Dates

- **`period_end` vs `filing_date`**:
  - `IncomeStatement`, `BalanceSheetStatement`, and `CashFlowStatement` include both `period_end` (reporting period end date, e.g. `2024-03-31`) and `filing_date` (public release date).
  - *Limitation*: For historical annual statements scraped from third-party sources, `filing_date` is frequently null or inferred, meaning backtesters and researchers must use caution when avoiding lookahead bias between period end and public release.
- **Corporate Disclosures**:
  - `CorporateDisclosure` contains exact `published_at` and `ingested_at` timestamps, making exchange announcements strictly PIT-safe.

---

## 6. Corporate Events, Filings & Exchange Disclosures

- **`CorporateEvent`**:
  - Types: `SPLIT`, `BONUS`, `DIVIDEND`, `MERGER`.
  - Fields: `announcement_date`, `ex_date`, `details` (JSON with split/bonus ratios, dividend per share).
- **`CorporateDisclosure`**:
  - Fields: `headline`, `category`, `source` (NSE/BSE), `announcement_id`, `url`, `published_at`, `ingested_at`, `details` (JSON).
  - Exposed via: `GET /api/v1/stocks/{symbol}/events/`.

---

## 7. Document Intelligence, Annual Reports & RAG Capability Status

| Dimension | Implementation Status | Finding |
| :--- | :--- | :--- |
| **PDF Document Storage** | **MISSING** | No S3/GCS bucket or file repository configured for PDFs. |
| **Annual Report Ingestion** | **MISSING** | PDF annual reports are not automatically downloaded or cataloged. |
| **Investor Presentations** | **MISSING** | No presentation file storage or ingestion. |
| **Earnings Transcripts** | **MISSING** | No audio or text transcript ingestion. |
| **Document Parsing & OCR** | **MISSING** | No PyPDF, pdfplumber, Tesseract, or layout parsing libraries installed. |
| **Vector Database & Embeddings** | **MISSING** | No pgvector, Chroma, FAISS, Pinecone, or text chunking pipeline in repository. |
| **Document RAG in Module 5** | **MISSING** | LLM uses deterministic SQL tools (`market_tool.py`), not unstructured document RAG. |

---

## 8. Integration Touchpoints with Other Workspaces

- **FE-5 Stock Detail (`/stocks/:symbol`)**:
  - FE-5 is the single-stock terminal (charting, indicators, high-level summary, news).
  - FE-9 should link from FE-5 via "Deep Fundamental & Filing Investigation" action.
- **FE-8 Research (`/research`)**:
  - FE-9 should provide a "Launch AI Research Memos" action linking to `/research?symbol={symbol}`.
- **FE-6 Recommendations (`/recommendations`)**:
  - FE-9 can display active trade setup badges if the company has active recommendations.
- **FE-7 Backtesting (`/backtests`)**:
  - Backtest engine does not directly parse annual reports; it relies on deterministic market features and audited ratios.

---

## 9. Recommended FE-9 Workspace Architecture

```
---------------------------------------------------------------------------------------------------
FE-9: COMPANY FUNDAMENTALS & CORPORATE INTELLIGENCE WORKSPACE (/companies/:symbol or /fundamentals)
---------------------------------------------------------------------------------------------------

1. COMPANY IDENTITY & BUSINESS PROFILE BANNER
   - Company Legal Name, NSE/BSE Ticker, ISIN, Sector, Industry, Website Link
   - Business Description & Operational Scope

2. FINANCIAL HEALTH & VALUATION METRIC CARDS
   - P/E Ratio, Return on Equity (ROE), ROCE, Debt/Equity, Operating Margin, Rev Growth YoY

3. FINANCIAL STATEMENT EXPLORER (Annual & Quarterly)
   - Tab 1: Income Statement (Revenue, EBITDA, EBIT, PBT, PAT, EPS)
   - Tab 2: Balance Sheet (Equity, Reserves, Borrowings, Assets, Liabilities)
   - Tab 3: Cash Flow (Operating Cash Flow, Free Cash Flow, Investing, Financing)
   - Toggle: Table View vs Interactive Multi-Period Trend Bar/Line Charts

4. CORPORATE ANNOUNCEMENTS & EXCHANGE FILINGS
   - Paginated list of regulatory disclosures from NSE/BSE
   - Filter by Category (Board Meetings, Financial Results, Dividends, General Announcements)
   - Direct link to official exchange filing URL

5. CORPORATE ACTIONS & CAPITAL HISTORY
   - Historical Dividend Payouts, Stock Splits, Bonus Issues, Mergers

6. AI RESEARCH HANDOFF
   - "Synthesize Company Thesis in AI Laboratory" → links to /research?symbol=...
---------------------------------------------------------------------------------------------------
```

---

## 10. Backend Gap Classification for FE-9

- **P0 (Blocks FE-9 MVP)**: **NONE**. Existing endpoints (`GET /api/v1/stocks/{symbol}/`, `GET /api/v1/stocks/{symbol}/fundamentals/`, `GET /api/v1/stocks/{symbol}/events/`) provide complete structured data for all financial statements, ratios, and regulatory filings.
- **P1 (Important Enhancements)**:
  - Add peer comparison endpoint (`GET /api/v1/stocks/{symbol}/peers/`) to compare valuation ratios against sector medians.
  - Populate missing P/B, EV/EBITDA, and Dividend Yield in `DerivedFundamentalMetric`.
- **P2 (Secondary Enhancements)**:
  - Add quarterly financial statements toggle support in `StockFundamentalsAPIView` (currently defaults to annual statements).
- **FUTURE**:
  - PDF Annual Report ingestion, parsing, chunking, and Vector Database RAG.
  - Earnings call audio/text transcript indexing and search.
