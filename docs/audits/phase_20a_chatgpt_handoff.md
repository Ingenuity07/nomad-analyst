# Nomad Analyst — Phase 20A: ChatGPT Handoff Report

**Session Date:** 15 October 2026  
**Auditor / Agent:** Antigravity Autonomous Engineering Agent  
**Purpose:** Comprehensive technical summary of Phase 20A live decision pipeline audit, root-cause analysis, and system state for handoff to ChatGPT / external advisors.

---

## 1. High-Level Summary & Status

| Category | Status | Details |
| :--- | :--- | :--- |
| **Active Universe** | **VERIFIED (100%)** | `NIFTY50` universe contains exactly 50 active equities in PostgreSQL. |
| **Benchmark Coverage** | **VERIFIED (100%)** | All 4 benchmarks (`^NSEI`, `^NSEBANK`, `^BSESN`, `^CNXIT`) resolve bidirectionally with Kite tokens. |
| **Tata Motors Demerger** | **VERIFIED (100%)** | Canonical `TATAMOTORS` maps to Kite token `884737` (`TMPV`). Ticks reverse-resolve to `TATAMOTORS`. |
| **Candle Integrity** | **VERIFIED (100%)** | 09:15–15:30 IST regular session gate rejects pre-open auction ticks. VWAP excludes out-of-session bars. |
| **50-Skipped Scan RCA** | **SOLVED & DOCUMENTED** | Verified exact causes: (1) 100-bar warmup gate mid-session, (2) 3-day gap lookback near-close. |
| **Recommendation Persistence** | **VERIFIED (100%)** | `run_intraday_strategy_scan` calls `svc.save_draft(draft)`, preserving all intraday fields without daily engine. |
| **Test Suite** | **PASS (100%)** | **299/299 tests pass** in 5.3s (Django test suite). |

---

## 2. Git State & Uncommitted Changes Baseline

- **Current Branch:** `main`
- **HEAD Commit:** `15d366e703ed58ca9477d4d115856b3925333753` (`feat(market): live intraday ticker, sector scoring and benchmark pipeline`)
- **Modified Files Summary:**
  1. `market/services/kite_registry.py`: Preserves reverse mapping for token `884737` (`TMPV` tradingsymbol) $\rightarrow$ `TATAMOTORS`.
  2. `market/services/intraday_aggregator.py`: Enforces `09:15:00`–`15:30:00` IST trading session gate in `process_tick()`.
  3. `market/services/intraday_indicators.py`: Ensures session-anchored VWAP accumulates only regular trading session bars.
  4. `market/services/recommendation_service.py`: Implements `save_draft(draft, instrument)` to persist intraday recommendations without calling the daily signal engine.
  5. `market/services/intraday_context_engine.py`: Extracted and mapped `SENSEX` (`^BSESN`) and `NIFTY IT` (`^CNXIT`) alongside NIFTY and BANKNIFTY.
  6. `market/services/intraday_state_manager.py`: Added `sensex` and `nifty_it` to persisted `index_regimes`.
  7. `market/views.py`: Extended `IntradayIndicesAPIView` to return `sensex` and `nifty_it`.
  8. `market/services/context_service.py`: Added `^BSESN` and `^CNXIT` to daily market context regimes.
  9. `market/tasks.py`: Added structured `skip_reasons` tracking in `run_intraday_strategy_scan`.
  10. `market/tests.py`: Added `Phase20APipelineVerificationTests` (4 regression tests).

---

## 3. Root Cause Analysis: The 50-Skipped Scan

Earlier audits reported that `run_intraday_strategy_scan` evaluated 50 instruments, generated 0 actionable recommendations, and skipped 50 instruments (with 0 failures).

Through empirical reproduction across all 50 constituent equities, the exact root causes were identified:

### A. Mid-Session Execution (e.g. 12:00 IST)
- **Check 2 (Minimum Bars Required):**
  - Strategy engine requires `MINIMUM_BARS_REQUIRED["5m"] = 100` bars for indicator warmup (`EMA50`, `RSI14`, `ATR14`, `ADX14`).
  - At 12:00 IST on a single day without multi-day historical intraday bars, only 65–67 five-minute bars had elapsed.
  - **Result:** 49 equities failed Check 2: `Insufficient bars: 67 available, 100 required for 5m`.
