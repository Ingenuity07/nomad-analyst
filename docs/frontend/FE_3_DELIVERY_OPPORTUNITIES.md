# Nomad Analyst — FE-3 Delivery Opportunities & Candidate Ranking Documentation

**Version:** 1.0.0 (FE-3 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (19/19 Vitest Tests + 229/229 Django Tests)  
**Route:** `/delivery`

---

## 1. Executive Summary

FE-3 implements the **Delivery Opportunities & Candidate Ranking Workspace** (`/delivery`). It exposes the backend's multi-factor cross-sectional scoring engine (Module 7) and trade recommendation linkage (Module 8) without inventing any client-side investment logic.

The workspace directly answers:
- Which Indian equity candidates currently present the highest quality setup for a swing or positional delivery trade?
- What is the composite multi-factor score (Technicals, Fundamentals, Sector Leadership, Macro, News)?
- Exactly *why* did each candidate surface (supporting positive evidence)?
- What specific structural risks or overhead hurdles are identified?
- Is there an active linked recommendation with formal entry, stop loss, and target levels?

---

## 2. Component Architecture

```
frontend/src/
├── features/delivery/components/
│   ├── DeliveryFilterToolbar.tsx        # Universe, Horizon, Sector, Min Score & Symbol filters
│   ├── OpportunitySummaryStrip.tsx      # Ranked candidate count, highest score, sector concentration
│   ├── OpportunityCandidateTable.tsx    # Multi-column ranked candidate table with inspect triggers
│   └── OpportunityQuickViewDrawer.tsx   # Detailed candidate investigation panel & recommendation linkage
├── pages/
│   └── DeliveryPage.tsx                 # Root workspace orchestrator with pagination & reset controls
└── test/
    └── deliveryPage.test.tsx            # Vitest unit & component test suite (4 tests, all passing)
```

---

## 3. Consumed REST APIs

| Endpoint | Method | Query Parameters | Response Mapping | Purpose |
|---|---|---|---|---|
| `GET /api/v1/opportunities/` | `GET` | `universe`, `horizon`, `sector`, `min_score`, `page`, `page_size` | `PaginatedResponse<StockOpportunitySnapshot>` | Primary ranked candidate discovery feed |
| `GET /api/v1/recommendations/` | `GET` | `horizon`, `status=ACTIVE` | `PaginatedResponse<StockRecommendation>` | Linkage with active trade recommendation orders |
| `GET /api/v1/market/overview/` | `GET` | `universe` | `MarketOverviewResponse` | Compact benchmark regime & breadth context |

---

## 4. Multi-Factor Score & Evidence Presentation

- **Composite Score:** Rendered as an institutional ranking score (`★ 87.5/100`) rather than a "probability of profit".
- **Component Breakdown:** 4-grid tile displaying Technical, Fundamental, Sector Leadership, and News scores (0–100).
- **Why It Surfaced:** Direct rendering of backend-generated `supporting_features.pros` strings.
- **Identified Risks:** Direct rendering of backend-generated `risks` strings.
- **Recommendation Linkage:** Automatic detection of matching active signals (`BUY`/`SELL`) with entry conditions and stop/target prices.
