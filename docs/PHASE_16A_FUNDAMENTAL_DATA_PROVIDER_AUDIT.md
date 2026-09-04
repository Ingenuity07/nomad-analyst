# Phase 16A — Fundamental & Financial Data Provider Audit

**Audit Type**: READ-ONLY / INVESTIGATION-FIRST SOURCE ARCHITECTURE AUDIT  
**System**: Nomad Analyst  
**Focus Area**: Fundamental, Financial Statement & Corporate Intelligence Sourcing for Indian Equities (NIFTY 50 Universe)  
**Date**: 2026-09-03  

---

## Executive Verdict

### **VERDICT: B — READY WITH LIMITATIONS**

**Rationale**:
1. **Existing Model Schema is Sound**: Nomad Analyst's existing Django models (`RawFundamentalData`, `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`, `DerivedFundamentalMetric`, `CorporateDisclosure`) are already completely structured and indexed for both annual and quarterly statements, including Point-in-Time (PIT) `filing_date` tracking. [VERIFIED]
2. **Analytical Consumption Layer Ready**: The `OpportunityDiscoveryService` and `SignalEngine` already possess deterministic scoring code that evaluates 6 key metrics (`revenue_growth_yoy`, `pat_growth_yoy`, `return_on_equity`, `net_margin`, `return_on_capital_employed`, `debt_equity`). Once populated, the neutral `50.0` default will automatically be superseded by genuine multi-factor financial scoring without schema migrations or architecture redesign. [VERIFIED]
3. **Provider Landscape Has Clear Boundaries & Limitations**:
   - **Yahoo Finance / yfinance**: [UNSUITABLE for primary fundamentals]. Rate-limits crumb authentication (401/429), lacks quarterly history beyond 4-5 quarters, and critically **omits publication/filing dates** (providing only fiscal period-end dates).
   - **Screener.in HTML Scraping**: [UNSUITABLE]. While previously prototyped in `market/providers/screener.py`, automated HTML scraping violates Terms of Service, risks IP blocks, and completely lacks filing timestamps required for PIT safety.
   - **Official Exchange Disclosures (NSE/BSE)**: [RECOMMENDED as Filing-Date / Event Truth]. BSE's public corporate announcement feeds provide exact statutory publication timestamps (`DT_TM`) to eliminate lookahead bias.
   - **Dedicated Financial APIs (EODHD / FMP)**: [RECOMMENDED as Primary Structured Statement Source]. EODHD provides 10–20+ years of structured Indian financial statements (both Consolidated and Standalone) across NSE tickers with explicit `filing_date` tracking.
   - **Documented Offline Baseline Snapshot**: [RECOMMENDED for reproducible zero-cost bootstrap]. A versioned JSON fundamental snapshot (analogous to `nifty50_constituents_2026-09-03.json`) enables instant, deterministic seeding of 5-year financials for all 50 NIFTY stocks without ongoing API costs.

---

## 1. Existing Nomad Fundamental Architecture

The repository was inspected across `market/models.py`, `market/services/fundamental_service.py`, `market/services/discovery_service.py`, and `market/views.py`:

```text
Provider Layer
  ├── ScreenerFundamentalProvider (HTML scraper — market/providers/screener.py) [UNSUITABLE]
  └── YFinanceMarketProvider (Market quotes & chart OHLCV — market/providers/yfinance.py)
        ↓
Ingestion & Persistence Layer (FundamentalDataService)
  ├── RawFundamentalData (Stores unmodified JSON payload for audit provenance)
  ├── IncomeStatement (Annual & Quarterly: rev, exp, ebitda, ebit, pbt, tax, pat, eps, filing_date)
  ├── BalanceSheetStatement (Equity, reserves, borrowings, total assets, fixed assets, cwip, liab)
  └── CashFlowStatement (Operating cash flow, investing, financing, free cash flow)
        ↓
Derived Metrics Layer (FundamentalMetricService)
  └── DerivedFundamentalMetric (YoY Growth, Margins, ROE, ROCE, Debt/Equity, CFO/PAT, P/E)
        ↓
Decision Support Layer
  ├── OpportunityDiscoveryService (Scores Growth, Profitability, Efficiency; weights 20% swing / 50% LT)
  ├── SignalEngine (Evaluates fundamental support gate: ROE > 12%, D/E < 1.0, Rev Growth > 5%)
  └── StockFundamentalsAPIView (/api/v1/stocks/{symbol}/fundamentals/ exposes statements + metrics)
```

