# Phase 22D — F&O Paper Execution Quote-Freshness Guard Remediation Report

**Date:** 2026-10-19  
**Repository:** `Ingenuity07/nomad-analyst`  
**Reviewed GitHub Baseline Commit:** `2df52f93b83504a78d0745dc79d60bf4c9165390`  
**Implementation Working Tree Commit:** `2df52f93b83504a78d0745dc79d60bf4c9165390` (uncommitted working tree modifications in `fno/`)  
**Scope:** F&O Paper Execution Quote-Freshness and Microstructure Safety Fix  
**Safety Boundary:** Simulated taker paper trading only. No live broker order capability enabled or invoked.

---

## 1. Executive Summary

This remediation resolves the quote-freshness safety gap identified in Phase 22D. Prior to this fix, the paper execution engine accepted limit order book quotes based merely on persisted ingestion-time flags (`is_stale=False`), without re-evaluating quote age at the execution decision boundary. Additionally, the exit order path lacked symmetrical quote eligibility validation (relying solely on zero/tiny-bid checks), creating a risk that stale, locked, crossed, or wide-spread quotes could close positions or distort simulated execution.

The engine, strategy validator, and feature snapshot generator have been upgraded with a unified quote-freshness policy enforcing dynamic age recalculation against an explicit validation clock, fail-closed timezone validation, symmetrical exit gating with `PENDING_LIQUIDITY` exposure preservation, and mutual consistency across metadata flags.

---

## 2. Root Cause & Before/After Behavior

### Finding A — Ingestion-Time Stale Flag Trusted at Decision Boundary
* **Root Cause:** `_check_quote_execution_eligibility()` in `fno/execution/paper_engine.py` only checked whether `quote.is_stale` or `quote.quote_status == "STALE"`. It never computed the elapsed duration between `quote.exchange_timestamp_utc` and the execution decision time. A quote ingested with `is_stale=False` could age several minutes in memory or the database and still be filled at obsolete prices.
* **Remediation:** `_check_quote_execution_eligibility()` now dynamically recalculates quote age against the decision clock (`decision_time - quote.exchange_timestamp_utc`). If elapsed time exceeds `QUOTE_FRESHNESS_LIMIT_SEC = Decimal("3.0")`, the quote is rejected with `REJECTED_STALE_QUOTE`.

### Finding B — Asymmetric Entry and Exit Gating
* **Root Cause:** `_handle_exit_signal()` only checked for missing execution timestamps, zero bids, and bids below slippage. Stale, locked, crossed, future-timestamped, timezone-ambiguous, or excessive-spread quotes were not evaluated before calculating fills and closing trades.
* **Remediation:** `_handle_exit_signal()` now executes `_check_quote_execution_eligibility(..., is_exit=True)`. When an exit quote is ineligible, the open trade transitions to `PENDING_LIQUIDITY` (preserving in-memory active tracking and DB ledger exposure), records the exact rejection code, and creates zero fills, zero fees, and zero realized P&L.

### Finding C — Clock Provenance and Separation
* **Root Cause:** The engine conflated matching engine event time with validation clock time.
* **Remediation:** 
  1. `PaperExecutionEngine` accepts a pluggable clock callable (`clock: Optional[Callable[[], datetime]] = None`), defaulting safely to UTC wall time (`lambda: datetime.now(timezone.utc)`).
  2. Public execution methods accept an explicit `validation_time: Optional[datetime] = None` for deterministic backtests and simulations.
  3. Authoritative matching engine event time (`execution_time`) is preserved for transaction recording, while decision time is strictly isolated for quote age recalculation.

### Finding D — Strategy Snapshot Validation Gaps
* **Root Cause:** `SignalValidator.validate_snapshot_eligibility()` only verified `snapshot.is_stale`. Inconsistent snapshots (`is_stale=False` while `is_quote_fresh=False`, quote age > 3.0s, negative age, or timezone-naive timestamps) were not rejected.
* **Remediation:** `SignalValidator` now validates `quote_age_seconds` (rejecting missing, negative, and >3.0s values), enforces metadata consistency (`is_stale` vs `is_quote_fresh`), fails closed on timezone-naive timestamps, and supports optional decision-time re-verification.

---

## 3. Freshness Policy & Clock Semantics

| Rule | Threshold / Condition | Rejection Outcome | Lifecycle Action (Exit) |
|---|---|---|---|
| **Exchange Time Verification** | `exchange_time_status != "VALID"` or `None` | `REJECTED_UNVERIFIED_TIMESTAMP` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Timezone Ambiguity** | `exchange_timestamp_utc.tzinfo is None` or naive clock | `REJECTED_TIMEZONE_AMBIGUOUS` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Future Skew** | `(decision_time - exch_ts) < 0.0s` | `REJECTED_FUTURE_TIMESTAMP` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Freshness Threshold** | `quote_age <= 3.0s` passes; `> 3.0s` rejects | `REJECTED_STALE_QUOTE` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Persisted Stale Flag** | `is_stale=True` or `quote_status == "STALE"` | `REJECTED_STALE_QUOTE` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Order Book Integrity** | Locked (`bid == ask`) | `REJECTED_LOCKED_QUOTE` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Order Book Integrity** | Crossed (`bid > ask`) | `REJECTED_CROSSED_BOOK` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Spread Limit** | `(ask - bid) / bid > 0.025` (2.5%) | `REJECTED_EXCESSIVE_SPREAD` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Liquidity Floor** | `bid <= 0` or `quote_status == "ZERO_BID"` | `EXIT_UNEXECUTABLE_ZERO_BID` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |
| **Slippage Floor** | `calculate_taker_sell_fill(bid) is None` | `EXIT_UNEXECUTABLE_TINY_BID` | Retains `PENDING_LIQUIDITY`, zero fills/fees/P&L |

