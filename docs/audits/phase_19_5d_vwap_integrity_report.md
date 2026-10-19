# Nomad Analyst — Phase 19.5D: VWAP Integrity and Historical Bar Remediation Report

**Date:** 2026-10-15  
**Audit & Remediation Scope:** Downstream VWAP Session Filtering, Historical Contaminated Bar Count Reconciliation & Safe Dry-Run Cleanup, Test Suite Redis Isolation, Full Suite Verification  
**Lead Engineer / Auditor:** Antigravity IDE Autonomous Agent  
**Report File:** `docs/audits/phase_19_5d_vwap_integrity_report.md`  
**Overall Status:** **PASS** (Zero code regressions, surgical session filter in place, dry-run completed with zero destructive mutations)

---

## 1. Executive Summary

During Phase 19.5 live-market acceptance testing, three specific issues were investigated and addressed:
1. **Downstream VWAP Session Filtering:** `intraday_indicators.py` previously filtered session bars using only calendar date (`bar_ist.date() == session_date`) without checking regular session trading hours (`09:15:00` to `15:30:00` IST). Any pre-open or post-market bars in the list leaked directly into the volume-weighted average price calculation. This was corrected with strict `REGULAR_SESSION_START <= bar_time < REGULAR_SESSION_END` bounds checking.
2. **Reconciliation of 318 vs 371 Contaminated Bars:** Mathematical reconciliation proved with 100% precision that:
   - Exactly **265** pre-open 1m bars (5 bars each across 53 instruments from 09:10 to 09:14 IST)
   - Exactly **53** pre-open 5m bars (1 bar each across 53 instruments at 09:10 IST)
   - Exactly **53** pre-open 15m bars (1 bar each across 53 instruments at 09:00 IST)
   - Previous count **318** = 1m (265) + 5m (53), omitting 15m bars.
   - Previous count **371** = 1m (265) + 5m (53) + 15m (53), covering all intraday timeframes.
3. **Safe, Auditable Historical Bar Cleanup:** Created `market/management/commands/cleanup_contaminated_preopen_bars.py` with strict safety constraints, defaulting to a dry-run preview and requiring `--confirm` for atomic transactional execution. The fresh dry-run re-confirmed exactly 371 bars targeted across 53 instruments on `2026-10-15`, preserving all 31,325 valid regular-session bars and all daily bars. **No destructive deletion was performed**, pending explicit user review and approval.
4. **Test Isolation & Full Suite Verification:**
   - Resolved the race condition in `test_cold_cache_postgresql_fallback` where concurrent background ticker streaming leaked live ticks into shared Redis `db=1`, isolating the unit test cache lookup so PostgreSQL fallback is strictly verified without flakiness.
   - Executed full test suites across backend and frontend:
     - `market.tests`: **277 passed, 0 failed** (5.90s)
     - `llm`: **21 passed, 0 failed** (1.93s)
     - `frontend` (vitest): **85 passed across 21 test files, 0 failed** (6.28s)

---

## 2. Root Cause Analysis & Code Paths Changed

### 2.1 VWAP Session Filtering (`market/services/intraday_indicators.py`)
- **Vulnerability:** In `compute_intraday_indicators()`, lines 219–227 previously iterated over input `bars` and added any bar where `bar_ist.date() == session_date`. If pre-open or post-market bars existed on that calendar date, their price and volume entered `np.sum(typical_prices * sess_volumes) / total_vol`.
- **Downstream Consumers Traced:**
  - `market.services.intraday_detectors`:
    - `PULLBACK_IN_TREND`: Checks if price is above VWAP (`close > ind.vwap`).
    - `VWAP_BOUNCE`: Checks distance to VWAP (`abs(close - vwap) / vwap <= 0.005`).
    - `VWAP_REVERSAL`: Checks mean-reversion pull toward VWAP.
  - `market.services.intraday_signal_engine`: Sets target and stop-loss levels anchored to VWAP.
  - `llm.tools.implementations.intraday_tool`: LLM introspection tool reading VWAP snapshot.
