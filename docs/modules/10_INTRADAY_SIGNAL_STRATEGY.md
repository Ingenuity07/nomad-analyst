# Module 10: Intraday Signal & Strategy Engine

## Overview

Module 10 builds the deterministic intraday strategy layer on top of the
intraday data infrastructure established in Module 9.

It does **not** re-run daily setup detectors on 5-minute candles.
It introduces a completely separate set of intraday-specific setup detectors,
session-aware logic, and no-trade / cooldown gates that are appropriate for
intraday market behavior.

---

## Position in the Pipeline

```
Intraday OHLCV Bars (Module 9)
         ↓
IntradayReadinessService (Module 9 gate)
         ↓
Session Classification (Module 10)
         ↓
Intraday Indicators — VWAP, EMA9/21, RSI, ATR, ADX, MACD, RelVol
         ↓
Opening Range Framework
         ↓
7 Intraday Detectors
         ↓
No-trade / Cooldown Gates
         ↓
Signal Selection & Confidence Scoring
         ↓
Entry / Stop / Target 1 & 2 Derivation
         ↓
RecommendationDraft (horizon=INTRADAY)
         ↓
StockRecommendation (persisted, expires_at = 15:30 IST)
         ↓
LLM Tools (3 read-only tools)
```

---

## Architecture

### Configuration (`market/intraday_strategy_config.py`)

Single versioned configuration file. No parameters are hardcoded inside
detector functions. Key constants:

| Constant | Default | Purpose |
|---|---|---|
| `STRATEGY_VERSION` | `"1.0"` | Written to every rec for traceability |
| `DEFAULT_INTRADAY_TIMEFRAME` | `"5m"` | Default scan timeframe |
| `SUPPORTED_INTRADAY_TIMEFRAMES` | `["5m", "15m"]` | Valid timeframes |
| `MIN_RISK_REWARD_INTRADAY` | `1.5` | Minimum R:R to recommend |
| `MIN_RELATIVE_VOLUME` | `1.1` | Entry requires ≥ 10% above-avg volume |
| `MIN_TAPE_VOLUME` | `0.5` | Dead-tape kill-switch |
| `COOLDOWN_MINUTES` | `30` | Duplicate signal prevention window |
| `STOP_ATR_MULTIPLIER` | `1.5` | Stop = entry ± ATR × 1.5 |
| `TARGET_1_ATR_MULTIPLIER` | `2.5` | Primary target |
| `TARGET_2_ATR_MULTIPLIER` | `3.0` | Secondary partial-exit target |
| `REGIME_GATE_RULES` | see config | Per-setup regime allow/block lists |
| `SETUP_SESSION_FILTERS` | see config | Per-setup valid session windows |

### Session Windows (`market/services/intraday_session.py`)

NSE session is divided into 5 named windows:

| Window | IST Range | Valid for trading |
|---|---|---|
| `OPENING` | 09:15–09:45 | ✓ |
| `MORNING` | 09:45–11:30 | ✓ |
| `MIDDAY` | 11:30–13:00 | ✓ |
| `AFTERNOON` | 13:00–14:30 | ✓ |
| `CLOSING` | 14:30–15:30 | ✓ |
| `OUTSIDE` | Before/after market | ✗ — NO_ACTION |

Each setup type has a `SETUP_SESSION_FILTERS` list — e.g.
`OPENING_RANGE_BREAKOUT` only fires from `MORNING` onwards (not during
`OPENING` when the OR is still forming).

### Intraday Indicators (`market/services/intraday_indicators.py`)

Computed **in-memory** from the loaded bar series — not stored in
`TechnicalFeature`. Session-anchored VWAP (reset at 09:15 IST every day).

| Indicator | Notes |
|---|---|
| `ema_fast` | EMA(9) |
| `ema_slow` | EMA(21) |
| `rsi` | RSI(14) |
| `atr` | ATR(14) |
| `adx` | ADX(14) |
| `macd_line`, `macd_signal`, `macd_hist` | MACD(12, 26, 9) |
| `relative_volume` | current bar vol / 20-bar avg vol |
| `vwap`, `vwap_available` | Session-reset VWAP |

