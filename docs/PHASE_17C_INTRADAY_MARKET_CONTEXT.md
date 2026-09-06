# PHASE 17C: INTRADAY MARKET CONTEXT & SIGNAL FOUNDATION

## 1. Executive Summary

Phase 17C upgrades Nomad Analyst from raw tick streaming and authentication into a continuous, real-time **intraday market-state and stock-context foundation layer**.

This foundation provides real-time market intelligence across the NIFTY 50 universe:
- Deterministic market breadth and advance/decline analytics.
- Real-time sector relative strength rankings.
- Stock-level VWAP positioning, Relative Strength vs. NIFTY 50 and Sector, and Opening Range Breakout (ORB) tracking.
- Volume confirmation states (RVOL vs. historical baselines).
- Deterministic market regime classification (`TRENDING_UP`, `TRENDING_DOWN`, `RANGE`, `VOLATILE`, `UNKNOWN`) backed by transparent reason arrays.
- Sub-second distribution via WebSocket (`ws/intraday/`) and standard REST endpoints (`/api/v1/intraday/*`).

---

## 2. Core Scope Safeguards & Non-Goals

> [!IMPORTANT]
> **Strict Phase 17C Constraints & Safeguards**:
> 1. **Data POC & Context Layer Only**: No automated order execution, broker placement, position sizing, or stop-loss execution.
> 2. **Zero Buy/Sell Recommendation Labels**: Output represents pure context (e.g. `TRENDING_UP`, `ABOVE_VWAP`, `CONFIRMED_UP`), never execution signals.
> 3. **Deterministic Calculations Only**: Zero LLMs in the calculation or tick streaming path.
> 4. **Equities & Indices Only**: No F&O, futures, or options contracts.

---

## 3. Architecture & Data Flow

```text
Kite Ticker WebSocket (Ticks)
            ↓
Kite Normalizer (ATP / Session VWAP)
            ↓
IntradayBarAggregator (1m, 5m, 15m OHLCV IST Bucketing)
            ↓
IntradayMarketContextEngine (Deterministic Math)
   ├── Market Breadth (Advances, Declines, A/D Ratio, Breadth State)
   ├── Sector Strengths (Weighted returns, breadth per sector, rank)
   ├── Stock Contexts (RS vs Nifty, RS vs Sector, VWAP diff, ORB, RVOL)
   └── Market Regime (Transparent rules + Reasons array)
            ↓
IntradayStateManager (Redis Cache + Rate-Throttled Broadcasts + DB Persistence)
   ├── Django Channels: ws/intraday/ (Real-Time State Push)
   └── Django REST API: /api/v1/intraday/* (Polling & Initial Page Load)
            ↓
React 19 Frontend (useIntradayMarketContext)
   ├── IntradayMarketHeader (NIFTY & BANKNIFTY cards, Regime badge, Drivers)
   ├── IntradayBreadthCard (Visual ratio bar, Adv/Dec, Above VWAP %)
   ├── IntradaySectorStrengthPanel (Sector leaderboards, Breadth)
   └── IntradayStockContextTable (Sortable 50-stock matrix with zero buy/sell labels)
```

---

## 4. Deterministic Engine Specifications

### 4.1 Market Breadth
- **Advances / Declines / Unchanged**: Counted against previous session close.
- **Advance/Decline Ratio**: $A / \max(D, 1)$.
- **Breadth State**:
  - `STRONG_POSITIVE`: $A/D \ge 2.0$ and $A \ge 30$.
  - `MODERATE_POSITIVE`: $A/D \ge 1.3$.
  - `NEUTRAL`: $0.77 \le A/D < 1.3$.
  - `MODERATE_NEGATIVE`: $0.5 < A/D < 0.77$.
  - `STRONG_NEGATIVE`: $A/D \le 0.5$ and $D \ge 30$.

### 4.2 VWAP & Volume Confirmation
- **VWAP Positioning**: Percentage distance of last price from average traded price (ATP):
  $$\text{vwap\_diff\_pct} = \frac{\text{price} - \text{vwap}}{\text{vwap}} \times 100$$