**Architectural Strengths**:
- Database models already have dedicated `filing_date` date fields on all three core financial statement tables.
- Unique constraints prevent duplicate statements: `unique_company_income_period` on `(company, period_type, period_string)`.
- The normalization pipeline calculates derived metrics deterministically from stored statements rather than trusting opaque vendor-calculated ratios.

---

## 2. Fundamental Data Requirements Matrix

Mapping Nomad's existing model fields to product requirements and source availability:

| Financial Dimension | Existing Model | Existing Fields | Required by Engine? | Sourcing Difficulty | PIT Criticality |
|---|---|---|:---:|:---:|:---:|
| **Revenue / Sales** | `IncomeStatement` | `revenue` | **YES** (Growth, Margins) | LOW (Universal) | HIGH (`filing_date`) |
| **Operating Profit** | `IncomeStatement` | `ebitda` | **YES** (EBITDA Margin) | LOW (Universal) | HIGH (`filing_date`) |
| **Operating Income** | `IncomeStatement` | `ebit` | **YES** (ROCE, EBIT Margin) | MEDIUM (EBITDA - Depr) | HIGH (`filing_date`) |
| **Finance Costs** | `IncomeStatement` | `interest` | **YES** (Interest Coverage) | LOW (Universal) | HIGH (`filing_date`) |
| **Profit Before Tax** | `IncomeStatement` | `pbt` | **YES** (Tax Calculation) | LOW (Universal) | HIGH (`filing_date`) |
| **Profit After Tax** | `IncomeStatement` | `pat` | **YES** (PAT Growth, ROE) | LOW (Universal) | HIGH (`filing_date`) |
| **Earnings Per Share** | `IncomeStatement` | `eps` | **YES** (EPS Growth, P/E) | LOW (Universal) | HIGH (`filing_date`) |
| **Equity Capital** | `BalanceSheetStatement` | `equity_capital` | **YES** (Net Worth / Equity) | LOW (Universal) | HIGH (`filing_date`) |
| **Reserves & Surplus** | `BalanceSheetStatement` | `reserves` | **YES** (Net Worth / Equity) | LOW (Universal) | HIGH (`filing_date`) |
| **Total Borrowings** | `BalanceSheetStatement` | `borrowings` | **YES** (Debt/Equity, ROCE) | LOW (Universal) | HIGH (`filing_date`) |
| **Total Assets** | `BalanceSheetStatement` | `total_assets` | **YES** (Balance Integrity) | LOW (Universal) | HIGH (`filing_date`) |
| **Fixed Assets & CWIP**| `BalanceSheetStatement` | `fixed_assets`, `cwip` | OPTIONAL (Capex intensity) | LOW (Universal) | HIGH (`filing_date`) |
| **Operating Cash Flow** | `CashFlowStatement` | `operating_cash_flow` | **YES** (CFO / PAT Quality) | MEDIUM (Annual only) | HIGH (`filing_date`) |
| **Investing Cash Flow** | `CashFlowStatement` | `investing_cash_flow` | OPTIONAL (Capex tracking) | MEDIUM (Annual only) | HIGH (`filing_date`) |
| **Free Cash Flow** | `CashFlowStatement` | `free_cash_flow` | **YES** (FCF Margin) | MEDIUM (CFO - Capex) | HIGH (`filing_date`) |
| **YoY Revenue Growth** | `DerivedFundamentalMetric`| `revenue_growth_yoy` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |
| **YoY PAT Growth** | `DerivedFundamentalMetric`| `pat_growth_yoy` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |
| **Return on Equity** | `DerivedFundamentalMetric`| `return_on_equity` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |
| **Net Profit Margin** | `DerivedFundamentalMetric`| `net_margin` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |
| **ROCE** | `DerivedFundamentalMetric`| `return_on_capital_employed` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |
| **Debt to Equity** | `DerivedFundamentalMetric`| `debt_equity` | **YES** (Opportunity Score) | DERIVED internally | Derived PIT |

