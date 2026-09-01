# FE-12 Alerts / Monitoring & Command Center — Technical Inspection Handoff

## 1. Executive Status

- **Status**: **INSPECTION COMPLETE (READ-ONLY)**
- **Date**: September 1, 2026
- **Workspace Route**: `/alerts`
- **Backend P0 Blockers**: **ZERO (0 P0 Blockers)** for an in-browser Analytical Command Center & Event Monitor consuming existing live endpoints and storing user monitor rules in `localStorage`.

---

## 2. Implemented vs Missing Backend Capabilities

| Capability | Status | Technical Details |
| :--- | :--- | :--- |
| **Backend Alert / Notification Model** | **MISSING** | No database model or REST endpoint exists in Django ORM. |
| **Trigger Rule Engine** | **MISSING** | No server-side Celery beat daemon evaluates condition rules. |
| **External Delivery Channels** | **MISSING** | No Email, SMS, Webhook, Telegram, or Slack delivery integrations. |
| **WebSocket Market Stream** | **MISSING** | Channels has `ChatConsumer` for AI LLM streaming; no market or alert WebSocket consumer exists. |
| **Active Strategy Signals Feed** | **IMPLEMENTED** | `GET /api/v1/recommendations/?status=ACTIVE` returns actionable trade setups. |
| **Discovery Opportunities Feed** | **IMPLEMENTED** | `GET /api/v1/opportunities/` returns scored delivery setups. |
| **Intraday Signal Feed** | **IMPLEMENTED** | `GET /api/v1/intraday/recommendations/` returns real-time intraday triggers. |
| **Market Regime Feed** | **IMPLEMENTED** | `GET /api/v1/market/regime/` returns trend, volatility, and breadth regimes. |
| **Client-Side Trigger Persistence** | **IMPLEMENTED** | Browser `localStorage` can persist custom price/technical threshold rules and historical triggered event logs. |

---

## 3. Recommended FE-12 MVP Option

- **Selected Option**: **Option B (Client-Side Command Center & Analytical Event Monitor)**.
- **Mechanism**:
  - Consumes existing 100% functional REST endpoints.
  - Users define monitor rules (Price Above, Price Below, New Active BUY Signal, High Opp Score >= 80, Regime Shift to BEARISH) stored in `localStorage`.
  - TanStack Query polls active feeds on controlled intervals (30s/60s during trading hours, paused outside) to detect transitions and log real-time event cards.
  - Interactive Action buttons route users directly to Stock Terminal (FE-5), Fundamentals (FE-9), AI Research (FE-8), Recommendations (FE-6), Delivery (FE-3), or Watchlists (FE-11).

---

## 4. Recommended Layout

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

## 5. Artifact & Documentation Locations

- **Full Inspection Report**: [docs/frontend/FE_12_ALERTS_MONITORING_INSPECTION.md](file:///Users/shivamsingh/personal/nomad-analyst/docs/frontend/FE_12_ALERTS_MONITORING_INSPECTION.md)
- **Inspection Handoff Document**: [FE_12_INSPECTION_HANDOFF.md](file:///Users/shivamsingh/personal/nomad-analyst/FE_12_INSPECTION_HANDOFF.md)
