# NOMAD ANALYST — LIVE SESSION BUG & DEFECT REPORT

**Date of Audit:** September 7, 2026 — 12:12 IST  
**Environment:** Active NSE Market Session (09:15–15:30 IST)  
**Evaluated Components:** Kite Authentication, Ticker Streaming, Intraday State Manager, Opportunity Engine, Research Engine, IntelligentRouter.

---

## 1. Summary of Identified Defects

| Bug ID | Severity | Component | Summary | Status |
| :---: | :---: | :--- | :--- | :--- |
| **BUG-01** | **CRITICAL** | `llm/router.py` & `llm/registry.py` | **Premature Provider Blacklisting on Upstream 503:** When `gemini-3.7-flash` returns 503, the router blacklists the entire `google` provider instead of failing over to working models (`gemini-3.6-flash`, `gemini-3.5-flash`). Fallbacks then fail because Groq/Cerebras model IDs return 404 and Ollama is offline. | Identified |
| **BUG-02** | **HIGH** | `market/services/kite_ticker.py` & `run_kite_ticker_poc.py` | **Python 3.14 / Twisted Signal Thread Violation:** Running KiteTicker in a background thread causes `signal.signal(signal.SIGINT)` to raise `ValueError: signal only works in main thread of the main interpreter` inside Twisted, aborting the connection upgrade. | Identified |
| **BUG-03** | **HIGH** | `market/management/commands/run_kite_ticker_poc.py` | **Hardcoded Env Credential Check Ignoring Database Tokens:** Management command checks `getattr(settings, 'KITE_ACCESS_TOKEN', '')` and falls back to mock mode if not found, even when a valid, active access token is already saved in PostgreSQL (`KiteCredential`). | Identified |
| **BUG-04** | **MEDIUM** | `market/services/intraday_opportunity_config.py` & `intraday_state_manager.py` | **Tight Freshness Expiry Window (60s):** `MAX_FRESHNESS_AGE_SECONDS = 60.0` causes opportunities to toggle into `STALE_MARKET_DATA` with a 25-point penalty if quote polling is delayed by even a few seconds. | Identified |
| **BUG-05** | **MEDIUM** | `market/services/intraday_opportunity_engine.py` | **Missing Convenience Wrapper `scan_and_rank()`:** In `intraday_opportunity_engine.py`, caller expects a top-level `scan_and_rank()` method, but the engine only exposes `evaluate_universe_opportunities()`, causing an `AttributeError` when invoked directly. | Identified |
| **BUG-06** | **LOW** | `market/models.py` (`KiteCredential`) | **Missing Class Method `KiteCredential.get_active()`:** Helper scripts attempt to call `KiteCredential.get_active()`, but `KiteCredential` only defines `objects.filter(account_id='default')`. | Identified |

---

## 2. In-Depth Defect Breakdown & Root Cause Analysis

