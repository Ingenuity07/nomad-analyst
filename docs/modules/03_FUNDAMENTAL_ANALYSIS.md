# Module 3 — Fundamental Analysis Foundation

This document details the architectural decisions, database models, formulas, and ingestion pipelines implemented for the **Fundamental Analysis Foundation** module (Module 3).

---

## 1. Selected Data Sources
*   **Provider**: Screener.in Consolidated Company Financials.
*   **URL Format**: `https://www.screener.in/company/{symbol}/consolidated/`
*   **Data Scraped**: 
    *   Quarterly results tables.
    *   Annual Profit & Loss tables (Income Statement).
    *   Annual Balance Sheet tables.
    *   Annual Cash Flow tables.

---

## 2. Provider Architecture
All financial scrapes are hidden behind a clean provider class:
*   `ScreenerFundamentalProvider` inside [`market/providers/screener.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/providers/screener.py).
*   Extracts HTML tables using BeautifulSoup, parses periods and values, and returns a raw structured dictionary of rows and columns.

---

## 3. Source Provenance
To audit data quality and support future AI research/verification, raw payloads are saved first before normalization:
*   `RawFundamentalData` logs symbol, source url, retrieved timestamp, reporting type, and the full raw unmodified JSON payload.
*   The raw payload is marked as `RAW` upon creation and updated to `NORMALIZED` once the ingestion transaction successfully commits.

---

## 4. Financial Period Semantics
*   **ANNUAL**: Extracted from the Profit & Loss, Balance Sheet, and Cash Flow tables (typically ending in March for Indian listed companies, e.g. "Mar 2025").
*   **QUARTERLY**: Extracted from the Quarters table (e.g. "Dec 2024", "Mar 2025").
*   **Trailing Twelve Months (TTM)**: Saved as a distinct string marker in the database to prevent mixing with standard annual bounds.

---

## 5. Normalized Statements Schema

### IncomeStatement
*   `revenue` (Sales)
*   `expenses`
*   `ebitda` (Operating Profit)
*   `ebit` (derived: operating profit - depreciation)
*   `depreciation`
*   `interest`
*   `pbt` (Profit Before Tax)
*   `tax` (derived: pbt - net profit)
*   `pat` (Net Profit)
*   `eps` (EPS in Rs)

### BalanceSheetStatement
*   `equity_capital`
*   `reserves`
*   `borrowings`
*   `other_liabilities`
*   `total_liabilities`
*   `fixed_assets`
*   `cwip`
*   `investments`
*   `other_assets`
*   `total_assets`

### CashFlowStatement
*   `operating_cash_flow`
*   `investing_cash_flow`
*   `financing_cash_flow`
*   `free_cash_flow`

---

## 6. Derived Metrics & Formulas
Deterministic indicators calculated by `FundamentalMetricService`:

*   **YoY Growth**:
    *   `revenue_growth_yoy` = $\frac{\text{revenue}_t - \text{revenue}_{t-1}}{\text{revenue}_{t-1}}$
    *   `ebitda_growth_yoy` = $\frac{\text{ebitda}_t - \text{ebitda}_{t-1}}{\text{ebitda}_{t-1}}$
    *   `pat_growth_yoy` = $\frac{\text{pat}_t - \text{pat}_{t-1}}{\text{pat}_{t-1}}$
    *   `eps_growth_yoy` = $\frac{\text{eps}_t - \text{eps}_{t-1}}{\text{eps}_{t-1}}$
*   **Margins**:
    *   `ebitda_margin` = $\frac{\text{ebitda}}{\text{revenue}}$
    *   `ebit_margin` = $\frac{\text{ebit}}{\text{revenue}}$
    *   `net_margin` = $\frac{\text{pat}}{\text{revenue}}$
*   **Returns**:
    *   `return_on_equity` (ROE) = $\frac{\text{pat}}{\text{equity\_capital} + \text{reserves}}$
    *   `return_on_capital_employed` (ROCE) = $\frac{\text{ebit}}{\text{equity} + \text{borrowings}}$
*   **Leverage**:
    *   `debt_equity` = $\frac{\text{borrowings}}{\text{equity}}$
*   **Cash flow**:
    *   `cfo_pat` = $\frac{\text{operating\_cash\_flow}}{\text{pat}}$
    *   `fcf_margin` = $\frac{\text{free\_cash\_flow}}{\text{revenue}}$
*   **Valuation**:
    *   `pe_ratio` = $\frac{\text{latest\_market\_price}}{\text{eps}}$ (Calculated dynamically using the latest close from `MarketSnapshot` model).

---

## 7. Versioning & Look-Ahead Prevention
*   **Idempotency**: Unique constraint on `(company, period_type, period_string)` ensures that repeated scrapes update rather than duplicate records.
*   **Look-Ahead Safety**: Financial statements are only associated with their official `period_string` and `fiscal_year`. Ratios are calculated chronologically.

---

## 8. Data Quality Rules
*   **Unknown ≠ Zero**: Missing fields in raw html pages are persisted as `None/Null` in Django rather than zero to avoid corrupting ratios.

---

## 9. Limitations & Future Extensions
*   **Rate Limits**: Scrapes are executed synchronously; future expansions should add caching or queueing.
*   **Future Extensions**: Adding quarterly segment breakdowns, shareholding patterns (promoter pledges), and split/bonus event adjustments.
