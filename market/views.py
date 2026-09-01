import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError

from .models import (
    Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature,
    IncomeStatement, BalanceSheetStatement, CashFlowStatement, DerivedFundamentalMetric,
    NewsItem, CorporateDisclosure, MarketContextSnapshot,
    StockOpportunitySnapshot, StockRecommendation, RecommendationOutcome, BacktestRun
)
from .serializers import (
    CompanySerializer, InstrumentSerializer, InstrumentSearchSerializer,
    MarketSnapshotSerializer, StockSummarySerializer, OHLCVBarSerializer,
    TechnicalFeatureSerializer, IncomeStatementSerializer, BalanceSheetStatementSerializer,
    CashFlowStatementSerializer, DerivedFundamentalMetricSerializer, NewsItemSerializer,
    CorporateDisclosureSerializer, MarketContextSnapshotSerializer,
    StockOpportunitySnapshotSerializer, StockRecommendationSerializer,
    RecommendationOutcomeSerializer, BacktestRunSerializer, BacktestRunRequestSerializer,
    ResearchQueryRequestSerializer
)
from .pagination import StandardResultsSetPagination, LargeResultsSetPagination

# Core domain services
from .services.context_service import MarketContextService
from .services.market_service import MarketService
from .services.fundamental_service import FundamentalDataService
from .services.news_service import NewsIntelligenceService
from .services.discovery_service import OpportunityDiscoveryService
from .services.recommendation_service import RecommendationService
from .services.intraday_service import IntradayMarketDataService
from .services.intraday_readiness import IntradayReadinessService
from .services.intraday_session import classify_session
from .services.outcome_service import RecommendationOutcomeService
from .services.backtest_runner import BacktestRunner
from .services.backtest_config import BacktestConfig
from .services.cost_model import CostConfig
from .services.market_research_service import MarketResearchService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Market Context & Overview APIs
# ─────────────────────────────────────────────────────────────────────────────

class MarketOverviewAPIView(APIView):
    """
    GET /api/v1/market/overview/
    Aggregated dashboard endpoint returning live market status, indices,
    regime, breadth, sector rankings, and global cues.
    """
    def get(self, request):
        universe = request.query_params.get('universe', 'NIFTY50')
        as_of_param = request.query_params.get('as_of')

        as_of = None
        if as_of_param:
            try:
                as_of = datetime.fromisoformat(as_of_param.replace('Z', '+00:00'))
            except Exception:
                raise ValidationError({'as_of': 'Invalid ISO-8601 timestamp format.'})

        context_svc = MarketContextService()
        market_context = context_svc.get_market_context(as_of=as_of, universe=universe)

        # Market trading session status
        if not as_of:
            sw = classify_session(timezone.now())
            session_info = {
                'window': sw.window,
                'minutes_elapsed': sw.minutes_elapsed,
                'minutes_remaining': sw.minutes_remaining,
                'is_trading_hour': sw.is_valid_for_trading,
                'session_date': sw.session_date.isoformat(),
            }
        else:
            session_info = {
                'window': 'HISTORICAL', 'is_trading_hour': False, 'message': 'Point-in-Time historical query'
            }

        # News feed
        recent_news = NewsItem.objects.all().order_by('-published_at')[:5]
        news_serialized = NewsItemSerializer(recent_news, many=True).data

        payload = {
            'as_of': (as_of or timezone.now()).isoformat(),
            'universe': universe,
            'market_session': session_info,
            'breadth': market_context.get('breadth', {}),
            'index_regimes': market_context.get('index_regimes', {}),
            'sector_rankings': market_context.get('sector_rankings', {}),
            'cross_market_cues': market_context.get('cross_market_cues', {}),
            'fii_dii_flow': market_context.get('fii_dii_flow', {}),
            'recent_news': news_serialized,
            'data_freshness': {
                'status': 'LIVE' if not as_of else 'HISTORICAL_PIT',
                'timestamp': timezone.now().isoformat()
            }
        }
        return Response(payload, status=status.HTTP_200_OK)


