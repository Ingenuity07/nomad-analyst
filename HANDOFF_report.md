# NOMAD ANALYST — LIVE MARKET PIPELINE & SYSTEM HANDOFF REPORT
**Date:** Monday, September 7, 2026  
**Session:** Live NSE Intraday Market Session (09:15 – 15:30 IST)  
**System Status:** **100% OPERATIONAL & VERIFIED**  
**Detailed Audit & Telemetry:** [docs/audits/HANDOFF_report_2026-09-07.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/HANDOFF_report_2026-09-07.md)

---

## 1. Executive Summary

Nomad Analyst's real-time intraday market intelligence pipeline has been fully implemented, calibrated, debugged, and verified live against the National Stock Exchange (NSE) during active market trading hours on September 7, 2026.

All five architectural tiers are operational:

```text
       LIVE DATA (Zerodha Kite WebSocket + REST Multi-Quote)
                           │
                           ▼
          TICKER (KiteTickerManager / run_intraday_ticker)
                           │
                           ▼
             REDIS (Shared Multi-Process In-Memory State)
                           │
                           ▼
          DATA FRESHNESS (Dual-Source Recency Validation)
                           │
                           ▼
       ALL INTELLIGENCE (Market Context + Opportunity Scanner + AI Deep-Dive)
```

### Core Architecture & Compliance Rules Confirmed:
1. **Zero LLM Background Calls:** Background streaming, Redis caching, Market Context calculations (Phase 17C), and Intraday Opportunity Scanning (Phase 17D) execute with **strictly 0 LLM calls**.
2. **Single-Call On-Demand AI Examination (Phase 17E):** Deep research examination (`POST /api/v1/research/examine/`) is strictly user-initiated. When triggered, it executes **exactly 1 LLM call** using `gemini-3.6-flash`. Repeated requests within the cache window reuse the report with **0 LLM calls**.
3. **Python 3.14 & Twisted Compatibility:** Resolved Twisted signal handling conflicts on macOS arm64 Python 3.14.
4. **Resilient Failover:** IntelligentRouter provider blacklisting has been isolated to individual model cooldowns, preventing provider cascade failures.

---

## 2. End-to-End Pipeline Architecture

### Tier 1: LIVE DATA
- **Provider:** Zerodha Kite Connect API v3.
- **Account:** Shivam Singh (`DUT812`).
- **Authentication:** OAuth 2.0 session persisted in PostgreSQL (`KiteCredential.objects.get(account_id='default')`). Access token valid until tomorrow 06:00 IST.
- **Streaming Socket:** `wss://ws.kite.trade` streaming binary packets for 52 instruments (50 NIFTY equities + `^NSEI` + `^NSEBANK`).

