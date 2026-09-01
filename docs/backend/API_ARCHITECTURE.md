# Nomad Analyst — Backend REST API Architecture (v1)

**Version:** 1.0.0 (BE-API-1)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (229/229 Passing Tests)  
**Base Path:** `/api/v1/`

---

## 1. Architectural Philosophy & Layering

The Nomad Analyst REST API layer serves strictly as a **presentation and serialization boundary**.

```
Frontend (React 19 + TypeScript Terminal)
    │
    ▼
REST API Layer (/api/v1/...) [Django 6.0 + DRF]
    │
    ├── Serializers & API Parameter Validation (Pydantic / DRF)
    │
    ├── Custom API Exception Handler (Standard Error Envelopes)
    │
    ▼
Domain Service Layer (Modules 0–11)
    │
    ├── MarketContextService, MarketService, TechnicalFeatureEngine
    ├── FundamentalDataService, FundamentalMetricService
    ├── NewsIntelligenceService
    ├── OpportunityDiscoveryService, RecommendationService
    ├── IntradaySignalEngine, IntradayReadinessService
    ├── RecommendationOutcomeService, PerformanceMetricsService
    ├── BacktestRunner (PIT-Safe Walk-Forward)
    └── MarketResearchService (Intelligent Multi-LLM Routing)
    │
    ▼
Database & Telemetry Layer (PostgreSQL 16 + SQLite + Redis)
```

### Core Rules Enforced:
1. **No Business Logic in Views:** All indicator formulas, setup criteria, opportunity weights, and backtest math live in `market.services.*`.
2. **Point-in-Time (PIT) Safety:** `as_of` parameters are passed directly down to domain service methods. Views do not perform client-side date slicing.
3. **Read-Only by Default:** All market, stock, opportunity, recommendation, outcome, and backtest endpoints are read-only. Computation endpoints (`/backtests/run/`, `/research/`) use `POST` to request deterministic or AI computations without mutating historical market data.

---

## 2. API Namespace & Route Map

All v1 routes are mounted under `/api/v1/`:

| Path | Method | View Class | Backend Service Provider |
|---|---|---|---|
| `/api/v1/market/overview/` | `GET` | `MarketOverviewAPIView` | `MarketContextService`, `MarketService`, `NewsIntelligenceService` |
| `/api/v1/market/indices/` | `GET` | `MarketIndicesAPIView` | `MarketContextService`, `MarketSnapshot` |
| `/api/v1/market/regime/` | `GET` | `MarketRegimeAPIView` | `MarketContextService` |
| `/api/v1/market/breadth/` | `GET` | `MarketBreadthAPIView` | `MarketContextService` |
| `/api/v1/market/sectors/` | `GET` | `MarketSectorsAPIView` | `MarketContextService` |
| `/api/v1/market/global/` | `GET` | `MarketGlobalCuesAPIView` | `MarketContextService` |
| `/api/v1/stocks/` | `GET` | `StockListAPIView` | `Instrument.objects.filter(is_active=True)` |
| `/api/v1/stocks/search/` | `GET` | `StockSearchAPIView` | Symbol & Company autocomplete (`Q(symbol__icontains=...)`) |
| `/api/v1/stocks/{symbol}/` | `GET` | `StockDetailAPIView` | `Instrument`, `MarketSnapshot`, `StockRecommendation` |
| `/api/v1/stocks/{symbol}/ohlcv/` | `GET` | `StockOHLCVAPIView` | `OHLCVBar.objects.filter(timeframe=...)` |
| `/api/v1/stocks/{symbol}/technicals/` | `GET` | `StockTechnicalsAPIView` | `TechnicalFeature.objects.filter(timeframe=...)` |
| `/api/v1/stocks/{symbol}/fundamentals/`| `GET` | `StockFundamentalsAPIView`| `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement`, `DerivedFundamentalMetric` |
| `/api/v1/stocks/{symbol}/news/` | `GET` | `StockNewsAPIView` | `NewsItem.objects.filter(...)` |
| `/api/v1/stocks/{symbol}/events/` | `GET` | `StockDisclosuresAPIView` | `CorporateDisclosure.objects.filter(...)` |
| `/api/v1/opportunities/` | `GET` | `OpportunityListAPIView` | `StockOpportunitySnapshot.objects.all()` |
| `/api/v1/opportunities/{id}/` | `GET` | `OpportunityDetailAPIView`| `StockOpportunitySnapshot.objects.get(id=...)` |
| `/api/v1/recommendations/` | `GET` | `RecommendationListAPIView`| `StockRecommendation.objects.all()` |
| `/api/v1/recommendations/{id}/` | `GET` | `RecommendationDetailAPIView`| `StockRecommendation.objects.get(id=...)` |
| `/api/v1/recommendations/{id}/outcome/`| `GET` | `RecommendationOutcomeDetailAPIView`| `RecommendationOutcome.objects.get(...)` |
| `/api/v1/intraday/overview/` | `GET` | `IntradayOverviewAPIView` | `classify_session`, `StockRecommendation` |
| `/api/v1/intraday/recommendations/` | `GET` | `IntradayRecommendationsAPIView`| `StockRecommendation.objects.filter(horizon='INTRADAY')` |
| `/api/v1/intraday/data-quality/` | `GET` | `IntradayDataQualityAPIView`| `IntradayReadinessService.check_readiness` |
| `/api/v1/outcomes/` | `GET` | `OutcomeListAPIView` | `RecommendationOutcome.objects.all()` |
| `/api/v1/strategies/` | `GET` | `StrategyListAPIView` | Strategy setup registry |
| `/api/v1/strategies/{strategy}/performance/`| `GET` | `StrategyPerformanceAPIView`| Aggregated metrics over `RecommendationOutcome` |
| `/api/v1/backtests/` | `GET` | `BacktestListAPIView` | `BacktestRun.objects.all()` |
| `/api/v1/backtests/run/` | `POST` | `BacktestRunAPIView` | `BacktestRunner.run(config)` |
| `/api/v1/backtests/{run_id}/` | `GET` | `BacktestDetailAPIView` | `BacktestRun.objects.get(run_id=...)` |
| `/api/v1/research/` | `POST` | `StockResearchAPIView` | `MarketResearchService.research_stock` |

---

## 3. Error Contract & Conventions

All endpoints adhere to the standard error envelope via `market/api_exceptions.py`:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Stock symbol 'XYZ' not found.",
    "details": {},
    "timestamp": "2026-09-01T13:25:00.000000+00:00"
  }
}
```

- **HTTP 400:** Validation errors (e.g. malformed date or query param).
- **HTTP 404:** Resource not found (`Instrument`, `Recommendation`, `BacktestRun`).
- **HTTP 500:** Unexpected server / provider failure with sanitized error message (zero exposed stack traces or keys).
