# MODULE 10 HANDOFF — Intraday Signal & Strategy Engine

## Status: COMPLETE ✅

## What Module 10 Built

Module 10 adds the first genuine intraday strategy layer. It does NOT
re-use daily setup detectors against 5-minute candles. It introduces
completely separate intraday-specific setup detectors, session-aware
logic, and no-trade / cooldown rules appropriate for intraday market behavior.

---

## New Files

### Core Strategy Services

| File | Purpose |
|---|---|
| `market/intraday_strategy_config.py` | Versioned configuration — all parameters externalized |
| `market/services/intraday_session.py` | Session window classification (OPENING/MORNING/MIDDAY/AFTERNOON/CLOSING/OUTSIDE) |
| `market/services/intraday_indicators.py` | In-memory indicator computation from bar series (session-anchored VWAP, EMA9/21, RSI, ATR, ADX, MACD, RelVol) |
| `market/services/opening_range.py` | Session-scoped OR (5m: first 3 bars; 15m: first 2 bars) |
| `market/services/intraday_detectors.py` | 7 deterministic intraday detectors |
| `market/services/intraday_cooldown.py` | Duplicate signal prevention gate (read-only DB check) |
| `market/services/intraday_lifecycle.py` | Session-close expiry logic |
| `market/services/intraday_signal_engine.py` | Orchestrating `IntradaySignalEngine` class |

### LLM Tools

| File | Purpose |
|---|---|
| `llm/tools/implementations/intraday_tool.py` | 3 read-only LLM tools |

### Migrations

| File | Purpose |
|---|---|
| `market/migrations/0017_stockrecommendation_intraday_fields.py` | Adds 6 nullable fields + lifecycle index to `StockRecommendation` |
| `market/migrations/0018_bootstrap_intraday_strategy_tasks.py` | Registers Celery beat tasks |

---

## Modified Files

| File | Change |
|---|---|
| `market/signal_enums.py` | Added 7 intraday `SetupType` values |
| `market/models.py` | Added 6 nullable intraday fields to `StockRecommendation` + `rec_intraday_lifecycle_idx` |
| `market/tasks.py` | Added `run_intraday_strategy_scan` + `expire_intraday_session_recommendations` |
| `llm/tools/implementations/market_tool.py` | Added `GetIntradayRecommendationsTool`, `GetIntradayRecommendationTool`, `GetIntradaySetupsTool` |
| `market/services/market_research_service.py` | Registered 3 new Module 10 LLM tools |
| `market/tests.py` | Added `IntradayStrategyEngineTests` (40 tests) |
| `docs/modules/10_INTRADAY_SIGNAL_STRATEGY.md` | Full module documentation |

---

## 7 Intraday Setup Detectors

| Detector | Signal | Valid Windows |
|---|---|---|
| `OPENING_RANGE_BREAKOUT` | BUY | MORNING, MIDDAY |
| `OPENING_RANGE_BREAKDOWN` | SELL | MORNING, MIDDAY |
| `INTRADAY_MOMENTUM_CONTINUATION` | BUY/SELL | MORNING, MIDDAY, AFTERNOON |
| `INTRADAY_PULLBACK` | BUY | MORNING, MIDDAY, AFTERNOON |
| `VWAP_RECLAIM` | BUY | MORNING, MIDDAY, AFTERNOON, CLOSING |
| `VWAP_REJECTION` | SELL | MORNING, MIDDAY, AFTERNOON, CLOSING |
| `INTRADAY_RANGE_BREAKOUT` | BUY/SELL | MORNING, MIDDAY, AFTERNOON |

---

## New `StockRecommendation` Fields (all `null=True`)

| Field | Purpose |
|---|---|
| `timeframe` | Generating timeframe (e.g. `5m`, `15m`) |
| `target_2_price` | Secondary partial-exit target |
| `target_2_method` | Method for target 2 |
| `session_window` | Session window at generation time |
| `strategy_version` | Config version for backtesting traceability |
| `expires_at` | UTC session-close expiry (15:30 IST) |