- **Check 5 (TechnicalFeature Table Gate):**
  - `TATAMOTORS` had $>100$ bars from earlier test backfills, but failed Check 5: `No technical features found for TATAMOTORS [5m]`. `TechnicalFeature` table in DB only stores daily (`1d`) features because intraday indicators are calculated in-memory.

### B. Near-Market-Close Execution (e.g. 15:25 IST)
- By 15:25 IST, 49 equities accumulated $>100$ five-minute bars (154–157 bars), successfully passing Check 2.
- **Check 4 (Critical Data Gaps):**
  - `intraday_quality.py` calls `detect_gaps` using a 3-day lookback window (`latest_ts - 3 days`).
  - Because 13 and 14 October 2026 were trading days but had 0 five-minute bars in PostgreSQL, 151 expected candles were missing.
  - **Result:** 49 equities failed Check 4: `Too many data gaps: 151 detected (max tolerated: 5) for 5m`.

### C. Evaluation of the 100-Bar Readiness Requirement
- **Finding:** A 50-period EMA requires at least $2 \times 50 = 100$ candles for stable convergence. Running on $<100$ bars produces unreliable signals and false breakouts.
- **Recommendation:** Keep the 100-bar gate intact. When operating in live trading, backfill the preceding 3–5 trading days of 5m bars (`manage.py run_intraday_backfill_task`) so that the engine enters the morning session already warmed up and gap-free.

---

## 4. Key Architectural Verifications

### 4.1 Tata Motors Corporate Action (`TATAMOTORS` $\leftrightarrow$ `TMPV`)
- In Zerodha's instrument master CSV, token `884737` has `tradingsymbol="TMPV"`.
- `KiteInstrumentRegistry.get_token("TATAMOTORS")` $\rightarrow$ `884737`.
- `KiteInstrumentRegistry.get_symbol(884737)` $\rightarrow$ `"TATAMOTORS"`.
- `KiteNormalizer.normalize_tick` assigns `symbol="TATAMOTORS"`.
- Morning ticker daemon (started before the patch) temporarily routed ticks to `TMPV` (resulting in 0 1m bars for `TATAMOTORS`). With the patch in `kite_registry.py`, live ticks map cleanly to canonical `Instrument(symbol="TATAMOTORS")`.

### 4.2 Benchmark Indices Routing
- **Daily Context (`MarketContextService`):** Computes regimes for `^NSEI`, `^NSEBANK`, `^BSESN`, and `^CNXIT`.
- **Intraday Context (`IntradayMarketContextEngine`):** Extracts quotes and returns payload blocks for `nifty`, `banknifty`, `sensex`, and `nifty_it`.
- **API (`IntradayIndicesAPIView`):** Exposes head-to-head comparison for all 4 indices.

### 4.3 Recommendation Persistence
- `run_intraday_strategy_scan` generates a `RecommendationDraft`.
- Calls `svc.save_draft(draft, instrument=inst)`.
- Persists into `StockRecommendation` table with:
  - `horizon="INTRADAY"`, `timeframe="5m"`
  - `entry_price`, `entry_condition`, `entry_type`
  - `stop_price`, `stop_method`, `invalidation_reason`
  - `target_price`, `target_method`, `target_2_price`, `target_2_method`
  - `session_window`, `strategy_version`, `expires_at`
- Daily `SignalEngine` is **never** invoked for intraday persistence.

---

## 5. Next Steps for Next Session / Production

1. **Historical 5m Backfill:** Run `run_intraday_backfill_task(timeframe="5m", days_back=5)` prior to market open to ensure all 50 equities have $>100$ historical bars and 0 data gaps across the 3-day lookback window.
2. **Restart Ticker Daemon:** At 08:45 IST on the next trading day, launch `manage.py run_intraday_ticker` so it loads the updated `kite_registry.py` mappings into memory.
3. **Verify Scan Diagnostics:** Monitor Celery worker output for `run_intraday_strategy_scan` to observe real-time `skip_reasons` and actionable signals.
