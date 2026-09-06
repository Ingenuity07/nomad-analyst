# PHASE 17D: INTRADAY OPPORTUNITY ENGINE

## 1. Executive Summary

Phase 17D delivers the **intraday stock opportunity-selection layer** on top of the Phase 17C Market Context & Signal Foundation.

It answers the core research question:
> **Which stocks in the NIFTY 50 are currently the most interesting intraday opportunities, and why?**

The engine evaluates all NIFTY 50 constituents in real-time, producing **ranked, explainable intraday opportunities** with 8-dimensional score breakdowns, transparent deductions, separate evidence confidence, and structured positive/negative factors.

---

## 2. Critical Scope Safeguards & Constraints

> [!IMPORTANT]
> **Strict Phase 17D Scope Boundaries & Safeguards**:
> 1. **Opportunity Discovery & Ranking Only**: Strictly zero automated order execution, broker placement (`place_order`, `modify_order`, `cancel_order`), position sizing, or automated stop-loss / target orders.
> 2. **Zero Buy/Sell Recommendation Labels**: Classifications describe research opportunity context (e.g. `MOMENTUM_CONTINUATION`, `RELATIVE_STRENGTH`, `VWAP_TREND`, `OPENING_RANGE_BREAKOUT`, `SECTOR_LEADERSHIP`, `MEAN_REVERSION_CONTEXT`), never trade execution commands (`BUY`, `SELL`).
> 3. **Deterministic Math Only**: Zero LLMs in the live tick, detection, scoring, or ranking paths.
> 4. **Equities & Indices Only**: No F&O, futures, options, or derivatives signals.
> 5. **No Look-Ahead Guarantee**: The engine is fully Point-In-Time (PIT) compliant and verified with a mandatory regression test proving future data does not alter earlier snapshot evaluations.

---

## 3. Architecture & Data Flow

```text
Kite Ticker / Market Feed (Phase 17B)
            ↓
Intraday Market Context & Bar Aggregator (Phase 17C)
   ├── Market Breadth (A/D ratio, state)
   ├── Sector Strengths & Leaderboards
   └── Stock Contexts (VWAP, RVOL, ORB, RS)
            ↓
┌─────────────────────────────────────────────────────────────┐
│          PHASE 17D INTRADAY OPPORTUNITY ENGINE              │
├─────────────────────────────────────────────────────────────┤
│ 1. IntradayOpportunityDetector                              │
│    ├── Candidate Eligibility Filtering (Price, VWAP, Vol)  │
│    └── Opportunity Family Classification                   │
│ 2. IntradayOpportunityScorer                                │
│    ├── 8-Dimensional Component Scoring (0-100)             │
│    ├── Transparent Penalty Deductions                      │
│    ├── Separate Confidence Estimation (0.0-1.0)            │
│    └── Lifecycle State Machine                             │
│ 3. IntradayOpportunityExplainer                             │
│    ├── Supporting Factors (Positive Evidence)              │
│    ├── Contradicting Factors (Contrary Signals)            │
│    ├── Warnings & Contextual Risks                         │
│    └── Invalidation Threshold                              │
│ 4. IntradayOpportunityRanker                                │
│    ├── Deterministic Tie-Breaking (Score > Conf > Sym)     │
│    └── Modes: RAW_RANKING vs SECTOR_DIVERSIFIED            │
└─────────────────────────────────────────────────────────────┘
            ↓
Distribution & Persistence
   ├── Django Channels: ws/intraday/ (opportunity_update)
   ├── Django REST APIs: /api/v1/intraday/opportunities/*
   └── Database: IntradayOpportunitySnapshot
            ↓
React 19 Frontend (IntradayOpportunityDashboard)
   ├── Filter Toolbar (Mode, Type, State, Sector, Min Score)
   ├── Ranked Opportunity Table
   └── Explainable Detail Drawer (Score bars, factors, invalidation)
```

---

## 4. Opportunity Families & Classifications

