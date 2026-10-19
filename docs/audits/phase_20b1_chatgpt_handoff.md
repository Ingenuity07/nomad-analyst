# Nomad Analyst — Phase 20B.1 ChatGPT Handoff Document

**Date:** 16 October 2026, 13:06 IST (Continuous Trading Session Open)  
**Task:** Independent Reliability Audit of Phase 20B Implementation & Claims  
**Audit Artifact:** `docs/audits/phase_20b1_independent_audit_report.md`  

---

## 1. Executive Verdict & Summary

- **Verdict:** **CONDITIONAL ACCEPTANCE (1 SEVERE CODE DEFECT, 2 OPERATIONAL RISKS)**
- **Audit Constraints Maintained:**
  - Zero code, tests, database records, credentials, or configs modified.
  - Zero live processes restarted or disconnected.
  - Zero commits or git resets.
  - All findings verified against actual database records, source code, and isolated tests.

---

## 2. PASS / FAIL / NOT VERIFIED Audit Matrix

| Verification Item | Target Component | Verdict | Summary of Finding |
| :--- | :--- | :---: | :--- |
| **Duplicate Process Locking** | `run_intraday_ticker.py` | **PASS / RISK** | Isolated test confirms `BlockingIOError` blocks duplicate startup. *Risk:* Mode `"w"` truncates PID file before lock check. |
| **Lock Cleanup on Shutdown** | `finally` in command | **PASS** | `fcntl.flock(LOCK_UN)`, close, and `os.remove` executed cleanly in outer `finally`. |
| **Watchdog Backoff** | Outer loop in command | **PASS** | Exponential backoff $[2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]$ verified with structured warning/success logs. |
| **Subscription Restoration** | `manager.subscribed_tokens` | **PASS** | All 54 tokens preserved in `manager.subscribed_tokens` and resubscribed in `MODE_FULL` upon reconnect. |
| **Live Disconnect Recovery** | WebSocket drop recovery | **NOT VERIFIED** | Live ticker (`PID 49422`) has remained connected continuously since 11:30 AM without drops; live recovery cannot be tested destructively. |
| **Completed Candle Rule** | $T_{start} \le as\_of - \Delta T$ | **PASS** | Correctly filters in-progress bars at DB query level (`max_completed_start = as_of - delta_t`). |
| **Grid Boundary Alignment** | Seconds & modulo minute | **PASS** | Rejects unaligned seconds (`11:34:50`) and non-boundary minutes (`(min - 15) % interval == 0`). |
| **Pre-Open / Off-Session Bars** | Regular session filtering | **FAIL** | **Severe Defect:** `_load_completed_bars` does not check `09:15 <= time < 15:30`. 2,703 existing off-session bars can enter signal generation. |
| **Provider Precedence** | Aggregator > KiteHist > YF | **PASS** | Applied per timestamp `ts` in `selected_by_ts`. Real-time `NomadAggregator` bars supersede external feeds. |
| **Stale Override Protection** | Cross-timestamp independence | **PASS** | Precedence strictly isolated to identical timestamps. Stale 10:00 bar cannot override newer 11:30 candle. |
| **Zero-Volume Bar Support** | Legitimate $V=0$ bars | **PASS** | Tested and verified: completed zero-volume bars (indices, illiquid intervals) are preserved. |
| **Gate 2 Staleness Lag** | Completion timestamp lag | **PASS** | Evaluated against $T_{start} + \Delta T$, eliminating false-positive stale flags for longer intervals. |
| **Intraday Engine Gates** | Readiness, R:R, Cooldown | **PASS** | Gate 1 (Readiness), Gate 4 (Dead tape), Gate 5 (ATR ratio), Gate 6 (Cooldown), Gate 7 ($RR \ge 1.5$) fully intact. |
| **Snapshot Arithmetic** | $10,080 + 300 + 80 + 100 = 10,560$ | **PASS** | 100% verified against exact database timestamps. Current count: 10,980. Every batch has exactly 20 rows. |
| **Actionable Recommendations**| ONGC (`SELL`) & TECHM (`BUY`)| **PASS** | Both records verified in PostgreSQL: `horizon="INTRADAY"`, `strategy_version="1.0"`, all fields populated, no swing substitution. |
| **Zero-LLM Invariant** | Background strategy scan | **PASS** | Deterministic technical indicators only (`llm_explanation=None`). |
| **Test Suites** | Unit & Integration | **PASS** | 14 targeted tests passed (0.118s), 314 market tests passed (6.091s), 85 frontend tests passed (7.17s). |

---

## 3. Key Issues Requiring Remediation

### A. [Severe Defect] Pre-Open & Off-Session Bar Leakage in `_load_completed_bars()`
- **Diagnosis:** `_load_completed_bars()` filters candidate bars using `(b_ist.minute - 15) % interval_minutes != 0`.
- **The Defect:** For 1m bars and for 5m bars starting at `09:10:00`, `(10 - 15) % 5 = -5 % 5 = 0`. Because there is no check that `b_ist.time() >= time(9, 15)` and `b_ist.time() < time(15, 30)`, pre-open bars (< 09:15) and post-market bars (> 15:30) pass the filter!
- **Evidence:** 2,703 off-session bars currently exist in `OHLCVBar`. Querying `ADANIENT` 1m bars at `09:25:00` loaded 15 bars, including 5 pre-open bars from `09:10:00` through `09:14:00`.
- **Remediation Needed:** Add explicit session time window checks in `_load_completed_bars`:
  ```python
  if b_ist.time() < time(9, 15) or b_ist.time() >= time(15, 30):
      continue
  ```

### B. [Operational Risk] PID File Truncation via `open(..., "w")`
- **Diagnosis:** In `run_intraday_ticker.py:L70`, `open(lock_file_path, "w")` truncates `/tmp/nomad_intraday_ticker.pid` before `fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)` is called.
- **Impact:** When a second command is launched, it gets blocked with `BlockingIOError` as expected, but it truncates the active PID in the file to 0 bytes.
- **Remediation Needed:** Use `os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)` or `open(lock_file_path, "a+")`, acquire the flock, and then truncate/write the PID.

### C. [Operational Note] Active Production Process Divergence
- Active daemon `PID 49422` was started at `11:30:33 IST`, prior to Phase 20B edits. To avoid dropping the production feed during market hours, it was not restarted. Consequently, `/tmp/nomad_intraday_ticker.pid` does not exist on disk during this session. A clean restart after market close will activate the file lock.

---

## 4. Verification Evidence & Test Commands

1. **Targeted Tests:**
   ```bash
   ./venv/bin/python manage.py test market.tests.Phase20A1IntradayWarmupAndReadinessTests market.tests.Phase20BRuntimeReliabilityTests
   ```
   **Result:** 14 passed in 0.118s (0 failures, 0 errors).

2. **Market App Suite:**
   ```bash
   ./venv/bin/python manage.py test market
   ```
   **Result:** 314 passed in 6.091s (0 failures, 0 errors).

3. **Frontend Suite:**
   ```bash
   cd frontend && npm test
   ```
   **Result:** 21 test files passed, 85 tests passed in 7.17s (0 failures, 0 errors).
