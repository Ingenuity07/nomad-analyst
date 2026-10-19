# Nomad Analyst — Phase 20B.2: Session Integrity & Process-Lock Audit Report

**Date:** 2026-10-16  
**Status:** COMPLETE (Automated Tests Verified, Production Preserved)  
**Target Files:**  
- `market/services/intraday_signal_engine.py` (Fix A: Off-session candle filter)  
- `market/management/commands/run_intraday_ticker.py` (Fix B: Non-truncating process lock)  
- `market/tests.py` (Regression test suite)

---

## 1. Executive Summary

During Phase 20B runtime auditing, two critical edge-case integrity defects were identified:
1. **Off-Session Candle Leakage:** In `_load_completed_bars()`, bars were filtered for boundary alignment (second=0, microsecond=0) and interval alignment (`(minute - 15) % interval == 0`), but lacked an explicit bounding filter for the NSE continuous equity trading window (`09:15:00` to `15:30:00` IST). Any pre-open auction bars (e.g. `09:10:00` from external feeds or earlier backfills) or post-market closing bars (e.g. `15:30:00+`) could pass into signal calculations and distort intraday indicators like session VWAP.
2. **PID Lock Truncation:** In `run_intraday_ticker.py`, the process lock opened the file using mode `"w"`. Because standard filesystem semantics truncate the file on open before `fcntl.flock()` is invoked, a second ticker process attempting startup would wipe the active PID in the lock file to 0 bytes before being blocked by `BlockingIOError`.

Both defects have been remediated cleanly in code and validated through automated regression tests, with **zero disturbance to the running live ticker daemon**.

---

## 2. Fix A — Off-Session Candle Leakage Remediation

### Implementation Details
In `market/services/intraday_signal_engine.py`, `_load_completed_bars()` now enforces strict session boundary validation in Asia/Kolkata (IST):

```python
for b in raw_bars:
    b_ist = b.timestamp.astimezone(ist)

    # Check regular session trading window in IST (09:15 to 15:30)
    # Strictly reject pre-open (< 09:15) and post-market / closing auction (>= 15:30) bars.
    b_time = b_ist.time()
    if b_time < time(9, 15) or b_time >= time(15, 30):
        continue
```

### Guarantees
- **Provider-Agnostic:** Applied at the head of the candidate filter loop across all sources (`NomadAggregator`, `KiteHistoricalProvider`, `YFinanceMarketProvider`).
- **Preserved Properties:** Retains candle completion cutoff (`timestamp <= as_of - delta_t`), grid alignment, source precedence ranking, and zero-volume bar preservation.
- **No Historical Data Mutation:** Does not delete, modify, or rewrite any database records.

### Regression Test Coverage
Added to `Phase20BRuntimeReliabilityTests`:
1. `test_completed_bars_rejects_preopen_and_postmarket_bars`:
   - **5-minute timeframe:** Rejects `09:10:00` (pre-open), accepts `09:15:00`, accepts `11:30:00`, accepts `15:25:00`, rejects `15:30:00` (closing boundary), rejects `15:35:00` (post-market).
   - **1-minute timeframe:** Rejects `09:14:00`, accepts `09:15:00`, accepts `15:29:00`, rejects `15:30:00`, rejects `16:00:00`.
   - **Timezone conversion:** Evaluates timestamps stored in UTC (`astimezone(ZoneInfo("UTC"))`) against IST session boundaries.
2. `test_preopen_bars_cannot_contaminate_vwap_calculations`:
   - Seeds a pre-open bar at `09:10:00` with an extreme outlier price (`200.0`, volume `100,000`) alongside regular trading bar at `09:15:00` (`100.0`).
   - Asserts that `_load_completed_bars()` excludes the pre-open bar and that `compute_intraday_indicators()` produces a pure session VWAP of `100.0`.

---

## 3. Fix B — PID Lock Truncation Remediation

### Implementation Details
In `market/management/commands/run_intraday_ticker.py`, the lock acquisition sequence was restructured:

```python
lock_file_path = "/tmp/nomad_intraday_ticker.pid"
try:
    # Open without truncation so existing lock PID is preserved if another daemon holds it
    lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)
    lock_file = open(lock_fd, "r+", closefd=True)
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Only truncate and write PID AFTER exclusive lock is safely acquired
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
except (BlockingIOError, IOError):
    try:
        if "lock_file" in locals() and not lock_file.closed:
            lock_file.close()
    except Exception:
        pass
    self.stderr.write(
        self.style.ERROR(
            f"Error: Another run_intraday_ticker daemon is already running (locked via {lock_file_path}). "
            "Aborting startup to prevent duplicate WebSocket connections and duplicate ticker processes."
        )
    )
    return
```

### Guarantees
- **Atomic Pre-Lock Preservation:** An existing active daemon's PID written in `/tmp/nomad_intraday_ticker.pid` is never truncated or overwritten by an aborting startup attempt.
- **Clean Unlock & Cleanup:** If the running daemon terminates or handles SIGINT/SIGTERM, outer `finally:` cleanly executes `LOCK_UN`, closes the descriptor, and unlinks the PID file.
- **Idempotent Restart:** Subsequent valid daemon invocations cleanly acquire the lock file.

### Regression Test Coverage
Added to `Phase20BRuntimeReliabilityTests`:
- `test_process_locking_guards_against_duplicate_daemons_and_preserves_pid`:
  - Process 1 creates lock file with PID `12345` and acquires exclusive lock.
  - Process 2 attempts startup on the same file, catching `BlockingIOError`.
  - Asserts that lock file content remains exactly `"12345"` (0 byte truncation prevented).
  - Process 1 releases lock and unlinks.
  - Process 3 attempts startup, acquiring the lock cleanly and writing `"67890"`.

---

## 4. Test Suite Execution Evidence

### 1. Targeted Phase 20B Regression Suite
```bash
./venv/bin/python manage.py test market.tests.Phase20BRuntimeReliabilityTests
```
**Output:**
```
Found 10 test(s).
Creating test database for alias 'default'...
Creating test database for alias 'telemetry'...
..........
----------------------------------------------------------------------
Ran 10 tests in 0.083s

OK
```

### 2. Intraday Strategy & Readiness Suite
```bash
./venv/bin/python manage.py test market.tests.IntradayStrategyEngineTests market.tests.Phase20A1IntradayWarmupAndReadinessTests market.tests.Phase20BRuntimeReliabilityTests
```
**Output:**
```
Found 58 test(s).
----------------------------------------------------------------------
Ran 58 tests in 0.323s

OK
```

### 3. Full Market Test Suite
```bash
./venv/bin/python manage.py test market
```
**Output:**
```
Found 316 test(s).
----------------------------------------------------------------------
Ran 316 tests in 5.622s

OK
```

---

## 5. Operational Constraints Verification

- **Production Continuity:** The production ticker process (`PID 85066` / active daemon) was neither killed nor restarted during market hours.
- **Scope Discipline:** No changes made to scoring formulas, readiness evaluation thresholds, risk/reward logic, or LLM routing.
- **Git State:** No commits or pushes made. All working-tree changes preserved intact.
- **Security:** Zero tokens, passwords, or credentials exposed.
