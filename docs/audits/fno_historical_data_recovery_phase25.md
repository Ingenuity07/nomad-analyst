# Nomad Analyst — Phase 2.5: Historical Options Data Recovery Report

**Phase:** Phase 2.5 Historical Options Data Recovery  
**Target Expiries Investigated:**
- `2025-10-21` (Tuesday Weekly Expiry)
- `2026-06-16` (Tuesday Weekly Expiry)
- `2026-06-23` (Tuesday Weekly Expiry)
- `2026-06-30` (Tuesday Weekly Expiry)

**Dataset Source:** `thetrademarkk/india-index-options-1m` on Hugging Face (License: CC BY-NC 4.0)  
**Date of Audit:** 2026-10-22  
**Auditor Role:** Senior Quantitative Systems Engineer (Phase 2.5 Investigation Pass)

---

## 1. Executive Summary & Provenance Blocker

In accordance with Phase 2.5 Requirements 4 and 6:
> *"4. Do not fabricate data or substitute a monthly contract for a missing weekly contract."*  
> *"6. Download only from the already-approved source if the files are available and the acquisition method is clear. If source availability or provenance is uncertain, stop and report the blocker rather than guessing."*  
> *"If a trustworthy source file cannot be obtained, document that clearly and leave the affected sessions excluded."*

### Key Findings
1. **Upstream Source Audit:**  
   The entire file manifest of `thetrademarkk/india-index-options-1m` on Hugging Face (3,337 files total, 267 NIFTY option files) was queried via the Hugging Face API (`https://huggingface.co/api/datasets/thetrademarkk/india-index-options-1m`).  
   **Result:** The 4 target weekly option files are **genuinely absent from the upstream Hugging Face repository**. The creator did not publish option files for `2025-10-21`, `2026-06-16`, `2026-06-23`, or `2026-06-30`.
2. **Current Local Inventory:**  
   The local repository at `data/historical/fno/nifty/options/` contains **all 54 files** that exist in the approved upstream repository for the `2025-07-01` to `2026-07-02` window. Zero files were missed during the Phase 2.2 download.
3. **No Monthly Contract Substitution:**  
   While `2026-07-07.parquet` contains traded bars during June 2026, those bars represent far-dated contracts (20–27 DTE). Substituting them for missing 0–7 DTE front-weekly options would violate strategy semantics, delta/gamma assumptions, and execution realism.
