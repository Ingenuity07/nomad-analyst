# NOMAD ANALYST — POST-FIX ARCHITECTURE AUDIT

**DATE:** 2026-09-07  
**AUDIT MODE:** READ-ONLY ARCHITECTURE INSPECTION  
**FILES INSPECTED:**
- `llm/gemini_api.py`
- `llm/health.py`
- `llm/registry.py`
- `llm/router.py`
- `llm/tests.py`
- `market/management/commands/run_intraday_ticker.py`
- `market/management/commands/run_kite_ticker_poc.py`
- `market/services/intraday_config.py`
- `market/services/intraday_opportunity_config.py`
- `market/services/intraday_opportunity_engine.py`
- `market/services/intraday_scanner.py`
- `market/services/intraday_state_manager.py`
- `market/services/kite_credentials.py`
- `market/services/kite_ticker.py`
- `market/tests.py`
- `research/schemas.py`
- `research/services/on_demand_research.py`
- `HANDOFF_report.md`
- `docs/audits/HANDOFF_report_2026-09-07.md`

---

## 1. EXECUTIVE SUMMARY

**Overall architecture:** MOSTLY CLEAN  
**Confidence:** 8.5 / 10  

**Main conclusion:**  
The live-market pipeline architecture successfully transitions Nomad Analyst from a mock-reliant state to a live, decoupled, event-driven market data pipeline. The separation of concerns between WebSocket ingestion, Redis state caching, market context building, and opportunity scoring is intact and strictly follows project design principles. Credential resolution is 100% centralized through `KiteCredentialService`, and no production credentials bypass the encrypted database store.

However, four specific issues require attention before committing:
1. **Four test failures** exist in `llm.tests` and `market.tests` due to test assertions holding outdated hardcoded constants (e.g., expecting `gemini-3.5-flash` first, and expecting stale data thresholds at 5s/60s instead of the updated 15s/180s).
2. **Freshness threshold discrepancy**: `UNAVAILABLE_THRESHOLD_SEC = 180.0` is declared in `intraday_config.py`, but `intraday_state_manager.py` never checks it (it marks anything older than 60.0s as `UNAVAILABLE`).
3. **AI Router timeout stacking**: The timeout in `llm/gemini_api.py` was increased from 30s to 90s. With 3 retries, a single unresponsive model can block for up to 273 seconds.
4. **Information exposure in documentation files**: Two untracked markdown audit reports contain a 6-character access token prefix (`[REDACTED_PREFIX]`).

---

## 2. GIT CHANGE SUMMARY

| File | Change | Expected? | Risk |
|------|--------|-----------|------|
| `llm/gemini_api.py` | MODIFIED | Outside Scope | LOW (Timeout raised to 90s, retry count to 3) |
| `llm/health.py` | MODIFIED | Outside Scope | LOW (Isolated health state to `(provider, model)`) |
| `llm/registry.py` | MODIFIED | Outside Scope | LOW (Priority order re-sequencing for Gemini 3.x models) |
| `llm/router.py` | MODIFIED | Outside Scope | LOW (Per-model failure cooldown checks) |
| `market/management/commands/run_kite_ticker_poc.py` | MODIFIED | Yes | LOW (POC runner updated to consume canonical credentials) |
| `market/services/intraday_config.py` | MODIFIED | Yes | MEDIUM (Relaxed freshness constants; `UNAVAILABLE_THRESHOLD_SEC` unused in state manager) |
| `market/services/intraday_opportunity_config.py` | MODIFIED | Yes | LOW (`MAX_FRESHNESS_AGE_SECONDS` raised to 180s) |
| `market/services/intraday_opportunity_engine.py` | MODIFIED | Yes | LOW (Candidate eligibility rule updated to 180s) |
| `market/services/intraday_state_manager.py` | MODIFIED | Yes | LOW (Freshness evaluation method aligns with 15s/60s thresholds) |
| `market/services/kite_ticker.py` | MODIFIED | Yes | LOW (Normalized tick timestamp parsing and Redis pipeline write) |
| `research/schemas.py` | MODIFIED | Outside Scope | LOW (Explicit schema fields & null handling for Gemini response parser) |
| `market/management/commands/run_intraday_ticker.py` | UNTRACKED (NEW) | Yes | LOW (Dedicated production CLI runner for background ticker process) |
| `HANDOFF_report.md` | UNTRACKED (NEW) | Yes | MEDIUM (Doc contains partial token prefix) |
| `docs/audits/HANDOFF_report_2026-09-07.md` | UNTRACKED (NEW) | Yes | MEDIUM (Doc contains partial token prefix) |
| `docs/audits/live_market_execution_report_2026-09-07.md` | UNTRACKED (NEW) | Yes | LOW (Audit logs and metrics) |
| `docs/audits/live_session_bug_report_2026-09-07.md` | UNTRACKED (NEW) | Yes | LOW (Audit bug logs) |

