# Module 9 — Intraday Market Data Infrastructure

## 1. Overview

Module 9 establishes the production-quality intraday data foundation needed to eventually enable genuine intraday analysis and intraday recommendations in the Nomad Analyst platform.

The module wraps the existing OHLCVBar + Yahoo Finance provider infrastructure with:
- Explicit Indian market-session semantics (IST timezone)
- Intraday candle validation
- Gap detection (EXPECTED_GAP vs DATA_GAP)
- Data quality/freshness assessment
- Idempotent backfill + incremental ingestion service
- IntradayReadinessService gating Module 8
- Celery periodic tasks
- 3 new LLM tools for intraday data inspection

## 2. Provider

**Yahoo Finance (existing confirmed provider)**

| Interval | Max History | Notes |
|---|---|---|
| 1m | 7 days | Rarely needed |
| 5m | 60 days | Primary intraday resolution |
| 15m | 60 days | Medium intraday resolution |
| 30m | 60 days | - |
| 1h | 730 days | Best for longer intraday history |

**Mode**: HTTP polling only. No live websocket streaming.
**Deduplication**: OHLCVBar UniqueConstraint(instrument, timeframe, timestamp) enforces at DB level.

## 3. Architecture

### Data Flow

```
Yahoo Finance Chart API
        ↓
YFinanceMarketProvider.get_historical_ohlcv(symbol, '5m', start, end)
        ↓
MarketService.fetch_and_save_historical_ohlcv() [existing — bulk idempotent]
        ↓
OHLCVBar table [instrument + timeframe + timestamp unique]
        ↓
TechnicalFeatureEngine.calculate_and_save_features(instrument, '5m')
        ↓
TechnicalFeature table [timeframe-aware]
        ↓
IntradayReadinessService.check_readiness()
        ↓
SignalEngine [INTRADAY gate lifted only when ready]
```

## 4. Timeframe Support

Supported intraday timeframes:

| Timeframe | Interval | Session Candles | Min Bars Required |
|---|---|---|---|
| 5m | 5 minutes | 75/session | 100 |
| 15m | 15 minutes | 25/session | 50 |
| 1h | 60 minutes | 6/session | 30 |

**Default intraday resolution for SignalEngine**: `5m`

## 5. Market Session Handling

- **Service**: `market/services/market_session.py` → `IndianMarketSession`
- **Timezone**: Asia/Kolkata (IST, UTC+05:30)
- **Session**: 09:15 – 15:30 IST, Monday–Friday
- **Weekends**: Not trading days
- **Holidays**: `KNOWN_EXCHANGE_HOLIDAYS` — curated NSE official calendar (2024–2025)
- **Expected candles**: `expected_candles_for_session(date, timeframe)` — deterministic count

All internal timestamps are stored and compared as **UTC-aware datetimes**. Session boundary checks convert to IST for comparison.

## 6. Candle Validation

- **Service**: `market/services/intraday_validator.py` → `validate_intraday_bar()`
- Returns `ValidationResult(is_valid, errors, warnings)`
- **Hard failures** (bar rejected): low > high, open > high, negative prices, negative volume, future timestamp, timezone-naive timestamp, unsupported timeframe
- **Warnings** (bar accepted): zero volume
- **Grid alignment**: timestamp must land on NSE session grid (offset from 09:15 IST divisible by interval)
- Does NOT silently repair data

## 7. Gap Detection

- **Service**: `market/services/gap_detector.py` → `detect_gaps(instrument, timeframe, from_dt, to_dt)`
- Returns `GapReport` with `expected_gaps` and `data_gaps` lists
- **EXPECTED_GAP**: weekend, exchange holiday, outside market hours
- **DATA_GAP**: missing candle during a valid NSE session window
- Does NOT fabricate candles to fill gaps

## 8. Data Quality / Freshness

- **Service**: `market/services/intraday_quality.py` → `get_data_quality(instrument, timeframe, as_of)`
- Returns `IntradayDataQuality` with status + lag + completeness

