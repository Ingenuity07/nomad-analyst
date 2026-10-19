# Nomad Analyst — Phase 20B.1: Independent Reliability Audit Report

**Date & Time:** 2026-10-16 13:06:00 IST  
**Auditor:** Antigravity Autonomous Engineering Agent (Independent Reviewer)  
**Target Artifacts Under Audit:**
- `docs/audits/phase_20b_runtime_reliability_report.md`
- `docs/audits/phase_20b_chatgpt_handoff.md`
- Implementation in:
  - `market/management/commands/run_intraday_ticker.py`
  - `market/services/kite_ticker.py`
  - `market/services/intraday_signal_engine.py`
  - `market/tests.py` (`Phase20BRuntimeReliabilityTests`)

---

## 1. Executive Summary & Acceptance Recommendation

### 1.1 Acceptance Recommendation: **CONDITIONAL ACCEPTANCE (WITH 1 SEVERE DEFECT AND 2 RUNTIME RISKS)**
Phase 20B achieved major architectural advances in ticker lifecycle management, authoritative PIT-safe candle deduplication, and snapshot auditing. However, independent static and dynamic verification revealed **one code defect** in regular-session bar filtering and **two operational risks** regarding advisory process locking and multi-threaded reconnect calls:

1. **[DEFECT — High Impact] Missing Pre-Open / Off-Session Guard in `_load_completed_bars()`:**
   - `_load_completed_bars()` filters timestamps using `second == 0 and microsecond == 0` and `(minute - 15) % interval == 0`.
   - It **omits** a session window check (`09:15 <= b_ist.time() < 15:30`).
   - For `1m` bars and `5m` bars (e.g. `09:10:00` where `(10 - 15) % 5 == 0`), pre-open and post-market bars pass into regular signal generation. Currently, **2,703 off-session bars** exist in the database from morning setup testing and enter candidate selection.
2. **[RISK — Process Locking] Lock Truncation via `open(..., "w")`:**
   - In `run_intraday_ticker.py`, the lock is opened via `open(lock_file_path, "w")`. In Unix/macOS, opening with mode `"w"` truncates the file *before* `fcntl.flock(LOCK_EX | LOCK_NB)` is evaluated.
   - When a second process attempts to start and is rejected with `BlockingIOError`, it wipes the PID written by the active daemon in `/tmp/nomad_intraday_ticker.pid` to 0 bytes (`""`).
3. **[STATUS — Live Process Divergence] Active Production Daemon Started Prior to Phase 20B:**
   - The active live ticker process (`PID 49422`) was launched at `11:30:33 IST`, prior to Phase 20B modifications. In accordance with zero-disruption constraints, the production daemon was not restarted. Therefore, `PID 49422` is running without the `/tmp/nomad_intraday_ticker.pid` lock file held on the filesystem.

---

## 2. PASS / FAIL / NOT VERIFIED Verification Matrix

