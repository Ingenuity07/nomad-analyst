# Nomad Analyst — Phase 2.5: Historical Options Data Recovery Report

**Phase:** Phase 2.5 Historical Options Data Recovery  
**Target Expiries Investigated:**
- `2025-10-21` (Tuesday Weekly Expiry)
- `2026-06-16` (Tuesday Weekly Expiry)
- `2026-06-23` (Tuesday Weekly Expiry)
- `2026-06-30` (Tuesday Weekly Expiry)

**Dataset Source:** `thetrademarkk/india-index-options-1m` on Hugging Face  
**Dataset License:** Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)  
**Date of Audit:** 2026-10-22  
**Auditor Role:** Senior Quantitative Systems Engineer  

---

## 1. Source Provenance and Licensing Constraints

### A. Source Identification & Approved Origin
- **Upstream Host:** Hugging Face Datasets (`thetrademarkk/india-index-options-1m`)
- **API Endpoint:** `https://huggingface.co/api/datasets/thetrademarkk/india-index-options-1m`
- **Raw Download Base:** `https://huggingface.co/datasets/thetrademarkk/india-index-options-1m/resolve/main`
- **Acquisition Tooling:** Custom Django management command [`fno/management/commands/fetch_fno_historical.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/management/commands/fetch_fno_historical.py) with exponential backoff, SHA-256 verification, atomic `.tmp` renames, and local caching.

### B. Licensing & Usage Restrictions
- **License:** CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International).
- **Terms:** Permits personal non-commercial research, backtesting, and development.
- **Redistribution Policy:** Raw data files, Parquet outputs, and SQLite/DuckDB databases are strictly excluded from version control via `.gitignore` (`data/historical/fno/`).
- **Data Integrity Constraints:**
  - Zero synthetic fabrication or interpolation of missing contract candles.
  - No substitution of distant monthly contracts for missing weekly options contracts.
  - Zero look-ahead bias or speculative Level-1 bid/ask quote generation.

---

## 2. Exact Files Downloaded, Reused, or Unavailable

An exhaustive API query of the entire upstream Hugging Face repository manifest (3,337 files total, 267 NIFTY option files) was conducted to investigate the availability of the four target expiry files:

### Status Breakdown of Target Expiry Files
| Target Expiry Date | Day of Week | Upstream Path | Upstream Status | Local File Status | Resolution |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **`2025-10-21`** | Tuesday | `options/NIFTY/2025-10-21.parquet` | **UNAVAILABLE** | Not present | Upstream gap; file does not exist in dataset |
| **`2026-06-16`** | Tuesday | `options/NIFTY/2026-06-16.parquet` | **UNAVAILABLE** | Not present | Upstream gap; file does not exist in dataset |
| **`2026-06-23`** | Tuesday | `options/NIFTY/2026-06-23.parquet` | **UNAVAILABLE** | Not present | Upstream gap; file does not exist in dataset |
| **`2026-06-30`** | Tuesday | `options/NIFTY/2026-06-30.parquet` | **UNAVAILABLE** | Not present | Upstream gap; file does not exist in dataset |

### Files Downloaded vs. Reused Summary
- **Files Downloaded in Phase 2.5:** **0** (No target files exist upstream to download; acquisition safely halted per Section 2 safeguards).
- **Files Reused Locally:** **54** NIFTY option files and **1** NIFTY spot index file (`NIFTY.parquet`), representing 100% of all published files covering the historical window (`2025-07-01` to `2026-07-02`).
- **Files Unavailable:** **4** weekly expiry files genuinely omitted by upstream dataset author.

---

## 3. Checksums, Sizes, Row Counts, and Date Coverage

### A. Spot Index Dataset
- **File:** `data/historical/fno/nifty/index/NIFTY.parquet`
- **SHA-256 Checksum:** `e3975769ea8aa80da8e244105267b2fc13ef047ae374f66dc0981ba8ab1e48fe`
- **File Size:** 4,813,103 bytes (~4.59 MB)
- **Total 1-Minute Rows:** 486,050 rows
- **Date Coverage:** 2021-01-01 to 2026-07-03 (1,262 total trading days, 242 days within backtest window)

### B. Option Dataset Coverage Surrounding Target Expiries
The existing local options dataset contains 54 weekly and monthly expiry files totaling 15,213,485 rows (~427 MB). Surrounding chronological coverage:

#### October 2025 Expiry Sequence
| Expiry File | Size | Rows | Min Timestamp (IST) | Max Timestamp (IST) | Status |
| :--- | :---: | :---: | :--- | :--- | :---: |
| `2025-10-07.parquet` | 6.88 MB | 267,002 | 2025-09-24 09:15 | 2025-10-07 15:30 | Reused |
| `2025-10-14.parquet` | 6.94 MB | 269,796 | 2025-10-01 09:15 | 2025-10-14 15:30 | Reused |
| **`2025-10-21.parquet`** | **0 MB** | **0** | **N/A** | **N/A** | **UNAVAILABLE** |
| `2025-10-28.parquet` | 13.97 MB | 511,180 | 2025-09-01 09:15 | 2025-10-28 15:30 | Reused |

#### June 2026 Expiry Sequence
| Expiry File | Size | Rows | Min Timestamp (IST) | Max Timestamp (IST) | Status |
| :--- | :---: | :---: | :--- | :--- | :---: |
| `2026-06-02.parquet` | 6.55 MB | 240,666 | 2026-05-20 09:15 | 2026-06-02 15:30 | Reused |
| `2026-06-09.parquet` | 6.64 MB | 241,452 | 2026-05-27 09:15 | 2026-06-09 15:30 | Reused |
| **`2026-06-16.parquet`** | **0 MB** | **0** | **N/A** | **N/A** | **UNAVAILABLE** |
| **`2026-06-23.parquet`** | **0 MB** | **0** | **N/A** | **N/A** | **UNAVAILABLE** |
| **`2026-06-30.parquet`** | **0 MB** | **0** | **N/A** | **N/A** | **UNAVAILABLE** |
| `2026-07-07.parquet` | 9.77 MB | 344,057 | 2026-06-01 09:15 | 2026-07-07 15:30 | Reused |

### C. Monthly Substitution Audit
While `2026-07-07.parquet` contains trades between `2026-06-10` and `2026-06-30`:
- **Days to Expiration (DTE):** 20 to 27 DTE.
- **Strategy Semantics:** The NIFTY ORB strategy specifically trades front-weekly options (0–7 DTE) to capitalize on high delta sensitivity and low absolute premium outlay. Far-dated monthly options exhibit lower delta, wider percentage spreads, and different gamma decay profiles.
- **Audit Decision:** Monthly substitution is strictly disallowed per Requirement 2 and Phase 2.3 specification DEC-01.

---

## 4. Duplicate and Conflict Validation

DuckDB analysis of local Parquet files confirmed the data integrity state:

1. **Spot Index (`NIFTY.parquet`):**
   - Exact Duplicates: **0**
   - Conflicting Duplicate Timestamps: **0**
   - Market Hours: 100% of bars fall within standard continuous and settlement trading sessions.

2. **Options Dataset (15,213,485 rows across 54 files):**
   - **Exact Identical Duplicates:** 33,261 identical rows across 2 files (`2025-12-30`: 1,716; `2026-01-06`: 31,545).
     - *Resolution:* All fields (`timestamp`, `strike`, `option_type`, `open`, `high`, `low`, `close`, `volume`, `open_interest`) are 100% identical. The DuckDB reader deterministically deduplicates these via `QUALIFY ROW_NUMBER() OVER (...) = 1`.
   - **Conflicting Duplicate Rows:** **0** (No conflicting prints with diverging prices for the same contract minute).
   - **Off-Hour Settlement Prints:** 8,227 rows fall between 15:39 and 15:45 IST (NSE post-market closing settlement session). Standard intraday backtester queries filter `timestamp < 15:30 IST`, preventing these settlement prints from contaminating execution.

---

## 5. Commands and Actual Test/Validator Output

### A. Historical Dataset Validator Command
```bash
venv/bin/python manage.py validate_fno_historical
```

#### Actual Console Output:
```text
================================================================================
NOMAD ANALYST — HISTORICAL F&O DATASET VALIDATOR
Target Directory: data/historical/fno/nifty
================================================================================

### Validation Checks Breakdown:
  [PASS        ] MANIFEST_VERIFICATION
               Details: manifest.json exists and is readable.
  [PASS        ] INDEX_SCHEMA
               Details: Index schema valid. Total rows: 486,050
  [PASS        ] INDEX_OHLC_GEOMETRY
               Details: All index rows satisfy geometric boundaries (high>=low, positive prices).
  [PASS        ] INDEX_DUPLICATES
               Details: Zero duplicate timestamps in index dataset.
  [PASS        ] INDEX_MARKET_HOURS
               Details: All index bars fall strictly within valid NSE trading and settlement session boundaries.
  [PARTIAL_PASS] INDEX_ORB_15M_READINESS
               Details: ORB 15m completeness: 1256/1262 days have complete 15/15 bars (6 days incomplete or shortened/Muhurat).
  [PASS        ] OPTIONS_SCHEMA
               Details: Option schema valid across 54 expiry files. Total rows: 15,213,485
  [PASS        ] OPTIONS_OHLC_GEOMETRY
               Details: All option rows satisfy geometric boundaries (high>=low, positive prices).
  [FAIL        ] OPTIONS_DUPLICATES
               Details: Found 33261 duplicate contract-minute rows in option dataset across 2 source files (2025-12-30: 1,716; 2026-01-06: 31,545). HistoricalReader deduplicates deterministically via QUALIFY ROW_NUMBER.
  [PASS        ] OPTIONS_CONTRACT_METADATA
               Details: All option contracts have valid symbol (NIFTY), strike (>0), and type (CE/PE).
  [PASS        ] OPTIONS_VOLUME_AND_OI
               Details: Volume & OI valid: 0 negative values. Active trade bars: 15,138,150 (99.5%), legitimate inactive bars: 75,335 (0.5%).
  [FAIL        ] OPTIONS_MARKET_HOURS
               Details: Found 8227 option rows outside standard continuous hours (09:15-15:30 IST); all fall between 15:39 and 15:45 IST (NSE post-market closing settlement session; 0 anomalous rows outside 09:15-15:45 IST).
  [PASS        ] OPTIONS_ATM_SERIES_COVERAGE
               Details: 100% ATM series coverage: Both CE and PE present for all 232 liquid window days (within 14d of expiry).
  [PASS        ] BID_ASK_AVAILABILITY_DISCLAIMER
               Details: Verified: Dataset contains 1-minute OHLCV only. Historical bid/ask order book quotes are confirmed UNAVAILABLE and not fabricated.

================================================================================
OVERALL STATUS: FAIL
Checks: 14 total | Passed: 11 | Failed: 2 | Not Tested: 0
================================================================================
Machine-readable audit report saved to: docs/audits/fno_historical_validation_report.json
```

### B. Unit & Backtester Test Suite Execution
```bash
venv/bin/python manage.py test fno.tests.test_historical_data fno.tests.test_backtester
```

#### Actual Test Output:
```text
Found 40 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
..........................[2026-10-22 13:31:58,486] WARNING [fno.backtester.calendar]: DATASET_EXPIRY_GAP_ALERT: 4 scheduled exchange expiries are missing from dataset storage: [datetime.date(2025, 10, 21), datetime.date(2026, 6, 16), datetime.date(2026, 6, 23), datetime.date(2026, 6, 30)]
..................
----------------------------------------------------------------------
Ran 40 tests in 14.325s

OK
Destroying test database for alias 'default'...
```

---

## 6. Before/After Session Eligibility Reconciliation

Because trustworthy files for the 4 weekly expiries are not published by the source repository, the fail-closed exclusion gate ([`DEC-01`](file:///Users/shivamsingh/personal/nomad-analyst/docs/historical_options_backtester_architecture.md#L30)) strictly keeps affected sessions excluded:

### Trading Session Breakdown (242 Trading Days Total)
| Session Classification | Phase 2.4 Baseline | Phase 2.5 Audit Outcome | Delta ($\Delta$) | Explanatory Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **Total Calendar Trading Days** | 242 | 242 | 0 | Window: `2025-07-01` to `2026-07-02` |
| **`EXCLUDED_MISSING_EXPIRY_DATA`** | **19** | **19** | **0** | Missing weekly files absent from upstream source |
| **`EXCLUDED_DATA_GAP`** | **1** | **1** | **0** | `2026-06-03` has only 6 bars (data begins at 15:25 IST) |
| **`EXCLUDED_RANGE_TOO_WIDE`** *(if 150-pt cap active)* | **18** | **18** | **0** | High morning volatility sessions (Budget day, etc.) |
| **Qualified Trading Sessions (`--max-orb-range 150`)** | **204** | **204** | **0** | Fully qualified sessions with clean data |
| **Executed Trades (`--max-orb-range 150`)** | **200** | **200** | **0** | (4 sessions had no breakout) |
| **Qualified Sessions (`--max-orb-range none`)** | **222** | **222** | **0** | Fully qualified sessions without 150-pt filter |
| **Executed Trades (`--max-orb-range none`)** | **217** | **217** | **0** | (5 sessions had no breakout/fill rejected past 14:30) |

### Detailed List of the 19 Permanently Excluded Missing Expiry Sessions
1. `2025-10-15` (Wednesday) — Missing expiry `2025-10-21`
2. `2025-10-16` (Thursday) — Missing expiry `2025-10-21`
3. `2025-10-17` (Friday) — Missing expiry `2025-10-21`
4. `2025-10-20` (Monday) — Missing expiry `2025-10-21`
5. `2025-10-21` (Tuesday) — Missing expiry `2025-10-21` *(Muhurat session: only 95 evening bars; zero morning bars)*
6. `2026-06-10` (Wednesday) — Missing expiry `2026-06-16`
7. `2026-06-11` (Thursday) — Missing expiry `2026-06-16`
8. `2026-06-12` (Friday) — Missing expiry `2026-06-16`
9. `2026-06-15` (Monday) — Missing expiry `2026-06-16`
10. `2026-06-16` (Tuesday) — Missing expiry `2026-06-16`
11. `2026-06-17` (Wednesday) — Missing expiry `2026-06-23`
12. `2026-06-18` (Thursday) — Missing expiry `2026-06-23`
13. `2026-06-19` (Friday) — Missing expiry `2026-06-23`
14. `2026-06-22` (Monday) — Missing expiry `2026-06-23`
15. `2026-06-23` (Tuesday) — Missing expiry `2026-06-23`
16. `2026-06-24` (Wednesday) — Missing expiry `2026-06-30`
17. `2026-06-25` (Thursday) — Missing expiry `2026-06-30`
18. `2026-06-29` (Monday) — Missing expiry `2026-06-30` (`2026-06-26` was exchange holiday for Eid)
19. `2026-06-30` (Tuesday) — Missing expiry `2026-06-30`

---

## 7. Remaining Gaps and Recommended Next Action

### A. Current Integrity Assessment
The backtester operates with complete mathematical determinism and strict data isolation across **204 qualified sessions** (or **222 sessions** under uncapped sensitivity). Zero synthetic data has been introduced.

### B. Recommended Next Actions
1. **Preserve Exclusion Gate:** Maintain DEC-01 in production backtests. Do not allow speculative fallbacks.
2. **External Vendor Acquisition (Phase 3 Opportunity):** If full historical coverage across the 19 excluded sessions is deemed mandatory by stakeholders, license 1-minute historical tick/candle data from an accredited NSE market data vendor (e.g. TrueData, GlobalDataFeeds).
3. **Vendor Intake Invariant Enforcement:** When external files are sourced:
   - Validate against the existing schema (`timestamp`, `open`, `high`, `low`, `close`, `volume`, `open_interest`, `strike`, `expiry`, `option_type`, `tradingsymbol`).
   - Run duplicate/conflict audit using DuckDB window partitioning.
   - Run `validate_fno_historical` and verify SHA-256 before updating `manifest.json`.

---

## Safety & Invariant Verification
- [x] No live broker/API calls executed.
- [x] No live or paper-trading runtime modified.
- [x] Operational database untouched (`PaperTradeLedger` row count = 0).
- [x] All 6 pre-existing frontend uncommitted files preserved untouched.
- [x] Zero Git staging, commits, pushes, resets, or reverts performed.
- [x] Datasets and Parquet artifacts kept out of Git.
