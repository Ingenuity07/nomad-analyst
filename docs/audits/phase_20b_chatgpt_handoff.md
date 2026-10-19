# Nomad Analyst — Phase 20B ChatGPT Handoff

## 1. Context & Objective
Phase 20B executed **Targeted Runtime Reliability Remediation** for Nomad Analyst's live intraday trading pipeline:
1. **Ticker Reconnect & Process Lifecycle:** Implemented outer watchdog reconnection with bounded exponential backoff ($2\text{s} \to 60\text{s}$), subscription restoration (all 54 tokens), and OS-level advisory file locking (`fcntl.flock`) preventing duplicate daemon instances.
2. **Authoritative Intraday Candle Selection:** Fixed the defect where unaligned, interim Yahoo Finance pseudo-bars ($V=0$, timestamp `11:34:50`) overrode completed `NomadAggregator` candles. Implemented PIT-safe completed candle loading ($T_{start} + \Delta T \le as\_of$), exchange boundary alignment (IST grid), source precedence (`NomadAggregator` > `KiteHistoricalProvider` > `YFinanceMarketProvider`), legitimate zero-volume preservation, and interval-aware completion-lag staleness checks.
3. **Opportunity Snapshot Reconciliation:** Audited database records to mathematically account for the 380-row difference ($10,080 \to 10,460 \to 10,560$).
4. **Testing & Live Verification:** Added 8 new unit/regression tests (14 total in suite, 100% passing), and verified live strategy scan execution yielding 2 actionable recommendations (`ONGC` and `TECHM`) with zero LLM calls.

---

## 2. File-by-File Changes

1. **`market/management/commands/run_intraday_ticker.py`:**
   - Added process-level file locking via `fcntl.flock` on `/tmp/nomad_intraday_ticker.pid` to immediately abort duplicate daemon startups.
   - Added outer watchdog coordination loop with bounded exponential backoff ($2.0\text{s}$ initial, $60.0\text{s}$ cap) that detects disconnections and triggers safe reconnects while preserving state.
   - Guaranteed clean lock release and file unlinking on exit or shutdown signal.

2. **`market/services/kite_ticker.py`:**
   - Added `_connect_lock = threading.Lock()` to `KiteTickerManager`.
   - Implemented thread-safe `reconnect()` method: skips duplicate reconnections if already connected, closes stale client cleanly, re-initializes `kws`, and preserves `subscribed_tokens`.
   - Updated `stop()` to acquire `_connect_lock` for thread safety.

3. **`market/services/intraday_signal_engine.py`:**
   - Replaced direct `OHLCVBar.objects.filter(..., timestamp__lte=as_of)` with `self._load_completed_bars()`.
   - Enforced PIT-safe completed bar threshold ($T_{start} + \Delta T \le as\_of$).
   - Enforced exchange boundary alignment: rejects unaligned interim ticks (`second != 0`, `microsecond != 0`, unaligned minute offsets).
   - Enforced source precedence: `NomadAggregator` (Rank 1) > `KiteHistoricalProvider` (Rank 2) > `YFinanceMarketProvider` (Rank 3).
   - Preserved legitimate zero-volume completed bars (e.g., indices like `^NSEI`).
   - Refactored Gate 2 (stale check) to measure lag against candle completion timestamp ($T_{start} + \Delta T$).
   - Updated `_load_index_bars()` to use `_load_completed_bars()` for relative strength computation.

4. **`market/tests.py`:**
   - Added `Phase20BRuntimeReliabilityTests` class covering:
     - `test_ticker_reconnect_guards_against_duplicate_connections`
     - `test_ticker_reconnect_preserves_and_restores_subscriptions`
     - `test_ticker_graceful_shutdown`
     - `test_completed_candle_selection_filters_interim_unaligned_candles`
     - `test_source_precedence_nomad_aggregator_over_yfinance`
     - `test_preserves_legitimate_zero_volume_completed_candles`
     - `test_missing_latest_bars_triggers_stale_draft`
     - `test_process_locking_guards_against_duplicate_daemons`

---

## 3. Snapshot Reconciliation Breakdown

| Timeline | Total Snapshots | Delta | Batches ($\times 20$ rows) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Oct 15 Baseline** | 10,080 | — | 504 batches | Count at initial audit checkpoint |
| **Oct 15 Late / Overnight** | 10,380 | +300 | +15 batches | Ticker daemon ran until 04:15 IST ($15 \times 20 = 300$) |
| **Oct 16 Morning (Pre-restart)** | 10,460 | +80 | +4 batches | Ran from 11:20:28 to 11:23:29 IST ($4 \times 20 = 80$) |
| **Subtotal before restart** | **10,460** | **+380** | **+19 batches** | **Exact 380-row difference reconciled** |
| **Oct 16 Morning (Post-restart)** | 10,560 | +100 | +5 batches | 5 batches from 11:31:26 to 11:35:27 IST ($5 \times 20 = 100$) |
| **Ongoing Live Run** | 10,640+ | +80 | +4 batches | Additional minutes continuing normally |

**Writer:** `IntradayStateManager.persist_snapshots()` called every 60 seconds by `run_intraday_ticker.py`. Batch size is fixed at `top_n = 20`. Zero duplicate records, zero deletions.

---

## 4. Live Acceptance & Strategy Scan Evidence

1. **Strategy Scan Execution (11:47:59 IST):**
   ```
   run_intraday_strategy_scan: complete.
   Total: 50 | Actionable: 2 | Skipped: 48 | Failed: 0
   ```
2. **Actionable Recommendations Created & Persisted:**
   - **ONGC (`f07fbe7d-759d-4061-858f-c9b6d36a4be0`):**
     `SELL` | Setup: `VWAP_REJECTION` | Conf: `HIGH` | Entry: `223.72` | Stop: `224.41` | Target1: `222.59` | Target2: `222.37` | $RR = 1.64$ | Status: `ACTIVE`
   - **TECHM (`946d2a28-1a3f-4951-a6e4-bbb3aa036d87`):**
     `BUY` | Setup: `INTRADAY_PULLBACK` | Conf: `MEDIUM` | Entry: `1760.80` | Stop: `1751.48` | Target1: `1776.02` | Target2: `1779.07` | $RR = 1.63$ | Status: `ACTIVE`
3. **Safety & Integrity Checks:**
   - `INFY`: Suppressed duplicate signal via 30-minute cooldown rule.
   - `TCS`: Rejected because $RR = 1.35 < 1.50$ (risk/reward gate strictly enforced).
   - Zero LLM calls during scanning.

---

## 5. Verification Command & Test Results

```bash
./venv/bin/python manage.py test market.tests.Phase20A1IntradayWarmupAndReadinessTests market.tests.Phase20BRuntimeReliabilityTests
```
**Result:** 14 passed in 0.116s, 0 errors, 0 failures.
