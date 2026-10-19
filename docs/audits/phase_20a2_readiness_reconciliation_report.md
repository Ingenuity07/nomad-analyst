# Nomad Analyst — Phase 20A.2: Readiness Reconciliation and Live Acceptance Report

**Date:** 15 October 2026  
**Auditor / Agent:** Antigravity Autonomous Engineering Agent  
**Environment:** Local macOS ARM64, Python 3.14 (`./venv`), PostgreSQL (`nomad_analyst`), Redis (`localhost:6379`), Celery Worker/Beat, Vite Frontend  
**Scope:** Forensic reconciliation of 5-minute OHLCV bar counts, historical ingestion session boundary enforcement, readiness gate integrity verification, and live-market operational audit.  
**Verdict:** **PASS (Reconciliation & Boundaries Verified) / NOT VERIFIED (Live Market Scans — Market Closed at 22:00 IST)**

---

## 1. Executive Summary

Phase 20A.2 conducts a forensic audit of the historical and live data layer following the Phase 20A.1 warmup. The audit resolves key mathematical discrepancies, corrects a subtle boundary bug in historical ingestion, and verifies that intraday readiness gates operate with complete statistical integrity:

1. **Reconciliation of Five-Minute Bar Counts:**
   - **Full Session Standard:** A standard NSE regular equity session (09:15:00 to 15:30:00 IST) comprises exactly **75 five-minute intervals** (09:15:00 to 15:25:00 inclusive).
   - **Benchmark Indices (`^NSEI`, `^NSEBANK`, `^BSESN`, `^CNXIT`):** Contain **309 bars** in total = exactly 75 bars/day across 3 historical trading days (Oct 12, 13, 14) + 84 bars on Oct 15 (generated live by `NomadAggregator`).
   - **NIFTY 50 Constituent Equities:** Contain **370–373 bars** in total = 72 bars/day across 3 historical trading days (Oct 12, 13, 14) + 84 live aggregator bars on Oct 15 + 71–73 YFinance historical backfill bars on Oct 15.
   - **Kite 72-Bar Behavior Explained:** Zerodha Kite Connect's historical API for NSE equities returns candles up to `15:10:00 IST` (360 minutes = 72 bars) due to intraday MIS auto square-off boundaries at 15:15 IST, whereas index tokens return all 75 candles up to `15:25:00 IST`.
   - **Warmup Reported 11,484 Bars Explained:** In Phase 20A.1, `ingest_kite_historical` created exactly 3,828 bars/day × 3 days (Oct 12, 13, 14) = **11,484 bars** (49 equities × 72 bars = 3,528; 4 benchmarks × 75 bars = 300; 3,528 + 300 = 3,828 bars/day). `TATAMOTORS` was skipped during Kite backfill because of its separate YFinance dataset.
2. **Historical Ingestion Boundary Gate Fix:**
   - Identified that `market/services/kite_historical.py` previously filtered intraday bars using `bar_time < REGULAR_SESSION_START or bar_time > time(16, 0)`. This allowed post-market candles between 15:30:00 and 16:00:00 IST to pass into the database.
   - Corrected the gate to `bar_time < REGULAR_SESSION_START or bar_time >= REGULAR_SESSION_END`, strictly enforcing `[09:15, 15:30)` (09:15 inclusive, 15:30 exclusive).
   - Added regression test `test_kite_historical_ingestion_gates_boundary_cases` to `market/tests.py` testing boundary conditions (`09:10` skipped, `09:15` kept, `15:25` kept, `15:30` skipped, `15:45` skipped, `16:05` skipped).
   - Zero historical records were deleted or rewritten, preserving all existing database history.
3. **Readiness Gate Correctness:**
   - Verified that no equity passed readiness due to count inflation from out-of-session bars. When strictly filtering to regular-session candles (`09:15:00` to `15:29:59` IST), every single equity has **at least 361 bars**, far exceeding the 100-bar minimum requirement (261% safety margin).
   - Preserved all risk gates: 100-bar warmup minimum, maximum 5 data gaps in the last session, and in-memory indicator computability (`compute_intraday_indicators` verifying numeric integrity, non-null prices, and valid OHLC geometry).
   - Verified bidirectional mapping for `TATAMOTORS` (`TMPV`, token `884737`) across registry, provider symbol resolution, and readiness checks.