- **Other Indicators Inspected:**
  - `compute_opening_range()` (`market/services/opening_range.py`): Already strictly guarded by `session_open <= ts_ist < or_end` (09:15 to 09:30/09:45 IST).
  - Rolling indicators (`EMA`, `RSI`, `ATR`, `MACD`): Rolling over input bar sequence; cleaning historical contaminated bars from `OHLCVBar` ensures the bar sequence begins at 09:15 IST.
- **Code Change:**
  ```python
  # market/services/intraday_indicators.py
  from market.services.market_session import IST
  from market.services.trading_session import REGULAR_SESSION_START, REGULAR_SESSION_END

  session_bars = []
  for b in bars:
      bar_ts = b.timestamp
      if bar_ts.tzinfo is None:
          bar_ts = bar_ts.replace(tzinfo=timezone.utc)
      bar_ist = bar_ts.astimezone(IST)
      if bar_ist.date() == session_date:
          bar_time = bar_ist.time()
          if REGULAR_SESSION_START <= bar_time < REGULAR_SESSION_END:
              session_bars.append(b)
  ```
  - Bounds: `09:15:00 <= time < 15:30:00` IST. Bars before 09:15:00 and bars at or after 15:30:00 are strictly excluded.
  - If only pre-open bars exist, `session_bars` is empty, `ind.vwap = None`, `ind.vwap_available = False`.

### 2.2 VWAP Regression Coverage
Two dedicated regression tests were added to `IntradayStrategyEngineTests`:
1. `test_vwap_excludes_pre_open_and_post_market_bars`:
   - Builds 10 clean regular-session bars (09:15 to 10:00 IST) and calculates `clean_vwap`.
   - Generates extreme pre-open bars (09:00, 09:05, 09:10 IST) with price 99,999 and volume 100,000,000.
   - Generates extreme post-market bars (15:30, 15:35 IST) with price 88,888 and volume 50,000,000.
   - Passes combined bar list to `compute_intraday_indicators`.
   - Asserts `ind_combined.vwap == clean_vwap`. Any leakage would distort VWAP by tens of thousands of rupees.
2. `test_vwap_all_pre_open_bars_unavailable`:
   - Supplies exclusively pre-open bars (< 09:15 IST) on `session_date`.
   - Asserts `ind.vwap_available is False` and `ind.vwap is None`.

### 2.3 Test Isolation & PostgreSQL Fallback Verification
- **Vulnerability Identified:** `test_cold_cache_postgresql_fallback` previously called `cache.clear()` and then `mgr.compute_current_context()`. Because the local Redis instance (`db=1`) is shared between the test runner and the concurrently running live ticker daemon (`run_intraday_ticker`), live ticks arriving in the millisecond between `cache.clear()` and `compute_current_context()` populated `stock_state:RELIANCE`, causing `compute_current_context()` to detect live streaming state (`source="live_stream"`) rather than exercising the PostgreSQL fallback (`source="persisted_snapshot"`).
- **Resolution:** Isolated `mgr.compute_current_context()` with `with patch.object(cache, "get", return_value=None):`.
- **Genuineness of PostgreSQL Fallback Assertion:**
  - Inside `IntradayStateManager.compute_current_context()`:
    1. Checks Redis cache keys `stock_state:{symbol}` for universe stocks.
    2. Because `cache.get()` returns `None`, `has_live_data` evaluates to `False`.
    3. The method falls back to querying PostgreSQL directly:
       - `snap = MarketContextSnapshot.objects.filter(universe=self.universe).order_by("-as_of").first()`
       - `stock_contexts = StockIntradayContext.objects.filter(timestamp=snap.as_of)`
    4. The test verifies:
       - `recovered_context["source"] == "persisted_snapshot"`
       - `recovered_context["as_of"] == past_ts.isoformat()` (the exact seeded database timestamp)
       - `recovered_context["freshness"] == "UNAVAILABLE"`
       - `recovered_context["is_fresh"] is False`
       - `recovered_context["freshness_age_seconds"] > 1000`
       - Constituent stocks list contains `"RELIANCE"`, populated directly from the PostgreSQL row.
  - This confirms that PostgreSQL fallback recovery is genuinely and deterministically verified from database models.