| Area | Item / Verification Goal | Target Component | Status | Evidence / Technical Finding |
| :--- | :--- | :--- | :---: | :--- |
| **1. Ticker Lifecycle** | **Duplicate Startup Rejection** | `run_intraday_ticker.py` | **PASS (Logic)** / **RISK** | Isolated test confirmed: second process raised `BlockingIOError` and exited. *Risk:* Mode `"w"` truncates PID file before lock check. |
| | **Lock Acquisition After Release** | `run_intraday_ticker.py` | **PASS** | Lock acquisition succeeds immediately once releasing process calls `LOCK_UN` and closes handle. |
| | **Thread-Safe Reconnect** | `KiteTickerManager._connect_lock` | **PASS (Loop)** / **WARN (API)** | Single-threaded watchdog in command serializes retries safely. At raw API level, `reconnect()` does not set in-flight state prior to callback. |
| | **Subscription Restoration** | `manager.subscribed_tokens` | **PASS** | Verified all 54 instruments are preserved in `manager.subscribed_tokens` and resubscribed in `MODE_FULL` upon reconnect. |
| | **Exponential Backoff** | Outer watchdog retry loop | **PASS** | Progression verified: $[2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]$; no busy-looping observed. |
| | **Graceful Shutdown** | `SIGINT`/`SIGTERM` handlers | **PASS** | Verified `stop()` sets `_stop_requested=True`, marks `is_connected=False`, and closes Twisted client cleanly. |
| | **Live Production Disconnect** | Real socket drop recovery | **NOT VERIFIED** | WebSocket feed has remained stable without involuntary disconnects since 11:30 AM (`PID 49422`). Unverified on real network failure. |
| **2. Candle Integrity** | **Completion Calculation** | $T_{start} \le as\_of - \Delta T$ | **PASS** | Evaluates $T_{start} + \Delta T \le as\_of$ accurately across timeframes ($5\text{m}, 15\text{m}$). |
| | **Incomplete Bar Exclusion** | In-progress bar rejection | **PASS** | Incomplete candles are excluded at DB query level (`timestamp__lte=max_completed_start`). |
| | **Timeframe Grid Alignment** | IST minute & second check | **PASS** | Rejects unaligned seconds (`11:34:50`) and unaligned minutes (`(min - 15) % interval == 0`). |
| | **Pre-Open / Post-Market Exclusion**| Regular session filtering | **FAIL** | **Defect:** `_load_completed_bars` does not check `09:15 <= time < 15:30`. 2,703 off-session bars loaded if present. |
| | **Provider Precedence** | Aggregator > KiteHist > YFinance | **PASS** | Implemented per timestamp in `selected_by_ts`. Real-time `NomadAggregator` bars supersede external feeds. |
| | **Stale Override Protection** | Cross-timestamp independence | **PASS** | Precedence only applies across bars with identical timestamps. A stale bar from 10:00 cannot override a newer bar from 11:30. |
| | **Deterministic Tie-Breaking** | Duplicate timestamps same rank | **PASS (DB Order)**| Deterministic according to DB query order (`order_by("-timestamp")`). |
| | **Zero-Volume Support** | Legitimate $V=0$ bars | **PASS** | Tested and verified: aligned completed bars with $V=0$ (e.g. indices) are preserved. |
| | **Gate 2 Staleness Anchoring** | Completion timestamp lag | **PASS** | Measured against $T_{start} + \Delta T$, eliminating false-positive stale flags for longer intraday candles. |
| | **Engine Gate Preservation** | Readiness, R:R, Cooldown | **PASS** | Gate 1 (Readiness), Gate 4 (Dead tape), Gate 5 (ATR ratio), Gate 6 (Cooldown), Gate 7 ($RR \ge 1.5$) remain intact. |
| **3. Snapshots** | **Arithmetic Reconciliation** | $10,080 + 300 + 80 + 100 = 10,560$ | **PASS** | Verified against exact database timestamps. Current count: 10,980. Every batch has exactly 20 rows. |
| **4. Recommendations**| **ONGC & TECHM Verification** | Persisted records in DB | **PASS** | Both records verified: `horizon="INTRADAY"`, `strategy_version="1.0"`, all trade fields populated. |
| | **Zero-LLM Invariant** | Background strategy scan | **PASS** | Deterministic technical indicators only (`llm_explanation=None`). |
| **5. Test Suites** | **Targeted & Full Suites** | `market` & `frontend` | **PASS** | 14 targeted tests pass (0.118s), 314 market tests pass (6.091s), 85 frontend tests pass (7.17s). |

---

## 3. Detailed Audit Findings