4. **Data Integrity Action:**  
   **No data was fabricated or synthetically injected.** In accordance with fail-closed architecture ([`DEC-01`](file:///Users/shivamsingh/personal/nomad-analyst/docs/historical_options_backtester_architecture.md#L30)), the 19 affected trading sessions **remain hard-excluded** (`EXCLUDED_MISSING_EXPIRY_DATA`).

---

## 2. Upstream Hugging Face Inventory Audit

The Hugging Face repository siblings list was inspected programmatically:
```python
# API Endpoint: https://huggingface.co/api/datasets/thetrademarkk/india-index-options-1m
```

### A. Target File Availability on Upstream Hugging Face
| Target Expiry File | Upstream Path | Upstream Status | Provenance Finding |
| :--- | :--- | :---: | :--- |
| **`2025-10-21`** | `options/NIFTY/2025-10-21.parquet` | **NOT FOUND** | File does not exist in Hugging Face repository |
| **`2026-06-16`** | `options/NIFTY/2026-06-16.parquet` | **NOT FOUND** | File does not exist in Hugging Face repository |
| **`2026-06-23`** | `options/NIFTY/2026-06-23.parquet` | **NOT FOUND** | File does not exist in Hugging Face repository |
| **`2026-06-30`** | `options/NIFTY/2026-06-30.parquet` | **NOT FOUND** | File does not exist in Hugging Face repository |

### B. Upstream Expiry Chronology Around Target Months
Inspection of all NIFTY option files in the source dataset revealed the exact gaps:

#### 1. October 2025 Chronology
* `options/NIFTY/2025-10-07.parquet` (Exists on HF & Locally)
* `options/NIFTY/2025-10-14.parquet` (Exists on HF & Locally)
* **GAP:** `2025-10-21` is missing from the creator's dataset
* `options/NIFTY/2025-10-28.parquet` (Exists on HF & Locally)

#### 2. June 2026 Chronology
* `options/NIFTY/2026-06-02.parquet` (Exists on HF & Locally)
* `options/NIFTY/2026-06-09.parquet` (Exists on HF & Locally)
* **GAP:** `2026-06-16` is missing from the creator's dataset
* **GAP:** `2026-06-23` is missing from the creator's dataset
* **GAP:** `2026-06-30` is missing from the creator's dataset
* `options/NIFTY/2026-07-07.parquet` (Exists on HF & Locally)

---

## 3. Analysis of Affected Trading Sessions

The 19 trading sessions impacted by these upstream gaps were audited:

### A. October 2025 Gap (`2025-10-15` through `2025-10-21`) — 5 Sessions
1. **Scheduled Weekly Expiry:** `2025-10-21` (Tuesday).
2. **Dependent Sessions:** `2025-10-15`, `2025-10-16`, `2025-10-17`, `2025-10-20`, `2025-10-21`.
3. **Special Muhurat Session Note:**
   `2025-10-21` was Diwali Laxmi Pujan (Muhurat Trading). Inspection of `data/historical/fno/nifty/index/NIFTY.parquet` confirmed that `2025-10-21` contains **only 95 index bars** from 18:15 to 19:15 IST, with 0 bars between 09:15 and 09:30 IST.  
   *Even if the option file were recovered, `2025-10-21` would still be ineligible under standard ORB rules (`EXCLUDED_INCOMPLETE_ORB`).*
4. **Current Status:** All 5 sessions remain **EXCLUDED_MISSING_EXPIRY_DATA**.

### B. June 2026 Gap (`2026-06-10` through `2026-06-30`) — 14 Sessions
1. **Scheduled Weekly Expiries:**
   * `2026-06-16` (Tuesday): Governs sessions `2026-06-10` through `2026-06-16` (5 sessions)
   * `2026-06-23` (Tuesday): Governs sessions `2026-06-17` through `2026-06-23` (5 sessions)
   * `2026-06-30` (Tuesday): Governs sessions `2026-06-24` through `2026-06-30` (4 sessions, `2026-06-26` was Eid holiday)
2. **Why `2026-07-07.parquet` Cannot Substitute:**
   * While `2026-07-07.parquet` has trade records during June 2026, those contracts had 20 to 27 days to expiry.
   * Front-weekly options have deltas of ~0.50 and high gamma. Monthly options 27 DTE out have lower delta sensitivity and much wider bid/ask spreads.
   * Substituting `2026-07-07` would violate strategy fidelity and artificially distort backtest results.
3. **Current Status:** All 14 sessions remain **EXCLUDED_MISSING_EXPIRY_DATA**.

---

## 4. Historical Dataset Validation Results

The dataset validator was executed across the existing local dataset:
```bash
venv/bin/python manage.py validate_fno_historical
```

### Validation Summary
* **Index Data:** `data/historical/fno/nifty/index/NIFTY.parquet` (486,050 rows, SHA-256 verified).
* **Option Data:** 54 Parquet files in `data/historical/fno/nifty/options/` (15,213,485 rows).
* **Checks:** 14 total | **Passed:** 11 | **Failed:** 2 (documented duplicates in `2025-12-30` and `2026-01-06` deduplicated deterministically via `DISTINCT`; post-market 15:39–15:45 prints excluded from intraday queries) | **Partial:** 1 (Muhurat/shortened sessions).
* **Manifest Status:** [`data/historical/fno/nifty/manifest.json`](file:///Users/shivamsingh/personal/nomad-analyst/data/historical/fno/nifty/manifest.json) is 100% synchronized with all 54 local Parquet files.

---

## 5. Session Eligibility Reconciliation

Across the 242 trading days in the `2025-07-01` to `2026-07-02` window:

| Exclusion Category | Reason | Sessions | Affected Dates |
| :--- | :--- | :---: | :--- |
| **`EXCLUDED_MISSING_EXPIRY_DATA`** | Genuinely absent upstream weekly option files | **19** | `2025-10-15` to `2025-10-21` (5 days)<br>`2026-06-10` to `2026-06-30` (14 days) |
| **`EXCLUDED_DATA_GAP`** | Insufficient index bars (only 6 bars from 15:25 IST) | **1** | `2026-06-03` |
| **`EXCLUDED_RANGE_TOO_WIDE`** *(If 150-pt limit active)* | Morning range width > 150.00 pts | **18** | High-volatility days (Budget day `2026-02-03`, etc.) |

### Resulting Eligibility Totals
* **Configuration A (`--max-orb-range 150`):**  
  **204 Qualified Sessions** / **38 Excluded Sessions** / **200 Executed Trades**
* **Configuration B (`--max-orb-range none`):**  
  **222 Qualified Sessions** / **20 Excluded Sessions** / **217 Executed Trades**

---

## 6. Recommendations & External Recovery Protocol

Because the approved Hugging Face repository does not contain the missing weekly files, recovering them requires acquiring data from an **alternative authoritative market data vendor** (e.g., licensed NSE Level-1 tick provider).

When an external dataset is sourced in the future, the following intake protocol must be enforced before installation:
1. **License & Provenance Verification:** Validate commercial/research usage terms and vendor credentials.
2. **Schema Uniformity:** Ensure columns match exactly: `timestamp` (IST), `open`, `high`, `low`, `close`, `volume`, `open_interest`, `strike`, `expiry`, `option_type`, `tradingsymbol`.
3. **Conflict Detection:** Run DuckDB window conflict detection to guarantee zero duplicate-conflict rows.
4. **Isolated Benchmark:** Re-run the backtester on the recovered sessions in an isolated audit pass before merging into baseline reports.

---

## Safety Confirmation
* No data was fabricated or hallucinated.
* Operational database (`PaperTradeLedger`) remains at **0**.
* All six pre-existing frontend files remain unstaged and uncommitted.
* No Git commits, pushes, or resets were performed.