---

## 3. Discrepancy Reconciliation: 318 vs 371 Contaminated Bars

### 3.1 Database Environment & Field Verification
- **Database Engine:** PostgreSQL 16 (Postgres.app on macOS).
- **Session Timezone:** UTC.
- **Column Definition:** `market_ohlcvbar.timestamp` is `timestamp with time zone` (`timestamptz`).
- **Interpretation:** Stored in UTC, converted to `Asia/Kolkata` (UTC+05:30) for session evaluation.

### 3.2 Exact Record Breakdown on 2026-10-15
Querying all bars in the 2026-10-15 IST window (2026-10-14 18:30:00 UTC to 2026-10-15 18:30:00 UTC):

| Timeframe | Total Bars | Pre-Open (< 09:15 IST) | Regular Session (09:15–15:30 IST) | Post-Market (>= 15:30 IST) | Pre-Open Timestamps (IST) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1m** | 21,590 | **265** | 21,325 | 0 | 09:10:00, 09:11:00, 09:12:00, 09:13:00, 09:14:00 (5 timestamps × 53 symbols = 265) |
| **5m** | 8,245 | **53** | 8,192 | 0 | 09:10:00 (1 timestamp × 53 symbols = 53) |
| **15m** | 1,861 | **53** | 1,808 | 0 | 09:00:00 (1 timestamp × 53 symbols = 53) |
| **1d** | 6 | 2* | 4 | 0 | 08:43:57, 08:44:15 (Daily bars from YFinance; excluded from cleanup) |
| **Total Intraday** | **31,696** | **371** | **31,325** | **0** | **Total Contaminated Pre-Open Intraday Bars** |

*\*Note: Daily (`1d`) bars are broad daily records and are explicitly excluded from intraday cleanup.*

### 3.3 Root Cause of the Discrepancy
- **318 Count:** `1m` (265 bars) + `5m` (53 bars) = **318 bars**. Querying only 1m and 5m timeframes (or filtering out 15m) produced 318.
- **371 Count:** `1m` (265 bars) + `5m` (53 bars) + `15m` (53 bars) = **371 bars**. Querying all intraday timeframes produced 371.
- **Affected Instruments:** Exactly 53 instruments (49 active NIFTY 50 equities + 4 benchmarks: `^NSEI`, `^NSEBANK`, `^BSESN`, `^CNXIT`). `TATAMOTORS` was demerged and traded under `TMPV.NS`, so it did not participate in pre-open tick generation.

---

## 4. Inspection of `cleanup_contaminated_preopen_bars.py`

### 4.1 Implementation & Safety Features
1. **Targeting & Deletion Filters:**
   - Filters `timeframe__in=INTRADAY_TIMEFRAMES` (`['1m', '5m', '15m']`). Daily bars (`1d`) are NEVER queried or targeted.
   - Converts the target date to start and end UTC timestamps (`00:00:00 IST` to `23:59:59 IST`).
   - Iterates through queryset and strictly targets bars where `bar_ist.time() < REGULAR_SESSION_START` (`09:15:00 IST`).
   - Contains a hard assertion verifying no non-intraday bar exists in `target_bars`; aborts immediately if violated.
2. **IST Conversion:**
   - Utilizes `IST_TIMEZONE = ZoneInfo("Asia/Kolkata")` from `market.services.trading_session`.
   - Converts UTC timestamp to IST before checking calendar date and session start time.