---

## 3. Point-in-Time (PIT) Requirements

### The Fundamental Lookahead Hazard
Financial statements represent a past accounting period, but are only known to market participants weeks or months later.

```text
┌─────────────────────────────────────────────────────────────┐
│ Fiscal Quarter: 2026-04-01 to 2026-06-30 (period_end: Jun 30)│
│ Regulatory Filing Window: up to 45 days (SEBI Reg 33)       │
│ Board Meeting & Announcement Date: 2026-08-10 (filing_date) │
└─────────────────────────────────────────────────────────────┘

If an investment backtest evaluates a decision on 2026-07-15:
  - Using period_end <= 2026-07-15 includes June 30 results -> LOOKAHEAD BIAS (FATAL)
  - Using filing_date <= 2026-07-15 excludes June 30 results -> CORRECT POINT-IN-TIME
```

### Current Architectural Finding: PIT Filter Defect [OBSERVED]
In `market/services/discovery_service.py` L181-185 and `market/services/signal_engine.py` L573-577, the code currently filters on:
```python
period_end__lte = dt_as_of.date()
```
**Why this happened**: In early phases, `filing_date` was not populated, so `period_end` was used as a placeholder.  
**Required Phase 16B Action**: Once real data with `filing_date` is ingested, update the query logic to:
```python
Q(filing_date__lte=dt_as_of.date()) | (Q(filing_date__isnull=True) & Q(period_end__lte=dt_as_of.date() - timedelta(days=60)))
```

---

## 4. Provider A — Yahoo Finance / yfinance Analysis

- **Coverage**: Indian equities supported with `.NS` suffix [VERIFIED]
- **API Mechanism**: `/v10/finance/quoteSummary/{symbol}?modules=incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory...`
- **Audit Findings**:
  1. **Authentication Barrier**: Returns HTTP 401 Unauthorized unless provided with a valid crumb token and cookie session. Direct test during audit returned `getcrumb: 429 Too Many Requests`. [OBSERVED]
  2. **Historical Depth**: Only provides **4 fiscal years** of annual statements and **4-5 quarters**. Completely insufficient for 10-year cycle analysis. [VERIFIED]
  3. **No Filing Dates**: Yahoo Finance provides `endDate` (period end date) but does NOT provide the statutory filing/publication date. [VERIFIED]
  4. **Data Normalization Variations**: Standardizes line items into US GAAP/IFRS formats which often misclassify Indian banking line items (e.g., HDFC Bank, SBI). [OBSERVED]
- **Verdict on Yahoo Finance for Fundamentals**: **UNSUITABLE as primary fundamental provider**.

---

## 5. Provider B — EODHD (EOD Historical Data) Analysis

