# Nomad Analyst — FE-4 Real-Time & WebSocket Technical Inspection

**Date:** September 1, 2026  
**Target Workspace:** FE-4 Intraday Scanner & Real-Time Signals (`/intraday`)  
**Status:** TECHNICAL INSPECTION COMPLETE (NO CODE MODIFICATIONS)

---

## 1. Executive Summary

This document provides a comprehensive audit of the backend data ingestion, strategy execution, outcome tracking, REST APIs, and WebSocket infrastructure for the upcoming FE-4 Intraday Scanner & Real-Time Signals workspace.

---

## 2. Backend Real-Time & WebSocket Component Matrix

| Component | Status | Location / Implementation Details |
|---|---|---|
| **Django Channels** | `IMPLEMENTED` | `channels==4.3.2` installed; registered in `INSTALLED_APPS` |
| **ASGI Application** | `IMPLEMENTED` | `config/asgi.py` with `ProtocolTypeRouter` & `AuthMiddlewareStack` |
| **Channel Layer** | `IMPLEMENTED` | `channels_redis.core.RedisChannelLayer` configured against Redis on port 6379 |
| **WebSocket Consumers** | `PARTIAL` | Only `ChatConsumer` at `ws/chat/<conversation_id>/` exists for LLM chat streaming |
| **Market WebSocket Consumer** | `NOT IMPLEMENTED` | No WebSocket consumer or route for market data/signals (`ws/intraday/` or `ws/market/`) exists |
| **Market Event Pub/Sub** | `NOT IMPLEMENTED` | Database writes do not publish domain events to Redis channel layers |

---

## 3. Intraday Data Pipeline & Strategy Flow

```
yfinance Provider (Batch HTTP)
       ↓
IntradayMarketDataService.incremental_update() [Module 9]
       ↓
OHLCVBar Table (PostgreSQL / SQLite, UniqueConstraint on [instrument, timeframe, timestamp])
       ↓
In-Memory Feature Engine (compute_intraday_indicators: VWAP, ATR, Opening Range)
       ↓
IntradaySignalEngine [Module 10] (ORB_BREAKOUT, VWAP_RECLAIM, TREND_CONTINUATION, MEAN_REVERSION)
       ↓
StockRecommendation (horizon='INTRADAY', status='ACTIVE', timeframe='5m', expires_at=15:30 IST)
       ↓
RecommendationOutcomeService [Module 11] (Evaluates triggers, stop-loss, targets against new bars)
       ↓
REST Presentation Layer (/api/v1/intraday/overview/, /api/v1/intraday/recommendations/)
```

### Flow Characteristics:
- **Ingestion Nature:** Periodic batch polling via Celery (`run_intraday_incremental_update`), NOT streaming.
- **Signal Generation:** Deterministic execution over in-memory indicators, gated by `IntradayReadinessService` and `IndianMarketSession`.
- **Outcome Evaluation:** `evaluate_active_recommendations` compares active recommendations with new bars using `select_for_update()` to prevent race conditions.

---

## 4. Current Intraday REST Endpoints

### 1. `GET /api/v1/intraday/overview/`
- **Request Parameters:** None
- **Response Structure:**
  ```json
  {
    "market_session": {
      "window": "MORNING",
      "minutes_elapsed": 45,
      "minutes_remaining": 330,
      "is_trading_hour": true,
      "session_date": "2026-09-01"
    },
    "summary": {
      "active_signals": 4,
      "triggered_signals": 2,
      "timeframes_supported": ["5m", "15m", "1h"]
    },
    "as_of": "2026-09-01T14:00:00Z"
  }
  ```

### 2. `GET /api/v1/intraday/recommendations/`
- **Query Parameters:** `timeframe` (`5m`, `15m`, `1h`), `signal` (`BUY`, `SELL`), `status` (`ACTIVE`, `TRIGGERED`, `TARGET_HIT`, `STOPPED`, `EXPIRED`), `setup_type`, `page`, `page_size`
- **Response Structure:** Paginated `StockRecommendation` records including entry condition, stop price, target price, risk/reward ratio, confidence, and intraday extras (`target_2_price`, `session_window`, `expires_at`).

### 3. `GET /api/v1/intraday/data-quality/?symbol=RELIANCE&timeframe=5m`
- **Response Structure:**
  ```json
  {
    "symbol": "RELIANCE",
    "timeframe": "5m",
    "is_ready": true,
    "bar_count": 75,
    "span_days": 1,
    "latest_bar_timestamp": "2026-09-01T10:00:00Z",
    "missing_bars_count": 0,
    "data_quality_grade": "A",
    "warnings": [],
    "checked_at": "2026-09-01T14:00:00Z"
  }
  ```

---

## 5. Lifecycle & Freshness Behavior

- **Intraday Session Expiry:** All intraday recommendations expire at 15:30 IST (session close) and are marked `EXPIRED` by `expire_intraday_session_recommendations`.
- **Freshness Grades:** Evaluated by `IntradayReadinessService` based on bar coverage, gap count, and latest candle latency.

---

## 6. FE-4 Readiness Assessment

### Can be Implemented Immediately in FE-4 (Ready Now):
1. **Intraday Scanner Dashboard:** Complete workspace displaying live IST session status, minutes remaining, and active signal metrics.
2. **Signals Matrix:** Tabular candidate triage with 5m/15m/1h timeframes, setups (`ORB_BREAKOUT`, `VWAP_RECLAIM`, `TREND_CONTINUATION`, `MEAN_REVERSION`), signal direction (`BUY`/`SELL`), entry price, stop-loss, Target 1, Target 2, Risk/Reward ratio, and confidence.
3. **Signal Deep Dive Drawer:** Inspecting supporting indicators, opening range high/low, session window, and execution condition.
4. **Data Readiness Modal:** 1-click inspection of bar count, gap count, and data quality grade via `/api/v1/intraday/data-quality/`.
5. **REST Polling Strategy:** TanStack Query configured with 15-second polling during active market hours (`is_trading_hour: true`) and paused when closed.

### Requires Future Backend Work (P1/P2 Enhancements):
1. **P1 — Celery Beat Schedule:** Configure `CELERY_BEAT_SCHEDULE` in `config/settings.py` for automated periodic execution of intraday tasks.
2. **P2 — Market Channels Consumer:** Dedicated `IntradayConsumer` broadcasting candle close and recommendation trigger events over WebSockets.