---

## 3. LIVE TICKER AUDIT

### Ingestion Flow
```
KiteCredentialService (Active DB row, Fernet decrypted)
        ↓
KiteTickerManager (market/services/kite_ticker.py)
        ↓
run_intraday_ticker (CLI daemon command)
        ↓
KiteTicker WebSocket (kiteconnect.KiteTicker)
        ↓
on_ticks -> Tick Normalization (price, volume, timestamp)
        ↓
Redis (live_tick:<SYM>, kite_last_tick, stock_state:<SYM>)
        ↓
IntradayStateManager (market/services/intraday_state_manager.py)
        ↓
IntradayMarketContextBuilder / IntradayScanner / OpportunityEngine / API
```

### Assessment: CLEAN

### Answers to Mandatory Questions:
1. **Is there exactly one primary ticker implementation?**  
   **Yes.** `KiteTickerManager` is the sole engine handling websocket subscriptions, tick receipt, normalization, and Redis publication.
2. **Are there duplicate ticker managers?**  
   **No.** No other ticker manager classes exist.
3. **Are there multiple competing management commands?**  
   **Warning:** Two commands exist:
   - `run_intraday_ticker` (production daemon command with signal handling and structured shutdown).
   - `run_kite_ticker_poc` (original proof-of-concept runner, now updated to call `KiteTickerManager`).  
   Both call `KiteTickerManager`, but only `run_intraday_ticker` should be used in production.
4. **Is any old ticker implementation still being used?**  
   **No.** Both commands use `KiteTickerManager`.
5. **Does the dedicated ticker process accidentally duplicate subscriptions?**  
   **No.** `KiteTickerManager.start()` performs a single `subscribe()` call with the full list of instrument tokens derived from `UNIVERSE_CONFIG`.
6. **Is WebSocket lifecycle handled in one clear place?**  
   **Yes.** Inside `KiteTickerManager` callbacks (`on_connect`, `on_ticks`, `on_close`, `on_error`, `on_reconnect`, `on_noreconnect`).
7. **Is reconnect behavior duplicated?**  
   **No.** KiteTicker's native auto-reconnect (`set_reconnect_settings(5, 5, 2)`) handles socket reconnects internally.
8. **Does Django API process still attempt to own the WebSocket?**  
   **No.** The Django ASGI/WSGI web workers do not initialize or own WebSockets. They read exclusively from Redis via `IntradayStateManager`.
9. **Is Redis the correct shared communication layer?**  
   **Yes.** Decoupling the continuous WebSocket ingestion process from the HTTP request/response cycle via Redis is the correct pattern.
10. **Is the architecture simpler or more complex than before?**  
    **Simpler and cleaner.** Ingestion runs as an independent daemon; web requests read atomic snapshots from Redis with sub-millisecond latencies.

---

## 4. CREDENTIAL AUDIT

### Canonical Credential Path
```
KiteCredentialService.get_valid_access_token()
        ↓
KiteCredential.objects.filter(is_active=True).first()
        ↓
KiteCredentialService.decrypt_token(credential.encrypted_access_token)
        ↓
Decrypted Plaintext Access Token
```

### Production Credential Access Table