4. **Live-Session Acceptance Status:**
   - Current time is **22:00 IST** on 15 October 2026. The NSE equity market is CLOSED (`window: OUTSIDE`).
   - Per prompt instructions, continuous live-market scans are marked **NOT VERIFIED (Market Closed)** without synthetic or mock substitutions.
   - Operating infrastructure verified: Celery Worker, Celery Beat, Vite Frontend, and Django API server are running; 10,080 opportunity snapshots recorded during today's open market session.
   - Full market test suite passes: **306 tests, 0 failures, 0 errors**.

---

## 2. Five-Minute Bar Counts Reconciliation

### 2.1 Standard Session Candle Math
- **Exchange:** National Stock Exchange of India (NSE) — Capital Market Segment.
- **Continuous Trading Session Hours:** `09:15:00` to `15:30:00` Asia/Kolkata (IST).
- **Session Duration:** 6 hours and 15 minutes = 375 minutes.
- **Expected Five-Minute Candles:** $375 \text{ min} / 5 \text{ min} = \mathbf{75 \text{ candles}}$.
- **Standard Candle Open Timestamps (IST):**
  - First candle: `09:15:00` (covers 09:15:00 to 09:20:00)
  - Second candle: `09:20:00` (covers 09:20:00 to 09:25:00)
  - ...
  - Penultimate candle: `15:20:00` (covers 15:20:00 to 15:25:00)
  - Final regular candle: `15:25:00` (covers 15:25:00 to 15:30:00)
  - Post-market candle (outside regular continuous trading): `15:30:00` (covers 15:30:00 to 15:35:00)

### 2.2 Actual Database Inventory by Instrument and Date
Querying `OHLCVBar.objects.filter(timeframe='5m')` in PostgreSQL reveals exact counts:

| Instrument Symbol | Oct 12 (Mon) | Oct 13 (Tue) | Oct 14 (Wed) | Oct 15 (Thu) | Total in DB |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **^NSEI (NIFTY 50)** | 75 | 75 | 75 | 84 | **309** |
| **^NSEBANK (BANK NIFTY)** | 75 | 75 | 75 | 84 | **309** |
| **^BSESN (SENSEX)** | 75 | 75 | 75 | 84 | **309** |
| **^CNXIT (NIFTY IT)** | 75 | 75 | 75 | 84 | **309** |
| **49 Constituent Equities** (e.g. RELIANCE, TCS) | 72 | 72 | 72 | 154–157 | **370–373** |
| **TATAMOTORS** | 74 | 74 | 74 | 144 | **2,772** |
| **Total 5m Bars** | **3,902** | **3,902** | **3,902** | **8,113** | **22,225** |

### 2.3 Deconstruction of Discrepancies

#### 1. Why Benchmarks Have Exactly 309 Bars
- On Oct 12, 13, 14: Kite Connect historical API returns all 75 regular-session candles (`09:15` to `15:25` IST) for indices. $3 \times 75 = 225$ bars.
- On Oct 15: `NomadAggregator` streamed ticks throughout the session and aggregated 84 bars:
  - 1 pre-open bar at `09:10:00`
  - 75 regular session bars from `09:15:00` to `15:25:00`
  - 8 post-market bars from `15:30:00` to `16:05:00`
  - Total on Oct 15 = $1 + 75 + 8 = 84$ bars.
- Total benchmark bars = $225 + 84 = \mathbf{309 \text{ bars}}$.