### Opening Range (`market/services/opening_range.py`)

Session-scoped opening range (OR):

- **5m**: First 3 bars (09:15–09:30) define OR high/low
- **15m**: First 2 bars (09:15–09:45) define OR high/low

The `OpeningRange` dataclass provides:
- `above_or_high(price)` / `below_or_low(price)` with configurable buffer
- `measured_move_target_up(entry)` / `measured_move_target_down(entry)`

### 7 Intraday Detectors (`market/services/intraday_detectors.py`)

Each detector is a pure function returning a `DetectorResult` with:
`detected`, `score (0–100)`, `conditions_met`, `conditions_failed`, `relevant_values`.

| Detector | Signal | Session |
|---|---|---|
| `detect_or_breakout` | BUY | MORNING, MIDDAY |
| `detect_or_breakdown` | SELL | MORNING, MIDDAY |
| `detect_momentum_continuation` | BUY/SELL | MORNING–AFTERNOON |
| `detect_intraday_pullback` | BUY | MORNING–AFTERNOON |
| `detect_vwap_reclaim` | BUY | MORNING–CLOSING |
| `detect_vwap_rejection` | SELL | MORNING–CLOSING |
| `detect_intraday_range_breakout` | BUY/SELL | MORNING–AFTERNOON |

**Key design rules:**
- OR breakout/breakdown require OR to be `is_complete`
- VWAP-based detectors require `vwap_available`
- Range breakout blocks when ADX ≥ 20 (already trending)
- Momentum continuation blocks in RANGING/LOW_VOLATILITY regimes

### No-trade Gates (in `IntradaySignalEngine`)

Applied in strict order before any signal is returned:

1. **ReadinessGate** — Module 9 `IntradayReadinessService` (bars, quality, features)
2. **Insufficient bars** — `len(bars) < MIN_BARS_FOR_ANALYSIS[timeframe]`
3. **Stale data** — last bar timestamp > 30 min before `as_of`
4. **Outside session** — `session_window == OUTSIDE`
5. **Dead tape** — `relative_volume < MIN_TAPE_VOLUME`

### Cooldown Gate (`market/services/intraday_cooldown.py`)

Read-only DB gate: blocks if an ACTIVE/TRIGGERED `StockRecommendation`
with the same `(instrument, signal, setup_type, horizon=INTRADAY)`
exists with `generated_at` within the last `COOLDOWN_MINUTES`.

A materially different setup type is **never** blocked by cooldown.

### Session Expiry (`market/services/intraday_lifecycle.py`)

At market close (15:35 IST via Celery cron), all ACTIVE intraday
recommendations with `expires_at <= now` are set to `EXPIRED`.
**No records are ever deleted** — full audit trail is preserved.

---

## Database Changes

### Migration 0017: `StockRecommendation` new fields

All fields are `null=True, blank=True` → zero impact on existing daily records.

| Field | Type | Purpose |
|---|---|---|
| `timeframe` | `CharField(10)` | Generating timeframe (`5m`, `15m`) |
| `target_2_price` | `DecimalField` | Secondary partial-exit target |
| `target_2_method` | `CharField(25)` | Method used to derive target 2 |
| `session_window` | `CharField(15)` | Session window at generation time |
| `strategy_version` | `CharField(20)` | Config version for traceability |
| `expires_at` | `DateTimeField` | UTC session-close expiry |

New index: `rec_intraday_lifecycle_idx` on `(instrument, horizon, status, expires_at)`.

### Migration 0018: Celery beat tasks

Bootstraps two tasks into `django_celery_beat`:

| Task | Schedule | Description |
|---|---|---|
| `run_intraday_strategy_scan` | Every 5 min | Self-gated on market hours |
| `expire_intraday_session_recommendations` | 15:35 IST daily | Session expiry |

---

## Celery Tasks (`market/tasks.py`)