3. **Transaction Handling:**
   - Deletion is wrapped in `with transaction.atomic():`.
   - Targeted rows are deleted by explicit primary key ID (`id__in=target_ids`), preventing accidental broad scans.
4. **`--confirm` Behavior:**
   - Defaults to dry-run mode unless `--confirm` is explicitly passed.
   - If `--confirm` is omitted or `--dry-run` is passed, prints full preview and exits without modifying database records.
5. **Foreign Key Integrity:**
   - Verified that `market_ohlcvbar` has 0 foreign keys referencing it. Deletions will not trigger cascading deletes or foreign key constraint errors.

### 4.2 Fresh Dry-Run Execution Results (2026-10-15)
Command executed:
```bash
./venv/bin/python manage.py cleanup_contaminated_preopen_bars --date 2026-10-15 --dry-run
```
Output:
```
================================================================================
CONTAMINATED PRE-OPEN BARS CLEANUP AUDIT
Target Session Date (IST): 2026-10-15
Mode: DRY RUN (PREVIEW ONLY)
================================================================================

[Audit Results for 2026-10-15]:
  Valid regular-session intraday bars (PRESERVED): 31325
  Contaminated pre-open intraday bars (TARGETED):   371
  Distinct Instruments Affected:                   53
  Sources:                                         NomadAggregator

[Breakdown by Timeframe]:
  - Timeframe 1m :  265 bars across 53 instruments. Timestamps (IST): ['09:10:00', '09:11:00', '09:12:00', '09:13:00', '09:14:00']
  - Timeframe 5m :   53 bars across 53 instruments. Timestamps (IST): ['09:10:00']
  - Timeframe 15m:   53 bars across 53 instruments. Timestamps (IST): ['09:00:00']

[DRY RUN SUMMARY]: 371 bars WOULD BE DELETED.
No changes were made to the database.
To execute transactional deletion, rerun with: --date 2026-10-15 --confirm
```
**Status:** Re-verified. Exactly 371 contaminated bars targeted. All 31,325 regular session bars preserved. **Zero deletions executed.**

---

## 5. Complete Test Suite Execution Results

### 5.1 Test Results Summary

| Suite | Scope | Command | Total Tests | Passed | Failed | Duration |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Market App** | Full `market.tests` | `./venv/bin/python manage.py test market.tests` | 277 | **277** | 0 | 5.904s |
| **LLM App** | Full `llm` | `./venv/bin/python manage.py test llm` | 21 | **21** | 0 | 1.929s |
| **Frontend** | Vitest unit/integration | `npm test` (in `frontend/`) | 85 (21 files) | **85** | 0 | 6.280s |
| **Targeted Regressions** | VWAP, Cold Cache, Cleanup | `./venv/bin/python manage.py test market.tests.IntradayStrategyEngineTests.test_vwap_excludes_pre_open_and_post_market_bars market.tests.IntradayStrategyEngineTests.test_vwap_all_pre_open_bars_unavailable market.tests.Phase19CorePipelineRemediationTests.test_cold_cache_postgresql_fallback market.tests.Phase19CorePipelineRemediationTests.test_cleanup_contaminated_preopen_bars_command` | 4 | **4** | 0 | 0.171s |
| **Combined Total** | **All System Suites** | — | **387** | **387** | **0** | **~14.28s** |

---

## 6. Repository Status & Working Tree Integrity

### 6.1 Working Tree Status
```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  modified:   market/services/intraday_aggregator.py    (P2 tick-level session boundary filter from Phase 19.5)
  modified:   market/services/intraday_indicators.py    (P4 VWAP regular-session filter: 09:15 <= t < 15:30 IST)
  modified:   market/services/kite_registry.py          (P3 benchmark token mapping from Phase 19.5)
  modified:   market/services/recommendation_service.py (P1 intraday rec persistence from Phase 19.5)
  modified:   market/tasks.py                           (P1 intraday Celery task from Phase 19.5)
  modified:   market/tests.py                           (Phase 19.5 & 19.5D test isolation & regression tests)

Untracked files:
  docs/audits/phase_19_5_independent_diff_audit.md
  docs/audits/phase_19_5_remediation_report.md
  docs/audits/phase_19_5d_vwap_integrity_report.md
  market/management/commands/cleanup_contaminated_preopen_bars.py
```