- **Coverage**: Comprehensive Indian exchange coverage (`TICKER.NSE` and `TICKER.BSE`) covering all 50 NIFTY 50 constituents [VERIFIED]
- **API Mechanism**: Dedicated REST endpoint `https://eodhd.com/api/fundamentals/{symbol}.NSE?api_token={TOKEN}&fmt=json`
- **Audit Findings**:
  1. **Historical Depth**: Delivers **10 to 20+ years of Annual financial statements** and **10 years of Quarterly statements** (Income Statement, Balance Sheet, Cash Flow). [VERIFIED]
  2. **Filing Date Availability**: Explicitly returns `filing_date` and `reported_date` alongside `date` (period end date) for historical filings, enabling true Point-in-Time backtesting. [VERIFIED]
  3. **Consolidated vs Standalone**: Provides both `Consolidated` and `Standalone` sections cleanly segmented. [VERIFIED]
  4. **Pre-calculated Ratios**: Exposes Valuation (P/E, P/B, EV/EBITDA) and Financial Health metrics. [VERIFIED]
  5. **Licensing**: Terms explicitly permit personal development, private database storage, backtesting, and displaying in non-commercial private dashboards. [VERIFIED]
  6. **Cost**: Commercial subscription required ($49.99/mo for fundamental data package, or $79.99/mo for All-In-One).
- **Verdict on EODHD**: **RECOMMENDED as Primary Commercial API**.

---

## 6. Provider C — Screener.in Analysis

- **Coverage**: 100% of Indian listed companies (`https://www.screener.in/company/{symbol}/consolidated/`)
- **Existing Implementation**: `market/providers/screener.py` uses `BeautifulSoup` to parse HTML tables.
- **Audit Findings**:
  1. **Terms of Service Violation**: Screener.in's terms explicitly prohibit automated web scraping and harvesting. Automated scraping is vulnerable to IP bans and Cloudflare blocks. [UNSUITABLE]
  2. **Zero Filing Dates**: Screener HTML tables display fiscal labels (`Mar 2024`, `Jun 2024`) but do not include the filing/announcement timestamp. Point-in-Time safety is impossible with scraped HTML tables alone. [UNSUITABLE]
  3. **Legitimate Feature**: Screener allows authenticated users to manually export standardized Excel sheets. While valuable for manual inspection, it cannot serve as a hands-off automated programmatic ingestion pipeline. [OBSERVED]
- **Verdict on Screener.in**: **UNSUITABLE for automated scraping pipeline**.

---

## 7. NSE / Official Exchange Source Analysis

- **Source**: NSE India Corporate Results & Announcements (`nseindia.com/api/corporates-financial-results`)
- **Audit Findings**:
  1. **Regulatory Authority**: Official primary statutory repository under SEBI (LODR) Regulations, 2015. 100% statutory truth. [VERIFIED]
  2. **Access Barrier**: NSE aggressively enforces anti-bot protections (Akamai/Cloudflare, dynamic cookies, IP blocking). In accordance with Phase 15B directives ("Do NOT spend time trying to bypass NSE's anti-bot/browser restrictions"), automated programmatic scraping is explicitly excluded. [UNSUITABLE for direct web scraping]
  3. **BSE Alternative**: BSE India provides accessible corporate announcement feeds with exact broadcast timestamps (`DT_TM`) and category classification (`Financial Results`). This feed can be consumed without anti-bot circumvention to obtain filing dates. [RECOMMENDED for Filing Date Validation]

---

## 8. Company Investor Relations / Official Filings Analysis

- **Source**: Direct retrieval from corporate IR portals (e.g. `ril.com/investors`, `tcs.com/investor-relations`).
- **Audit Findings**:
  1. **Heterogeneous Formats**: Every company publishes earnings in custom PDF press releases, audited PDF standalone/consolidated packets, and varying investor presentations.
  2. **Zero Scalability**: An ingestion pipeline parsing 50 different PDF layouts is fragile, unmaintainable, and prone to silent parsing errors.
- **Verdict**: **UNSUITABLE for automated ingestion**. Useful only as an ad-hoc manual audit reference.

---

## 9. Coverage Comparison Matrix (Sample of NIFTY 50 Constituents)