### BUG-01: IntelligentRouter Provider Blacklisting & Deprecated Fallback Model IDs
* **Location:** [`llm/router.py:403-433`](file:///Users/shivamsingh/personal/nomad-analyst/llm/router.py#L403-L433) and [`llm/registry.py:143-149`](file:///Users/shivamsingh/personal/nomad-analyst/llm/registry.py#L143-L149)
* **Observed Behavior:**
  When `POST /api/v1/research/examine/` was called for `INFY`, the request failed with:
  ```text
  API request failed: HTTPConnectionPool(host='localhost', port=11434): Max retries exceeded with url: /v1/chat/completions (Connection refused)
  ```
* **Root Cause:**
  1. `MODEL_POOLS[LLMComplexity.COMPLEX]` lists `gemini-3.7-flash` as first priority. When Google Cloud returns an upstream `503 Service Unavailable` on that specific preview model, `self.health_monitor.report_failure("google")` is immediately triggered.
  2. In the next iteration of the loop, line 403 checks `if not self.health_monitor.is_healthy(config.provider_key): continue`. Because provider `"google"` is marked in cooldown, `gemini-3.6-flash` and `gemini-3.5-flash` are **completely skipped**, despite both being active, responsive, and working with your API key!
  3. The router then triggers global fallbacks:
     * `groq` (`mixtral-8x7b-32768`): Returns 404 (model deprecated by Groq).
     * `cerebras` (`llama3.1-8b`): Returns 404.
     * `openrouter` (`meta-llama/llama-3-8b-instruct:free`): Returns 404.
     * `ollama` (`qwen3:8b`): Fails with `Connection refused` (local Ollama server not running).
* **Proposed Surgical Fix:**
  1. Update `MODEL_POOLS[COMPLEX]` in `llm/registry.py` to prioritize `gemini-3.6-flash` and `gemini-3.5-flash`.
  2. Update `health_monitor` to track health at the `(provider, model)` level rather than penalizing the entire provider on a single model 503.
  3. Update fallback model names in `.env` (e.g. Groq to `llama-3.3-70b-versatile`).

---

### BUG-02: Twisted Signal Handler Thread Violation in Python 3.14
* **Location:** [`market/services/kite_ticker.py:188-196`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/kite_ticker.py#L188-L196)
* **Observed Behavior:**
  When running `python manage.py run_kite_ticker_poc`, the worker thread starts, but Twisted fails during socket initialization:
  ```text
  File ".../twisted/internet/_signals.py", line 150, in install
    signal.signal(signal.SIGINT, self._sigInt)
  ValueError: signal only works in main thread of the main interpreter
  ```
* **Root Cause:**
  The `kiteconnect.KiteTicker` library uses Twisted under the hood. Twisted attempts to install POSIX signal handlers (`SIGINT`, `SIGTERM`) by default. Because `KiteTickerManager.start()` starts Twisted in a daemon background thread (`threading.Thread(target=self._run, daemon=True)`), Python 3.14 forbids signal handler installation outside the main interpreter thread.
* **Proposed Surgical Fix:**
  Either disable Twisted signal installation prior to running the thread (`twisted.internet.base.DelayedCall.debug = False` or passing `installSignalHandlers=False` to `reactor.run()`), or run the ticker process as a dedicated CLI process where the reactor executes on the main thread.

---

### BUG-03: Hardcoded Env Check in `run_kite_ticker_poc.py`
* **Location:** [`market/management/commands/run_kite_ticker_poc.py:93-102`](file:///Users/shivamsingh/personal/nomad-analyst/market/management/commands/run_kite_ticker_poc.py#L93-L102)
* **Observed Behavior:**
  Running the management command printed:
  ```text
  No active Kite credentials found in settings/.env.
  Automatically activating MOCK mode for live ticker validation.
  ```
* **Root Cause:**
  Line 93 performs:
  ```python
  has_creds = bool(getattr(settings, "KITE_API_KEY", "") and getattr(settings, "KITE_ACCESS_TOKEN", ""))
  ```
  It ignores the database model `KiteCredential.objects.filter(account_id='default')`, which was updated when Shivam authenticated via OAuth. Because `.env` had a placeholder `KITE_ACCESS_TOKEN=your_actual_access_token`, it falsely concluded that no credentials existed.
* **Proposed Surgical Fix:**
  Replace line 93 with:
  ```python
  from market.services.kite_auth import KiteCredentialService
  has_creds = bool(KiteCredentialService.get_valid_access_token())
  ```

---

### BUG-04: Overly Strict Freshness Expiry Window (60s)
* **Location:** [`market/services/intraday_opportunity_config.py:14`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_opportunity_config.py#L14)
* **Observed Behavior:**
  When querying `GET /api/v1/intraday/opportunities/`, all 50 candidates were excluded with `STALE_MARKET_DATA` because `freshness_age_seconds` was `63.1s` (exceeding `MAX_FRESHNESS_AGE_SECONDS = 60.0`).
* **Root Cause:**
  Zerodha quote snapshots were polled periodically. If the polling interval is 60 seconds, slight network jitter pushes the age to 62–65 seconds, instantly triggering a total exclusion of all opportunities.
* **Proposed Surgical Fix:**
  Increase `MAX_FRESHNESS_AGE_SECONDS` to `120.0`s (or `180.0`s) in config, with gradual penalty degradation rather than a binary cliff-edge exclusion.

---

### BUG-05: Missing Method `scan_and_rank` on `IntradayOpportunityEngine`
* **Location:** [`market/services/intraday_opportunity_engine.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/intraday_opportunity_engine.py)
* **Observed Behavior:**
  Calling `opp_engine.scan_and_rank()` threw:
  ```text
  AttributeError: 'IntradayOpportunityEngine' object has no attribute 'scan_and_rank'
  ```
* **Root Cause:**
  The engine is designed as a functional pipeline where `IntradayStateManager.compute_current_opportunities()` calls `evaluate_universe_opportunities()`. External callers expecting a standalone `scan_and_rank()` method encounter an `AttributeError`.
* **Proposed Surgical Fix:**
  Add a helper convenience method `scan_and_rank(self, mode='RAW_RANKING', limit=10)` directly on `IntradayOpportunityEngine` that fetches current state and returns ranked results.

---

### BUG-06: Missing Helper `KiteCredential.get_active()`
* **Location:** [`market/models.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/models.py)
* **Observed Behavior:**
  Calling `KiteCredential.get_active()` threw `AttributeError: type object 'KiteCredential' has no attribute 'get_active'`.
* **Root Cause:**
  `KiteCredential` has no `@classmethod get_active()`. Callers must either use `KiteCredential.objects.filter(account_id="default").first()` or `KiteCredentialService.get_valid_access_token()`.
* **Proposed Surgical Fix:**
  Add a `@classmethod get_active(cls, account_id="default")` to `KiteCredential` to provide standard convenience across scripts.
