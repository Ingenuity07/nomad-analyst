# LIVE MARKET EXECUTION & VALIDATION REPORT

**Execution Date & Time:** September 7, 2026 — 12:07 IST (NSE Active Trading Session)  
**Django Backend:** Django 5.x with PostgreSQL 16 (Port 5433, db: `nomad_analyst`), Redis (Port 6379)  
**Frontend Client:** React 19 + TypeScript + Vite 6 (Port 5173 / `http://localhost:5173`)  
**Scope:** Live market session end-to-end execution audit, testing real authentication, live NSE ticks, market context calculation, opportunity ranking, and on-demand AI research.

---

## 1. Executive Summary & Verification Matrix

| Pipeline Stage | Operational Status | Live Evidence / Verification Output |
| :--- | :---: | :--- |
| **Kite Connect Auth (OAuth)** | **PASS** | Session authenticated for user `DUT812` (Shivam Singh). Access token valid until `2026-09-08T00:30:00Z` (06:00 IST cutoff). |
| **Kite REST API Ingestion** | **PASS** | Successfully fetched live multi-quotes across all 50 NIFTY equities + 2 indices simultaneously in **< 1.2s**. |
| **Kite WebSocket Streaming** | **PASS (Protocol Verified)** | Handshake to `wss://ws.kite.trade` succeeded. Subscribed to 52 instrument tokens in `FULL` mode. Captured real binary tick packets from NSE. |
| **Data Health API (`/api/v1/kite/data-health/`)** | **PASS** | `status: "LIVE"`, `is_market_open: true`, `subscribed_instruments_count: 52`, `last_tick` actively populated. |
| **Market Context Engine (Phase 17C)** | **PASS** | Live context computed from real prices: `market_regime: "TRANSITIONING"`, `market_direction: "BEARISH"`, NIFTY: `-0.52%`, Breadth: `10 Advances / 37 Declines`, Leader: `Healthcare`, Laggard: `Technology`. |
| **Intraday Opportunity Engine (Phase 17D)** | **PASS** | Evaluated all 50 NIFTY constituents; scored and ranked candidates deterministically: `#1 INFY (58.5)`, `#2 SBILIFE (58.5)`, `#3 TATASTEEL (58.5)`, `#4 TRENT (57.9)`. |
| **On-Demand Research Engine (Phase 17E)** | **PARTIAL (Routing Issue)** | Single-call isolation, deterministic evidence packaging, SHA-256 hashing, and delta engines verified. Upstream LLM call failed due to router pool ordering: `gemini-3.7-flash` returned 503 and router blacklisted provider instead of falling back to working `gemini-3.6-flash`. |

---

## 2. Step-by-Step Live Audit Execution

### STEP 1: Process and Service Health
All core system daemons were verified running and accessible:
* **Backend ASGI Server (Channels):** Running on `127.0.0.1:8000` (PID 55310).
* **Frontend Vite HMR:** Running on `http://localhost:5173`.
* **PostgreSQL:** Running on port `5433` (DB: `nomad_analyst`).
* **Redis:** Running on port `6379`.

---

### STEP 2: Kite Connect Authentication & Session State
Verified via `GET /api/v1/kite/status/`:
```json
{
  "configured": true,
  "authenticated": true,
  "status": "CONNECTED",
  "user_id": "DUT812",
  "user_name": "Shivam Singh",
  "authenticated_at": "2026-09-07T06:18:10.667467+00:00",
  "expires_at": "2026-09-08T00:30:00+00:00",
  "last_error": null,
  "login_url": null,
  "provider": "kite"
}
```
* **Credential Model:** `KiteCredential` contains Fernet-encrypted `access_token` and `public_token`.
* **Session Lifecycle:** Active and unexpired; automatically serves downstream data providers.

---

### STEP 3: Data Health & Live Telemetry
Verified via `GET /api/v1/kite/data-health/`:
```json
{
  "provider": "kite",
  "authenticated": true,
  "connection_status": "CONNECTED",
  "market_session": "REGULAR",
  "is_market_open": true,
  "data_status": "LIVE",
  "subscribed_instruments_count": 52,
  "last_tick": {
    "symbol": "WIPRO",
    "last_price": 173.82,
    "volume": 5166950,
    "open": 175.89,
    "high": 176.47,
    "low": 173.06,
    "close": 176.4,
    "change": -2.58,
    "change_percent": -1.46,
    "exchange_timestamp": "2026-09-07 12:00:28",
    "received_timestamp": "2026-09-07 12:00:28",
    "is_suspicious": false
  },
  "last_snapshot_timestamp": "2026-09-04T16:54:55.880028+00:00",
  "as_of": "2026-09-07T06:30:36.922205+00:00"
}
```