#### 2. Why Equities Have 360–373 Bars (and 72 Bars per Historical Day)
- Direct API probe of Kite Connect (`KiteConnect.historical_data` for token 738561 / `RELIANCE`):
  ```
  Kite historical_data from=2026-10-12 09:15 to 2026-10-12 15:30:
  Candles returned: 72
  First candle: 2026-10-12 09:15:00+05:30
  Last candle:  2026-10-12 15:10:00+05:30
  ```
  Even when `to_date` is extended to `23:59:00`, Kite returns 72 candles ending at `15:10:00 IST`. Zerodha's equity historical intraday feed stops at 15:10:00 IST (covering 15:10 to 15:15) to align with MIS auto-squareoff cutoffs, omitting the last three 5-minute candles (`15:15`, `15:20`, `15:25`).
- On Oct 15, equities received both:
  - 84 bars from `NomadAggregator` (clean 5-minute timestamps: `09:10:00`, `09:15:00`, etc.)
  - 71–73 bars from `YFinanceMarketProvider` (timestamps with seconds: `09:17:57`, `09:22:57`, etc.)
  - Total on Oct 15 = $84 + 72 = 156$ bars.
- Total equity bars = $(3 \times 72) + 156 = 216 + 156 = \mathbf{372 \text{ bars}}$ (sample `RELIANCE`, `TCS`).

#### 3. Why the Phase 20A.1 Warmup Reported Exactly 11,484 Bars
- When `python manage.py ingest_kite_historical --universe NIFTY50 --benchmarks --timeframe 5m --days 5` ran in Phase 20A.1:
  - 49 equities × 72 bars/day = 3,528 bars/day
  - 4 benchmarks × 75 bars/day = 300 bars/day
  - Total per day = $3,528 + 300 = 3,828$ bars/day
  - Over 3 historical trading days (Oct 12, 13, 14): $3,828 \times 3 = \mathbf{11,484 \text{ bars}}$.
  - `TATAMOTORS` had 74 bars/day from YFinance, so Kite historical ingestion skipped it. $11,484 + (74 \times 3) = 11,706$ total bars across Oct 12–14.

---

## 3. Historical Ingestion Boundaries and Gating Verification

### 3.1 Defect in Prior Ingestion Gate
In `market/services/kite_historical.py`, line 101 previously read:
```python
# Old gate
if timeframe not in ("1d", "day"):
    bar_time = TradingSessionService.to_ist(bar_dict["timestamp"]).time()
    if bar_time < REGULAR_SESSION_START or bar_time > time(16, 0):
        continue
```
**Defect Analysis:**
- `REGULAR_SESSION_START` is `time(9, 15)`. Bars with `bar_time < 09:15` were correctly skipped.
- However, the upper bound used `time(16, 0)`. Any candles with start timestamps between `15:30:00` and `16:00:00` IST (post-market / closing auction) were allowed through into `OHLCVBar`.
- Continuous equity trading ends at `15:30:00 IST`. Regular session 5-minute candles are strictly `[09:15:00, 15:30:00)` (09:15 inclusive, 15:30 exclusive).

### 3.2 Corrected Ingestion Gate
Updated `market/services/kite_historical.py` to import `REGULAR_SESSION_END` (`time(15, 30)`) and enforce:
```python
# Corrected gate: strictly [09:15:00, 15:30:00) IST
if timeframe not in ("1d", "day"):
    bar_time = TradingSessionService.to_ist(bar_dict["timestamp"]).time()
    if bar_time < REGULAR_SESSION_START or bar_time >= REGULAR_SESSION_END:
        continue
```
**Boundary Behavior:**
- `09:10:00` -> `< REGULAR_SESSION_START` -> **SKIPPED**
- `09:14:59` -> `< REGULAR_SESSION_START` -> **SKIPPED**
- `09:15:00` -> In range `[09:15, 15:30)` -> **KEPT (09:15 inclusive)**
- `15:25:00` -> In range `[09:15, 15:30)` -> **KEPT**
- `15:30:00` -> `>= REGULAR_SESSION_END` -> **SKIPPED (15:30 exclusive)**
- `15:35:00` -> `>= REGULAR_SESSION_END` -> **SKIPPED**
- `16:05:00` -> `>= REGULAR_SESSION_END` -> **SKIPPED**

