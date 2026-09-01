# FE-6 INSPECTION HANDOFF — RECOMMENDATIONS & OUTCOME TRACKING

**Status:** TECHNICAL INSPECTION COMPLETE ✅  
**Date:** September 1, 2026  
**Action:** READ-ONLY AUDIT (NO CODE MODIFIED)

---

## 1. Executive Summary

This handoff details the findings of the technical inspection regarding trade recommendation generation, lifecycle state management, outcome tracking, performance aggregations, and strategy attribution for the future **FE-6 Recommendations & Outcome Tracking Workspace** (`/recommendations`).

---

## 2. Core Inspection Answers

### Q1: Exact recommendation APIs available
- `GET /api/v1/recommendations/?horizon=...&signal=...&status=...&confidence=...&page=...` -> Paginated recommendation records with entry, stop, targets, R:R, supporting factors, and risk factors.
- `GET /api/v1/recommendations/{id}/` -> Single recommendation record detail.

### Q2: Exact outcome APIs available
- `GET /api/v1/recommendations/{id}/outcome/` -> Dedicated outcome evaluation for a recommendation (entry price/time, exit price/time, net P&L %, R-multiple, MFE %, MAE %, holding duration).
- `GET /api/v1/outcomes/?signal=...&setup_type=...&exit_reason=...&page=...` -> Paginated historical recommendation outcomes.
- `GET /api/v1/strategies/` -> List of supported strategy horizons and setups.
- `GET /api/v1/strategies/{strategy}/performance/` -> Aggregated performance metrics (sample size, win rate, avg R-multiple, small sample warning flag).

### Q3: Actual lifecycle states
- `ACTIVE` -> Generated and armed, waiting for entry price trigger.
- `TRIGGERED` -> Price penetrated entry zone; position opened.
- `TARGET_HIT` -> Market confirmed Target 1 hit.
- `STOPPED` -> Market confirmed Stop Loss hit.
- `EXPIRED` -> Expired at session close (15:30 IST for intraday) or holding duration.
- `INVALIDATED` -> Market invalidated setup conditions prior to entry.
- `CANCELLED` -> Manually or programmatically cancelled.
- `AMBIGUOUS_INTRABAR` -> Same-bar stop + target collision resolved conservatively.

### Q4: Actual performance metrics
- `sample_size`, `wins`, `losses`, `win_rate`, `avg_r_multiple`, `is_small_sample` (<30 trades flag), `net_pnl_percent`, `gross_pnl_percent`, `cost_absolute`, `risk_amount`, `r_multiple`, `max_favorable_excursion` (MFE), `max_adverse_excursion` (MAE), `holding_duration_bars`.

### Q5: Actual strategy / setup attribution
- **Horizons:** `DELIVERY_SWING`, `INTRADAY`, `LONG_TERM`.
- **Setups:** `BREAKOUT`, `PULLBACK`, `MOMENTUM`, `ORB_BREAKOUT`, `VWAP_RECLAIM`, `TREND_CONTINUATION`, `MEAN_REVERSION`.
- **Sectors:** Filterable via `company.sector`.

### Q6: Point-In-Time (PIT) / Look-ahead status
- **Fully Protected:** All recommendation and outcome records store explicit chronological timestamps (`generated_at`, `entry_timestamp`, `exit_timestamp`, `evaluated_at`) and are immutable.

### Q7: Whether backend work blocks FE-6
- **NO BACKEND WORK BLOCKS FE-6.** All 6 required REST endpoints are fully operational and verified.

### Q8: Recommended FE-6 information architecture
- Strategy performance metric summary strip (Win Rate, Avg R, Sample Size, Small Sample Alert).
- Multi-parameter filter toolbar (Horizon, Signal, Setup, Status, Confidence, Symbol search).
- Dual-tab layout: **Active Signals** (Armed/Triggered) and **Historical Outcomes** (Closed/Evaluated).
- Recommendation & Outcome detail drawer exposing trade parameters, supporting evidence, risks, and realized P&L/R-multiple metrics.

---

## 3. Exact Next Step

**Technical inspection complete. Awaiting user instruction before implementing FE-6.**
