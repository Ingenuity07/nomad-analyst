# Nomad Analyst — Phase 21: ChatGPT Handoff Document

**Date:** 2026-10-16  
**Context:** Handoff from Phase 20B.2 Closure to ChatGPT for Phase 21 Alignment & Architectural Oversight  
**Repository Working Tree:** 19 modified files, 27 untracked audit/script files (all preserved untouched)  
**Test Suite Health:** **337 / 337 tests passing (100% green)**  

---

## 1. Executive Summary & Closure Verdict

This document transfers technical oversight to ChatGPT following the independent verification and formal closure of **Phase 20B (Targeted Runtime Reliability Remediation)**.

### Phase 20B Closure Verdict:
**`ACCEPTED WITH DOCUMENTED LIMITATIONS`**

- **Fix A (Session-Boundary Filtering):** `_load_completed_bars()` in `market/services/intraday_signal_engine.py` strictly excludes off-session bars (`< 09:15:00` IST and `>= 15:30:00` IST) across all sources (`NomadAggregator`, `KiteHistoricalProvider`, `YFinanceMarketProvider`). Timezone conversions are handled with timezone-aware `Asia/Kolkata` evaluation, and pre-open bar contamination of session VWAP is mathematically eliminated.
- **Fix B (Process Locking & PID File Integrity):** `run_intraday_ticker.py` now opens `/tmp/nomad_intraday_ticker.pid` using non-truncating descriptor flags (`os.O_CREAT | os.O_RDWR` with mode `"r+"`). A second attempting daemon catches `BlockingIOError` on `fcntl.flock()`, closes its descriptor, and returns cleanly without zeroing out the active daemon's PID and without executing the outer cleanup `finally:` block.
- **Suite Verification:**
  - `Phase20BRuntimeReliabilityTests`: 10/10 PASS (0.068s)
  - `IntradayStrategyEngineTests` + `Phase20A1IntradayWarmupAndReadinessTests`: 48/48 PASS (0.294s)
  - Full `market` suite: 316/316 PASS (5.537s)
  - Full `llm` router suite: 21/21 PASS (12.881s)
- **Documented Limitations:**
  - Active daemon `PID 49422` was preserved running during continuous trading to maintain uninterrupted live WebSocket streaming. Lock acquisition was hermetically verified via unit tests; post-market daemon restart will create the physical PID file on disk.
  - Existing off-session bars in PostgreSQL from prior morning testing are filtered out at query time, but physical row deletion via `cleanup_contaminated_preopen_bars.py` remains a pending maintenance task.

---

## 2. System Status Matrix

| Component | Status | Empirical Evidence |
| :--- | :--- | :--- |
| **PostgreSQL 16** | **ONLINE** | Port 5432, migrations up-to-date, 54 instruments active. |
| **Redis Cache** | **ONLINE** | Port 6379 (db=1 for Django cache), live ticks and states active. |
| **Django API Server** | **ONLINE** | Port 8000, responds HTTP 200 on `/api/v1/market/overview/`. |
| **Celery Worker & Beat** | **ONLINE** | Registered tasks active; periodic context snapshots executing. |
| **Kite Ticker Daemon** | **ONLINE** | `PID 49422`, streaming 54 instruments via `wss://ws.kite.trade`. |
| **React 19 Frontend** | **ONLINE** | Port 5173, Vite connected, responsive UI. |
| **Readiness Gate** | **100% READY** | 50/50 NIFTY 50 equities ready, 4/4 benchmarks ready. |
| **Zero-LLM Invariant** | **PRESERVED** | Zero LLM calls during scans; 1 call per user examination with caching. |

---

## 3. Authoritative Determination of Next Phase

A search across all repository documents confirms that **no document titled "Phase 21" currently exists in the repository**.