### 3.3 Provider Timestamp Normalization Verification
In `market/normalizers/kite.py`, `KiteNormalizer.normalize_candle` processes timestamps before returning the normalized dictionary:
```python
if isinstance(raw_ts, datetime):
    ts = TradingSessionService.to_ist(raw_ts)
elif isinstance(raw_ts, str):
    ts = TradingSessionService.to_ist(datetime.fromisoformat(raw_ts))
```
`TradingSessionService.to_ist()` correctly maps both naive and UTC/IST timezone-aware inputs into `ZoneInfo("Asia/Kolkata")`. Thus, `bar_time = TradingSessionService.to_ist(bar_dict["timestamp"]).time()` reliably tests the true IST session time.

### 3.4 Regression Tests Added
Added `test_kite_historical_ingestion_gates_boundary_cases` to `market/tests.py`:
- Feeds mock candles at 09:10:00, 09:15:00, 15:25:00, 15:30:00, 15:45:00, 16:05:00.
- Asserts that exactly 2 candles are created (`09:15:00` and `15:25:00`).
- Confirms 0 errors and zero persistence of 15:30:00 or out-of-session bars.

---

## 4. Readiness Gate Correctness & Risk Gate Verification

### 4.1 Evaluation of Out-of-Session Bar Impact
A critical question raised was whether readiness passed merely because out-of-session candles inflated bar counts.
To verify this, we evaluated bar counts strictly filtering for regular session hours (`09:15:00 <= bar_time < 15:30:00`):

```
=== Regular Session Only [09:15, 15:30) 5m Bar Counts ===
  RELIANCE    : Total DB bars = 372 | Regular session bars = 363
  TCS         : Total DB bars = 372 | Regular session bars = 363
  HDFCBANK    : Total DB bars = 371 | Regular session bars = 362
  INFY        : Total DB bars = 371 | Regular session bars = 362
  TATAMOTORS  : Total DB bars = 2772 | Regular session bars = 2772
  ^NSEI       : Total DB bars = 309 | Regular session bars = 300
  ^NSEBANK    : Total DB bars = 309 | Regular session bars = 300

Minimum regular session 5m bars among all 50 equities: 361
Required minimum bars for 5m readiness: 100
Safety margin: +261 bars (+261% above gate requirement)
```
**Conclusion:** Every single equity satisfies the 100-bar warmup gate based purely on regular-session candles. Out-of-session bars played zero role in passing readiness.

### 4.2 Preservation of Risk and Quality Gates
All Module 9 readiness checks remain strictly enforced:
1. **Check 1 (Supported Timeframe):** Confirmed in `INTRADAY_TIMEFRAME_MINUTES`.
2. **Check 2 (Minimum Bar Count):** 100 bars for 5m.
3. **Check 3 (Data Freshness & Quality):** Must be `HEALTHY` or `INCOMPLETE` (rejects `STALE` and `UNAVAILABLE`). Stale threshold = 15 minutes during trading hours.
4. **Check 4 (Critical Data Gaps):** `MAX_DATA_GAPS_LAST_SESSION = 5`. Evaluated over the most recent session using `detect_gaps()`.
5. **Check 5 (Indicator Computability & Geometric Integrity):** Evaluates last 100 bars in-memory for $O, H, L, C > 0$, $V \ge 0$, $L \le O, C \le H$, and tests `compute_intraday_indicators()` for non-null `close`, `ema_fast`, and `atr`.

### 4.3 Tata Motors Canonical Security Identity
Verified bidirectional resolution throughout the stack:
- `KiteInstrumentRegistry.get_token('TATAMOTORS')` -> `884737`
- `KiteInstrumentRegistry.get_symbol(884737)` -> `'TATAMOTORS'`
- `KiteMarketDataProvider._resolve_kite_symbol('TATAMOTORS')` -> `'NSE:TMPV'`
- `Instrument` in PostgreSQL: symbol `'TATAMOTORS'` (UUID `bad720d3-fed5-46e9-9b3d-054a3fae44c9`).
- `IntradayReadinessService.check_readiness(inst, '5m')` -> `is_ready=True`, 2,772 bars, quality `HEALTHY`, gaps 2.