| File | Component | Credential Source | Production Safe? | Expected? |
|------|-----------|-------------------|------------------|-----------|
| `market/services/kite_credentials.py` | `KiteCredentialService` | PostgreSQL (`KiteCredential`) via `get_valid_access_token()` | YES | YES (Canonical) |
| `market/services/kite_ticker.py` | `KiteTickerManager.__init__` | `KiteCredentialService.get_valid_access_token()` | YES | YES |
| `market/services/kite_client.py` | `KiteClientService.get_kite_client()` | `KiteCredentialService.get_valid_access_token()` | YES | YES |
| `market/management/commands/run_intraday_ticker.py` | CLI Command | Instantiates `KiteTickerManager()` (delegates to `KiteCredentialService`) | YES | YES |
| `market/management/commands/run_kite_ticker_poc.py` | POC CLI Command | Instantiates `KiteTickerManager()` (delegates to `KiteCredentialService`) | YES | YES |
| `market/management/commands/test_kite_auth.py` | Diagnostic CLI | `KiteCredentialService.get_valid_access_token()` | YES | YES |
| `market/views/kite_views.py` | OAuth Callback View | Stores newly generated session token via `KiteCredentialService.store_credentials()` | YES | YES |

### Bypasses and Violations:
- **Production Bypasses:** **NONE.** No production runtime component reads `KITE_ACCESS_TOKEN` directly from environment variables or bypasses `KiteCredentialService`.
- **Note on Settings:** `KITE_API_KEY` and `KITE_API_SECRET` are read from Django settings/environment to initiate the KiteConnect instance and perform token decryption/login, which is standard KiteConnect OAuth design.

---

## 5. FRESHNESS AUDIT

### Actual Freshness Thresholds in Code
- **Configuration File:** `market/services/intraday_config.py`
  - `FRESH_THRESHOLD_SEC = 15.0`
  - `STALE_THRESHOLD_SEC = 60.0`
  - `UNAVAILABLE_THRESHOLD_SEC = 180.0`
- **Opportunity Config:** `market/services/intraday_opportunity_config.py`
  - `MAX_FRESHNESS_AGE_SECONDS = 180.0`
- **Implementation:** `market/services/intraday_state_manager.py` (lines 227-235)
  ```python
  if age_sec <= FRESH_THRESHOLD_SEC:
      return MarketDataFreshness.FRESH
  elif age_sec <= STALE_THRESHOLD_SEC:
      return MarketDataFreshness.STALE
  else:
      return MarketDataFreshness.UNAVAILABLE
  ```

### Freshness Tiers & Boundary Behavior

| State | Min Age | Max Age | Boundary Behavior |
|-------|---------|---------|-------------------|
| **FRESH** | 0.0 sec | 15.0 sec | `age <= 15.0` is FRESH |
| **STALE** | 15.000...1 sec | 60.0 sec | `15.0 < age <= 60.0` is STALE |
| **UNAVAILABLE** | > 60.0 sec | $\infty$ | `age > 60.0` is UNAVAILABLE |

### Exact Age Evaluation

| Age | Evaluated State in `IntradayStateManager` |
|-----|-------------------------------------------|
| **0 sec** | `FRESH` |
| **14.9 sec** | `FRESH` |
| **15 sec** | `FRESH` (`15.0 <= 15.0`) |
| **59.9 sec** | `STALE` |
| **60 sec** | `STALE` (`60.0 <= 60.0`) |
| **120 sec** | `UNAVAILABLE` (`120.0 > 60.0`) |
| **179.9 sec** | `UNAVAILABLE` (`179.9 > 60.0`) |
| **180 sec** | `UNAVAILABLE` (`180.0 > 60.0`) |
| **181 sec** | `UNAVAILABLE` (`181.0 > 60.0`) |

### Key Findings:
1. **Is there a single centralized freshness implementation?**  
   **Yes.** `IntradayStateManager.evaluate_freshness()` is the sole calculation function used by scanners, context builders, and API views.
2. **Are thresholds duplicated or inconsistent?**  
   **Warning:** `intraday_config.py` defines `UNAVAILABLE_THRESHOLD_SEC = 180.0`, but `intraday_state_manager.py` has an `else: return MarketDataFreshness.UNAVAILABLE` right after `age_sec <= STALE_THRESHOLD_SEC` (60s). Thus, any tick between 60.0s and 180.0s is evaluated as `UNAVAILABLE` by the state manager, even though `MAX_FRESHNESS_AGE_SECONDS` in `intraday_opportunity_config.py` was increased to 180.0s.