---

## Celery Beat Tasks

| Task | Schedule | Self-gated |
|---|---|---|
| `market.tasks.run_intraday_strategy_scan` | Every 5 minutes | Yes — checks `is_market_open()` |
| `market.tasks.expire_intraday_session_recommendations` | 15:35 IST daily (10:05 UTC) | No |

---

## No-trade Gates (strict order)

1. `IntradayReadinessService` (Module 9) → `NOT_READY`
2. Insufficient bars < `MIN_BARS_FOR_ANALYSIS[timeframe]` → `NO_ACTION`
3. Stale data (last bar > 30 min before `as_of`) → `NO_ACTION`
4. `session_window == OUTSIDE` → `NO_ACTION`
5. `relative_volume < MIN_TAPE_VOLUME (0.5)` → `NO_ACTION` ("dead tape")
6. Cooldown gate (same instrument + signal + setup within 30 min) → `NO_ACTION`

---

## Architecture Decisions

### 1. Daily detectors are not called on intraday bars
`run_all_detectors()` in `setup_detectors.py` is unchanged. The 7 new
intraday detectors are a completely separate code path in `intraday_detectors.py`.

### 2. Intraday indicators are in-memory, not stored in `TechnicalFeature`
Intraday indicators (especially session-anchored VWAP) are computed freshly
from the bar series on every engine call. This avoids stale precomputed
features and is appropriate for the sub-30-minute latency requirement.

### 3. Cooldown is purely read-based
The cooldown service only queries `StockRecommendation`. It holds no local
state. This means it is safe to run across multiple Celery workers.

### 4. Expiry is status mutation, never deletion
At session close, `status` is set to `EXPIRED`. The historical record is
never deleted. This preserves the full audit trail for future backtesting.

### 5. OR breakout is blocked during OPENING window
`SETUP_SESSION_FILTERS["OPENING_RANGE_BREAKOUT"]` does not include `OPENING`.
This prevents the engine from acting on an incomplete OR while it is still forming.

### 6. LLM is read-only
The 3 Module 10 LLM tools are strictly read-only. LLM explanations may not
modify `signal`, `entry_price`, `stop_price`, `target_price`, or `confidence`.

---

## Test Coverage

**146/146 tests passing (full suite)**

`IntradayStrategyEngineTests` covers 40 cases:
- Session window classification (6 windows)
- VWAP computation and unavailability
- Opening range (complete, incomplete, helper methods: above_or_high, measured_move_target_up)
- 7 detectors (all detected / not-detected conditions)
- No-trade gates (NOT_READY, OUTSIDE, dead tape)
- Cooldown (blocks duplicate, allows different setup, allows after expiry window)
- Lifecycle (marks EXPIRED, ignores non-intraday, UTC calculation)
- Daily regression (daily detectors don't return intraday setup types)
- PIT safety (future bars invisible)
- Config structure
- Model field nullability

---

## Key Invariants to Preserve in Future Modules

1. **Do not call daily `run_all_detectors()` on intraday bars.**
2. **Do not hardcode parameters inside detector functions** — all must come from `intraday_strategy_config.py`.
3. **Always set `expires_at` for INTRADAY recs** = 15:30 IST of the session date.
4. **Cooldown checks use `generated_at__gte=cooldown_start`** — the DB timestamp, not `as_of`.
5. **OR-based setups require `or_range.is_complete=True`** before detecting.
6. **VWAP-based setups require `ind.vwap_available=True`** before detecting.
7. **Module 9's `IntradayReadinessService` must remain the first gate** before any intraday signal logic.

---

## What Module 11 Could Build On This

- Intraday recommendations are now being generated, persisted, and expired.
- The LLM can now query, explain, and diagnose intraday setups.
- Natural next steps:
  - Intraday recommendation status tracking (TRIGGERED when price hits entry)
  - Position-level exit tracking (when stop or target is hit intraday)
  - Backtesting harness for intraday setups using historical bar data
  - Per-setup win rate and performance statistics
