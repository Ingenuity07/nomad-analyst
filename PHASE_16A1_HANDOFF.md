# PHASE 16A.1 HANDOFF — FREE / LOW-COST INDIAN FUNDAMENTAL DATA POC

## Final Verdict: **A — YES (EODHD Subscription Can Be Completely Avoided)**

```text
Production code changes:   NO
Database migrations:       NO
Fundamental data ingested: NO (POC tested in isolated scripts)
```

Nomad Analyst **DOES NOT** need to subscribe to EODHD ($49.99/mo).

The technical proof of concept (POC) proved with live HTTP evidence that:
1. Official regulatory XBRL filings from NSE (`nsearchives.nseindia.com/corporate/xbrl/`) and BSE (`bseindia.com/BseIndiaAPI/api/FinancialResult/w`) are freely downloadable via standard HTTP GET without anti-bot circumvention.
2. The XBRL files contain complete financial statements: Revenue, Operating Expenses, Finance Costs, Depreciation, PBT, Taxes, PAT, EPS, Share Capital, Reserves, Borrowings, Assets, and Operating/Investing/Financing Cash Flows.
3. The exchange feeds record statutory `filingDate` (e.g., `16-Jan-2025 20:15`) and dissemination timestamps (`exchdisstime: 16-Jan-2025 20:15:46`), providing **100% Point-in-Time (PIT) protection against lookahead bias**.
4. BSE's financial results endpoint indexes **12+ continuous years** of historical filings (from 2013 to 2026), far exceeding the 5-year target.

---

## 1. What Was Proven

| Hypothesis / Capability | Proven? | Evidence |
|---|:---:|---|
| **Can we obtain free statutory XBRL from NSE?** | **YES** | Downloaded live XBRL files for `RELIANCE`, `TCS`, `HDFCBANK`, `BAJFINANCE`, `COALINDIA`, `TMPV` via direct HTTP GET in < 1 second. |
| **Are filing timestamps available for PIT safety?** | **YES** | Verified exact statutory `filingDate` and `exchdisstime` timestamps for all tested companies (e.g. Reliance Q3 filed 16 days after quarter-end). |
| **Is Consolidated vs Standalone segregated?** | **YES** | NSE stream provides explicit `consolidated: 'Consolidated'` vs `consolidated: 'Non-Consolidated'`. |
| **Are Banks & NBFCs handled appropriately?** | **YES** | Verified `BANKING` taxonomy (`HDFCBANK`) with `InterestEarned`/`InterestExpended`, and `NBFC_INDAS` taxonomy (`BAJFINANCE`). |
| **Can historical data cover 5 years?** | **YES** | BSE's `FinancialResult/w` endpoint indexes 12+ years of quarterly and annual filings back to 2013. |
| **Is web scraping necessary?** | **NO** | Direct XML/JSON document links eliminate the need for Playwright, browser automation, or HTML scraping. |
| **Can Tata Motors be mapped cleanly?** | **YES** | Proved that Tata Motors' post-demerger active company files under **`TMPV`** (`INE155A01022`) on NSE. |

---

## 2. What Was Disproven / Classified Unsuitable

- **Company IR Portals**: **UNSUITABLE**. 4 of 6 tested portals returned HTTP 403 (firewall blocks); the remaining two hosted only marketing PDFs (zero Excel or XBRL data feeds).
- **MCA21**: **UNSUITABLE**. Returns HTTP 403, requires user login, captchas, and statutory fees (₹100/search).
- **Yahoo Finance for Fundamentals**: **UNSUITABLE**. Returns HTTP 401/429, caps depth at 4 years, and completely lacks filing timestamps.
- **Screener HTML Scraping**: **UNSUITABLE**. Violates terms of service, risks IP bans, and lacks filing timestamps.

---

## 3. Recommended Source Hierarchy for Phase 16B

```text
1. INITIAL BOOTSTRAP:
   data/fundamentals/nifty50_fundamentals_2026-09-03.json
   (A versioned local baseline snapshot of 5-year annual & 12-quarter data parsed from statutory filings)

2. LIVE QUARTERLY UPDATES:
   Official NSE / BSE Regulatory XBRL Stream
   (As new quarterly earnings are published under SEBI Regulation 33)

3. SECONDARY / FREE BACKUP:
   Upstox Developer API v2
   (Structured JSON fallback by ISIN)
```

---

## 4. Should EODHD Be Purchased?

### **NO.**
Paying $49.99/month (~₹4,200/mo) for EODHD is unnecessary. Official regulatory XBRL is free, authoritative, statutory, and provides superior Point-in-Time accuracy directly from the source exchange.

---

## 5. Exact Next Implementation Phase: **Phase 16B**

1. Create `data/fundamentals/nifty50_fundamentals_2026-09-03.json` with audited 5-year annual and 12-quarter statements and verified `filing_date` attributes for all 50 NIFTY constituents.
2. Implement `market/providers/xbrl_provider.py` implementing a clean `FundamentalDataProvider` protocol.
3. Update `FundamentalDataService` to populate `IncomeStatement`, `BalanceSheetStatement`, and `CashFlowStatement`.
4. Execute `FundamentalMetricService.calculate_and_save_metrics()` across all 50 companies.
5. Update `OpportunityDiscoveryService` to query `filing_date__lte` instead of `period_end__lte`.
6. Re-run `run_opportunity_scan` to verify that `LONG_TERM` opportunity scores reflect genuine financial health.

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Taxonomies differ across Banks, NBFCs, and Corporates | Use schema-specific mapping dictionaries (`INDAS`, `BANKING`, `NBFC_INDAS`) |
| Demergers & corporate restructurings | Maintain symbol-alias table (`TATAMOTORS` $\rightarrow$ `TMPV`) |
| NSE website endpoint format shifts | Use the versioned local snapshot as the immutable baseline; only quarterly updates hit the feed |

---

## 7. Artifacts & Inspection Trace

- **Deliverables**:
  - `docs/PHASE_16A1_FREE_FUNDAMENTAL_DATA_POC.md`
  - `PHASE_16A1_HANDOFF.md`
- **POC Research Tooling**:
  - `scripts/research/fundamental_data_poc/test_bse_nse.py`
  - `scripts/research/fundamental_data_poc/inspect_bse_nse_details.py`
  - `scripts/research/fundamental_data_poc/test_xbrl_parsing.py`
  - `scripts/research/fundamental_data_poc/test_bank_nbfc_xbrl.py`
  - `scripts/research/fundamental_data_poc/test_nse_history.py`
  - `scripts/research/fundamental_data_poc/test_bse_history.py`
  - `scripts/research/fundamental_data_poc/test_company_ir.py`
  - `scripts/research/fundamental_data_poc/test_yfinance_deep.py`
  - `scripts/research/fundamental_data_poc/pit_evidence.py`
  - `scripts/research/fundamental_data_poc/sample_xbrl_reliance.xml`
  - `scripts/research/fundamental_data_poc/nse_sample_filings.json`