### Tier 2: TICKER DAEMON
- **Service:** `python manage.py run_intraday_ticker` (Management command).
- **Manager:** [KiteTickerManager](file:///Users/shivamsingh/personal/nomad-analyst/market/services/kite_ticker.py).
- **Mode:** `MODE_FULL` (LTP, LTQ, Volume, OHLC, VWAP, Bid/Ask Market Depth, Exchange Timestamps).
- **Throughput:** ~40–50 ticks/second during active trading, batched and normalized into `NomadMarketTick` dataclasses.

### Tier 3: REDIS STATE
- **Host / Port:** `127.0.0.1:6379`.
- **Key Hierarchy:**
  - `kite_last_tick`: Latest tick received across the entire market.
  - `live_tick:<SYMBOL>`: Real-time price, volume, OHLC, change %, and timestamp per instrument.
  - `stock_state:<SYMBOL>`: Pre-calculated constituent state with sector mapping.
  - `index_state:<INDEX>`: Live index state for NIFTY 50 and BANKNIFTY.

### Tier 4: DATA FRESHNESS
- **Tracker:** [IntradayStateManager.get_freshness_status()](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_state_manager.py).
- **Mechanism:** Evaluates timestamp recency by cross-referencing in-memory timestamps and shared Redis `kite_last_tick`.
- **Thresholds:**
  - `FRESH`: $< 15.0$ seconds (active streaming).
  - `STALE`: $15.0$ – $60.0$ seconds (delayed or intermittent feed).
  - `UNAVAILABLE`: $> 180.0$ seconds (disconnected or closed market).
- **Live Reading:** **`FRESH` (age: 0.1s – 0.2s)** during active streaming.

### Tier 5: ALL INTELLIGENCE
1. **Intraday Market Context (Phase 17C):**
   - Live regime classification (Trending vs Range vs Volatile vs Transitioning).
   - Market breadth (Advancing/Declining ratio, % above VWAP, % at day highs/lows).
   - Deterministic sector rankings (Leaders vs Laggards).
2. **Intraday Opportunity Scanner (Phase 17D):**
   - 8-dimensional multi-factor quantitative scoring (0–100) across all 50 stocks in $<100$ms.
   - Categorization: `EMERGING`, `CONFIRMED`, `WEAKENING`.
   - Explainable factors: Supporting factors, contradicting factors, penalties.
3. **On-Demand AI Research Examination (Phase 17E):**
   - Triggered on-demand by user click on dashboard or REST endpoint.
   - Grounds analysis strictly on deterministic evidence package.
   - Validates output against Pydantic [StructuredResearchOutput](file:///Users/shivamsingh/personal/nomad-analyst/research/schemas.py).

---

## 3. Bugs Identified & Resolutions Implemented

| Bug ID | Severity | Affected Component | Root Cause | Fix Applied | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BUG-01** | **CRITICAL** | `llm/router.py`, `llm/health.py`, `llm/registry.py` | Over-broad health monitor blacklisted `"google"` provider entirely when `gemini-3.7-flash` returned a 503, preventing intra-provider failover to `gemini-3.6-flash`. | 1. Isolated failure tracking to `(provider, model)` in [ProviderHealthMonitor](file:///Users/shivamsingh/personal/nomad-analyst/llm/health.py).<br>2. Prioritized `gemini-3.6-flash` and `gemini-3.5-flash` at the top of `MODEL_POOLS[COMPLEX]`.<br>3. Automatically injected Pydantic schema in [IntelligentRouter.execute()](file:///Users/shivamsingh/personal/nomad-analyst/llm/router.py). | **VERIFIED** (Calls succeed on attempt 1 with `gemini-3.6-flash`). |
| **BUG-02** | **HIGH** | `market/services/kite_ticker.py` | Twisted's reactor called `signal.signal(SIGINT)` outside the main thread, throwing `ValueError: signal only works in main thread` under Python 3.14. | Refactored `KiteTickerManager.start()` to invoke `kws.connect(threaded=True)` which passes `installSignalHandlers=False` to the Twisted reactor. | **VERIFIED** (Clean daemon startup and shutdown without signal crashes). |
| **BUG-03** | **HIGH** | `market/management/commands/run_kite_ticker_poc.py`, `market/services/kite_ticker.py` | Commands inspected `settings.KITE_ACCESS_TOKEN` (which held a dummy string) instead of querying PostgreSQL OAuth tokens. | Updated ticker initialization to resolve credentials dynamically via `KiteCredentialService.get_valid_access_token()`. | **VERIFIED** (Pulls active decrypted token for `DUT812`). |
| **BUG-04** | **MEDIUM** | `market/services/intraday_config.py`, `intraday_opportunity_config.py` | Overly tight freshness thresholds (5.0s) caused opportunities to be docked 25 points during normal market quiet periods. | 1. Calibrated `FRESH_THRESHOLD_SEC` to 15.0s, `STALE_THRESHOLD_SEC` to 60.0s, and `MAX_FRESHNESS_AGE_SECONDS` to 180.0s.<br>2. Bridged in-memory and Redis timestamps in [IntradayStateManager.get_freshness_status()](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_state_manager.py). | **VERIFIED** (`FRESH` status maintained continuously). |
| **BUG-05** | **MEDIUM** | `market/services/intraday_opportunity_engine.py` | `IntradayOpportunityEngine` lacked a direct `scan_and_rank()` convenience execution method. | Added `scan_and_rank()` method to evaluate, rank, and format universe opportunities directly. | **VERIFIED** (`scan_and_rank(limit=5)` executes in $<100$ms). |
| **BUG-06** | **MEDIUM** | `llm/gemini_api.py` | Hardcoded 30-second HTTP timeout in `GeminiAPIProvider` was too brief for large 25k-token research evidence packages. | Increased `timeout` to 90 seconds and categorized timeout exceptions as HTTP 408. | **VERIFIED** (Deep research synthesis completes reliably in 35–45s). |

---

## 4. Live Market Verification Telemetry Summary

All telemetry below was captured during the live NSE market session on September 7, 2026:

- **Feed Status:** `FRESH (age: 0.1s – 0.2s)`
- **Market Direction:** `BEARISH`
- **Market Regime:** `TRANSITIONING`
- **NIFTY 50 Change:** `-0.52%`
- **Market Breadth:** `11 Advances / 37 Declines` (Strong Negative Breadth)
- **Sector Leaders:** `Healthcare` (+0.73%), `Pharmaceutical` (+0.19%)
- **Sector Laggards:** `Technology` (-2.27%)
- **Top 5 Intraday Opportunities:**
  1. **INFY** — Score: **58.50** (`EMERGING`, Relative Strength, Technology)
  2. **SBILIFE** — Score: **58.50** (`EMERGING`, Relative Strength, Financial Services)
  3. **TATASTEEL** — Score: **58.50** (`EMERGING`, Relative Strength, Metals & Mining)
  4. **SBIN** — Score: **57.12** (`EMERGING`, Relative Strength, Financial Services)
  5. **TRENT** — Score: **56.92** (`EMERGING`, Relative Strength, Consumer Discretionary)
- **On-Demand AI Examination (`INFY`):**
  - Completed with **exactly 1 LLM call** via `gemini-3.6-flash`.
  - Second invocation returned in **0.01s** with **0 LLM calls** (cached reuse).

---

## 5. Operations & Quickstart Runbook

To run the complete Nomad Analyst system during live trading hours:

```bash
# Terminal 1: Background Data Services
brew services start postgresql@16
brew services start redis

# Terminal 2: Django Backend API (Port 8000)
cd /Users/shivamsingh/personal/nomad-analyst
source venv/bin/activate
python manage.py runserver 127.0.0.1:8000

# Terminal 3: Continuous Live Ticker Daemon
cd /Users/shivamsingh/personal/nomad-analyst
source venv/bin/activate
python manage.py run_intraday_ticker

# Terminal 4: Frontend UI (Port 5173)
cd /Users/shivamsingh/personal/nomad-analyst/frontend
npm run dev
```

For full system details, API endpoint documentation, and historical telemetry, see the complete report at [docs/audits/HANDOFF_report_2026-09-07.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/HANDOFF_report_2026-09-07.md).