---

## 4. Exact Files Changed

1. **`fno/execution/paper_engine.py`**:
   - Added `clock: Optional[Callable[[], datetime]] = None` dependency injection and `get_decision_time()` helper.
   - Added `validation_time: Optional[datetime] = None` parameter across `process_signal()`, `_test_only_process_signal_with_override()`, `_process_signal_internal()`, `_handle_buy_signal()`, and `_handle_exit_signal()`.
   - Updated `_check_quote_execution_eligibility()` to recalculate quote age dynamically against the decision clock, fail closed on timezone-naive timestamps, and reject future timestamps.
   - Symmetrically integrated quote eligibility checks into `_handle_exit_signal()` while preserving `PENDING_LIQUIDITY` and zero fee/P&L guarantees.
   - Preserved `allow_default_schedule` isolation for explicit synthetic unit test helpers.
2. **`fno/strategies/validator.py`**:
   - Updated `SignalValidator.validate_snapshot_eligibility()` to reject missing, negative, and >3.0s quote ages.
   - Enforced rejection of inconsistent freshness metadata (`is_stale=False` while `is_quote_fresh=False`).
   - Added timezone-naive fail-closed rejection (`REJECTED_TIMEZONE_AMBIGUOUS`).
   - Added optional decision-time re-verification against `validation_time`.
3. **`fno/services/feature_engine.py`**:
   - Updated `OptionFeatureEngine.construct_snapshot()` to detect negative time deltas, setting `exch_status = "FUTURE_SKEW_REJECTED"`, `is_fresh = False`, and `is_stale = True`.
   - Enforced strict mutual consistency: `is_stale` is synchronized with `not is_fresh`.
   - Handled timezone-naive datetimes defensively with `exch_status = "TIMEZONE_AMBIGUOUS_REJECTED"`.
4. **`fno/tests/test_paper_execution.py`**:
   - Injected deterministic clock (`clock=lambda: self.now_utc`) in `setUp()`.
   - Provided authentic `validation_time` in provenance isolation tests.
   - Added `QuoteFreshnessGuardTestCase` covering threshold boundaries (0.0s, 3.0s, 3.001s), quotes aging after ingestion, future timestamps, timezone-naive datetimes, open exposure preservation in `PENDING_LIQUIDITY`, zero friction/P&L assertions, and exit microstructure rejections.
5. **`fno/tests/test_strategy_engine.py`**:
   - Added `exchange_timestamp_utc` to `self.snapshot_ce` in `setUp()`.
   - Added regression test cases for inconsistent freshness metadata, quote ages exceeding 3.0s, negative quote age, missing quote age, and timezone-naive timestamps.
6. **`fno/tests/test_feature_engine.py`**:
   - Added regression tests for future exchange timestamp detection (`FUTURE_SKEW_REJECTED`) and quote aging after arrival.

---

## 5. Verification Commands and Actual Evidence

### Test Evidence Summary Table

| Test Suite / Command | Exit Code | Tests Run | Result | Evidence Notes |
|---|---|---|---|---|
| `venv/bin/python manage.py test fno.tests.test_paper_execution` | `0` | 38 | `PASS` | All 32 legacy tests + 6 new freshness guard tests passed. |
| `venv/bin/python manage.py test fno.tests.test_strategy_engine` | `0` | 10 | `PASS` | All 6 legacy tests + 4 new snapshot freshness tests passed. |
| `venv/bin/python manage.py test fno.tests.test_feature_engine` | `0` | 14 | `PASS` | All 12 legacy tests + 2 new future skew/aging tests passed. |
| `venv/bin/python manage.py test fno` | `0` | 109 | `PASS` | Full F&O suite passed (up from 97 baseline tests). |
| `venv/bin/python manage.py test market.tests` | `0` | 298 | `PASS` | Full equity regression suite passed with zero regressions. |
| `git diff --name-only market/normalizers/kite.py` | `0` | 0 lines | `PASS` | Confirmed zero edits to equity Kite normalizer. |
| `venv/bin/python manage.py check` | `0` | N/A | `PASS` | System check identified no issues (0 silenced). |
| `venv/bin/python manage.py makemigrations --check --dry-run` | `0` | N/A | `PASS` | No changes detected; zero unintended migrations. |

### Command Output Records

1. **Paper Execution Test Suite:**
   ```
   venv/bin/python manage.py test fno.tests.test_paper_execution
   Ran 38 tests in 0.153s
   OK
   ```