| Status | Condition |
|---|---|
| HEALTHY | Lag within threshold, completeness ≥ 80% |
| STALE | Lag exceeds threshold (5m: 15min, 15m: 30min, 1h: 90min) |
| INCOMPLETE | Completeness < 80% |
| UNAVAILABLE | No bars exist at all |

## 9. Ingestion

### Backfill
- **Service**: `market/services/intraday_service.py` → `IntradayMarketDataService.backfill()`
- Enforces provider limits: 5m/15m ≤ 60 days, 1h ≤ 730 days
- Batched by configurable `BATCH_SIZE_DAYS` (5m: 7d batches)
- 1.5s inter-batch delay for rate-limit awareness
- Idempotent — re-running is safe
- On rate-limit error: sleeps 30s and retries once

### Incremental Update
- `IntradayMarketDataService.incremental_update()`
- Fetches last `INCREMENTAL_LOOKBACK_DAYS` (5m: 2 days)
- If no data exists: triggers full backfill automatically
- Idempotent

## 10. IntradayReadinessService

- **Service**: `market/services/intraday_readiness.py`
- Called by `SignalEngine` when `horizon == INTRADAY`
- **5 sequential checks** (all must pass):
  1. Timeframe is in supported set
  2. Bar count ≥ minimum (5m: 100, 15m: 50, 1h: 30)
  3. Quality status ≠ UNAVAILABLE and ≠ STALE
  4. Data gaps ≤ MAX_DATA_GAPS_LAST_SESSION (5)
  5. TechnicalFeature records exist for the timeframe

Returns `ReadinessResult(is_ready, reason, quality, bar_count, checks_passed, checks_failed)`

## 11. Module 8 Integration

**Before Module 9** (simple check):
```python
if not OHLCVBar.objects.filter(timeframe__in=INTRADAY_TIMEFRAMES).exists():
    return NOT_READY
```

**After Module 9** (structured gate):
```python
readiness = IntradayReadinessService().check_readiness(instrument, "5m", as_of=dt_as_of)
if not readiness.is_ready:
    return NOT_READY with structured reason
```

Entry/stop/target calculation logic is unchanged. Only the gate is upgraded.

## 12. Celery Tasks

| Task | Schedule | Purpose |
|---|---|---|
| `run_intraday_incremental_update` | Every 5 minutes | Fetch recent 5m bars; skips if market closed |
| `run_intraday_backfill_task` | On-demand | Historical backfill for specific symbol/timeframe |

The incremental update task self-gates on `IndianMarketSession.is_market_open()`.

## 13. LLM Tools

| Tool | Description |
|---|---|
| `get_intraday_ohlcv` | Returns stored intraday OHLCV bars |
| `get_intraday_data_quality` | Returns quality/freshness status |
| `get_intraday_features` | Returns latest technical features for intraday timeframe |

All tools are read-only and deterministic. LLM cannot trigger data fetches.

## 14. Performance Considerations

- OHLCVBar has `UniqueConstraint(instrument, timeframe, timestamp)` — prevents duplicates at DB level
- OHLCVBar has composite index on `(instrument, timeframe, timestamp)` — fast PIT queries
- `bulk_create` used for batch insertion — no N+1 writes
- Intraday features reuse existing `TechnicalFeatureEngine` (no code duplication)

## 15. Known Limitations

1. **Yahoo Finance intraday limits**: 5m/15m history limited to 60 days. Historical data beyond this window is not available via Yahoo Finance.
2. **No live streaming**: Only polling. Freshness depends on how often `run_intraday_incremental_update` runs.
3. **Holiday calendar**: `KNOWN_EXCHANGE_HOLIDAYS` covers 2024–2025 only. Must be updated annually.
4. **Intraday NOT_READY by default**: First intraday recommendations require successful backfill + feature calculation per instrument.

## 16. Intraday Recommendation Status

> **NOT_READY by default.** Lifted per instrument, per timeframe, per as_of — not globally.
>
> An instrument becomes intraday-eligible only after:
> 1. Successful backfill of ≥ 100 5m bars
> 2. TechnicalFeatureEngine run for 5m timeframe
> 3. IntradayReadinessService confirms HEALTHY or INCOMPLETE quality with acceptable gaps