### `run_intraday_strategy_scan()`
- Self-gates: if `IndianMarketSession.is_market_open()` is False → `SKIPPED`
- Iterates up to 200 active EQUITY instruments
- Calls `IntradaySignalEngine.generate_recommendation()`
- Persists only BUY/SELL signals via `RecommendationService`
- Writes intraday extras (timeframe, session_window, expires_at, etc.) via `update()`

### `expire_intraday_session_recommendations()`
- Should run at 15:35 IST = 10:05 UTC
- Calls `expire_intraday_session_recommendations(now)`
- Never deletes records — sets status to `EXPIRED`

---

## LLM Tools (`llm/tools/implementations/intraday_tool.py`)

Three read-only tools registered in `MarketResearchService`:

| Tool | Description |
|---|---|
| `get_intraday_recommendations` | List with filters (symbol, timeframe, setup, direction, session) |
| `get_intraday_recommendation` | Full detail by UUID or latest-active for a symbol |
| `get_intraday_setups` | Diagnostic: run all 7 detectors, return scores — does NOT persist |

**LLM constraints:**
- LLM may read and explain all fields
- LLM may NOT modify: `signal`, `entry_price`, `stop_price`, `target_price`, `confidence`

---

## Tests (`market/tests.py` — `IntradayStrategyEngineTests`)

40 tests across 11 areas:

1. Session window classification (6 windows)
2. VWAP computation and unavailability
3. Opening range (complete, incomplete, helper methods)
4. 7 detectors (OR breakout/breakdown, momentum, pullback, VWAP reclaim/rejection, range breakout)
5. No-trade conditions (NOT_READY, outside session, dead tape)
6. Cooldown gate (blocks duplicate, allows different setup, allows after expiry)
7. Lifecycle / session expiry (marks EXPIRED, ignores non-intraday, UTC calculation)
8. Daily recommendation regression (daily detectors don't return intraday setup types)
9. PIT safety (future bars invisible to engine)
10. Strategy config structure
11. Model field nullable guarantees

**Full suite result: 146/146 OK**

---

## Key Invariants

- **Daily recommendations are not affected.** The `SetupType` values for the 7 new intraday setups are added to the enum but `run_all_detectors()` (daily) does not call any of the new intraday detector functions.
- **Intraday recommendations expire at session close.** `expires_at` is always set to 15:30 IST of the generating day for INTRADAY recs.
- **OR breakout never fires during OPENING window.** `SETUP_SESSION_FILTERS` blocks `OPENING_RANGE_BREAKOUT` and `OPENING_RANGE_BREAKDOWN` during the OPENING window when the OR is still forming.
- **All parameters are externalized.** No numeric thresholds are hardcoded inside detector functions — all come from `intraday_strategy_config.py`.
- **PIT safety is guaranteed.** Bar queries always use `timestamp__lte=as_of`.

---

## Files Created / Modified

### New Files
| File | Purpose |
|---|---|
| `market/intraday_strategy_config.py` | Central versioned parameters |
| `market/services/intraday_session.py` | Session window classification |
| `market/services/intraday_indicators.py` | In-memory indicator computation |
| `market/services/opening_range.py` | OR high/low/methods |
| `market/services/intraday_detectors.py` | 7 deterministic detectors |
| `market/services/intraday_cooldown.py` | Duplicate signal gate |
| `market/services/intraday_lifecycle.py` | Session-close expiry |
| `market/services/intraday_signal_engine.py` | Orchestrating engine |
| `llm/tools/implementations/intraday_tool.py` | 3 LLM read-only tools |
| `market/migrations/0017_stockrecommendation_intraday_fields.py` | DB migration |
| `market/migrations/0018_bootstrap_intraday_strategy_tasks.py` | Beat task bootstrap |

### Modified Files
| File | Change |
|---|---|
| `market/signal_enums.py` | +7 intraday `SetupType` values |
| `market/models.py` | +6 nullable intraday fields + lifecycle index |
| `market/tasks.py` | +2 Celery tasks |
| `llm/tools/implementations/market_tool.py` | +3 tool classes |
| `market/services/market_research_service.py` | +3 tool registrations |
| `market/tests.py` | +40 tests (`IntradayStrategyEngineTests`) |
