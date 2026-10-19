# Nomad Analyst — Phase 22A: F&O Market Data Ingestion & Storage Architecture
## Independent Audit & Completion Report

**Date:** 2026-10-17  
**Status:** COMPLETE & VERIFIED  
**Author:** AI Systems Engineer & Quantitative Architect  
**Target Environment:** Local macOS / PostgreSQL / Redis / Celery / Zerodha Kite WebSocket (`wss://ws.kite.trade`)

---

## 1. Executive Summary

Phase 22A establishes the foundational real-time and historical market data architecture for Indian Equity Derivatives (NSE F&O / NFO) within Nomad Analyst. The implementation strictly adheres to the non-negotiable architectural mandate: **Zero Contamination of Equity Pipeline**.

The dedicated Django app `fno` has been implemented with its own PostgreSQL tables (`fno_option_ohlcvbar` and `fno_option_quote_snapshot`), specialized parsing and normalization logic for Zerodha Kite 184-byte binary packets and dictionary ticks, dynamic strike universe management (ATM ± 5 strikes, 22 contracts), and an automated Celery rolling retention policy.

All 4 critical gaps identified in the architecture review have been fully remediated and verified through 34 passing automated tests in `fno.tests` and 298 passing regression tests in `market.tests`.

---

## 2. Core Architecture & Database Models

### 2.1 Decoupled Data Layer

| Model | Table Name | Purpose | Retention |
|---|---|---|---|
| `OptionOHLCVBar` | `fno_option_ohlcvbar` | 1-minute OHLCV + Open Interest storage for active option contracts. Fully decoupled from equity `market_ohlcvbar`. | Permanent historical record |
| `OptionQuoteSnapshot` | `fno_option_quote_snapshot` | High-frequency best bid/ask, L1 quantities, 5-level market depth, and execution eligibility flags. | Rolling 5-day retention policy |

### 2.2 Migrations
- Migration `fno/migrations/0001_initial.py` created and applied to database `nomad_analyst`.
- Constraints: `unique_fno_ohlcv_token_tf_ts` on `(instrument_token, timeframe, timestamp)`.
- Indexes: `(tradingsymbol, timeframe, timestamp)`, `(underlying_symbol, expiry_date, timestamp)`, `(instrument_token, exchange_timestamp_utc)`, `(received_wall_clock_utc)`.

---

## 3. Remediated Architecture Gaps & Implementation Details

### 3.1 Gap 1: ATM Strike Boundary Crossing Rebalance (`fno/services/desired_universe.py`)
- **Issue:** Previously, `should_rebalance()` checked only if the spot price drifted by more than `rebalance_threshold_pts` (50 points). If spot drifted by 2 points (e.g., 24,524.00 to 24,526.00) across the 50-point strike midpoint (24,525.00), the mathematical ATM strike shifted from 24,500 to 24,550, but rebalancing was not triggered.
- **Remediation:** Updated `should_rebalance()` to compare `calculate_atm_strike(current_spot) != self.last_atm_strike`. Whenever the calculated ATM strike changes, rebalancing is triggered immediately regardless of drift magnitude.
- **Verification:** Unit test `test_atm_boundary_crossing_rebalance_spot_24524_to_24526` demonstrates spot moving from 24,524 to 24,526 triggers rebalance (+2 new strikes subscribed, -2 dropped strikes unsubscribed).

### 3.2 Gap 2: Zero-Bid Quote Normalization & Classification (`fno/services/option_normalizer.py`)
- **Issue:** Illiquid deep OTM options often have asks but zero bids (`best_bid is None`). Treating `best_bid` as 0.0 or failing to classify this resulted in invalid execution pricing or misclassified `LOCKED`/`CROSSED` states.
- **Remediation:**
  - Added quote status `"ZERO_BID"` when `best_bid is None and best_ask is not None`.
  - Added quote status `"EMPTY_BOOK"` when both `best_bid is None and best_ask is None`.
  - Enforced `is_execution_eligible = False` whenever `quote_status in ("ZERO_BID", "EMPTY_BOOK")`.
- **Verification:** Unit tests `test_zero_bid_illiquid_quote_classification` and `test_empty_book_classification` verify that both binary packets and dictionary ticks with zero bids are assigned `ZERO_BID` and strictly disqualified from execution.