### 3.1 Section 1: Ticker Lifecycle & Reconnection
1. **Advisory Process Locking:**
   - Located in [run_intraday_ticker.py:L68-L82](file:///Users/shivamsingh/personal/nomad-analyst/market/management/commands/run_intraday_ticker.py#L68-L82):
     ```python
     lock_file_path = "/tmp/nomad_intraday_ticker.pid"
     try:
         lock_file = open(lock_file_path, "w")
         fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
         lock_file.write(str(os.getpid()))
         lock_file.flush()
     except (BlockingIOError, IOError): ...
     ```
   - **Finding (Unresolved Risk):** `open(lock_file_path, "w")` truncates the file immediately upon opening before acquiring the lock. When a second process attempts to acquire the lock, it raises `BlockingIOError` (blocking startup correctly), but truncates the existing file to 0 bytes.
   - **Recommended Fix for Future Phase:** Use `os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)` or `open(lock_file_path, "a+")`, acquire the flock, and then truncate/write PID.
2. **Runtime Process Status:**
   - Active process `PID 49422` was started at `11:30:33 IST`, before Phase 20B was applied. The lock file `/tmp/nomad_intraday_ticker.pid` does not exist on disk because `PID 49422` never executed the new startup routine.
3. **Watchdog & Reconnect:**
   - Thread-safety is enforced in `KiteTickerManager.reconnect()` using `with self._connect_lock:`.
   - The outer loop in `run_intraday_ticker.py` implements bounded exponential backoff ($2.0\text{s} \to 60.0\text{s}$ ceiling) and successfully resubscribes all 54 instruments in `MODE_FULL` via `_on_connect`.

---

### 3.2 Section 2: Authoritative Completed Candle Selection
1. **Completed Bar Logic ($T_{start} + \Delta T \le as\_of$):**
   - Correctly implemented in [intraday_signal_engine.py:L386-L399](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_signal_engine.py#L386-L399):
     `max_completed_start = as_of - delta_t`
     `OHLCVBar.objects.filter(..., timestamp__lte=max_completed_start)`
2. **Defect Identified: Session Boundary Omission:**
   - Lines 420-427 check:
     `b_ist.second != 0 or b_ist.microsecond != 0`
     `(b_ist.minute - 15) % interval_minutes != 0`
   - **Missing Guard:** There is no check that `time(9, 15) <= b_ist.time() < time(15, 30)`.
   - **Empirical Evidence:** A query of the database revealed **2,703 intraday bars** outside `09:15-15:30 IST` on 2026-10-15 and 2026-10-16.
   - Calling `_load_completed_bars(ADANIENT, "1m", as_of=2026-10-15 09:25:00)` loaded 15 bars, including pre-open bars from `09:10:00`, `09:11:00`, `09:12:00`, `09:13:00`, and `09:14:00`.
   - **Smallest Required Test Case to Add (in next phase):**
     ```python
     def test_completed_bars_excludes_preopen_and_postmarket_bars(self):
         ts_pre = datetime(2026, 10, 16, 9, 10, 0, tzinfo=self.IST)
         OHLCVBar.objects.create(instrument=self.instrument, timeframe="5m", timestamp=ts_pre, ...)
         as_of = datetime(2026, 10, 16, 9, 25, 0, tzinfo=self.IST)
         bars = engine._load_completed_bars(self.instrument, "5m", as_of)
         self.assertNotIn(ts_pre, [b.timestamp for b in bars])
     ```
3. **Source Precedence & Staleness:**
   - Source precedence hierarchy (`NomadAggregator` > `KiteHistoricalProvider` > `YFinanceMarketProvider`) operates strictly within identical timestamp buckets (`selected_by_ts[ts]`). Stale external candles cannot displace newer completed aggregator candles.
   - Gate 2 measures lag against `bar_completion_time = latest_bar.timestamp + delta_t`. Verified PASS.

---

### 3.3 Section 3: Snapshot Count Reconciliation
The formula $10,080 + 300 + 80 + 100 = 10,560$ was independently audited against all 549 distinct batch timestamps:

| Batch Group | IST Window | Batches | Rows/Batch | Total Rows | Running Count |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Initial Audit Baseline** | Up to Oct 15 17:37:25 IST | 504 | 20 | 10,080 | 10,080 |
| **Oct 15 Late / Overnight** | Oct 15 23:00 – Oct 16 04:15 IST | 15 | 20 | +300 | 10,380 |
| **Oct 16 Morning Pre-Restart** | Oct 16 11:20:28 – 11:23:29 IST | 4 | 20 | +80 | 10,460 |
| **Oct 16 Post-Restart (Batch 1–5)**| Oct 16 11:31:26 – 11:35:27 IST | 5 | 20 | +100 | **10,560** |
| **Subsequent Live Batches** | Oct 16 11:36:27 – 11:56:34 IST | 21 | 20 | +420 | 10,980 |

- Every single batch persisted by `IntradayStateManager.persist_snapshots()` contains exactly 20 records.
- Zero rows were deleted or corrupted; the arithmetic is verified.

---

### 3.4 Section 4: Recommendation Path & Zero-LLM Invariant
1. **Inspected Records in PostgreSQL:**
   - **ONGC (`f07fbe7d-759d-4061-858f-c9b6d36a4be0`):**
     `horizon="INTRADAY"`, `signal="SELL"`, `setup_type="VWAP_REJECTION"`, `strategy_version="1.0"`, `session_window="MIDDAY"`, `entry_price=223.72`, `stop_price=224.41`, `target_price=222.59`, `target_2_price=222.37`, `risk_reward_ratio=1.64`.
   - **TECHM (`946d2a28-1a3f-4951-a6e4-bbb3aa036d87`):**
     `horizon="INTRADAY"`, `signal="BUY"`, `setup_type="INTRADAY_PULLBACK"`, `strategy_version="1.0"`, `session_window="MIDDAY"`, `entry_price=1760.80`, `stop_price=1751.48`, `target_price=1776.02`, `target_2_price=1779.07`, `risk_reward_ratio=1.63`.
2. **Absence of Swing Engine Substitution:**
   - Swing engine uses `horizon="DELIVERY_SWING"` and does not populate `session_window`, `timeframe`, or `target_2_price`. The verified records originated directly from `IntradaySignalEngine` and `RecommendationService.save_draft()`.
3. **Zero-LLM Invariant:**
   - `llm_explanation` is `None` on all persisted intraday recommendation records.
   - Code path in `tasks.py::run_intraday_strategy_scan` uses deterministic technical indicator calculations without any LLM invocations.

---

## 4. Test Execution & Suite Results

### 4.1 Backend Targeted Tests
- **Command:** `./venv/bin/python manage.py test market.tests.Phase20A1IntradayWarmupAndReadinessTests market.tests.Phase20BRuntimeReliabilityTests`
- **Result:** **14 passed in 0.118s (0 failures, 0 errors)**.

### 4.2 Backend Market App Suite
- **Command:** `./venv/bin/python manage.py test market`
- **Result:** **314 passed in 6.091s (0 failures, 0 errors)**.

### 4.3 Frontend Test Suite
- **Command:** `npm test` (in `frontend/`)
- **Result:** **21 test files passed, 85 tests passed in 7.17s (0 failures, 0 errors)**.

---

## 5. Working Tree Inventory
Per audit constraints, zero files were modified, committed, or discarded during this audit.
- **Git status:** Clean relative to Phase 20B state. Uncommitted working changes from Phase 19/20 are preserved untouched.