- **Relative Volume (RVOL)**: Ratio of current cumulative volume to expected intraday pace or 20-day historical average.
- **Volume Confirmation States**:
  - `CONFIRMED_UP`: Price above VWAP and $\text{RVOL} \ge 1.2$.
  - `WEAK_UP`: Price above VWAP and $\text{RVOL} < 1.2$.
  - `CONFIRMED_DOWN`: Price below VWAP and $\text{RVOL} \ge 1.2$.
  - `WEAK_DOWN`: Price below VWAP and $\text{RVOL} < 1.2$.
  - `NEUTRAL`: Price within $\pm 0.1\%$ of VWAP.

### 4.3 Opening Range Breakout (ORB)
- **Window**: First 15 minutes of trading session (09:15–09:30 IST).
- **Classifications**:
  - `ABOVE_ORB`: Price $> \text{High}_{15m}$.
  - `BELOW_ORB`: Price $< \text{Low}_{15m}$.
  - `INSIDE_ORB`: $\text{Low}_{15m} \le \text{Price} \le \text{High}_{15m}$.

### 4.4 Deterministic Market Regime Decision Matrix
Regimes are classified without machine learning or heuristics using explicit thresholds configured in `market/services/intraday_config.py`:
- `TRENDING_UP`:
  - NIFTY 50 return $> +0.3\%$.
  - Advance/Decline ratio $> 1.5$.
  - $> 60\%$ of constituents trading above VWAP.
  - Sector breadth $> 60\%$ positive.
- `TRENDING_DOWN`:
  - NIFTY 50 return $< -0.3\%$.
  - Advance/Decline ratio $< 0.67$.
  - $> 60\%$ of constituents trading below VWAP.
  - Sector breadth $> 60\%$ negative.
- `RANGE`:
  - NIFTY 50 return between $-0.2\%$ and $+0.2\%$.
  - Advance/Decline ratio between $0.8$ and $1.25$.
- `VOLATILE`:
  - Divergence between price index direction and market breadth (e.g. index green but $A/D < 0.8$, or wide intraday swing).

Each classification generates an explicit human-readable `regime_reasons` array (e.g., `["NIFTY return +0.45% above bullish threshold", "A/D ratio 2.50 shows strong positive participation", "72.0% stocks trading above session VWAP"]`).

---

## 5. API Endpoints Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/intraday/context/` | Full market context snapshot (indices, breadth, regime, sectors, leaders). |
| `GET` | `/api/v1/intraday/stocks/` | All constituent stock intraday context records (sortable, filterable by sector). |
| `GET` | `/api/v1/intraday/stocks/{symbol}/` | Detailed single-stock intraday context (VWAP, RS, ORB, Volume states). |
| `GET` | `/api/v1/intraday/sectors/` | Sector performance leaderboard and breadth distribution. |
| `GET` | `/api/v1/intraday/indices/` | Major indices status (NIFTY 50, NIFTY BANK, etc.). |
| `GET` | `/api/v1/intraday/data-health/` | Session status, feed freshness tier (`FRESH`/`STALE`/`UNAVAILABLE`), tick counts. |
| `WS` | `/ws/intraday/` | Sub-second real-time streaming channel for market context and stock updates. |

---

## 6. Test & Validation Summary

- **Backend Tests**:
  - `market.tests.IntradayMarketContextTests`: 10/10 tests passed (Breadth, Sector ranking, VWAP & Volume confirmation, ORB classification, Deterministic regimes, Bar aggregator 1m/5m/15m, Persistence, REST APIs, Freshness tiers, Tick ATP normalization).
  - Full `market` suite: 272/272 tests passed.
- **Frontend Tests**:
  - `frontend/src/test/intradayMarketContext.test.tsx`: 5/5 tests passed.
  - Full Vitest suite: 19 test files, 77/77 tests passed.
  - TypeScript build (`tsc -b && vite build`): Succeeded cleanly with 0 errors.