### 3.3 Gap 3: KiteTicker WebSocket Integration & Dynamic Resubscription (`fno/services/fno_ticker_consumer.py` & `market/services/kite_ticker.py`)
- **Issue:** Ticker daemon had no wiring to feed NFO option contracts, and options need `MODE_FULL` (depth + quote) rather than `MODE_QUOTE`, and dynamic rebalancing requires issuing `ws.subscribe()` and `ws.unsubscribe()` when underlying spot drifts.
- **Remediation:**
  - Implemented `FnoTickerConsumer` in `fno/services/fno_ticker_consumer.py`.
  - Injected optional `fno_consumer` into `KiteTickerManager`.
  - In `KiteTickerManager._on_ticks()`, checks `if self.fno_consumer and self.fno_consumer.is_fno_token(token)`. When true, dispatches directly to `fno_consumer.on_tick()` and skips `IntradayStateManager`. Zero contamination of equity states.
  - When underlying index tick (e.g. `^NSEI` / token `256265`) arrives, `KiteTickerManager` notifies `fno_consumer.on_underlying_spot_update(spot, ws)`. If ATM shifts, `fno_consumer` calls `ws.subscribe(new_tokens)`, `ws.set_mode(ws.MODE_FULL, new_tokens)`, and `ws.unsubscribe(dropped_tokens)`.
  - Added CLI flag `--enable-fno` to `market/management/commands/run_intraday_ticker.py` to optionally activate F&O ingestion alongside equity streaming.

### 3.4 Gap 4: Celery Daily Purge Task for Quote Snapshots (`fno/tasks.py` & `config/settings.py`)
- **Issue:** High-frequency quote snapshots (5-level depth) would cause unbounded database bloat without an automated retention schedule.
- **Remediation:**
  - Created Celery task `purge_expired_option_quotes(days=5)` in `fno/tasks.py`.
  - Registered task in `CELERY_BEAT_SCHEDULE` in `config/settings.py` under key `'purge-expired-option-quotes-daily'`, scheduled at 17:00 IST (11:30 UTC) Monday through Friday.
  - Handled JSON serialization of `depth` inside `OptionQuoteManager.record_quote_snapshot` to convert Decimal prices to floats, ensuring bulletproof persistence.
- **Verification:** Integration test `test_celery_purge_expired_option_quotes_task` verified that snapshots older than 5 days are cleanly purged while active records remain intact. Direct Celery execution confirmed success.

---

## 4. Test Verification Matrix

All tests executed in local Python 3.14 virtual environment against PostgreSQL test databases.

```bash
# F&O Test Suite Execution
./venv/bin/python manage.py test fno.tests
Ran 34 tests in 0.301s — OK (0 failures, 0 errors)

# Equity Regression Suite Execution
./venv/bin/python manage.py test market.tests
Ran 298 tests in 6.207s — OK (0 failures, 0 errors)
```

### Breakdown of Passing F&O Test Suites:
1. `fno.tests.test_option_registry`: 6 tests (CSV loading, contract indexing, strike step resolution, expiry lookup, staleness detection).
2. `fno.tests.test_option_normalizer`: 12 tests (184-byte binary unpacking, OI semantics, sparse depth, locked/crossed quotes, zero-bid classification, empty book classification, dictionary normalization, timestamp skew rejection).
3. `fno.tests.test_desired_universe`: 7 tests (ATM strike calculation, initial spot K=5 allocation, drift suppression, significant shift rebalance, ATM midpoint boundary crossing, expiry day 13:00 IST next-weekly staging).
4. `fno.tests.test_option_bar_persistence`: 3 tests (1-minute bar aggregation, volume deltas, partial bar tagging, PostgreSQL uniqueness constraints).
5. `fno.tests.test_option_quote_snapshots`: 2 tests (Point-in-time quote retrieval, execution eligibility filter, retention purge queries).
6. `fno.tests.test_fno_ticker_integration`: 4 tests (KiteTickerManager NFO routing isolation, underlying spot dynamic rebalancing with mock WebSocket, quote snapshot persistence, Celery purge task).

---

## 5. Architectural Compliance Verification

| Requirement | Audit Verdict | Evidence |
|---|---|---|
| **Zero Contamination of Equity Pipeline** | **PASS** | F&O tables are distinct (`fno_*`). In `KiteTickerManager._on_ticks`, F&O tokens route strictly to `FnoTickerConsumer` and bypass `IntradayStateManager`. Equity tests passed 298/298. |
| **Authentic Taker Execution Modeling** | **PASS** | `OptionQuoteSnapshot` stores full 5-level depth, L1 bid/ask, and calculates `is_execution_eligible` requiring non-stale timestamps, non-locked/crossed quotes, and non-zero bids. |
| **Dynamic Universe Management** | **PASS** | ATM ± 5 strikes (11 CE + 11 PE = 22 contracts) automatically updates when spot price crosses strike boundaries. Rebalance commands issue live subscribe/unsubscribe calls. |
| **Bounded Database Growth** | **PASS** | High-frequency quote table is subject to rolling 5-day deletion via scheduled Celery Beat task `purge_expired_option_quotes`. |
| **Code Preservation** | **PASS** | All prior Phase 19/20 working tree changes preserved intact. |

---

## 6. Next Steps (Phase 22B)
With data ingestion, normalization, storage, and ticker consumer fully operational, Phase 22B can proceed with:
1. Volatility surface and Black-Scholes implied volatility (IV) calculations using historical and live 1m bars.
2. Greeks calculation (Delta, Gamma, Theta, Vega) linked to underlying spot.
3. Intraday Options Strategy Engine (Long Straddle, Short Strangle, Iron Condor, Momentum Breakouts).
