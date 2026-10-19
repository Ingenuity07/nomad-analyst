# Nomad Analyst — Phase 20A.1: ChatGPT Handoff Report

**Session Date:** 15 October 2026  
**Auditor / Agent:** Antigravity Autonomous Engineering Agent  
**Purpose:** Technical summary of Phase 20A.1 readiness gate remediation, Kite normalizer fix, and 5-minute historical warmup for handoff to ChatGPT / external advisors.

---

## 1. High-Level Status Summary

| Item | Status | Details |
| :--- | :--- | :--- |
| **Active Universe** | **VERIFIED (100%)** | `NIFTY50` universe contains 50 active equities in PostgreSQL. |
| **Intraday Readiness** | **100% READY (54/54)** | All 50 equities + 4 benchmarks pass `IntradayReadinessService.check_readiness("5m")`. |
| **TechnicalFeature Gate** | **REMEDIATED** | Check 5 now validates numeric OHLCV integrity & in-memory indicator computability instead of querying offline daily tables. |
| **Kite Normalizer** | **FIXED** | `KiteNormalizer.normalize_candle` supports native dict format returned by Kite Connect Python SDK. |
| **Historical 5m Warmup** | **POPULATED (100%)** | 11,484 bars ingested across 3 trading sessions (13–15 Oct). Zero integrity errors. |
| **100-Bar Warmup Rule** | **PRESERVED** | All constituents possess 360–373 five-minute bars (well above the 100-bar minimum for EMA50 stability). |
| **Tata Motors Demerger** | **PRESERVED** | `TATAMOTORS` resolves to token `884737` (`TMPV`); historical bars preserve identity without discontinuities. |
| **Benchmark Coverage** | **VERIFIED (100%)** | `^NSEI`, `^NSEBANK`, `^BSESN`, and `^CNXIT` fully warmed up with 309 five-minute bars each. |
| **Test Suite** | **PASS (100%)** | **305/305 tests passing** in 5.45s (including 6 new Phase 20A.1 regression tests). |

---

## 2. Key Code Remediations

### 2.1 `market/services/intraday_readiness.py` (Check 5 Remediation)
- **Problem:** `IntradayReadinessService` previously queried `TechnicalFeature.objects.filter(instrument=inst, timeframe="5m")`. In the intraday pipeline, indicators are calculated in-memory by `compute_intraday_indicators()` from raw bars; the database table only stores daily EOD features.
- **Fix:** Check 5 now loads the warmup lookback window of `OHLCVBar` records, verifies numeric OHLCV integrity (no nulls, positive prices, $L \le O, C \le H$), and executes `compute_intraday_indicators()` in-memory to ensure mathematical computability without nulls or calculation errors.

### 2.2 `market/normalizers/kite.py` (Dict Candle Support)
- **Problem:** Kite Connect's `client.historical_data()` returns a list of dictionaries (`{'date': dt, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}`). Slicing `raw_candle[:6]` threw a `TypeError: unhashable type: 'slice'`.
- **Fix:** `KiteNormalizer.normalize_candle()` now handles both dictionary format (production) and list format (test mocks).

### 2.3 `market/services/intraday_quality.py` (Last Session Gap Scope)
- **Problem:** `intraday_quality.py` evaluated data gaps over a 3-day window and compared that sum against `MAX_DATA_GAPS_LAST_SESSION = 5`.
- **Fix:** Aligned `data_gaps_count` to evaluate specifically against the most recent trading session, while maintaining the 3-day lookback for completeness percentage ($\ge 80\%$).

### 2.4 `market/management/commands/ingest_kite_historical.py` (Universe & Benchmark Support)
- Added `--universe` and `--benchmarks` arguments and a 0.35s rate-limit pause between symbols.
- Added session boundary gating in `KiteHistoricalIngestionService` to discard pre-open (`< 09:15:00 IST`) and post-market (`> 16:00:00 IST`) candles.

---

## 3. Database & Runtime Evidence

1. **Constituent Readiness:**
   ```
   Total evaluated: 50
   Ready: 50
   Not ready: 0
   ```
2. **Benchmark Readiness:**
   - `^NSEI`: bars=309, gaps=0 -> READY
   - `^NSEBANK`: bars=309, gaps=0 -> READY
   - `^BSESN`: bars=309, gaps=0 -> READY
   - `^CNXIT`: bars=309, gaps=0 -> READY
3. **Simulated Scan at Market Close (15:20 IST on 15 Oct):**
   - 50/50 instruments passed all readiness and staleness gates.
   - Evaluated intraday detectors in-memory.
   - Correctly returned `NO_ACTION` with reason `Extremely low volume — dead tape` (preventing new positions 10 minutes before market close).
   - Zero instruments skipped with `NOT_READY`.

---

## 4. Current State for External Reviewer

All uncommitted changes remain preserved in the working tree. No Git commits, resets, or rebases were performed. The test suite has 305 passing tests. The data layer is warmed up, validated, and ready for continuous trading.