The authoritative next phase is established from the project's foundational architecture documents:
1. **[`docs/audits/nomad_analyst_current_state_audit.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/nomad_analyst_current_state_audit.md#L923-L927):**
   > `### 4. NEXT DEVELOPMENT PHASE: Horizon v2 & Fundamental Engine`
   > 1. Adjust banking and NBFC scoring to use Credit Growth, NIM, GNPA/NNPA instead of Debt/Equity and ROCE.
   > 2. Wire quarterly statements (`period_type="QUARTERLY"`) into Horizon scoring for earnings momentum detection.
   > 3. Incorporate P/E and valuation discount/premium relative to 5-year sector medians.
2. **[`PHASE_16C_HANDOFF.md`](file:///Users/shivamsingh/personal/nomad-analyst/PHASE_16C_HANDOFF.md#L55-L59):**
   > `2. Phase 18 (Horizon Refinement):`
   > - Branch banking efficiency scoring (NIM / Capital Adequacy).
   > - Add Trailing Twelve Months (TTM) quarterly momentum.
   > - Integrate P/E valuation into the fundamental opportunity formula.

Because Phase 18 was temporarily deferred to build Phase 17 (Kite live intraday integration), and Phases 19 and 20 were dedicated to live-market data backfilling, integrity audits, and runtime reliability remediation, this work is the direct next substantive engineering phase:

### Designated Title:
**Phase 21: Horizon v2 & Banking/Fundamental Engine Refinement**

---

## 4. Phase 21 Detailed Specification & Scope

### 4.1 Objectives
Refactor the fundamental scoring engine and Horizon discovery pipeline to eliminate structural distortions and provide accurate, multi-year, and sector-aware ranking for the entire NIFTY 50 universe.

### 4.2 Core Defects & Design Solutions

#### 1. Banking & Financial Sector Distortion
- **Issue:** Commercial banks (`HDFCBANK`, `ICICIBANK`, `SBIN`, `AXISBANK`, `KOTAKBANK`, `INDUSINDBK`, `BAJFINANCE`) are evaluated using industrial formulas:
  $$\text{Sub}_{\text{Efficiency}} = 0.50 \cdot S(\text{ROCE}) + 0.50 \cdot S(\text{Debt/Equity})$$
  Customer deposits are treated as distressed debt (showing 5.5x–8.5x leverage), and ROCE is artificially depressed to 2%–3%, placing India's premier banks in the bottom tier of long-term opportunity rankings.
- **Phase 21 Solution:**
  - Inspect `company.sector` or taxonomy (`BANKING` / `NBFC_INDAS`).
  - Branch into a banking-specific scoring module:
    - Replace Debt/Equity with **Capital Adequacy Ratio (CAR)** and **Gross/Net NPA ratios**.
    - Replace ROCE with **Net Interest Margin (NIM)** and **Return on Assets (ROA)**.
    - Evaluate **Credit / Loan Book Growth (YoY)**.

#### 2. Quarterly Statements Integration (TTM & Momentum)
- **Issue:** 600 verified quarterly financial statements exist in the database (`period_type="QUARTERLY"`), but `OpportunityDiscoveryService` filters exclusively for `period_type="ANNUAL"`. Rapid quarterly turnarounds or decelerations are invisible.
- **Phase 21 Solution:**
  - Build a Trailing Twelve Months (TTM) statement aggregator.
  - Compute YoY quarterly revenue growth and PAT margin expansion to capture momentum.

#### 3. Cyclical Peak Earnings Normalization
- **Issue:** Single-year annual metrics cause commodity producers (e.g. `COALINDIA`) at cyclical peak pricing to capture artificially high rankings (ROE 44%, ROCE 58.5%).
- **Phase 21 Solution:**
  - Implement a 3-to-5 year normalized smoothing average for ROCE and ROE in cyclical sectors (Metals, Mining, Oil & Gas).

#### 4. Valuation Integration
- **Issue:** P/E and price-to-book ratios are computed during ingestion but discarded by the opportunity ranking formula.
- **Phase 21 Solution:**
  - Wire P/E ratio and sector valuation percentile into the composite score, penalizing excessive multiple expansion.

### 4.3 Architectural Safeguards & Invariants
- **Spot Equities Only:** Strictly NIFTY 50 equities (no F&O, no options, no futures).
- **Deterministic Calculation:** 100% Python/NumPy/Django deterministic math; **ZERO LLM calls** during scans or ranking.
- **Point-in-Time Integrity:** Strict enforcement of `filing_date <= as_of` to prevent lookahead bias.
- **Full Test Isolation:** New tests must mock external calls and preserve complete independence from live network services.

---

## 5. Immediate Recommended Next Action

The recommended sequence for the engineering team and ChatGPT:

1. **Step 1 (Post-Market Housekeeping):**
   - After market close (15:30 IST), perform a clean restart of `run_intraday_ticker.py` to verify physical `/tmp/nomad_intraday_ticker.pid` creation.
   - Run `python manage.py cleanup_contaminated_preopen_bars --date 2026-10-15 --dry-run` and review before optionally cleaning off-session bars.
2. **Step 2 (Alignment on Phase 21):**
   - Review and align on the Phase 21 design specification (Banking taxonomy scoring formulas, TTM quarterly aggregation, and cyclical smoothing).
3. **Step 3 (Implementation):**
   - Begin Phase 21 implementation by creating the banking scoring module and updating `FundamentalEngine` and `OpportunityDiscoveryService`.

---

## 6. Authoritative Reference Files

- Phase 20B Closure Report: [`docs/audits/phase_20b_closure_and_phase_21_readiness_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_20b_closure_and_phase_21_readiness_report.md)
- Phase 20B.2 Session Integrity Report: [`docs/audits/phase_20b2_session_integrity_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_20b2_session_integrity_report.md)
- Current State Audit: [`docs/audits/nomad_analyst_current_state_audit.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/nomad_analyst_current_state_audit.md)
- Phase 16C Handoff: [`PHASE_16C_HANDOFF.md`](file:///Users/shivamsingh/personal/nomad-analyst/PHASE_16C_HANDOFF.md)