2. **Strategy Engine Test Suite:**
   ```
   venv/bin/python manage.py test fno.tests.test_strategy_engine
   Ran 10 tests in 0.004s
   OK
   ```
3. **Feature Engine Test Suite:**
   ```
   venv/bin/python manage.py test fno.tests.test_feature_engine
   Ran 14 tests in 0.022s
   OK
   ```
4. **Full F&O Suite:**
   ```
   venv/bin/python manage.py test fno
   Ran 109 tests in 2.613s
   OK
   ```
5. **Equity Regression Suite:**
   ```
   venv/bin/python manage.py test market.tests
   Ran 298 tests in 5.510s
   OK
   ```
6. **Django Check & Migration Verification:**
   ```
   venv/bin/python manage.py check && venv/bin/python manage.py makemigrations --check --dry-run
   System check identified no issues (0 silenced).
   No changes detected
   ```

---

## 6. Exposure Preservation & Zero Frictions Verification

Explicit assertions verified in regression tests:
- **Entry Rejections:** When buy orders are rejected due to stale, future, or invalid quotes:
  - Database row created with `status="REJECTED"`, `entry_fill_price=Decimal("0.00")`, `entry_slippage=Decimal("0.00")`.
  - `total_frictions = Decimal("0.00")`.
  - `gross_pnl is None` and `net_pnl is None`.
- **Exit Rejections:** When exit orders are rejected due to stale quotes (>3.0s), locked quotes, crossed quotes, or excessive spreads:
  - Position remains open and transitions to `trade.status = "PENDING_LIQUIDITY"`.
  - `trade.rejection_reason` records the exact rejection code (e.g. `REJECTED_STALE_QUOTE`, `REJECTED_LOCKED_QUOTE`).
  - `trade.exit_timestamp is None`, `trade.exit_fill_price is None`.
  - `trade.total_frictions = Decimal("0.00")`.
  - `trade.gross_pnl is None` and `trade.net_pnl is None`.
  - `self.engine.active_trades` retains the trade key; unresolved risk remains visible.

---

## 7. Status Table Against Phase 22D Acceptance Criteria

| Criterion | Status | Evidence / Notes |
|---|---|---|
| Quote age independently checked at execution decision boundary | `PASS` | `_check_quote_execution_eligibility` computes `(decision_time - quote.exchange_timestamp_utc)`. |
| 3.0-second threshold applied symmetrically to entry and exit | `PASS` | Verified in `QuoteFreshnessGuardTestCase.test_fresh_quote_at_exact_threshold_boundary` and `test_stale_exit_rejected_preserves_unresolved_exposure`. |
| Future, missing, invalid, and timezone-naive timestamps fail closed | `PASS` | Returns `REJECTED_FUTURE_TIMESTAMP`, `REJECTED_UNVERIFIED_TIMESTAMP`, `REJECTED_TIMEZONE_AMBIGUOUS`. |
| Strategy snapshot validator rejects inconsistent freshness metadata | `PASS` | Verified in `test_signal_rejection_on_inconsistent_freshness_metadata`. |
| Invalid/stale entry cannot create a fill, fee, or P&L | `PASS` | Verified in DB assertions in `test_quote_aging_after_ingestion_rejection`. |
| Invalid/stale exit preserves unresolved exposure in `PENDING_LIQUIDITY` with 0 fill/fee/P&L | `PASS` | Verified in `test_stale_exit_rejected_preserves_unresolved_exposure`. |
| Existing pending-liquidity, expiry, fee-schedule, and timestamp protections pass | `PASS` | Zero-bid, tiny-bid, cutoff, fee-schedule, and statutory tests all pass. |
| Targeted and full F&O tests pass with command evidence | `PASS` | 109/109 tests passed (exit code 0). |
| Equity regression tests pass with command evidence | `PASS` | 298/298 tests passed (exit code 0); `market/normalizers/kite.py` untouched. |
| Django check and migration dry-run pass | `PASS` | 0 issues; no migrations created. |
| Remediation report written | `PASS` | `docs/audits/phase_22d_quote_freshness_guard_remediation_report.md` |
| No live broker order capability enabled or invoked | `PASS` | Verified paper execution taker simulations only. |
| Authentic live market session validation | `NOT TESTED` | Live market acceptance requires authentic live trading session telemetry. Offline tests cannot mark this PASS. |

---

## 8. Remaining Risks & Next Recommended Action

1. **Clock Drift between Ingestion Daemon and Local System:**
   - *Risk:* If local system clock drifts significantly relative to the exchange matching engine clock, quotes could erroneously trigger `REJECTED_FUTURE_TIMESTAMP` or `REJECTED_STALE_QUOTE`.
   - *Mitigation:* Ensure NTP synchronization (e.g. `chrony` or `systemd-timesyncd`) is active on paper/live execution hosts.
2. **Live Acceptance Validation:**
   - *Next Action:* Schedule observation during market hours (09:15 - 15:30 IST) to collect authentic telemetry on quote rejection frequency and fill rate under actual tick feed volatility.