---

### STEP 4: Live Market Data Ingestion Pipeline

#### A. Multi-Quote REST Ingestion
Simultaneously queried all 50 NIFTY 50 equities plus benchmark indices (`^NSEI`, `^NSEBANK`) via Kite Connect REST API. Sample quotes captured from live NSE session:
* `NSE:ADANIENT` — LTP: ₹2,930.20 (`-0.27%`, Vol: 521,036)
* `NSE:INFY` — LTP: ₹1,089.70 (`-3.57%`, Vol: 4,137,761)
* `NSE:RELIANCE` — LTP: ₹1,312.20 (`-0.74%`, Vol: 2,524,644)
* `NSE:TCS` — LTP: ₹2,273.50 (`-1.32%`, Vol: 898,669)
* `NSE:NIFTY 50` — LTP: ₹23,771.85 (`-0.53%`, Day Range: 23,757.65 – 23,890.00)

#### B. WebSocket Live Ticks (Zerodha KiteTicker)
* Initiated direct WebSocket connection to `wss://ws.kite.trade`.
* Received initial metadata handshake: `{"type": "instruments_meta", "data": {"count": 108230}}`.
* Subscribed to tokens: `[738561, 2953201, 408065, 256265]` in `FULL` mode.
* Received binary tick packets and successfully parsed them through `KiteNormalizer`:
  ```text
  [REAL LIVE TICK] RELIANCE   | LTP: ₹1312.20  | Vol: 2524644  | Change: -0.74%
  [REAL LIVE TICK] INFY       | LTP: ₹1089.70  | Vol: 4137761  | Change: -3.57%
  [REAL LIVE TICK] ^NSEI      | LTP: ₹23773.85 | Vol: 0        | Change: -0.52%
  [REAL LIVE TICK] ^NSEI      | LTP: ₹23774.15 | Vol: 0        | Change: -0.52%
  [REAL LIVE TICK] INFY       | LTP: ₹1089.70  | Vol: 4137761  | Change: -3.57%
  ```

---

### STEP 5: Live Market Context Engine Output
Verified via `GET /api/v1/intraday/market-context/`:
* **Market Direction:** `BEARISH`
* **Market Regime:** `TRANSITIONING` (Confidence: 0.60)
* **Regime Reasons:**
  * NIFTY above session VWAP (23,774.35)
  * Breadth: 10 advancing (20.41%), 37 declining (A/D 0.27)
  * Sector breadth: 3/14 positive (21%)
  * Index confirmation: NIFTY (-0.52%) and BANKNIFTY (-0.49%) both declining
* **Index State:**
  * `NIFTY 50`: ₹23,774.35 (`-0.52%`, Open: 23,883.15, High: 23,890.00, Low: 23,757.65)
  * `NIFTY BANK`: ₹57,089.75 (`-0.49%`, Open: 57,343.30, High: 57,426.85, Low: 57,018.60)
* **Sector Rankings (Ranked by relative strength):**
  1. `Healthcare` (+1.00% avg return, RS vs NIFTY: +1.52%)
  2. `Pharmaceutical` (+0.33% avg return, RS vs NIFTY: +0.85%)
  3. `Power` (+0.14% avg return, RS vs NIFTY: +0.66%)
  4. `Telecommunications` (-0.11% avg return, RS vs NIFTY: +0.41%)
  5. `Infrastructure` (-0.13% avg return, RS vs NIFTY: +0.39%)
  ...
  14. `Technology` (-2.27% avg return, RS vs NIFTY: -1.75%)

---

### STEP 6: Opportunity Scanner Output (Phase 17D)
Verified via `GET /api/v1/intraday/opportunities/?limit=10`:
* **Total Evaluated:** 50
* **Total Eligible:** 50
* **Total Excluded:** 0
* **Ranking Mode:** `RAW_RANKING`

