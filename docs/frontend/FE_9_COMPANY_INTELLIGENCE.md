# FE-9 Company Fundamentals & Corporate Intelligence Documentation

## Overview

The **Company Fundamentals & Corporate Intelligence Workspace** (`/fundamentals`) provides a dedicated institutional workspace for investigating Indian corporate financial statements, multi-year margin trends, capital structure health, backend-computed valuation ratios, and exchange regulatory disclosures.

---

## Workspace Architecture & Routing

- **Primary Route**: `/fundamentals`
- **Optional Context Route**: `/fundamentals?symbol=RELIANCE`
- **Complementary Roles**:
  - `FE-5` (`/stocks/:symbol`): Technical charting terminal, price action, intraday signals.
  - `FE-9` (`/fundamentals`): Multi-year statement explorer, balance sheet health, regulatory filings.
  - `FE-8` (`/research`): Multi-tool synthesized AI intelligence dossiers.
  - `FE-6` (`/recommendations`): Actionable trade setups and outcome tracking.
  - `FE-7` (`/backtests`): Historical strategy simulations.

---

## Core Components & Layout

```
---------------------------------------------------------------------------------------------------
FE-9: COMPANY FUNDAMENTALS & CORPORATE INTELLIGENCE WORKSPACE (/fundamentals)
---------------------------------------------------------------------------------------------------

1. COMPANY SELECTOR (CompanySearchSelector)
   - Popular ticker presets (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, etc.) + Symbol search input.

2. COMPANY IDENTITY & BUSINESS PROFILE (CompanyProfileHeader)
   - Company Name, Legal Name, Canonical Ticker, ISIN, Sector, Industry, Official Website Link.
   - Latest Close Price & Day Change Quote.
   - Direct Handoffs: "📈 Stock Terminal" (/stocks/:symbol) & "🤖 AI Research Memos" (/research?symbol=...).
   - Collapsible Business Overview description.

3. FUNDAMENTAL HEALTH & PROFITABILITY CARDS (FundamentalSnapshotCards)
   - P/E Ratio, Return on Equity (ROE), ROCE, Debt/Equity, EBITDA Margin, Net Margin, Revenue Growth YoY, PAT Growth YoY, CFO/PAT.

4. FINANCIAL STATEMENT EXPLORER (FinancialStatementExplorer)
   - Tabs: Income Statement | Balance Sheet | Cash Flow Statement.
   - View Mode Switcher: "📋 Tabular Statement View" vs "📈 Performance Trends".
   - Tables display full normalized statement fields with fiscal periods and PIT filing dates.
   - Performance Trends visualizes multi-year trajectories (Revenue, EBITDA, PAT, EPS, Operating CF, Free CF).

5. REGULATORY DISCLOSURES & CORPORATE ACTIONS (ExchangeDisclosuresCard)
   - Paginated regulatory announcements from NSE/BSE.
   - Category filtering (Board Meetings, Financial Results, Dividends, General).
   - "📄 View Official Exchange Filing ↗" external links.

6. MATERIAL CORPORATE NEWS (RecentNewsCard)
   - Recent corporate news headlines with handoff to full terminal news feed.
---------------------------------------------------------------------------------------------------
```

---

## API Endpoints Consumed

| Endpoint | Method | Response Payload | Description |
| :--- | :--- | :--- | :--- |
| `GET /api/v1/stocks/{symbol}/` | `GET` | `StockDetailResponse` | Company profile, legal name, ISIN, sector, industry, description, website, and snapshot quote. |
| `GET /api/v1/stocks/{symbol}/fundamentals/` | `GET` | `StockFundamentalsResponse` | 10-year historical statements (`income_statement`, `balance_sheet`, `cash_flow`) and derived ratios. |
| `GET /api/v1/stocks/{symbol}/events/` | `GET` | `PaginatedResponse<CorporateDisclosure>` | Paginated regulatory announcements, board meetings, dividend notices, and exchange URLs. |
| `GET /api/v1/stocks/{symbol}/news/` | `GET` | `PaginatedResponse<NewsItem>` | Paginated corporate news headlines with summaries and sentiment categories. |
| `GET /api/v1/stocks/search/` | `GET` | `PaginatedResponse<InstrumentSearchResult>` | Search autocomplete by symbol and company name. |

---

## Point-in-Time (PIT) & Lookahead Handling

- **Regulatory Disclosures**: Carry verified `published_at` timestamps making announcements strictly PIT-safe.
- **Financial Statements**: Display `period_end` and `filing_date`. When third-party scraped balance sheets lack an exact public release timestamp, the table explicitly denotes `Historical (PIT Unavail)` to prevent lookahead assumptions in backtesting and historical research.

---

## Scope Boundaries & Future Capabilities

### IMPLEMENTED:
- Company identity, profile, sector, ISIN, website, and description.
- Multi-year normalized Income, Balance Sheet, and Cash Flow statement explorer.
- Tabular grid and interactive multi-period trend visualizations.
- Backend-computed fundamental ratios (ROE, ROCE, Debt/Equity, margins, growth).
- Paginated exchange regulatory disclosures with official exchange links.
- Cross-workspace handoffs to FE-5 (Stock Terminal), FE-8 (AI Research), FE-6 (Recommendations).

### NOT IMPLEMENTED / FUTURE:
- PDF annual report ingestion and object storage.
- Vector database (pgvector/Chroma) and document chunking RAG.
- Earnings call audio/text transcript indexing and search.
- Consensus analyst estimates and earnings surprise tracking.
- Peer valuation comparison against sector medians.