3. **Can stale data be labeled fresh?**  
   **No.** Any tick older than 15.0 seconds is immediately labeled STALE.
4. **Can temporary quiet-market periods incorrectly invalidate opportunities?**  
   **Yes, partially.** For low-beta or illiquid stocks that do not tick for 60 seconds, `IntradayStateManager` marks them `UNAVAILABLE`, which drops them from candidate pools.
5. **Can stale data silently affect opportunity scores?**  
   **No.** Stale data receives an explicit penalty (multiplier reduction or candidate filtering in `IntradayOpportunityEngine`).

---

## 6. REDIS AUDIT

### Redis Keys Map

| Key Pattern | Writer | Readers | TTL | Payload Type | Purpose |
|-------------|--------|---------|-----|--------------|---------|
| `kite_last_tick` | `KiteTickerManager.on_ticks` | Health checks, diagnostics, ticker status views | None (Persistent until overwritten) | JSON String | Heartbeat timestamp & symbol of most recent market tick |
| `live_tick:<SYMBOL>` | `KiteTickerManager.on_ticks` | `IntradayStateManager.get_live_tick()` | 300 seconds (5 min) | JSON String (Price, Vol, Timestamp) | Fast atomic snapshot of latest instrument tick |
| `stock_state:<SYMBOL>` | `IntradayStateManager.update_stock_state()` | `IntradayStateManager`, `IntradayScanner` | 86400 seconds (24h) | JSON String (OHLC, Vol, VWAP, EMA) | Intraday cumulative state and indicators |
| `index_state:<INDEX>` | `IntradayStateManager.update_index_state()` | `IntradayMarketContextBuilder` | 86400 seconds (24h) | JSON String (LTP, Change, Trend) | Sector/benchmark market regime state |
| `nomad:research_lock:<SYM>:<MODE>` | `OnDemandResearchService` | `OnDemandResearchService` | 60 seconds | String `"locked"` | Concurrency mutex avoiding duplicate LLM calls |

### Assessment:
1. **Is Redis usage consistent?**  
   **Yes.** All keys follow clear prefix conventions (`live_tick:`, `stock_state:`, `nomad:research_lock:`).
2. **Are timestamps timezone-consistent?**  
   **Yes.** Normalization uses `datetime.now(timezone.utc).isoformat()` uniformly.
3. **Are TTLs appropriate?**  
   **Yes.** `live_tick` keys expire after 300 seconds, preventing stale ticks from persisting across trading sessions if the ticker process stops.
4. **Can multiple processes overwrite incorrectly?**  
   **No.** Only the dedicated ticker daemon writes to `live_tick:<SYMBOL>`. Web workers operate strictly as readers.

---

## 7. AI ROUTER AUDIT

### Model Failure Flow
```
Research Request
      ↓
IntelligentRouter.route()
      ↓
Active Candidates Filtered by:
  - capability (e.g. STRUCTURED_OUTPUT)
  - health cooldown check for (provider, model_name)
      ↓
Sorted by Model Priority
  1. gemini-3.7-flash (Priority 1)
  2. gemini-3.6-flash (Priority 2)
  3. gemini-3.5-flash (Priority 3)
      ↓
Attempt Execution on Top Candidate
      ↓
[Failure Occurs (e.g. 503, 429, Timeout)]
      ↓
ProviderHealthMonitor.record_failure(provider, model_name)
      ↓
Model marked unhealthy for its cooldown period (default 60s)
      ↓
IntelligentRouter attempts next candidate in priority list
      ↓
All models exhausted -> Provider-level failure triggered
```

### Assessment: CLEAN
1. **Health Tracking Granularity:**  
   Health is now strictly tracked at the `(provider, model_name)` composite key level. Previously, a 503 on `gemini-3.7-flash` would erroneously blacklist the entire Gemini provider, blocking fallbacks to `gemini-3.6-flash` and `gemini-3.5-flash`.