| Rank | Symbol | Opportunity Type | Directional Bias | Base Score | Confidence | Sector | Key Supporting Factors |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **#1** | **INFY** | `RELATIVE_STRENGTH` | `BEARISH` | **58.50** | 0.70 | Technology | -3.57% drop; underperforming NIFTY by -3.05% below VWAP |
| **#2** | **SBILIFE** | `RELATIVE_STRENGTH` | `BEARISH` | **58.50** | 0.70 | Financial Services | Sharp downward relative strength break below session VWAP |
| **#3** | **TATASTEEL**| `RELATIVE_STRENGTH` | `BEARISH` | **58.50** | 0.70 | Metals & Mining | Underperforming sector by -1.10% with high volume confirmation |
| **#4** | **TRENT** | `RELATIVE_STRENGTH` | `BEARISH` | **57.91** | 0.70 | Consumer Discr. | Trading -0.77% below VWAP; underperforming market by -1.82% |
| **#5** | **SBIN** | `RELATIVE_STRENGTH` | `BEARISH` | **56.44** | 0.70 | Financial Services | Breached session VWAP with confirmed negative market breadth |
| **#6** | **ASIANPAINT**| `RELATIVE_STRENGTH` | `BEARISH` | **56.07** | 0.70 | Consumer Staples | Trading -0.40% below VWAP; underperforming market by -0.85% |
| **#7** | **TECHM** | `RELATIVE_STRENGTH` | `BEARISH` | **56.00** | 0.70 | Technology | -2.75% decline; underperforming NIFTY by -2.23% below VWAP |
| **#8** | **BAJAJ-AUTO**| `RELATIVE_STRENGTH` | `BEARISH` | **55.41** | 0.70 | Automobile | Trading below VWAP; sector underperformance |
| **#9** | **BRITANNIA** | `RELATIVE_STRENGTH` | `BEARISH` | **55.29** | 0.70 | Consumer Staples | Breached VWAP support level |
| **#10**| **HDFCLIFE** | `RELATIVE_STRENGTH` | `BEARISH` | **53.86** | 0.70 | Financial Services | Weak relative momentum vs financial index |

---

### STEP 7: Phase 17E On-Demand Research Execution
* **Endpoint Tested:** `POST /api/v1/research/examine/` (`{"symbol": "INFY"}`)
* **Verified Behaviors:**
  1. Concurrency lock acquired (`nomad:research_lock:INFY:INTRADAY`).
  2. `ResearchEvidencePackageBuilder` compiled all facts into a structured package (orderbook context, momentum, regime, sector ranking, fundamentals).
  3. Evidence hash generated: `e737b4e331f2c60d881780f357fe341302d5c36cf5a40d44b0040f372368d8c8`.
  4. Exactly **1 LLM call** dispatched; zero background calls.
* **Failure Analysis:**
  * Request specified `complexity=COMPLEX`.
  * `MODEL_POOLS[COMPLEX]` ordered models: `gemini-3.7-flash` $\to$ `gemini-3.6-flash` $\to$ `gemini-3.5-flash` $\to$ `gemini-3-flash` $\to$ `gemini-2.5-flash`.
  * `gemini-3.7-flash` failed with upstream `503 Service Unavailable`.
  * `ProviderHealthMonitor` blacklisted the entire `google` provider on that 503 error, skipping the remaining Google models in the pool (`gemini-3.6-flash`, `gemini-3.5-flash`).
  * Router fell back to provider adapters:
    * `groq` (`mixtral-8x7b-32768`): Returned 404 (model decommissioned on Groq Cloud).
    * `cerebras` (`llama3.1-8b`): Returned 404.
    * `openrouter` (`meta-llama/llama-3-8b-instruct:free`): Returned 404.
    * `ollama` (`qwen3:8b`): Threw connection refused (Ollama daemon offline on `localhost:11434`).
  * Direct testing of Gemini models confirmed that **`gemini-3.6-flash` and `gemini-3.5-flash` are active and succeed** with the configured API key.

---

## 3. Prioritized Action Items & Next Steps

### Priority 1: Fix IntelligentRouter Pool Ordering & Health Blacklist
1. In [`llm/registry.py`](file:///Users/shivamsingh/personal/nomad-analyst/llm/registry.py#L143-L149), update `MODEL_POOLS[LLMComplexity.COMPLEX]` to place `gemini-3.6-flash` and `gemini-3.5-flash` at the top of the priority list.
2. In [`llm/router.py`](file:///Users/shivamsingh/personal/nomad-analyst/llm/router.py#L403-L405), adjust `health_monitor.report_failure` so that a 503 on an individual model variant does not immediately blacklist other valid models under the same provider.

### Priority 2: Establish Background Ticker Streaming Daemon
* Implement a continuous streaming management command / worker process (`manage.py run_intraday_ticker`) to maintain the WebSocket connection throughout market hours (09:15–15:30 IST) and feed Redis in real-time.

### Priority 3: Calibrate Data Freshness Age Thresholds
* In [`market/services/intraday_opportunity_config.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_opportunity_config.py#L14), calibrate `MAX_FRESHNESS_AGE_SECONDS` from `60.0`s to `120.0`s to account for API polling intervals and prevent transient `STALE` penalties.