| Family | Directional Bias | Key Contextual Evidence |
| :--- | :--- | :--- |
| `MOMENTUM_CONTINUATION` | `BULLISH` / `BEARISH` | Persistent 5m & 15m momentum aligned with price on the correct side of VWAP with volume confirmation. |
| `RELATIVE_STRENGTH` | `BULLISH` / `BEARISH` | Stock materially outperforming or underperforming both NIFTY 50 ($\ge +0.3\%$) and its sector ($\ge +0.3\%$). |
| `VWAP_TREND` | `BULLISH` / `BEARISH` | Sustained distance beyond VWAP ($\ge 0.3\%$) supported by volume confirmation (`CONFIRMED_UP` / `CONFIRMED_DOWN`). |
| `OPENING_RANGE_BREAKOUT` | `BULLISH` | Price trading above the 15-minute Opening Range high with VWAP support and momentum. |
| `OPENING_RANGE_BREAKDOWN` | `BEARISH` | Price trading below the 15-minute Opening Range low with VWAP breakdown. |
| `SECTOR_LEADERSHIP` | `BULLISH` | Stock outperforming within a top 2 ranked sector, with positive market RS and VWAP support. |
| `MEAN_REVERSION_CONTEXT` | `BULLISH_EXHAUSTION` / `BEARISH_EXHAUSTION` | Unusually large VWAP deviation ($\ge 2.5\%$) paired with decelerating short-term momentum (pure context, never a "buy the dip" signal). |
| `NO_CLEAR_OPPORTUNITY` | `NEUTRAL` | Fallback when technical metrics do not satisfy primary opportunity thresholds. |

---

## 5. 8-Dimensional Scoring Model (0–100)

The composite score reflects the **quality of the current intraday opportunity context** without double-counting correlated signals.

| Component | Weight | Purpose |
| :--- | :---: | :--- |
| **Momentum** | 20% | Directional persistence across 5m and 15m intervals. |
| **Relative Strength** | 20% | Balanced performance relative to benchmark NIFTY 50 and Sector peers. |
| **Volume Confirmation** | 15% | Participation confirmation using Relative Volume (RVOL). |
| **VWAP Positioning** | 10% | Location relative to the session's volume-weighted average price. |
| **Market Alignment** | 10% | Alignment with broader NIFTY 50 direction, regime, and breadth ratio. |
| **Sector Alignment** | 10% | Alignment with sector trend and constituent participation. |
| **ORB / Structure** | 5% | Structural position relative to the 15-minute opening range. |
| **Data Quality** | 10% | Recency, completeness of indicators, and data integrity. |

### Transparent Penalties
- `STALE_MARKET_DATA`: -25 points.
- `MISSING_INDEX_CONTEXT`: -15 points.
- `MISSING_SECTOR_CONTEXT`: -15 points.
- `MARKET_DIVERGENCE`: -12 points (e.g. bullish candidate in a strong downtrend).
- `SECTOR_DIVERGENCE`: -10 points.
- `LOW_VOLUME_CONFIRMATION`: -10 points (RVOL < 0.8).

### Separate Confidence Score (0.0 to 1.0)
Confidence represents evidence completeness and agreement, **NOT** probability of profit:
$$\text{Confidence} = 0.30 \times \text{Data Quality} + 0.40 \times \text{Evidence Agreement} + 0.30 \times \text{Volume Participation}$$

---

## 6. Opportunity Lifecycle State Machine

- `EMERGING`: Initial conditions forming ($\text{Score} \ge 50.0$).
- `CONFIRMED`: Multiple independent dimensions agree ($\text{Score} \ge 70.0$, $\text{Confidence} \ge 0.65$).
- `WEAKENING`: Previously confirmed setup experiencing a score drop ($\ge 10$ points).
- `INVALIDATED`: Core conditions broken (e.g., price crossed back across VWAP or ORB boundary).
- `STALE`: Market feed delayed beyond configured threshold (60s).

---

## 7. REST & WebSocket API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/v1/intraday/opportunities/` | `GET` | Ranked opportunities with filters: `limit`, `sector`, `opportunity_type`, `state`, `min_score`, `mode`. |
| `/api/v1/intraday/opportunities/top/` | `GET` | Lightweight top 5/10/20 opportunities for dashboard cards. |
| `/api/v1/intraday/opportunities/{symbol}/` | `GET` | Single-stock opportunity evaluation with full dimensional breakdown and factors. |
| `/api/v1/intraday/opportunities/{symbol}/history/` | `GET` | Historical snapshots showing state and score transitions for that symbol. |
| `ws/intraday/` | `WS` | Receives `opportunity_init` upon connection and throttled `opportunity_update` live broadcasts. |

---

## 8. Verification & Test Results

- **Backend Unit Tests**:
  - `market.tests.IntradayOpportunityEngineTests`: **8/8 tests passed** (Candidate filtering, Opportunity family detection, 8-dimensional scoring & penalties, Structured explainability, Deterministic ranking & tie-breakers, Snapshot persistence, REST APIs, and the **mandatory No-Look-Ahead regression test**).
  - `market.tests.IntradayMarketContextTests`: **10/10 tests passed**.
  - Full `market` suite: **280/280 tests passed**.
- **Frontend Unit Tests**:
  - `frontend/src/test/intradayOpportunities.test.tsx`: **4/4 tests passed**.
  - Full Vitest suite: **20 test files, 81/81 tests passed**.
  - Production build (`tsc -b && vite build`): **Compiled cleanly with 0 TypeScript errors**.
