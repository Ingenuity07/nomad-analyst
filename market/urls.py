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
    StockResearchAPIView,
    # Kite Authentication & Intraday Data Layer (Phase 17B)
    KiteLoginAPIView, KiteCallbackView, KiteStatusAPIView,
    KiteDisconnectAPIView, KiteDataHealthAPIView,
    # Phase 17C — Intraday Market Context & Signal Foundation
    IntradayMarketContextAPIView, IntradayStocksAPIView, IntradayStockDetailAPIView,
    IntradaySectorsAPIView, IntradayIndicesAPIView, IntradayDataHealthAPIView,
    # Phase 17D — Intraday Opportunity Engine
    IntradayOpportunitiesAPIView, IntradayOpportunityDetailAPIView,
    IntradayOpportunityHistoryAPIView, IntradayTopOpportunitiesAPIView,
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

    # ── AI Research & Phase 17E On-Demand Research Engine ─────────────────────
    path('research/', StockResearchAPIView.as_view(), name='api-stock-research'),
    path('research/examine/', __import__('research.views', fromlist=['ResearchExamineAPIView']).ResearchExamineAPIView.as_view(), name='api-research-examine'),
    path('research/<uuid:id>/', __import__('research.views', fromlist=['ResearchDetailAPIView']).ResearchDetailAPIView.as_view(), name='api-research-detail'),
    path('research/company/<str:symbol>/', __import__('research.views', fromlist=['CompanyResearchAPIView']).CompanyResearchAPIView.as_view(), name='api-research-company'),
    path('research/<uuid:id>/refresh/', __import__('research.views', fromlist=['ResearchRefreshAPIView']).ResearchRefreshAPIView.as_view(), name='api-research-refresh'),
    path('research/<uuid:id>/delta/', __import__('research.views', fromlist=['ResearchDeltaAPIView']).ResearchDeltaAPIView.as_view(), name='api-research-delta'),

    # ── Kite Connect Authentication & Data Health (Phase 17B) ────────────────
    path('kite/auth/login/', KiteLoginAPIView.as_view(), name='api-kite-login'),
    path('kite/callback/', KiteCallbackView.as_view(), name='api-kite-callback'),
    path('kite/status/', KiteStatusAPIView.as_view(), name='api-kite-status'),
    path('kite/auth/disconnect/', KiteDisconnectAPIView.as_view(), name='api-kite-disconnect'),
    path('kite/data-health/', KiteDataHealthAPIView.as_view(), name='api-kite-data-health'),

    # ── Phase 17C — Intraday Market Context & Signal Foundation ─────────────
    path('intraday/market-context/', IntradayMarketContextAPIView.as_view(), name='api-intraday-market-context'),
    path('intraday/stocks/', IntradayStocksAPIView.as_view(), name='api-intraday-stocks'),
    path('intraday/stocks/<str:symbol>/', IntradayStockDetailAPIView.as_view(), name='api-intraday-stock-detail'),
    path('intraday/sectors/', IntradaySectorsAPIView.as_view(), name='api-intraday-sectors'),
    path('intraday/indices/', IntradayIndicesAPIView.as_view(), name='api-intraday-indices'),
    path('intraday/data-health/', IntradayDataHealthAPIView.as_view(), name='api-intraday-data-health'),

    # ── Phase 17D — Intraday Opportunity Engine ─────────────────────────────
    path('intraday/opportunities/', IntradayOpportunitiesAPIView.as_view(), name='api-intraday-opportunities'),
    path('intraday/opportunities/top/', IntradayTopOpportunitiesAPIView.as_view(), name='api-intraday-opportunities-top'),
    path('intraday/opportunities/<str:symbol>/', IntradayOpportunityDetailAPIView.as_view(), name='api-intraday-opportunity-detail'),
    path('intraday/opportunities/<str:symbol>/history/', IntradayOpportunityHistoryAPIView.as_view(), name='api-intraday-opportunity-history'),
]