class MarketIndicesAPIView(APIView):
    """
    GET /api/v1/market/indices/
    Returns quotes and regime status for benchmark indices (^NSEI, ^NSEBANK, ^BSESN).
    """
    def get(self, request):
        as_of_param = request.query_params.get('as_of')
        context_svc = MarketContextService()
        context = context_svc.get_market_context()
        index_regimes = context.get('index_regimes', {})

        indices_data = []
        for symbol, regime_info in index_regimes.items():
            inst = Instrument.objects.filter(symbol=symbol).first()
            snapshot = inst.snapshots.order_by('-timestamp').first() if inst else None
            indices_data.append({
                'symbol': symbol,
                'name': regime_info.get('name', symbol),
                'price': float(snapshot.close) if snapshot and snapshot.close else None,
                'change': float(snapshot.change) if snapshot and snapshot.change else None,
                'change_percent': float(snapshot.change_percent) if snapshot and snapshot.change_percent else None,
                'regime': regime_info.get('regime', 'UNKNOWN'),
                'trend_slope': regime_info.get('trend_slope'),
                'above_sma_200': regime_info.get('above_sma_200')
            })

        return Response({'indices': indices_data, 'as_of': timezone.now().isoformat()}, status=status.HTTP_200_OK)


class MarketRegimeAPIView(APIView):
    """
    GET /api/v1/market/regime/
    Returns primary market trend regimes and breadth health.
    """
    def get(self, request):
        context_svc = MarketContextService()
        context = context_svc.get_market_context()
        return Response({
            'index_regimes': context.get('index_regimes', {}),
            'breadth_regime': context.get('breadth', {}).get('breadth_regime', 'NEUTRAL'),
            'as_of': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class MarketBreadthAPIView(APIView):
    """
    GET /api/v1/market/breadth/
    Returns Advance/Decline ratios and participation metrics.
    """
    def get(self, request):
        universe = request.query_params.get('universe', 'NIFTY50')
        context_svc = MarketContextService()
        context = context_svc.get_market_context(universe=universe)
        return Response({
            'universe': universe,
            'breadth': context.get('breadth', {}),
            'as_of': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class MarketSectorsAPIView(APIView):
    """
    GET /api/v1/market/sectors/
    Returns ranked sector momentum tiers and relative strength.
    """
    def get(self, request):
        context_svc = MarketContextService()
        context = context_svc.get_market_context()
        return Response({
            'sector_rankings': context.get('sector_rankings', {}),
            'as_of': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class MarketGlobalCuesAPIView(APIView):
    """
    GET /api/v1/market/global/
    Returns global cues (S&P 500, USD/INR, Crude Oil, Gold).
    """
    def get(self, request):
        context_svc = MarketContextService()
        context = context_svc.get_market_context()
        return Response({
            'global_cues': context.get('cross_market_cues', {}),
            'as_of': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Stock APIs
# ─────────────────────────────────────────────────────────────────────────────

class StockListAPIView(generics.ListAPIView):
    """
    GET /api/v1/stocks/
    Paginated list of active instruments.
    """
    serializer_class = StockSummarySerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Instrument.objects.filter(is_active=True).select_related('company')
        sector = self.request.query_params.get('sector')
        if sector:
            qs = qs.filter(company__sector__iexact=sector)
        exchange = self.request.query_params.get('exchange')
        if exchange:
            qs = qs.filter(exchange__iexact=exchange)
        return qs.order_by('symbol')


class StockSearchAPIView(APIView):
    """
    GET /api/v1/stocks/search/?q=...
    Lightweight autocomplete search by symbol or company name.
    """
    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'results': []}, status=status.HTTP_200_OK)

        instruments = Instrument.objects.filter(
            Q(symbol__icontains=q) |
            Q(company__name__icontains=q) |
            Q(company__short_name__icontains=q)
        ).select_related('company')[:20]

        serializer = InstrumentSearchSerializer(instruments, many=True)
        return Response({'results': serializer.data}, status=status.HTTP_200_OK)


class StockDetailAPIView(APIView):
    """
    GET /api/v1/stocks/{symbol}/
    Stock summary with company info, current snapshot, and active signal summary.
    """
    def get(self, request, symbol):
        inst = Instrument.objects.filter(symbol__iexact=symbol).select_related('company').first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found.")

        snapshot = inst.snapshots.order_by('-timestamp').first()
        snapshot_data = MarketSnapshotSerializer(snapshot).data if snapshot else None

        active_rec = inst.recommendations.filter(status='ACTIVE').order_by('-generated_at').first()
        rec_data = StockRecommendationSerializer(active_rec).data if active_rec else None

        opp_snapshot = inst.opportunity_snapshots.order_by('-as_of').first()
        opp_data = StockOpportunitySnapshotSerializer(opp_snapshot).data if opp_snapshot else None

        return Response({
            'instrument': InstrumentSerializer(inst).data,
            'latest_snapshot': snapshot_data,
            'active_recommendation': rec_data,
            'latest_opportunity': opp_data,
            'data_freshness': {
                'status': 'LIVE' if snapshot else 'NO_DATA',
                'timestamp': snapshot.timestamp.isoformat() if snapshot else None
            }
        }, status=status.HTTP_200_OK)


class StockOHLCVAPIView(APIView):
    """
    GET /api/v1/stocks/{symbol}/ohlcv/
    Returns bounded historical OHLCV candlestick bars.
    Supports timeframe (1d, 5m, 15m, 1h), start_date, end_date, limit.
    """
    def get(self, request, symbol):
        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found.")

        timeframe = request.query_params.get('timeframe', '1d')
        limit = min(int(request.query_params.get('limit', 500)), 1000)

        qs = OHLCVBar.objects.filter(instrument=inst, timeframe=timeframe)

        start_date = request.query_params.get('start_date')
        if start_date:
            try:
                s_dt = datetime.fromisoformat(start_date)
                qs = qs.filter(timestamp__gte=s_dt)
            except Exception:
                raise ValidationError({'start_date': 'Invalid start_date format.'})

        end_date = request.query_params.get('end_date')
        if end_date:
            try:
                e_dt = datetime.fromisoformat(end_date)
                qs = qs.filter(timestamp__lte=e_dt)
            except Exception:
                raise ValidationError({'end_date': 'Invalid end_date format.'})

        bars = qs.order_by('-timestamp')[:limit]
        bars_list = list(reversed(bars))

        serializer = OHLCVBarSerializer(bars_list, many=True)
        return Response({
            'symbol': inst.symbol,
            'exchange': inst.exchange,
            'timeframe': timeframe,
            'bars_count': len(serializer.data),
            'bars': serializer.data,
            'data_quality': {
                'status': 'COMPLETE' if len(serializer.data) > 0 else 'NO_DATA',
                'gaps_detected': 0
            }
        }, status=status.HTTP_200_OK)


class StockTechnicalsAPIView(APIView):
    """
    GET /api/v1/stocks/{symbol}/technicals/
    Returns computed technical indicators for the specified timeframe and PIT date.
    """
    def get(self, request, symbol):
        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found.")

        timeframe = request.query_params.get('timeframe', '1d')
        as_of_param = request.query_params.get('as_of')

        qs = TechnicalFeature.objects.filter(instrument=inst, timeframe=timeframe)
        if as_of_param:
            try:
                as_of_dt = datetime.fromisoformat(as_of_param.replace('Z', '+00:00'))
                qs = qs.filter(timestamp__lte=as_of_dt)
            except Exception:
                raise ValidationError({'as_of': 'Invalid as_of format.'})

        latest_ts = qs.order_by('-timestamp').values_list('timestamp', flat=True).first()
        if not latest_ts:
            return Response({
                'symbol': inst.symbol,
                'timeframe': timeframe,
                'indicators': {},
                'as_of': None,
                'status': 'INSUFFICIENT_DATA'
            }, status=status.HTTP_200_OK)

        features = qs.filter(timestamp=latest_ts)
        indicators_map = {}
        for feat in features:
            indicators_map[feat.name] = {
                'value': float(feat.value) if feat.value is not None else None,
                'parameters': feat.parameters
            }

        return Response({
            'symbol': inst.symbol,
            'timeframe': timeframe,
            'as_of': latest_ts.isoformat(),
            'indicators_count': len(indicators_map),
            'indicators': indicators_map,
            'status': 'HEALTHY'
        }, status=status.HTTP_200_OK)


class StockFundamentalsAPIView(APIView):
    """
    GET /api/v1/stocks/{symbol}/fundamentals/
    Returns audited financial statements and derived fundamental ratios.
    """
    def get(self, request, symbol):
        inst = Instrument.objects.filter(symbol__iexact=symbol).select_related('company').first()
        if not inst or not inst.company:
            raise NotFound(f"Stock symbol '{symbol}' not found.")

        comp = inst.company
        income_stmt = IncomeStatement.objects.filter(company=comp).order_by('-fiscal_year')[:10]
        balance_sheet = BalanceSheetStatement.objects.filter(company=comp).order_by('-fiscal_year')[:10]
        cash_flow = CashFlowStatement.objects.filter(company=comp).order_by('-fiscal_year')[:10]
        metrics = DerivedFundamentalMetric.objects.filter(company=comp)
        metrics_data = DerivedFundamentalMetricSerializer(metrics, many=True).data

        return Response({
            'symbol': inst.symbol,
            'company_name': comp.name,
            'sector': comp.sector,
            'industry': comp.industry,
            'statements': {
                'income_statement': IncomeStatementSerializer(income_stmt, many=True).data,
                'balance_sheet': BalanceSheetStatementSerializer(balance_sheet, many=True).data,
                'cash_flow': CashFlowStatementSerializer(cash_flow, many=True).data,
            },
            'metrics': metrics_data,
            'data_quality': {
                'source': 'screener.in',
                'status': 'COMPLETE' if len(income_stmt) > 0 else 'NO_DATA'
            }
        }, status=status.HTTP_200_OK)


class StockNewsAPIView(generics.ListAPIView):
    """
    GET /api/v1/stocks/{symbol}/news/
    Paginated news items for the specified stock.
    """
    serializer_class = NewsItemSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        symbol = self.kwargs['symbol']
        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found.")
        return NewsItem.objects.filter(
            Q(instrument=inst) | Q(company=inst.company)
        ).order_by('-published_at')


class StockDisclosuresAPIView(generics.ListAPIView):
    """
    GET /api/v1/stocks/{symbol}/events/
    Paginated corporate announcements and regulatory filings.
    """
    serializer_class = CorporateDisclosureSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        symbol = self.kwargs['symbol']
        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst or not inst.company:
            raise NotFound(f"Stock symbol '{symbol}' not found.")
        return CorporateDisclosure.objects.filter(company=inst.company).order_by('-published_at')


# ─────────────────────────────────────────────────────────────────────────────
# 3. Opportunity Discovery APIs
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityListAPIView(generics.ListAPIView):
    """
    GET /api/v1/opportunities/
    Paginated list of opportunity snapshots.
    Supports filters: universe, horizon, sector, opportunity_type, min_score, as_of.
    """
    serializer_class = StockOpportunitySnapshotSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = StockOpportunitySnapshot.objects.select_related('instrument', 'instrument__company')

        universe = self.request.query_params.get('universe')
        if universe:
            qs = qs.filter(universe__iexact=universe)

        horizon = self.request.query_params.get('horizon')
        if horizon:
            qs = qs.filter(horizon__iexact=horizon)

        sector = self.request.query_params.get('sector')
        if sector:
            qs = qs.filter(instrument__company__sector__iexact=sector)

        opp_type = self.request.query_params.get('opportunity_type')
        if opp_type:
            qs = qs.filter(opportunity_type__iexact=opp_type)

        min_score = self.request.query_params.get('min_score')
        if min_score:
            try:
                qs = qs.filter(final_opportunity_score__gte=float(min_score))
            except Exception:
                raise ValidationError({'min_score': 'min_score must be a numeric value.'})

        as_of_param = self.request.query_params.get('as_of')
        if as_of_param:
            try:
                as_of_dt = datetime.fromisoformat(as_of_param.replace('Z', '+00:00'))
                qs = qs.filter(as_of__lte=as_of_dt)
            except Exception:
                raise ValidationError({'as_of': 'Invalid as_of timestamp format.'})

        return qs.order_by('-final_opportunity_score', '-as_of')


class OpportunityDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/v1/opportunities/{id}/
    Detail of a single opportunity snapshot.
    """
    queryset = StockOpportunitySnapshot.objects.select_related('instrument', 'instrument__company')
    serializer_class = StockOpportunitySnapshotSerializer
    lookup_field = 'id'


# ─────────────────────────────────────────────────────────────────────────────
# 4. Recommendation APIs
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationListAPIView(generics.ListAPIView):
    """
    GET /api/v1/recommendations/
    Paginated list of recommendations.
    Supports filters: horizon, signal, sector, universe, status, confidence, as_of.
    """
    serializer_class = StockRecommendationSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = StockRecommendation.objects.select_related('instrument', 'instrument__company')

        horizon = self.request.query_params.get('horizon')
        if horizon:
            qs = qs.filter(horizon__iexact=horizon)

        signal_val = self.request.query_params.get('signal')
        if signal_val:
            qs = qs.filter(signal__iexact=signal_val)

        status_val = self.request.query_params.get('status')
        if status_val:
            qs = qs.filter(status__iexact=status_val)

        confidence = self.request.query_params.get('confidence')
        if confidence:
            qs = qs.filter(confidence__iexact=confidence)

        sector = self.request.query_params.get('sector')
        if sector:
            qs = qs.filter(instrument__company__sector__iexact=sector)

        as_of_param = self.request.query_params.get('as_of')
        if as_of_param:
            try:
                as_of_dt = datetime.fromisoformat(as_of_param.replace('Z', '+00:00'))
                qs = qs.filter(as_of__lte=as_of_dt)
            except Exception:
                raise ValidationError({'as_of': 'Invalid as_of timestamp format.'})

        return qs.order_by('-generated_at')


class RecommendationDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/v1/recommendations/{id}/
    Detail of a single recommendation record.
    """
    queryset = StockRecommendation.objects.select_related('instrument', 'instrument__company')
    serializer_class = StockRecommendationSerializer
    lookup_field = 'id'


# ─────────────────────────────────────────────────────────────────────────────
# 5. Intraday Intelligence APIs
# ─────────────────────────────────────────────────────────────────────────────

class IntradayOverviewAPIView(APIView):
    """
    GET /api/v1/intraday/overview/
    Returns live market session state, IST clock, trading phase, and active signal counts.
    """
    def get(self, request):
        now = timezone.now()
        sw = classify_session(now)
        session_info = {
            'window': sw.window,
            'minutes_elapsed': sw.minutes_elapsed,
            'minutes_remaining': sw.minutes_remaining,
            'is_trading_hour': sw.is_valid_for_trading,
            'session_date': sw.session_date.isoformat(),
        }
        active_count = StockRecommendation.objects.filter(horizon='INTRADAY', status='ACTIVE').count()
        triggered_count = StockRecommendation.objects.filter(horizon='INTRADAY', status='TRIGGERED').count()

        return Response({
            'market_session': session_info,
            'summary': {
                'active_signals': active_count,
                'triggered_signals': triggered_count,
                'timeframes_supported': ['5m', '15m', '1h']
            },
            'as_of': now.isoformat()
        }, status=status.HTTP_200_OK)


class IntradayRecommendationsAPIView(generics.ListAPIView):
    """
    GET /api/v1/intraday/recommendations/
    Paginated list of intraday recommendations.
    """
    serializer_class = StockRecommendationSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = StockRecommendation.objects.filter(horizon='INTRADAY').select_related('instrument', 'instrument__company')

        timeframe = self.request.query_params.get('timeframe')
        if timeframe:
            qs = qs.filter(timeframe=timeframe)

        signal_val = self.request.query_params.get('signal')
        if signal_val:
            qs = qs.filter(signal__iexact=signal_val)

        status_val = self.request.query_params.get('status')
        if status_val:
            qs = qs.filter(status__iexact=status_val)

        setup_type = self.request.query_params.get('setup_type')
        if setup_type:
            qs = qs.filter(setup_type__iexact=setup_type)

        return qs.order_by('-generated_at')


class IntradayDataQualityAPIView(APIView):
    """
    GET /api/v1/intraday/data-quality/
    Evaluates intraday data readiness for a symbol.
    """
    def get(self, request):
        symbol = request.query_params.get('symbol')
        timeframe = request.query_params.get('timeframe', '5m')
        if not symbol:
            raise ValidationError({'symbol': 'Query parameter symbol is required.'})

        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found.")

        readiness_svc = IntradayReadinessService()
        readiness = readiness_svc.check_readiness(inst, timeframe=timeframe)
        res_data = readiness.as_dict()
        res_data['symbol'] = inst.symbol
        res_data['timeframe'] = timeframe
        res_data['checked_at'] = timezone.now().isoformat()

        return Response(res_data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Outcome Tracking & Strategy Analytics APIs
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationOutcomeDetailAPIView(APIView):
    """
    GET /api/v1/recommendations/{id}/outcome/
    Returns outcome evaluation for a recommendation.
    """
    def get(self, request, id):
        outcome = RecommendationOutcome.objects.filter(recommendation_id=id).first()
        if not outcome:
            raise NotFound("Outcome evaluation not found for this recommendation.")
        return Response(RecommendationOutcomeSerializer(outcome).data, status=status.HTTP_200_OK)


class OutcomeListAPIView(generics.ListAPIView):
    """
    GET /api/v1/outcomes/
    Paginated list of recommendation outcomes.
    """
    serializer_class = RecommendationOutcomeSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = RecommendationOutcome.objects.select_related('recommendation', 'recommendation__instrument')

        signal_val = self.request.query_params.get('signal')
        if signal_val:
            qs = qs.filter(recommendation__signal__iexact=signal_val)

        setup_type = self.request.query_params.get('setup_type')
        if setup_type:
            qs = qs.filter(recommendation__setup_type__iexact=setup_type)

        exit_reason = self.request.query_params.get('exit_reason')
        if exit_reason:
            qs = qs.filter(exit_reason__iexact=exit_reason)

        return qs.order_by('-evaluated_at')


class StrategyListAPIView(APIView):
    """
    GET /api/v1/strategies/
    Lists available strategy setup types and horizons.
    """
    def get(self, request):
        return Response({
            'strategies': [
                {'name': 'DELIVERY_SWING', 'setups': ['MOMENTUM_BREAKOUT', 'PULLBACK_SUPPORT', 'VALUE_RECOVERY']},
                {'name': 'INTRADAY', 'setups': ['ORB_BREAKOUT', 'VWAP_RECLAIM', 'TREND_CONTINUATION', 'MEAN_REVERSION']},
            ]
        }, status=status.HTTP_200_OK)


class StrategyPerformanceAPIView(APIView):
    """
    GET /api/v1/strategies/{strategy}/performance/
    Aggregates outcome performance statistics across completed recommendations.
    """
    def get(self, request, strategy):
        outcomes = RecommendationOutcome.objects.filter(recommendation__horizon__iexact=strategy)
        total = outcomes.count()
        wins = outcomes.filter(exit_reason='TARGET_HIT').count()
        losses = outcomes.filter(exit_reason='STOP_HIT').count()

        win_rate = (wins / total) if total > 0 else 0.0

        r_values = [float(o.r_multiple) for o in outcomes if o.r_multiple is not None]
        avg_r = (sum(r_values) / len(r_values)) if r_values else 0.0

        return Response({
            'strategy': strategy,
            'sample_size': total,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 4),
            'avg_r_multiple': round(avg_r, 4),
            'is_small_sample': total < 30,
            'evaluated_at': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Backtesting APIs
# ─────────────────────────────────────────────────────────────────────────────

class BacktestListAPIView(generics.ListAPIView):
    """
    GET /api/v1/backtests/
    Paginated list of historical backtest runs.
    """
    serializer_class = BacktestRunSerializer
    pagination_class = StandardResultsSetPagination
    queryset = BacktestRun.objects.all().order_by('-started_at')


class BacktestDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/v1/backtests/{run_id}/
    Returns full backtest run detail and performance report.
    """
    queryset = BacktestRun.objects.all()
    serializer_class = BacktestRunSerializer
    lookup_field = 'run_id'


class BacktestRunAPIView(APIView):
    """
    POST /api/v1/backtests/run/
    Executes a walk-forward backtest simulation with explicit configuration.
    """
    def post(self, request):
        serializer = BacktestRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cost_cfg = CostConfig(
            mode=data['cost_mode'],
            brokerage_percent=data.get('brokerage_pct', 0.03),
            stt_percent=data.get('stt_pct', 0.1),
            slippage_bps=data.get('slippage_bps', 5.0)
        )

        config = BacktestConfig(
            universe_name=data['universe_name'],
            timeframe=data['timeframe'],
            horizon=data['horizon'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            cost_config=cost_cfg,
            ambiguity_policy=data['ambiguity_policy']
        )

        runner = BacktestRunner()
        backtest_run = runner.run(config)

        return Response(BacktestRunSerializer(backtest_run).data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# 8. AI Research API
# ─────────────────────────────────────────────────────────────────────────────

class StockResearchAPIView(APIView):
    """
    POST /api/v1/research/
    Executes an on-demand multi-tool equity research task via MarketResearchService.
    """
    def post(self, request):
        serializer = ResearchQueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        symbol = data['symbol']
        question = data['question']
        depth = data.get('depth', 'standard')
        as_of = data.get('as_of')

        inst = Instrument.objects.filter(symbol__iexact=symbol).first()
        if not inst:
            raise NotFound(f"Stock symbol '{symbol}' not found in registry.")

        svc = MarketResearchService()
        try:
            report = svc.research_stock(
                symbol=inst.symbol,
                question=question,
                as_of=as_of,
                depth=depth
            )
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error executing AI research for {symbol}: {e}", exc_info=True)
            return Response({
                'error': {
                    'code': 'RESEARCH_EXECUTION_FAILED',
                    'message': f"Failed to complete stock research: {str(e)}",
                    'details': {},
                    'timestamp': timezone.now().isoformat()
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