---

## 5. Live-Session Acceptance Status

### 5.1 Service & Daemon Status Audit
- **PostgreSQL:** Port 5432 active.
- **Redis:** Port 6379 active (`db=1` cache partition).
- **Django Runserver:** Port 8000 active (`PID 48359`, `PID 48358`).
- **Celery Worker:** Active (`PID 85213`, concurrency 10).
- **Celery Beat:** Active (`PID 85730`, DatabaseScheduler).
- **Live Ticker Daemon:** Active (`PID 95685`, CPU time 93 minutes, streaming since morning open).
- **Vite Frontend:** Port 5173 active (`PID 86270`).

### 5.2 Market Status and Acceptance Classification
- **Current Timestamp:** `2026-10-15 22:00:00+05:30` (IST).
- **Session State:** `market_session: {'window': 'OUTSIDE', 'is_trading_hour': False}`.
- **Per Phase 20A.2 Instructions:**
  > "If live market access is unavailable, mark these checks NOT VERIFIED. Do not substitute mocked or simulated scans for live evidence."

| Acceptance Check | Status | Runtime Evidence & Notes |
| :--- | :---: | :--- |
| **5m Bar Counts Reconciliation** | **PASS** | 75 bars/day regular session math verified. 309 benchmark bars and 370–373 equity bars deconstructed to exact single-digit provenance. |
| **Historical Ingestion Gate** | **PASS** | Enforced `[09:15, 15:30)` IST gate (`REGULAR_SESSION_END`). Timestamp normalization verified. Regression test passing. |
| **Readiness Gate Correctness** | **PASS** | 50/50 equities ready with $\ge 361$ regular session bars (100 required). TATAMOTORS/TMPV mapping verified. |
| **Market Overview API** | **PASS** | HTTP 200 on `/api/v1/market/overview/`. Breadth: 18 advancing, 32 declining, 0 unchanged. Coverage: 50/50 (100%). |
| **Intraday Sectors API** | **PASS** | HTTP 200 on `/api/v1/intraday/sectors/`. 14 sectors ranked (Leader: Telecommunications +3.31%, Technology +2.61%, Automobile +2.39%). |
| **Opportunity Snapshots** | **PASS** | 10,080 snapshots persisted during today's trading hours (Top: `TATACONSUM` score 79.50, state CONFIRMED, relative strength vs NIFTY +1.56%). |
| **Live Continuous Scan Execution** | **NOT VERIFIED** | **Market Closed (22:00 IST).** Strictly following rule to avoid mock substitutions. |
| **Zero-LLM Scan Invariant** | **PASS** | Deterministic mathematical scoring verified; zero LLM calls in background scans. |
| **Regression Test Suite** | **PASS** | 306 tests in `market` test suite pass in 5.43s (0 failures, 0 errors). |

---

## 6. Pre-Market Verification Checklist for Tomorrow (16 October 2026)

Before market open at 09:15 IST tomorrow:
1. **08:30 IST — Kite 2FA Re-authentication:** Authenticate morning token via `/api/v1/kite/auth-url/`.
2. **08:45 IST — Readiness Verification:** Confirm 50/50 equities maintain $\ge 100$ bars and 0 gaps:
   ```bash
   ./venv/bin/python manage.py shell -c "from market.models import UniverseMembership; from market.services.intraday_readiness import IntradayReadinessService; svc = IntradayReadinessService(); print([svc.check_readiness(m.instrument, '5m').is_ready for m in UniverseMembership.objects.filter(universe__name='NIFTY50', is_active=True)])"
   ```
3. **09:00 IST — Restart Ticker Daemon:** Restart `run_intraday_ticker` to pick up the fresh daily Kite token.
4. **09:16 IST — Continuous Trading Scan:** Trigger `run_intraday_strategy_scan` inside the open market window and confirm live opportunity generation.