2. **Duplicate Systems:** None. `ProviderHealthMonitor` is the single authority.
3. **Infinite Retries:** None. The candidate pool is finite and strictly bounded by configured models.

---

## 8. GEMINI TIMEOUT AUDIT

### Implementation Details:
- **Location:** `llm/gemini_api.py` (line 38)
  - `DEFAULT_TIMEOUT = 90` (previously 30 seconds)
  - `MAX_RETRIES = 3`
- **Configurability:** Controllable via `settings.LLM_TIMEOUT` or constructor kwargs.

### Maximum Request Wait Time:
If an API call hangs indefinitely:
$$\text{Attempt 1 (90s)} + \text{Backoff 1 (1s)} + \text{Attempt 2 (90s)} + \text{Backoff 2 (2s)} + \text{Attempt 3 (90s)} = 273 \text{ seconds}$$

### Assessment: ACCEPTABLE (with Warning)
- **Reasoning:** For complex on-demand research syntheses (with 4000+ output tokens and Pydantic schema validation), 30 seconds was frequently timing out under high Google API load. 90 seconds resolved dropped connections.
- **Worker Risk:** Because Nomad Analyst executes on-demand research in asynchronous background threads/tasks, this does not block the ASGI web worker event loop. However, 273 seconds maximum stacking on a hard network hang is high; setting `MAX_RETRIES = 1` or `2` when `DEFAULT_TIMEOUT = 90` would be safer.

---

## 9. scan_and_rank() AUDIT

### Call Graph:
```
IntradayScanner.scan_and_rank(user)
      ↓
IntradayScanner.scan(user)
      ↓ (Fetches universe, builds intraday market context, filters candidate symbols)
IntradayOpportunityEngine.evaluate_candidates(candidates, market_context)
      ↓ (Scores and ranks candidates by composite score)
Returns: List[IntradayOpportunity] (sorted descending by composite_score)
```

### Assessment: CLEAN (Convenience Method)
- **Duplication:** **NO.** `scan_and_rank()` does not re-implement scanning or ranking. It simply composes `self.scan(user)` and `self.engine.evaluate_candidates(candidates, context)`.
- **Existing Scanner Behavior:** Unaltered. `scan()` remains untouched.
- **Used by:** Direct evaluation scripts, diagnostics, and test cases.

---

## 10. OPPORTUNITY ENGINE REGRESSION CHECK

### Detailed Regression Analysis:
- **Opportunity scoring weights:** **UNCHANGED.** Technical (0.35), Momentum (0.25), Volume (0.20), Volatility (0.10), Market Confirmation (0.10).
- **Score calculation formulas:** **UNCHANGED.** Relative volume, VWAP distance, EMA slope, breakout signals remain bit-for-bit identical.
- **Market regime logic:** **UNCHANGED.** ADX and EMA trend filters in `IntradayMarketContextBuilder` remain unaltered.
- **Sector calculations:** **UNCHANGED.** Weightings and relative strength calculations remain identical.
- **Eligibility rules:** **MODIFIED ONLY FOR FRESHNESS WINDOW.** Candidate filtering threshold `MAX_FRESHNESS_AGE_SECONDS` was widened from 60s to 180s to prevent intermittent ticker pauses from discarding valid trading setups.

### Question:
**Did any live infrastructure change alter the meaning of opportunity scores?**  
**NO.** The mathematical calculation and semantic meaning of opportunity scores are identical.

---

## 11. API CONTRACT AUDIT

### Inspected Endpoints:
- `GET /api/v1/market/intraday/opportunities/`
- `GET /api/v1/market/intraday/context/`
- `GET /api/v1/market/intraday/state/<symbol>/`
- `POST /api/v1/research/on-demand/`

### Findings:
- **Response fields:** Identical. No fields added, deleted, or renamed.
- **Response types:** Identical (numbers remain floats, timestamps remain ISO-8601 strings).
- **Status fields:** Identical (`FRESH`, `STALE`, `UNAVAILABLE` enum strings preserved).
- **Endpoint paths:** No changes.
- **Authentication:** Preserves standard Django REST Framework permission classes.
- **Backwards compatibility risk:** **NONE.**

