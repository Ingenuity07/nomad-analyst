# Module 8 Handoff — Recommendation & Signal Engine

## 1. What Was Built

### Signal Domain Enumerations
- Created [`market/signal_enums.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/signal_enums.py) with all domain enums:
  - `SignalDirection`: `BUY`, `SELL`, `NO_ACTION`, `INSUFFICIENT_DATA`, `NOT_READY`
  - `SignalHorizon`: `INTRADAY`, `DELIVERY_SWING`, `LONG_TERM`
  - `SetupType`: `BREAKOUT`, `BREAKDOWN`, `PULLBACK`, `MOMENTUM`, `TREND_CONTINUATION`, `RECOVERY_REVERSAL`, `NONE`, etc.
  - `ConfidenceLevel`: `LOW`, `MEDIUM`, `HIGH`
  - `RecommendationStatus`: `ACTIVE`, `TRIGGERED`, `TARGET_HIT`, `STOPPED`, `EXPIRED`, `INVALIDATED`, `CANCELLED`
  - `EntryType`, `StopMethod`, `TargetMethod`
  - Config constants: `MIN_RISK_REWARD`, `CONFIDENCE_WEIGHTS`, `REGIME_GATE_RULES`, `CONFIDENCE_THRESHOLD`

### Deterministic Setup Detectors
- Created [`market/services/setup_detectors.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/setup_detectors.py)
  - `detect_breakout()` — price near 20-day high + volume + RSI + trend
  - `detect_breakdown()` — price at 20-day low + volume + bearish RSI + below SMA-50
  - `detect_pullback()` — above SMA-200 + controlled retracement + RSI 35–55
  - `detect_momentum()` — golden cross + RSI 55–75 + volume + MACD alignment
  - `detect_reversal()` — RSI < 35 + near 20-day low + MACD histogram turning
  - `detect_trend_continuation()` — golden cross + price above SMA-50 + RSI 50–65
  - `run_all_detectors()` — runs all detectors and returns sorted by (detected, score) desc
  - Each returns a `SetupResult` dataclass with `conditions_met`, `conditions_failed`, `relevant_values`

### Signal Engine
- Created [`market/services/signal_engine.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/signal_engine.py)
  - `SignalEngine.generate_recommendation(instrument, horizon, as_of)` — fully deterministic
  - Intraday gate: returns `NOT_READY` for `INTRADAY` horizon when no intraday bars exist
  - PIT safety: all feature/bar/fundamental/news queries filtered to `timestamp__lte=as_of`
  - Entry calculation: setup-specific logic (breakout confirmation, support retest, CMP)
  - Stop calculation: structural → ATR-based → percentage fallback priority chain
  - Target calculation: measured move → ATR multiple → R:R derived priority chain
  - R:R rejection gate: recommendations below `MIN_RISK_REWARD` return `NO_ACTION`
  - Multi-dimensional confidence: 5 dimensions (technical, market, sector, fundamental, news) with configurable weights

### StockRecommendation Model
- Added [`market/models.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/models.py) `StockRecommendation` model
  - **Append-only**: every generation creates a new record, history is never overwritten
  - **Deterministic fields** (frozen at creation): `signal`, `entry_price`, `stop_price`, `target_price`, `risk_reward_ratio`
  - **Mutable fields**: `status`, `status_updated_at`, `llm_explanation` (LLM-written, isolated)
  - 3 composite indexes for performance: `(instrument, as_of)`, `(horizon, signal, status)`, `(as_of, status)`

### Recommendation Service
- Created [`market/services/recommendation_service.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/recommendation_service.py)
  - `generate_and_save(instrument, horizon, as_of)` — generates + persists (append-only)
  - `scan_and_recommend(universe_name, horizon, as_of)` — batch universe scan
  - `update_status(rec, new_status)` — lifecycle transitions (status only, never deterministic fields)
  - `expire_old_active_recommendations(max_age_days)` — batch expiration for scheduled task
  - `save_explanation(rec, text)` — LLM-only write-back to `llm_explanation`
  - `get_active_recommendations(horizon, signal, limit)` — query ACTIVE records
  - `get_recommendations_for_symbol(symbol, limit)` — history for a ticker

### LLM Recommendation Tools
- Added to [`llm/tools/implementations/market_tool.py`](file:///Users/shivamsingh/personal/nomad-analyst/llm/tools/implementations/market_tool.py):
  - `GetRecommendationsTool` — filter by status/horizon/signal/confidence/symbol
  - `GetRecommendationTool` — full detail (all fields, evidence, confidence components) for UUID or symbol
  - `GetActiveRecommendationsTool` — all ACTIVE records with horizon/signal filters

### Agent & System Prompt
- Updated [`market/services/market_research_service.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/market_research_service.py) to register all 3 new tools
- Updated [`chat/agents/market_research_agent.py`](file:///Users/shivamsingh/personal/nomad-analyst/chat/agents/market_research_agent.py) system prompt with explicit Rule 7 (recommendation tool usage) and LLM boundary rules

### Celery Periodic Task
- Added `run_daily_recommendation_scan` to [`market/tasks.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/tasks.py)
  - Runs for all active universes at `DELIVERY_SWING` + `LONG_TERM` horizons
  - Calls `expire_old_active_recommendations(max_age_days=10)` after each scan run

### Migrations
- `0014_stockrecommendation` — creates `StockRecommendation` table
- `0015_bootstrap_daily_recommendation_task` — registers Celery beat task

---

## 2. Key Architecture Rules (MUST PRESERVE)

1. **Append-only records**: `StockRecommendation` records are never overwritten. Every call to `generate_and_save` creates a new UUID record.
2. **LLM boundary**: The LLM never modifies `entry_price`, `stop_price`, `target_price`, `signal`. It writes only `llm_explanation`.
3. **Intraday disabled**: `INTRADAY` horizon returns `NOT_READY` until true intraday (5m/1h) data is available.
4. **R:R gate**: Setups with R:R < `MIN_RISK_REWARD` return `NO_ACTION` — nothing is persisted.
5. **PIT safety**: All signal engine queries use `timestamp__lte=as_of`. Future data never leaks.

---

## 3. Verification Results

```bash
venv/bin/python manage.py test market --verbosity=1
# Ran 58 tests in 0.923s → OK (0 failures)
```

New tests in `SignalEngineSubsystemTests` (21 tests):
- Setup detector unit tests (breakout detection, pullback failure, volume gate, etc.)
- Signal engine PIT safety (future bars hidden, no bars → INSUFFICIENT_DATA)
- Intraday gate (daily bars only → NOT_READY)
- Full recommendation generation with features
- R:R rejection gate scenario test
- Service append-only persistence (2 creates → 2 records)
- Deterministic field immutability (update_status never touches entry/stop/signal)
- LLM explanation write-back isolation
- Expiration task
- All 3 LLM tool executions: get_recommendations, get_recommendation, get_active_recommendations
- System check (0 issues)

---

## 4. Next Steps (Module 9+)

- **Intraday data ingestion**: Once 5m bars are available, the intraday gate can be lifted
- **Recommendation lifecycle monitor**: A task that checks current prices against stop/target levels and auto-transitions status
- **LLM explanation generator**: A task or API endpoint that calls the LLM to fill `llm_explanation` for new ACTIVE recommendations
- **Backtesting layer**: VectorBT integration using the append-only recommendation history