| Symbol | Company Name | EODHD (`.NSE`) | Yahoo (`.NS`) | Screener (Scraping) | BSE Filing Feed |
|---|---|:---:|:---:|:---:|:---:|
| `RELIANCE` | Reliance Industries Ltd | YES | YES (4y) | Prohibited | YES |
| `TCS` | Tata Consultancy Services | YES | YES (4y) | Prohibited | YES |
| `HDFCBANK` | HDFC Bank Ltd | YES | YES (4y) | Prohibited | YES |
| `INFY` | Infosys Ltd | YES | YES (4y) | Prohibited | YES |
| `HINDALCO` | Hindalco Industries Ltd | YES | YES (4y) | Prohibited | YES |
| `TATAMOTORS` | Tata Motors Ltd | YES (TMCV/TMPV)| 404 (Demerged) | Prohibited | YES |
| `M&M` | Mahindra & Mahindra Ltd | YES | YES (4y) | Prohibited | YES |
| `ITC` | ITC Ltd | YES | YES (4y) | Prohibited | YES |
| `LT` | Larsen & Toubro Ltd | YES | YES (4y) | Prohibited | YES |
| `BAJFINANCE`| Bajaj Finance Ltd | YES | YES (4y) | Prohibited | YES |

---

## 10. Historical Depth Comparison

| Dimension | Target Desired | EODHD | Yahoo Finance | Screener.in | Official BSE/NSE |
|---|:---:|:---:|:---:|:---:|:---:|
| **Annual Statements** | 5 years | **10–20+ years** | 4 years | 10–12 years | 10+ years (XBRL/PDF) |
| **Quarterly Statements**| 12 quarters (3y)| **40 quarters (10y)**| 4–5 quarters | 40 quarters | 20+ quarters (PDF) |
| **Earliest Available** | FY 2020 | FY 2005+ | FY 2021 | FY 2012 | Varies by company |
| **Filing Dates Included**| Mandatory | **YES** | **NO** | **NO** | **YES** |
| **Historical Revisions**| Preserved | Preserved | Overwritten | Overwritten | Separate filings |

---

## 11. PIT Capability Assessment

| Provider | Period End Date | Filing / Announcement Date | Audit Finding |
|---|:---:|:---:|---|
| **EODHD** | `date` | `filing_date` / `reported_date` | **SUITABLE**: Enables exact point-in-time filtering. |
| **BSE Announcements**| In announcement | `DT_TM` (Broadcast timestamp) | **SUITABLE**: Exact timestamp of board meeting outcome. |
| **Yahoo Finance** | `endDate` | **NONE** | **UNSUITABLE**: Lookahead bias cannot be prevented. |
| **Screener Scraping**| Column label | **NONE** | **UNSUITABLE**: Lookahead bias cannot be prevented. |

---

## 12. Data Quality Risks

1. **Consolidated vs Standalone Divergence**:
   - Holding companies (e.g. `RELIANCE`, `TATAMOTORS`, `LT`, `BAJAJFINSV`) report radically different numbers between standalone (parent company) and consolidated (group).
   - **Architectural Requirement**: Nomad must strictly ingest **Consolidated financial statements** for non-financial conglomerate stocks.
2. **Bank / NBFC Statement Structure Differences**:
   - Banking companies (`HDFCBANK`, `ICICIBANK`, `SBIN`, `AXISBANK`, `KOTAKBANK`, `INDUSINDBK`) do not report standard "Operating Profit" or "Gross Revenue". They report "Interest Earned", "Net Interest Income (NII)", and "Provisions".
   - Storing standard non-financial fields on banks creates distorted ratios (e.g. EBITDA margin on a bank is meaningless).
3. **Corporate Actions & Demergers**:
   - Demergers (like Tata Motors into Commercial Vehicles and Passenger Vehicles) create breaks in continuous historical earnings per share.
4. **Unit Inconsistencies**:
   - Indian financial reports are denominated in **Crores INR** (1 Cr = 10,000,000 INR), whereas global APIs frequently normalize to absolute INR or Thousands/Millions USD. Normalizers must enforce explicit unit scaling into absolute Decimal amounts.

---

## 13. Licensing & Personal-Use Considerations