---

## 12. DEAD CODE / DUPLICATION

1. **`run_kite_ticker_poc.py` vs `run_intraday_ticker.py`:**
   - Both management commands instantiate `KiteTickerManager`.
   - `run_intraday_ticker.py` includes proper UNIX signal traps (`SIGINT`, `SIGTERM`) and clean graceful exit handling.
   - `run_kite_ticker_poc.py` is a development leftover and can be retired once verified.
2. **`UNAVAILABLE_THRESHOLD_SEC` in `intraday_config.py`:**
   - Defined at line 34 (`UNAVAILABLE_THRESHOLD_SEC = 180.0`) but never referenced in `intraday_state_manager.py`.

---

## 13. SECURITY AUDIT

- **Secrets exposed in code/git:** **NO.** No API keys or credentials committed to git.
- **Token logging:** **NO in application code.** Token strings are sanitized in `kite_ticker.py` and `kite_credentials.py`.
- **Credential API exposure:** **NO.** API responses never serialize access tokens or secrets.
- **Redis secret storage:** **NO.** Redis stores only market data ticks (prices, volumes, timestamps) and lock mutexes.
- **Documentation Exposure Risk:**
  - **SECRET TYPE:** Kite Access Token Prefix (Partial)
  - **LOCATION:** `HANDOFF_report.md` (line 92) and `docs/audits/HANDOFF_report_2026-09-07.md` (line 92)
  - **EXPOSURE RISK:** Contains a 6-character prefix `[REDACTED_PREFIX]` printed in an audit log excerpt.
  - **SEVERITY:** LOW (Only a partial prefix; full 32-character secret is not present. However, it should be redacted before any git commit).

---

## 14. CRITICAL FINDINGS

### 1. Pre-existing Unit Test Failures (4 Tests Failing)
Running the test suite (`python manage.py test llm research market --keepdb`) reveals 4 failing tests due to updated constants in the production code:
1. **`llm.tests.LLMGenericModelRoutingTestCase.test_pool_selection_and_priority`**
   - *Failure:* `AssertionError: 'gemini-3.7-flash' != 'gemini-3.5-flash'`
   - *Cause:* Test asserts that index 0 in the model pool is `gemini-3.5-flash`. The registry re-prioritized `gemini-3.7-flash` to the top.
2. **`llm.tests.LLMGenericModelRoutingTestCase.test_structured_output_schema_validation_and_fallback`**
   - *Failure:* `AssertionError: 'Structured output failed after 1 attempts' not found in None`
   - *Cause:* Test fixture mocks `gemini-3.5` and `gemini-3.7` with a hardcoded assumption of the order in which fallback attempts occur.
3. **`market.tests.IntradayMarketContextTests.test_data_freshness_tiers`**
   - *Failure:* `AssertionError: <MarketDataFreshness.FRESH: 'FRESH'> != <MarketDataFreshness.STALE: 'STALE'>`
   - *Cause:* Test asserts that a 15-second-old tick is `STALE`. Under the updated configuration, `FRESH_THRESHOLD_SEC = 15.0`, so `age <= 15.0` evaluates to `FRESH`.
4. **`market.tests.IntradayOpportunityEngineTests.test_candidate_eligibility_filtering`**
   - *Failure:* `AssertionError: 0 != 1`
   - *Cause:* Test injects a mock tick with age 120 seconds, expecting it to be rejected by `MAX_FRESHNESS_AGE_SECONDS = 60.0`. In the updated configuration, `MAX_FRESHNESS_AGE_SECONDS = 180.0`, so the candidate is retained.

---

## 15. WARNINGS

1. **Dead Constant / Threshold Gap in `intraday_state_manager.py`:**
   `intraday_state_manager.py` defines:
   ```python
   if age_sec <= FRESH_THRESHOLD_SEC: # 15s
       return MarketDataFreshness.FRESH
   elif age_sec <= STALE_THRESHOLD_SEC: # 60s
       return MarketDataFreshness.STALE
   else:
       return MarketDataFreshness.UNAVAILABLE
   ```
   Because it jumps straight from `STALE` to `UNAVAILABLE` at 60 seconds, `UNAVAILABLE_THRESHOLD_SEC = 180.0` in `intraday_config.py` is unused. Any tick older than 60s is classified as `UNAVAILABLE` by the state manager, contradicting the 180s window in `intraday_opportunity_config.py`.
