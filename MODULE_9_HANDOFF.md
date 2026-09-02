# MODULE 9 HANDOFF — Intraday Market Data Infrastructure

## Status: COMPLETE ✅

## What Module 9 Built

Module 9 establishes the production-quality intraday data layer that lifts
the `NOT_READY` gate introduced in Module 8, on a per-instrument, per-timeframe
basis, only when data quality meets all 5 readiness criteria.

---

## New Files

### Services

| File | Class | Purpose |
|---|---|---|
| `market/services/market_session.py` | `IndianMarketSession` | NSE session semantics, IST→UTC, holiday calendar, expected candle counts |
| `market/services/intraday_validator.py` | `validate_intraday_bar()` | OHLCV validation, grid alignment, timezone enforcement |
| `market/services/gap_detector.py` | `detect_gaps()` | EXPECTED_GAP vs DATA_GAP classification |
| `market/services/intraday_quality.py` | `get_data_quality()` | HEALTHY/STALE/INCOMPLETE/UNAVAILABLE freshness assessment |
| `market/services/intraday_service.py` | `IntradayMarketDataService` | Idempotent backfill + incremental update |
| `market/services/intraday_readiness.py` | `IntradayReadinessService` | 5-check gate for SignalEngine |

### Other Modified/New

| File | Change |
|---|---|
| `market/services/signal_engine.py` | Intraday gate delegates to `IntradayReadinessService` |
| `market/tasks.py` | Added `run_intraday_incremental_update` and `run_intraday_backfill_task` |
| `market/migrations/0016_bootstrap_intraday_tasks.py` | Registers 5-minute Celery beat task |
| `llm/tools/implementations/market_tool.py` | Added `GetIntradayOHLCVTool`, `GetIntradayDataQualityTool`, `GetIntradayFeaturesTool` |
| `market/services/market_research_service.py` | Registers 3 new intraday LLM tools |
| `market/tests.py` | Added `IntradayInfrastructureTests` (31 tests) |
| `docs/modules/09_INTRADAY_DATA_INFRASTRUCTURE.md` | Full module documentation |

---

## Architecture Decisions Confirmed

1. **Yahoo Finance (existing)** — no new provider, no new library
2. **No streaming** — polling only (5-minute Celery task during market hours)
3. **Per-instrument readiness** — NOT_READY gate lifted instrument-by-instrument
4. **No synthetic candles** — never synthesize intraday from daily OHLCV
5. **IST timezone throughout** — session boundaries in IST, stored UTC
6. **Idempotency at DB level** — UniqueConstraint prevents duplicates

---

## IntradayReadinessService Gate (5 checks)

For `horizon == INTRADAY`, SignalEngine now calls:

```python
readiness = IntradayReadinessService().check_readiness(instrument, "5m", as_of=dt_as_of)
```

1. Timeframe in supported set (`5m`, `15m`, `1h`, ...)
2. Bar count ≥ minimum (5m: 100 bars)
3. Quality ≠ UNAVAILABLE and ≠ STALE
4. Data gaps ≤ 5 in last 3 trading days
5. TechnicalFeature records exist for `5m`

---

## How to Trigger Initial Intraday Backfill

```python
# One instrument:
from market.tasks import run_intraday_backfill_task
run_intraday_backfill_task.delay(symbol="RELIANCE", timeframe="5m", days_back=30)

# All active universe instruments:
run_intraday_backfill_task.delay(timeframe="5m", days_back=30)
```

After backfill, run feature calculation:

```python
from market.services.feature_engine import TechnicalFeatureEngine
from market.models import Instrument
inst = Instrument.objects.get(symbol="RELIANCE")
TechnicalFeatureEngine().calculate_and_save_features(inst, "5m")
```

Then `IntradayReadinessService().check_readiness(inst, "5m")` will pass.

---

## NSE Holiday Calendar

`KNOWN_EXCHANGE_HOLIDAYS` in `market_session.py` covers 2024–2025.
**Must be updated annually** from NSE official calendar.

---

## Test Coverage

`IntradayInfrastructureTests` covers:
- Market session: trading days, session boundaries, expected candles, timestamps
- Validator: OHLC consistency, timezone, grid alignment, volume
- Gap detector: EXPECTED_GAP vs DATA_GAP classification
- Quality: UNAVAILABLE, STALE detection, as_dict structure
- OHLCVBar idempotency
- IntradayReadinessService: all failure paths + happy path structure
- Module 8 integration: intraday gate + daily pipeline unaffected
- PIT safety: future bars invisible at as_of
- Feature engine: 5m/15m/1h calculation, timeframe isolation
- LLM tools: all 3 tools
- Celery task: market-hours gate

---

## Module 10 Considerations

The foundation for a future module enabling a full intraday recommendation pipeline:

1. IntradayReadinessService gate is already lifted per instrument once data is healthy
2. SignalEngine intraday signal generation path exists (entry/stop/target logic incomplete for intraday)
3. The 5m feature set (RSI, SMA, MACD, ATR, etc.) is already calculated correctly
4. Possible next step: intraday-specific indicator parameters (shorter periods), intraday-specific scoring
