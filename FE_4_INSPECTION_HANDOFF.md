# FE-4 INSPECTION HANDOFF — INTRADAY SCANNER & REAL-TIME ARCHITECTURE

**Status:** TECHNICAL INSPECTION COMPLETE ✅  
**Date:** September 1, 2026  
**Action:** NO CODE MODIFICATIONS PERFORMED (Read-Only Audit)

---

## 1. Executive Summary

This handoff details the findings of the technical inspection regarding real-time market data, intraday strategy execution, outcome tracking, REST APIs, and WebSocket infrastructure for the future **FE-4 Intraday Scanner & Real-Time Signals Workspace**.

---

## 2. Core Inspection Answers

### Q1: Is WebSocket currently implemented?
- **ASGI & Channels:** Configured with Redis backend.
- **Market / Intraday WebSocket:** **NOT IMPLEMENTED**. Only `ws/chat/<conversation_id>/` exists for LLM chat streaming. No WebSocket endpoint exists for market tickers, candles, or signal generation.

### Q2: Is genuine real-time streaming currently implemented?
- **No.** The intraday data ingestion (`IntradayMarketDataService`) operates via **periodic batch polling** of provider endpoints (`yfinance`), not a live socket feed.

### Q3: How does intraday data currently reach the system?
- Via `IntradayMarketDataService.incremental_update()` called periodically (or triggered via Celery tasks) fetching 5m/15m bars into the `OHLCVBar` table.

### Q4: How do recommendation updates currently reach clients?
- Via versioned REST APIs (`GET /api/v1/intraday/overview/`, `GET /api/v1/intraday/recommendations/`, `GET /api/v1/intraday/data-quality/`).

### Q5: What backend work, if any, blocks FE-4?
- **NO BLOCKERS for a robust REST-polled FE-4.**
- FE-4 can be fully implemented using TanStack Query polling (15s–30s interval during trading hours).
- *Optional Non-Blocking Enhancement (P1/P2):* Adding `CELERY_BEAT_SCHEDULE` and a dedicated `IntradayConsumer` WebSocket route.

### Q6: What can FE-4 implement immediately?
- Full Intraday Scanner workspace (`/intraday`).
- Real-time IST trading session tracker (`OPENING`, `MORNING`, `MIDDAY`, `AFTERNOON`, `CLOSING`, `OUTSIDE`).
- 5m / 15m / 1h signal filters and setup selectors (`ORB_BREAKOUT`, `VWAP_RECLAIM`, `TREND_CONTINUATION`, `MEAN_REVERSION`).
- Signal candidate triage table (Signal, Confidence, Entry, Stop, Target 1, Target 2, Risk/Reward).
- Signal detail drawer with execution conditions and opening range levels.
- 1-click Data Quality inspection modal (`/api/v1/intraday/data-quality/`).

---

## 3. Recommended FE-4 Query & Freshness Strategy

```
┌────────────────────────────────────────────────────────┬───────────────────────────────────────────┐
│ ENDPOINT                                               │ RECOMMENDED CLIENT POLLING STRATEGY       │
├────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
│ GET /api/v1/intraday/overview/                         │ 15-second polling during market hours     │
│ GET /api/v1/intraday/recommendations/?timeframe=...    │ 15-second polling during market hours     │
│ GET /api/v1/intraday/data-quality/?symbol=...          │ On-demand (when modal is opened)          │
└────────────────────────────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 4. Exact Next Step

**Technical inspection complete. Awaiting user instruction before implementing FE-4.**