2. **LLM Timeout Stacking:**
   A 90-second timeout with 3 retries in `llm/gemini_api.py` could potentially stall a research task for 273 seconds if Google's API hangs without returning a TCP reset.

---

## 16. UNEXPECTED CHANGES

### 1. Model Registry Re-ordering & Health Monitor Refactoring
- **CHANGE:** Modified `llm/registry.py`, `llm/health.py`, and `llm/router.py` to prioritize `gemini-3.7-flash` and track health per `(provider, model)`.
- **WHY IT HAPPENED:** During live testing of on-demand research, a temporary upstream 503 error on one model caused the entire Gemini provider to be marked down, blocking all other Gemini models from being attempted.
- **IS IT GOOD:** Yes. Per-model cooldown isolation is strictly superior to whole-provider blacklisting.
- **VERDICT:** **KEEP** (Update tests to reflect the new priority order).

### 2. Gemini API Timeout Increased to 90s
- **CHANGE:** Raised timeout from 30s to 90s in `llm/gemini_api.py`.
- **WHY IT HAPPENED:** Complex structured output synthesis on live market data was exceeding the 30s window.
- **IS IT GOOD:** Yes, but retry counts should be reduced from 3 to 1 or 2 to avoid excessive 273s worst-case waits.
- **VERDICT:** **REVIEW**

### 3. Added `scan_and_rank()` to `IntradayScanner`
- **CHANGE:** Added helper method `scan_and_rank()` in `market/services/intraday_scanner.py`.
- **WHY IT HAPPENED:** Added as a direct convenience utility during live test validation.
- **IS IT GOOD:** Yes, it is clean composition without duplicating logic.
- **VERDICT:** **KEEP**

---

## 17. FINAL VERDICT

1. **Is the live ticker architecture clean?**  
   **YES.** The separation between `KiteTickerManager` (daemon ingestion) and `IntradayStateManager` (Redis read snapshot) is clean and decoupled.
2. **Is credential access centralized?**  
   **YES.** All production paths resolve credentials through `KiteCredentialService.get_valid_access_token()`.
3. **Is freshness logic consistent?**  
   **NO (Requires Alignment).** `intraday_config.py` specifies 180s for `UNAVAILABLE`, but `intraday_state_manager.py` marks data `UNAVAILABLE` after 60s.
4. **Is Redis architecture clean?**  
   **YES.** Key naming, data types, TTL management, and atomic read patterns are cleanly isolated.
5. **Did AI router changes introduce risk?**  
   **NO.** Per-model health isolation improved resiliency.
6. **Did `scan_and_rank()` introduce duplication?**  
   **NO.** It cleanly delegates to existing `scan()` and `engine.evaluate_candidates()` methods.
7. **Did recent fixes alter opportunity intelligence?**  
   **NO.** Scoring weights, math formulas, and regime classifications remain untouched.
8. **Are recent changes safe to commit?**  
   **NOT YET.** The 4 failing unit tests and the freshness threshold mismatch must be resolved before committing.
9. **What should be fixed BEFORE committing?**  
   - Update the 4 unit test assertions in `llm/tests.py` and `market/tests.py` to match the intended configuration constants.
   - Align `intraday_state_manager.py` so that its freshness tiers match `intraday_config.py` (`UNAVAILABLE_THRESHOLD_SEC = 180.0`).
   - Redact the 6-character token prefix from the untracked markdown audit documents.
10. **What should NOT be touched?**  
    - Do NOT alter `IntradayOpportunityEngine` scoring formulas or weights.
    - Do NOT alter the Redis key structure or normalization logic in `KiteTickerManager`.
    - Do NOT re-introduce provider-level blacklisting in `ProviderHealthMonitor`.

---
*(Strict Read-Only Audit Complete. Generated and saved as markdown.)*
