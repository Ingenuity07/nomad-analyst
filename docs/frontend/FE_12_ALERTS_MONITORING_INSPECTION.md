# FE-12 Alerts / Monitoring & Command Center — Technical Inspection Report

## Executive Summary

This document provides a comprehensive, read-only technical inspection of the backend and frontend systems for **FE-12: Alerts / Monitoring & Command Center**.

The inspection establishes that:
1. **Server-Side Alert / Notification Infrastructure is MISSING**: No `Alert`, `Notification`, `TriggerRule`, or `UserAlertSubscription` database models or `/api/v1/alerts/` endpoints exist in the Django backend.
2. **Server-Side Background Trigger Engine is MISSING**: While Celery is configured in `settings.py`, there is no Celery beat scheduler or background worker evaluating event rules against live data feeds.
3. **Real-time Channels**: Django Channels is installed for LLM token streaming (`ChatConsumer` at `ws/chat/<conversation_id>/`), but no market or alert WebSocket consumer (`ws/alerts/` or `ws/market/`) exists.
4. **FE-12 Feasible Architecture (Option B / Client-Side Command Center)**: FE-12 can be implemented cleanly and robustly as a **Client-Side Analytical Command Center & Event Monitor**. The frontend can poll existing authoritative REST APIs (`/api/v1/recommendations/`, `/api/v1/opportunities/`, `/api/v1/intraday/recommendations/`, `/api/v1/market/regime/`, `/api/v1/stocks/{symbol}/`), detect analytical event triggers in-session (or compare against cached timestamps), display an aggregated real-time event log, manage custom user trigger rules persisted in `localStorage`, and route analysts to relevant terminals.

---

## 1. Alert Model & API Audit

| Entity / Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **`Alert` / `Notification` Model** | **MISSING** | No alert, trigger, or notification table in Django ORM. |
| **Alert REST APIs** | **MISSING** | No `/api/v1/alerts/` CRUD endpoints exist. |
| **Trigger Rule Engine** | **MISSING** | No backend cron/celery job evaluates threshold rules. |
| **External Notification Channels** | **MISSING** | No Email, SMS, Webhook, Telegram, or Slack delivery integrations. |
| **WebSocket Alert Streaming** | **MISSING** | No WebSocket consumer exists for broadcasting alerts. |
| **Client-Side Trigger Persistence** | **FEASIBLE** | Browser `localStorage` can persist custom price/technical threshold rules and historical triggered event logs. |

---

## 2. Event Detection Capabilities Across Domains

| Event Domain | Backend Source Endpoint | Detectable Conditions |
| :--- | :--- | :--- |
| **Strategy Recommendations** | `GET /api/v1/recommendations/?status=ACTIVE` | New active BUY/SELL signals, target hits, stop-loss triggers, confidence updates. |
| **Delivery Opportunities** | `GET /api/v1/opportunities/` | New high-score opportunities (Score >= 80), volume surges, setup changes. |
| **Intraday Signals** | `GET /api/v1/intraday/recommendations/` | New momentum / VWAP intraday triggers during market hours. |
| **Market Regime Shifts** | `GET /api/v1/market/regime/` | Trend flips (`BULLISH` ↔ `BEARISH`), volatility regime transitions (`NORMAL` → `ELEVATED`), breadth deterioration. |
| **Watched Stocks Price Triggers** | `GET /api/v1/stocks/{symbol}/` | Price above threshold, price below threshold, 1D % move exceeding limit. |
| **Corporate Disclosures & News** | `GET /api/v1/stocks/{symbol}/events/`, `/news/` | New exchange filings, quarterly earnings announcements, board meetings. |

---

## 3. Client-Side vs Server-Side Architecture Comparison

- **Option A: Server-Side Alert Engine**: Requires building `AlertRule`, `AlertEvent` models, Celery beat scheduled runners, and notification delivery adapters. **BLOCKED (Requires major backend module)**.
- **Option B: Client-Side Analytical Command Center (RECOMMENDED MVP)**: Consumes existing 100% functional REST endpoints. Users define local monitor triggers (Price Target, Stop Loss Warning, New Active Signal, Regime Shift) stored in `localStorage`. While the workspace is open, TanStack Query polls active feeds on controlled intervals (e.g. 30s/60s during market hours, paused outside), evaluates conditions, fires in-app toasts/audio cues, and appends to an interactive Event Feed.
- **Option C: Hybrid**: Client-side monitoring now, transitioning to server-side Celery webhooks in future roadmap.

---

## 4. Polling Feasibility & Performance Safeguards

- **Polling Frequency**: Minimum 30s interval for active recommendations and market regime; 60s for watchlist stock quotes.
- **Market-Hours Awareness**: Respects `MarketSessionInfo.is_trading_hour`. Polling slows or pauses outside NSE market hours (09:15–15:30 IST) to eliminate wasteful server requests.
- **Staleness Handling**: Clear `DataStatus` (`LIVE` vs `HISTORICAL_PIT` / `STALE`) flags ensure old snapshots do not falsely trigger "new live" alerts.

---

## 5. Recommended FE-12 Workspace Layout

```
---------------------------------------------------------------------------------------------------
FE-12: ALERTS / MONITORING & COMMAND CENTER (/alerts)
---------------------------------------------------------------------------------------------------

1. COMMAND CENTER SYSTEM STATUS STRIP
   - Market Trading Phase Indicator (PRE_OPEN, REGULAR, POST_CLOSE, CLOSED).
   - Real-time Engine Status (Active Monitor Rules Count, Polling Health: 30s Heartbeat).
   - Total Triggered Events Today, High-Severity Actionable Signals Count.

2. ACTIVE EVENT FEED (Filterable by Category, Severity, and Source)
   - Categories: 🎯 All, 💡 Recommendations, ⚡ Intraday, 📊 Market Regime, ⭐ Watchlist Triggers, 🏛️ Corporate Filings.
   - Event Card: Timestamp (IST), Severity Badge (HIGH/MEDIUM/INFO), Source, Trigger Summary, Quick Action Link (Stock Terminal, Research, Setup Detail).

3. CUSTOM MONITOR RULE MANAGER (Create & Track In-Browser Triggers)
   - Add Custom Monitor Modal:
     - Target: Specific Watched Symbol or Market-Wide.
     - Condition Type: Price Above, Price Below, New Active BUY Signal, High Opp Score (>=80), Regime Shift to BEARISH.
     - Notification Style: In-app banner, browser desktop toast, or audio chime.
   - Active Rules Table with Toggle (Active / Paused), Delete Rule.

4. REAL-TIME EVENT DETAIL DRAWER (On Event Click)
   - Event Narrative, Associated Stock Quote snapshot, Full Trade Parameters (Entry/Stop/Target), Action Buttons (📈 Terminal, 🤖 AI Research, 💡 Recommendations).

5. SERVER-SIDE NOTIFICATION BOUNDARY (Informational Card)
   - Restrained note identifying SMS, Email, and Webhook external delivery as FUTURE backend features.
---------------------------------------------------------------------------------------------------
```

---

## 6. Backend Gap Classification

- **P0 (Blocks FE-12 MVP)**: **ZERO (0 Blockers)**. Client-side analytical command center operates 100% on existing endpoints.
- **P1 (Important Enhancements)**:
  - Add backend `AlertRule` and `AlertNotification` tables with user accounts.
  - Add Django Celery beat worker evaluating price levels on every ingested candle.
- **P2 / FUTURE**:
  - Webhook delivery (Slack, Telegram, Discord).
  - Browser Push API / FCM server integration.