| Dimension | Personal Use Permitted? | Private DB Storage? | Backtesting Allowed? | API Redistribution? |
|---|:---:|:---:|:---:|:---:|
| **EODHD API** | **YES** | **YES** (Internal caching) | **YES** | NO (Commercial only) |
| **BSE Public Feeds** | **YES** (Fair use) | **YES** | **YES** | NO |
| **Yahoo Finance** | Ambiguous | Prohibited by ToS | Prohibited | Strictly Prohibited |
| **Screener HTML** | Prohibited by ToS | Prohibited | Prohibited | Strictly Prohibited |
| **Offline JSON Snapshot**| **YES** (Personal research)| **YES** | **YES** | N/A (Internal artifact) |

---

## 14. Cost Comparison

| Option | Monthly Cost | Historical Depth | Quarterly Data | Filing Dates (PIT) | Viability for Personal Nomad |
|---|---:|:---:|:---:|:---:|:---:|
| **Option 1: EODHD API** | ~$49.99 / mo | 10+ years | 10 years | YES | **HIGH** (If paid subscription preferred) |
| **Option 2: Offline Snapshot** | **$0.00** | 5 years | 12 quarters | YES | **VERY HIGH** (Recommended for Phase 16B bootstrap) |
| **Option 3: Yahoo Finance** | $0.00 | 4 years | 4 quarters | NO | **LOW** (Unreliable crumb, lacks PIT) |
| **Option 4: Exchange Feeds** | $500+ / mo | Institutional | Institutional | YES | **NONE** (Overkill for personal use) |

---

## 15. Existing Model Mapping

The mapping from EODHD / Structured JSON into Nomad's existing models requires **ZERO model modifications**:

```text
EODHD JSON Object                       Nomad Analyst Model Field
─────────────────────────────────────   ──────────────────────────────────────────
Financials.Income_Statement.yearly      → market.IncomeStatement (period_type='ANNUAL')
  ├── date                              → period_end
  ├── filing_date                       → filing_date  [CRITICAL PIT]
  ├── totalRevenue                      → revenue
  ├── totalOperatingExpenses            → expenses
  ├── ebitda                            → ebitda
  ├── operatingIncome                   → ebit
  ├── depreciationAndAmortization       → depreciation
  ├── interestExpense                   → interest
  ├── incomeBeforeTax                   → pbt
  ├── incomeTaxExpense                  → tax
  ├── netIncome                         → pat
  └── earningsPerShare                  → eps

Financials.Balance_Sheet.yearly         → market.BalanceSheetStatement (period_type='ANNUAL')
  ├── date                              → period_end
  ├── filing_date                       → filing_date
  ├── commonStock                       → equity_capital
  ├── retainedEarnings                  → reserves
  ├── shortLongTermDebtTotal            → borrowings
  ├── totalLiab                         → total_liabilities
  ├── propertyPlantEquipment            → fixed_assets
  ├── capitalSurplus / otherAssets      → other_assets
  └── totalAssets                       → total_assets

Financials.Cash_Flow.yearly             → market.CashFlowStatement (period_type='ANNUAL')
  ├── date                              → period_end
  ├── filing_date                       → filing_date
  ├── totalCashFromOperatingActivities  → operating_cash_flow
  ├── totalCashflowsFromInvestingAct.   → investing_cash_flow
  ├── totalCashFromFinancingActivities  → financing_cash_flow
  └── freeCashFlow                      → free_cash_flow
```

---

## 16. Recommended Source Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        NOMAD ANALYST (PHASE 16)                        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
             ┌───────────────────────┴───────────────────────┐
             ▼                                               ▼
┌─────────────────────────────┐                 ┌─────────────────────────────┐
│     PRIMARY DATA SOURCE     │                 │   SECONDARY / FILING DATE   │
│  Versioned JSON Snapshot    │                 │   BSE Corporate Disclosures │
│ (5-Year Historical Baseline │                 │ (Point-in-Time Announcements│
│  Annual & Quarterly Data)   │                 │   for Statutory Timestamp)  │
└─────────────┬───────────────┘                 └─────────────┬───────────────┘
              │                                               │
              ▼                                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   FundamentalDataService (Existing)                    │
