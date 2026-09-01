# FE-9 Company Fundamentals & Document Intelligence — Technical Inspection Handoff

## 1. Executive Status

- **Status**: **INSPECTION COMPLETE (READ-ONLY)**
- **Date**: September 1, 2026
- **Workspace Route**: `/fundamentals` or `/stocks/:symbol/fundamentals`
- **Backend P0 Blockers**: **ZERO (0 P0 Blockers)** for structured company fundamentals and exchange filings.

---

## 2. Implemented vs Missing Backend Capabilities

| Domain | Status | Technical Details |
| :--- | :--- | :--- |
| **Company Identity & Profile** | **IMPLEMENTED** | `GET /api/v1/stocks/{symbol}/` returns `name`, `legal_name`, `isin`, `sector`, `industry`, `description`, `website`. |
| **Income Statements** | **IMPLEMENTED** | `GET /api/v1/stocks/{symbol}/fundamentals/` returns 10-year annual history (`revenue`, `ebitda`, `ebit`, `pbt`, `tax`, `pat`, `eps`). |
| **Balance Sheets** | **IMPLEMENTED** | Returns 10-year history (`equity_capital`, `reserves`, `borrowings`, `total_assets`, `total_liabilities`, `fixed_assets`, `investments`). |
| **Cash Flows** | **IMPLEMENTED** | Returns 10-year history (`operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `free_cash_flow`). |
| **Derived Ratios** | **IMPLEMENTED** | Computed on backend: `return_on_equity`, `return_on_capital_employed`, `debt_equity`, `net_margin`, `ebitda_margin`, `revenue_growth_yoy`, `pe_ratio`, `cfo_pat`. |
| **Exchange Disclosures / Filings** | **IMPLEMENTED** | `GET /api/v1/stocks/{symbol}/events/` returns paginated regulatory filings from NSE/BSE with categories and official exchange URLs. |
| **Corporate Actions** | **IMPLEMENTED** | `CorporateEvent` model stores historical splits, bonuses, dividends, and mergers with announcement and ex-dates. |
| **PDF Annual Reports** | **MISSING** | No PDF storage, download, or parsing infrastructure exists in codebase. |
| **Vector Search / Document RAG** | **MISSING** | No vector database (pgvector, Chroma), text chunking, or document embedding pipeline exists. |
| **Earnings Call Transcripts** | **MISSING** | No audio or transcript ingestion exists in codebase. |
| **Consensus Estimates / Guidance** | **MISSING** | No analyst consensus estimate or surprise database models exist. |

---

## 3. Point-in-Time (PIT) & Lookahead Safety

- **Structured Statements**: `IncomeStatement`, `BalanceSheetStatement`, and `CashFlowStatement` store `period_end` and `filing_date`. When `filing_date` is absent, statements must be labeled with reporting period date to avoid lookahead assumptions.
- **Corporate Disclosures**: `CorporateDisclosure` stores verified `published_at` timestamps.

---

## 4. Relationship with Existing Workspaces

- **FE-5 Stock Detail (`/stocks/:symbol`)**: FE-5 focuses on price action, charting terminal, technical indicators, and quick summary. FE-9 will provide the dedicated deep-dive into multi-year financial statements, margin progression, balance sheet health, and exchange disclosures.
- **FE-8 Research (`/research`)**: FE-9 should provide an action button to launch deep AI research in FE-8 pre-populated with the company symbol (`/research?symbol={symbol}`).
- **FE-6 Recommendations (`/recommendations`)**: Displays active recommendation badges if a setup exists.
- **FE-7 Backtesting (`/backtests`)**: Backtests consume quantitative features and derived fundamental ratios.

---

## 5. Recommended FE-9 Workspace Layout

```
---------------------------------------------------------------------------------------------------
FE-9: COMPANY FUNDAMENTALS & CORPORATE INTELLIGENCE WORKSPACE
---------------------------------------------------------------------------------------------------

1. COMPANY IDENTITY & BUSINESS PROFILE
   - Legal Name, NSE/BSE Ticker, ISIN, Sector, Industry, Website Link
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

## 6. Artifact Locations

- **Full Inspection Report**: [docs/frontend/FE_9_COMPANY_INTELLIGENCE_INSPECTION.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/frontend/FE_9_COMPANY_INTELLIGENCE_INSPECTION.md)
- **Handoff Document**: [FE_9_INSPECTION_HANDOFF.md](file:///Users/shivamsingh/personal/nomad-analyst/FE_9_INSPECTION_HANDOFF.md)
