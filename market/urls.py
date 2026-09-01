from django.urls import path
from .views import (
    # Market
    MarketOverviewAPIView, MarketIndicesAPIView, MarketRegimeAPIView,
    MarketBreadthAPIView, MarketSectorsAPIView, MarketGlobalCuesAPIView,
    # Stocks
    StockListAPIView, StockSearchAPIView, StockDetailAPIView,
    StockOHLCVAPIView, StockTechnicalsAPIView, StockFundamentalsAPIView,
    StockNewsAPIView, StockDisclosuresAPIView,
    # Opportunities
    OpportunityListAPIView, OpportunityDetailAPIView,
    # Recommendations
    RecommendationListAPIView, RecommendationDetailAPIView,
    # Intraday
    IntradayOverviewAPIView, IntradayRecommendationsAPIView, IntradayDataQualityAPIView,
    # Outcomes & Strategy
    RecommendationOutcomeDetailAPIView, OutcomeListAPIView,
    StrategyListAPIView, StrategyPerformanceAPIView,
    # Backtests
    BacktestListAPIView, BacktestDetailAPIView, BacktestRunAPIView,
    # Research
    StockResearchAPIView
)

urlpatterns = [
    # ── Market Context ────────────────────────────────────────────────────────
    path('market/overview/', MarketOverviewAPIView.as_view(), name='api-market-overview'),
    path('market/indices/', MarketIndicesAPIView.as_view(), name='api-market-indices'),
    path('market/regime/', MarketRegimeAPIView.as_view(), name='api-market-regime'),
    path('market/breadth/', MarketBreadthAPIView.as_view(), name='api-market-breadth'),
    path('market/sectors/', MarketSectorsAPIView.as_view(), name='api-market-sectors'),
    path('market/global/', MarketGlobalCuesAPIView.as_view(), name='api-market-global'),

    # ── Stocks & Historical Data ──────────────────────────────────────────────
    path('stocks/', StockListAPIView.as_view(), name='api-stock-list'),
    path('stocks/search/', StockSearchAPIView.as_view(), name='api-stock-search'),
    path('stocks/<str:symbol>/', StockDetailAPIView.as_view(), name='api-stock-detail'),
    path('stocks/<str:symbol>/ohlcv/', StockOHLCVAPIView.as_view(), name='api-stock-ohlcv'),
    path('stocks/<str:symbol>/technicals/', StockTechnicalsAPIView.as_view(), name='api-stock-technicals'),
    path('stocks/<str:symbol>/fundamentals/', StockFundamentalsAPIView.as_view(), name='api-stock-fundamentals'),
    path('stocks/<str:symbol>/news/', StockNewsAPIView.as_view(), name='api-stock-news'),
    path('stocks/<str:symbol>/events/', StockDisclosuresAPIView.as_view(), name='api-stock-events'),

    # ── Opportunity Discovery ─────────────────────────────────────────────────
    path('opportunities/', OpportunityListAPIView.as_view(), name='api-opportunity-list'),
    path('opportunities/<uuid:id>/', OpportunityDetailAPIView.as_view(), name='api-opportunity-detail'),

    # ── Recommendations ───────────────────────────────────────────────────────
    path('recommendations/', RecommendationListAPIView.as_view(), name='api-recommendation-list'),
    path('recommendations/<uuid:id>/', RecommendationDetailAPIView.as_view(), name='api-recommendation-detail'),
    path('recommendations/<uuid:id>/outcome/', RecommendationOutcomeDetailAPIView.as_view(), name='api-recommendation-outcome'),

    # ── Intraday ──────────────────────────────────────────────────────────────
    path('intraday/overview/', IntradayOverviewAPIView.as_view(), name='api-intraday-overview'),
    path('intraday/recommendations/', IntradayRecommendationsAPIView.as_view(), name='api-intraday-recommendations'),
    path('intraday/data-quality/', IntradayDataQualityAPIView.as_view(), name='api-intraday-data-quality'),

    # ── Outcomes & Strategy Performance ───────────────────────────────────────
    path('outcomes/', OutcomeListAPIView.as_view(), name='api-outcome-list'),
    path('strategies/', StrategyListAPIView.as_view(), name='api-strategy-list'),
    path('strategies/<str:strategy>/performance/', StrategyPerformanceAPIView.as_view(), name='api-strategy-performance'),

    # ── Backtesting ───────────────────────────────────────────────────────────
    path('backtests/', BacktestListAPIView.as_view(), name='api-backtest-list'),
    path('backtests/run/', BacktestRunAPIView.as_view(), name='api-backtest-run'),
    path('backtests/<str:run_id>/', BacktestDetailAPIView.as_view(), name='api-backtest-detail'),

    # ── AI Research ───────────────────────────────────────────────────────────
    path('research/', StockResearchAPIView.as_view(), name='api-stock-research'),
]