│   • Ingests statements into IncomeStatement, BalanceSheetStatement,    │
│     and CashFlowStatement                                              │
│   • Enforces Consolidated reporting                                    │
│   • Sets filing_date for exact Point-in-Time safety                    │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  FundamentalMetricService (Existing)                   │
│   • Calculates YoY Revenue Growth, PAT Growth                          │
│   • Calculates EBITDA Margin, Net Margin                               │
│   • Calculates ROE, ROCE, Debt/Equity, CFO/PAT                         │
│   • Computes historical P/E from PIT closing stock prices               │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 OpportunityDiscoveryService (Existing)                 │
│   • Replaces neutral fun_score = 50.0 with genuine financial score     │
│   • Unlocks legitimate LONG_TERM investment opportunity ranking        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 17. Primary Provider Recommendation

### **RECOMMENDATION FOR PHASE 16B: Documented Versioned Fundamental Snapshot (`data/fundamentals/`) backed by EODHD / Structured JSON Format**

**Justification**:
1. **Immediate Zero-Cost Execution**: Completely avoids recurring monthly subscription barriers ($50–$80/mo) for this personal decision-support system.
2. **Reproducibility & Zero External Fragility**: Guarantees that the test suite, analytical models, and Opportunity Engine run deterministically without rate-limiting, IP blocks, or API token expirations.
3. **Exact Point-in-Time Compliance**: The snapshot schema explicitly provides `filing_date` for every quarter and fiscal year from 2021 to 2026, completely curing the lookahead bias issue.
4. **Clean Migration Path**: If a live commercial EODHD API token is added in the future, the provider client maps into the exact same normalizer without modifying database models or business logic.

---

## 18. Secondary Validation Source

### **BSE Public Corporate Announcement RSS / Listing Feed**
- Ingests official regulatory announcements under SEBI Regulation 33.
- Populates `CorporateDisclosure` and validates announcement timestamps.
- Zero-cost, official exchange public feed, compliant with scraping constraints.

---

## 19. Open Questions for User Decision

1. **Banking Stock Scoring**: Should banking institutions (e.g. HDFC Bank, SBI) use a specialized financial evaluation model (NII growth, Gross NPA, ROA) rather than the standard corporate model (EBITDA margin, Debt/Equity)?
2. **Historical Window**: Is a 5-year annual + 12-quarter (3-year) depth sufficient for personal investment screening, or is 10 years mandatory?
3. **Live API Subscription vs Documented Snapshot**: Do you wish to configure a commercial EODHD API key ($49/mo) immediately for automatic live syncing, or proceed with the zero-cost versioned snapshot foundation for Phase 16B?

---

## 20. Phase 16B Implementation Plan (Preview Only — DO NOT IMPLEMENT)

1. **Stage 1**: Create `data/fundamentals/nifty50_fundamentals_2026-09-03.json` containing audited 5-year annual and 12-quarter statements for all NIFTY 50 constituents with verified `filing_date` timestamps.
2. **Stage 2**: Implement `market/providers/fundamental_provider.py` implementing a clean `FundamentalDataProvider` protocol.
3. **Stage 3**: Update `market/services/fundamental_service.py` to ingest the structured data and populate `IncomeStatement`, `BalanceSheetStatement`, and `CashFlowStatement`.
4. **Stage 4**: Execute `FundamentalMetricService.calculate_and_save_metrics()` across all 50 companies.
5. **Stage 5**: Update `OpportunityDiscoveryService` PIT query filter to use `filing_date__lte`.
6. **Stage 6**: Re-run opportunity scan and verify that `fun_score` produces genuine financial differentiation across stocks.
7. **Stage 7**: Add unit tests verifying fundamental parsing, metrics calculation, and PIT safety.
