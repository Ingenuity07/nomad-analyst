# FE-12 — ALERTS / MONITORING & COMMAND CENTER WORKSPACE SPECIFICATION

## Overview
The **Alerts / Monitoring & Command Center** (`/alerts`) serves as an in-browser live tactical monitoring workspace for Nomad Analyst. It monitors existing authoritative backend feeds (live recommendations, delivery opportunities, market regimes, and specific price movements) while the browser is open.

## Scope & Architectural Boundary
- **Client-Side Analytical Command Center**: All triggers, crossing transitions, and event aggregations are evaluated in the browser session.
- **Strict Scope Boundaries**:
  - NO custom backend Alert/Notification models.
  - NO server-side automated alert daemons, SMS, Email, Webhook (Slack/Telegram) dispatches.
  - Informational boundary card explicitly clarifies that external channel notifications are planned backend infrastructure (FUTURE).

## Storage & Rule Model
- **Storage Key**: `nomad_analyst_monitors_v1` in `localStorage`.
- **Max Event History**: Capped at 500 events to prevent unbounded storage growth.
- **Monitor Rule Types**:
  - `PRICE_ABOVE`: Triggers on transition when live price crosses above threshold (`prev < threshold && curr >= threshold`).
  - `PRICE_BELOW`: Triggers on transition when live price crosses below support (`prev > threshold && curr <= threshold`).
  - `NEW_ACTIVE_BUY`: Triggers on discovery of active BUY recommendation setups.
  - `OPPORTUNITY_SCORE_ABOVE`: Triggers when an opportunity setup scores at or above the user's score threshold.
  - `REGIME_SHIFT_TO_BEARISH`: Triggers when structural trend shifts to BEARISH below SMA200.

## User Interface Components
1. **`CommandCenterStatusStrip`**: Displays market session phase, monitoring heartbeat polling interval (30s during trading hours, 120s outside), count of active rules, and high-severity event counts.
2. **`CustomMonitorManager`**: Interactive rule configuration manager allowing users to add, pause/resume, and delete threshold rules with form validation.
3. **`ActiveEventFeed`**: Real-time categorized event stream with filter pills (`ALL`, `RECOMMENDATIONS`, `OPPORTUNITIES`, `MARKET_REGIME`, `WATCHLIST_TRIGGERS`, `CORPORATE_EVENTS`), severity indicators (`HIGH`, `MEDIUM`, `INFO`), relative timestamps, and one-click navigation.
4. **`AlertDetailDrawer`**: Full modal dossier on event click displaying comprehensive analysis, observed session timestamps, and quick action links (`Stock Terminal`, `Fundamentals`, `AI Research`).
5. **`ServerNotificationBoundaryCard`**: Disclaimer component communicating client-side evaluation boundaries vs server-side alert daemons.

## Quality Gates & Verification
- Unit test suite: `frontend/src/test/alertsPage.test.tsx` (5 tests verifying strip, rules management, feed filtering, drawer navigation, and event clearing).
- Full Vitest suite: 15 test files, 62 passing tests.
- TypeScript check (`tsc --noEmit`), lint (`tsc -b`), and Vite production build (`vite build`) passing cleanly.