### 6.2 Invariants Preserved
- Unrelated files: restored `data/universe/kite_nifty50_mapping.json` to pristine working tree state.
- Zero Git commits, resets, rebases, or branch changes made.
- Zero changes to scoring engine weights or opportunity ranking logic.
- Zero unapproved deletions in database.

---

## 7. Acceptance Criteria Matrix

| Criterion | Requirement | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. Cleanup Command Inspection** | Verify deletion filters, IST conversion, atomic transaction handling, and `--confirm` safety | **PASS** | Inspected `cleanup_contaminated_preopen_bars.py`: strictly bounds timeframes to `1m, 5m, 15m`, checks `bar_ist.time() < 09:15:00`, wraps in `transaction.atomic()`, defaults to dry-run. |
| **2. Fresh Dry-Run Execution** | Re-run dry run for 2026-10-15 and verify exact target of 371 bars | **PASS** | Output verified: exactly 371 bars targeted (265 1m, 53 5m, 53 15m) across 53 instruments; 31,325 regular session bars and daily bars untouched. |
| **3. Zero Deletion Before Approval** | Do not execute deletion until explicitly approved | **PASS** | Database remains unchanged. All 371 contaminated bars remain available for confirmed execution upon operator approval. |
| **4. Full Test Suites Execution** | Run `market.tests`, `llm`, and frontend tests; report exact results | **PASS** | `market.tests`: 277/277 passed; `llm`: 21/21 passed; frontend: 85/85 passed across 21 files. Zero failures. |
| **5. VWAP Regression Coverage** | Ensure VWAP excludes pre-open and post-market bars | **PASS** | `test_vwap_excludes_pre_open_and_post_market_bars` and `test_vwap_all_pre_open_bars_unavailable` passed; verified 0 impact from extreme out-of-session bars. |
| **6. PostgreSQL Fallback Verification** | Confirm cache-isolation test genuinely exercises PostgreSQL fallback | **PASS** | `test_cold_cache_postgresql_fallback` passed; verified assertion of `source="persisted_snapshot"`, `as_of=past_ts`, and stock recovery from database models. |
| **7. Clean Working Tree** | No commits, pushes, or modifications to unrelated files | **PASS** | Restored `kite_nifty50_mapping.json`; only Phase 19.5/19.5D files modified; zero commits made. |

---

## 8. Remaining Risks & Recommended Next Steps

1. **Database Contaminated Bar Deletion Approval:**
   - Execute confirmed cleanup once approved:
     ```bash
     ./venv/bin/python manage.py cleanup_contaminated_preopen_bars --date 2026-10-15 --confirm
     ```
   - This will remove the 371 pre-open bars from PostgreSQL `market_ohlcvbar`.
2. **Commit Working Tree Changes:**
   - Stage and commit the Phase 19.5 and Phase 19.5D changes and audit documentation:
     ```bash
     git add market/services/intraday_aggregator.py \
             market/services/intraday_indicators.py \
             market/services/kite_registry.py \
             market/services/recommendation_service.py \
             market/tasks.py \
             market/tests.py \
             market/management/commands/cleanup_contaminated_preopen_bars.py \
             docs/audits/phase_19_5_remediation_report.md \
             docs/audits/phase_19_5_independent_diff_audit.md \
             docs/audits/phase_19_5d_vwap_integrity_report.md
     git commit -m "fix(market): remediate intraday pipeline gaps, VWAP session boundaries, and pre-open cleanup"
     ```
