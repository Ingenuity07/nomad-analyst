# Phase 17E — On-Demand Research Engine

## 1. Architectural Mission

Phase 17E integrates the existing Nomad AI/LLM capability with the completed deterministic intelligence pipeline (Phase 17C Market Context & Phase 17D Intraday Opportunity Engine).

The primary architectural mandate is **strict LLM cost control, determinism, and explainability**:
1. **Zero LLM Calls for Default Nomad Operations**:
   Market Context, Sector Rotation, Technical Analysis, Fundamentals, News Ingestion, Intraday Opportunity Detection, Opportunity Scoring, Opportunity Ranking, and Horizon Scoring run 100% deterministically without making any LLM calls.
2. **User-Initiated Only**:
   The LLM is invoked only when the user explicitly clicks **"Examine"** or **"Refresh Research"**. There are zero automatic cron jobs, zero background scans, and zero LLM calls on ticks or WebSocket updates.
3. **One-Call-Per-Examination Guarantee**:
   Python/Django collects, validates, and packages all facts into a structured `ResearchEvidencePackage` beforehand. Exactly one LLM request is sent to `IntelligentRouter`, producing one structured JSON response validated against Pydantic schema `StructuredResearchOutput`.
4. **Research Caching**:
   Opening existing research consumes zero LLM calls.
5. **Deterministic Delta Service**:
   Live changes since analysis (score delta, rank delta, momentum shift, VWAP shift, regime shift) are computed in Python with zero LLM calls.

---

## 2. Core User Flow & Architecture

```text
DATA
 │
 ▼
DETERMINISTIC ENGINES (0 LLM Calls)
 │
 ├── Market Context & Breadth
 ├── Sector Rotation & Ranking
 ├── Technical Indicators & VWAP
 ├── Fundamentals & Statements
 └── News & Corporate Events
 │
 ▼
INTRADAY OPPORTUNITY ENGINE (0 LLM Calls)
 │
 ▼
RANKED OPPORTUNITIES TABLE
 │
 ├── Ignore (0 LLM Calls)
 │
 └── EXAMINE [TATASTEEL] (Explicit User Action)
       │
       ▼
   ResearchEvidencePackageBuilder (Deterministic Fact Gathering)
       │
       ▼
   ONE COMPLETE LLM REQUEST (IntelligentRouter)
       │
       ▼
   Pydantic Schema Validation (StructuredResearchOutput)
       │
       ▼
   Persist to ResearchRun (DB)
       │
       ▼
   Display Research Modal
       │
       ├── Reopen Existing Research (0 LLM Calls)
       │
       ├── Live Delta Tracking (0 LLM Calls)
       │
       └── REFRESH RESEARCH (Explicit User Action -> 1 LLM Call)
```

---

## 3. Evidence Package Structure

The `ResearchEvidencePackageBuilder` (`research/services/evidence_builder.py`) gathers all available signals deterministically and structures them into a normalized JSON package:

```json
{
  "research_mode": "INTRADAY",
  "asset": "TATASTEEL",
  "timestamp": "2026-09-06T10:30:00Z",
  "company": {
    "symbol": "TATASTEEL",
    "name": "Tata Steel Limited",
    "sector": "Metals",
    "industry": "Steel",
    "status": "AVAILABLE",
    "source": "DATABASE"
  },
  "opportunity": {
    "status": "AVAILABLE",
    "source": "INTRADAY_OPPORTUNITY_ENGINE",
    "opportunity_type": "RELATIVE_STRENGTH",
    "state": "CONFIRMED",
    "score": 84.0,
    "confidence": 0.89,
    "rank": 1,
    "bias": "BULLISH",
    "component_scores": {
      "momentum": 85.0,
      "relative_strength": 90.0,
      "volume": 82.0,
      "vwap": 88.0,
      "market_alignment": 80.0,
      "sector_alignment": 95.0,
      "orb": 85.0,
      "data_quality": 90.0
    },
    "supporting_factors": ["Strong relative strength vs NIFTY (+1.95%)", "Above VWAP"],
    "contradicting_factors": ["Market breadth declined slightly from peak"],
    "warnings": ["Watch for resistance near 158.00"],
    "invalidation_condition": "Close below VWAP 154.20"
  },
  "stock_context": {
    "status": "AVAILABLE",
    "source": "KITE_LIVE_FEED",
    "last_price": 156.4,
    "change_pct": 2.8,
    "vwap": 154.2,
    "distance_from_vwap": 1.43,
    "volume": 4500000,
    "relative_volume": 2.4,
    "momentum_5m": 0.45,
    "momentum_15m": 1.20,
    "momentum_30m": 2.10,
    "relative_strength_vs_market": 1.95,
    "relative_strength_vs_sector": 0.40,
    "volume_confirmation": "STRONG",
    "opening_range_state": "ABOVE_ORB_HIGH"
  },
  "market_context": {
    "status": "AVAILABLE",
    "source": "KITE_MARKET_FEED",
    "regime": "TRENDING_UP",
    "direction": "BULLISH",
    "breadth_state": "EXPANDING",
    "advances": 38,
    "declines": 12,
    "advance_decline_ratio": 3.16,
    "nifty_return_pct": 0.85,
    "banknifty_return_pct": 1.10,
    "pct_above_vwap": 76.0,
    "freshness": "FRESH"
  },
  "sector_context": {
    "sector": "Metals",
    "rank": 1,
    "status": "AVAILABLE",
    "return_pct": 2.4,
    "momentum": "STRONG"
  },
  "fundamentals": { ... },
  "recent_news": [ ... ],
  "recent_events": [ ... ],
  "data_quality": {
    "overall_status": "HIGH",
    "coverage_pct": 100,
    "missing_data": []
  },
  "deterministic_summary": {
    "symbol": "TATASTEEL",
    "opportunity_score": 84.0,
    "opportunity_rank": 1,
    "market_regime": "TRENDING_UP",
    "sector_name": "Metals",
    "sector_rank": 1,
    "generated_deterministically": true
  },
  "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

---

## 4. Structured Output Schema (`StructuredResearchOutput`)

The response from `IntelligentRouter` is validated against Pydantic schema:

```python
class StructuredResearchOutput(BaseModel):
    summary: str
    observed_facts: List[str]
    analyst_interpretation: str
    why_interesting: List[str]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    key_risks: List[str]
    unknowns: List[str]
    market_context_interpretation: str
    sector_context_interpretation: str
    thesis: str
    thesis_strength: Literal["HIGH", "MEDIUM", "LOW"]
    what_to_monitor: List[str]
    invalidating_developments: List[str]
    research_confidence: Literal["HIGH", "MEDIUM", "LOW"]
```

---

## 5. API Reference

| Method | Path | Description | Cost |
|---|---|---|---|
| `POST` | `/api/v1/research/examine/` | Examines a stock. Reuses cached run if fresh; calls LLM once if uncached. | 0 or 1 LLM call |
| `GET` | `/api/v1/research/{id}/` | Retrieves existing research run and live delta. | 0 LLM calls |
| `GET` | `/api/v1/research/company/{symbol}/` | Retrieves latest completed research for a symbol. | 0 LLM calls |
| `POST` | `/api/v1/research/{id}/refresh/` | Explicitly forces a fresh AI examination for the asset. | Exactly 1 LLM call |
| `GET` | `/api/v1/research/{id}/delta/` | Real-time delta between analysis snapshot and current state. | 0 LLM calls |

---

## 6. Verification Results

- **Backend Test Suite**: 295/295 tests passing (`manage.py test research market`).
- **Frontend Test Suite**: 85/85 tests passing (`npm test -- --run`).
- **Frontend Production Build**: Cleanly compiled (`npm run build`).
- **One-Call Guarantee Verification**:
  - Examine new: `call_count == 1`.
  - Reopen existing: `call_count == 0`.
  - Market update: `call_count == 0`.
  - Opportunity update: `call_count == 0`.
  - Explicit refresh: `call_count == 1`.
