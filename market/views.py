import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional

from django.db.models import Q
from django.utils import timezone
from django.views import View
from django.http import HttpResponseRedirect
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError

from .models import (
    Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature,
    IncomeStatement, BalanceSheetStatement, CashFlowStatement, DerivedFundamentalMetric,
    NewsItem, CorporateDisclosure, MarketContextSnapshot,
    StockOpportunitySnapshot, StockRecommendation, RecommendationOutcome, BacktestRun,
    IntradayOpportunitySnapshot
)
from .serializers import (
    CompanySerializer, InstrumentSerializer, InstrumentSearchSerializer,
    MarketSnapshotSerializer, StockSummarySerializer, OHLCVBarSerializer,
    TechnicalFeatureSerializer, IncomeStatementSerializer, BalanceSheetStatementSerializer,
    CashFlowStatementSerializer, DerivedFundamentalMetricSerializer, NewsItemSerializer,
    CorporateDisclosureSerializer, MarketContextSnapshotSerializer,
    StockOpportunitySnapshotSerializer, StockRecommendationSerializer,
    RecommendationOutcomeSerializer, BacktestRunSerializer, BacktestRunRequestSerializer,
    ResearchQueryRequestSerializer, IntradayOpportunitySnapshotSerializer
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


# ==============================================================================
# 9. Kite Authentication Lifecycle & Intraday Data Health Views (Phase 17B)
# ==============================================================================

class KiteLoginAPIView(APIView):
    """
    GET /api/v1/kite/auth/login/
    Generates Zerodha Kite Connect login URL.
    Query param ?redirect=true triggers HTTP 302 redirect directly to Zerodha.
    """
    def get(self, request):
        from market.services.kite_auth import KiteCredentialService
        try:
            login_url = KiteCredentialService.generate_login_url()
            if request.GET.get('redirect', '').lower() in ('true', '1', 'yes'):
                return HttpResponseRedirect(login_url)
            return Response({"login_url": login_url}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class KiteCallbackView(View):
    """
    GET /kite/callback/ (and /api/v1/kite/callback/)
    Handles Zerodha's redirect callback with request_token.
    Performs server-side token exchange and securely stores the access_token.
    Redirects back to frontend without exposing tokens.
    """
    def get(self, request):
        import urllib.parse
        from django.http import HttpResponseRedirect
        from django.conf import settings
        from market.services.kite_auth import KiteCredentialService

        frontend_base = getattr(settings, "KITE_FRONTEND_REDIRECT_URL", "http://localhost:5173/intraday")

        # Handle user cancellation or errors from Zerodha
        req_status = request.GET.get("status")
        req_error = request.GET.get("message") or request.GET.get("error")
        if req_status == "cancelled" or req_error:
            logger.warning(f"Kite login cancelled or errored: status={req_status}, error={req_error}")
            target = f"{frontend_base}?kite_auth=cancelled&msg={urllib.parse.quote(req_error or 'Authentication cancelled')}"
            return HttpResponseRedirect(target)

        request_token = request.GET.get("request_token")
        if not request_token:
            logger.error("Kite callback received without request_token.")
            target = f"{frontend_base}?kite_auth=error&msg=Missing+request_token"
            return HttpResponseRedirect(target)

        try:
            result = KiteCredentialService.exchange_request_token(request_token)
            logger.info(f"Kite authentication successful for user {result.get('user_id')}.")
            target = f"{frontend_base}?kite_auth=success&user={urllib.parse.quote(result.get('user_id') or '')}"
            return HttpResponseRedirect(target)
        except Exception as e:
            logger.error(f"Kite token exchange error: {e}")
            target = f"{frontend_base}?kite_auth=error&msg={urllib.parse.quote(str(e))}"
            return HttpResponseRedirect(target)


class KiteStatusAPIView(APIView):
    """
    GET /api/v1/kite/status/
    Returns safe, non-sensitive Kite connection & authentication lifecycle status.
    Never exposes API secret, access_token, or request_token.
    """
    def get(self, request):
        from market.services.kite_auth import KiteCredentialService
        status_data = KiteCredentialService.get_safe_status()
        return Response(status_data, status=status.HTTP_200_OK)


class KiteDisconnectAPIView(APIView):
    """
    POST /api/v1/kite/auth/disconnect/
    Clears local Kite session and marks connection AUTHENTICATION_REQUIRED.
    """
    def post(self, request):
        from market.services.kite_auth import KiteCredentialService
        success = KiteCredentialService.disconnect()
        return Response({
            "success": success,
            "message": "Kite session disconnected successfully."
        }, status=status.HTTP_200_OK)


class KiteDataHealthAPIView(APIView):
    """
    GET /api/v1/kite/data-health/
    Returns real-time data ingestion health:
    - Provider connection status
    - Current trading session (PRE_MARKET, REGULAR, POST_MARKET, CLOSED)
    - Data status (LIVE, WAITING_FOR_DATA, MARKET CLOSED)
    - Latest tick details and snapshot timestamp
    - Subscribed instrument count
    """
    def get(self, request):
        from django.core.cache import cache
        from market.services.kite_auth import KiteCredentialService
        from market.services.trading_session import TradingSessionService
        from market.models import MarketSnapshot

        auth_status = KiteCredentialService.get_safe_status()
        is_authenticated = auth_status.get("authenticated", False)
        
        session = TradingSessionService.get_current_session()
        is_market_open = TradingSessionService.is_market_open()

        # Check last tick from cache
        last_tick = cache.get("kite_last_tick")

        # Check last market snapshot from DB
        latest_snapshot = MarketSnapshot.objects.order_by("-timestamp").first()
        last_snapshot_time = latest_snapshot.timestamp.isoformat() if latest_snapshot else None

        if not is_authenticated:
            data_status = "DISCONNECTED"
        elif not is_market_open:
            data_status = "MARKET CLOSED"
        elif last_tick:
            data_status = "LIVE"
        else:
            data_status = "WAITING_FOR_DATA"

        return Response({
            "provider": "kite",
            "authenticated": is_authenticated,
            "connection_status": auth_status.get("status"),
            "market_session": session.value,
            "is_market_open": is_market_open,
            "data_status": data_status,
            "subscribed_instruments_count": 52,
            "last_tick": last_tick,
            "last_snapshot_timestamp": last_snapshot_time,
            "as_of": timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 10. Phase 17C — Intraday Market Context & Signal Foundation Views
# ==============================================================================

class IntradayMarketContextAPIView(APIView):
    """
    GET /api/v1/intraday/market-context/
    Returns unified real-time intraday market context:
    - Market direction & regime classification with explainable reasons
    - Breadth (Advances/Declines, Above/Below VWAP %, A/D ratio)
    - NIFTY 50 and BANKNIFTY live states
    - Ranked sector strengths and leaders/laggards
    - Data freshness tier (FRESH, STALE, UNAVAILABLE)
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        context = mgr.compute_current_context()

        # Remove heavy stocks array from the high-level market context endpoint
        response_data = {
            "as_of": context["as_of"],
            "freshness": context["freshness"],
            "freshness_age_seconds": context["freshness_age_seconds"],
            "is_fresh": context["is_fresh"],
            "market_direction": context["market_direction"],
            "market_regime": context["market_regime"],
            "regime_confidence": context["regime_confidence"],
            "regime_reasons": context["regime_reasons"],
            "index_confirmation": context["index_confirmation"],
            "market_volatility": context["market_volatility"],
            "nifty": context["nifty"],
            "banknifty": context["banknifty"],
            "breadth": context["breadth"],
            "sectors": context["sectors"],
            "sector_leader": context["sector_leader"],
            "sector_laggard": context["sector_laggard"],
        }
        return Response(response_data, status=status.HTTP_200_OK)


class IntradayStocksAPIView(APIView):
    """
    GET /api/v1/intraday/stocks/
    Filterable and sortable list of NIFTY 50 stock-level intraday contexts:
    Price, VWAP, Distance from VWAP, Relative Strength vs NIFTY & Sector,
    Volume Confirmation, Opening Range state, and Foundation component scores.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        context = mgr.compute_current_context()
        stocks = list(context.get("stocks", []))

        # Query parameter filters
        sector_filter = request.GET.get("sector")
        if sector_filter:
            stocks = [s for s in stocks if s.get("sector", "").lower() == sector_filter.lower()]

        vol_filter = request.GET.get("volume_confirmation")
        if vol_filter:
            stocks = [s for s in stocks if s.get("volume_confirmation", "").upper() == vol_filter.upper()]

        search_filter = request.GET.get("search")
        if search_filter:
            q = search_filter.strip().lower()
            stocks = [s for s in stocks if q in s.get("symbol", "").lower()]

        # Sorting
        sort_by = request.GET.get("sort_by", "change_pct")
        order = request.GET.get("order", "desc").lower()
        reverse = (order == "desc")

        def sort_key(st):
            val = st.get(sort_by)
            if val is None:
                return float("-inf") if reverse else float("inf")
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val)

        stocks.sort(key=sort_key, reverse=reverse)

        # Convert Decimal values for JSON response
        serializable_stocks = []
        for st in stocks:
            item = {}
            for k, v in st.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)
                else:
                    item[k] = v
            serializable_stocks.append(item)

        return Response({
            "as_of": context["as_of"],
            "freshness": context["freshness"],
            "count": len(serializable_stocks),
            "stocks": serializable_stocks,
        }, status=status.HTTP_200_OK)


class IntradayStockDetailAPIView(APIView):
    """
    GET /api/v1/intraday/stocks/<symbol>/
    Returns detailed intraday context and latest 1m/5m bars for a single constituent.
    """
    def get(self, request, symbol):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        context = mgr.compute_current_context()

        stock_item = None
        for s in context.get("stocks", []):
            if s.get("symbol", "").upper() == symbol.upper():
                stock_item = s
                break

        if not stock_item:
            raise NotFound(f"Symbol '{symbol}' not found in active NIFTY 50 intraday universe.")

        # Serialize
        serialized = {}
        for k, v in stock_item.items():
            serialized[k] = float(v) if isinstance(v, Decimal) else v

        # Add latest 1m bar from aggregator if available
        current_1m = mgr.aggregator.get_current_bar(symbol.upper(), "1m")
        serialized["current_1m_bar"] = current_1m.to_dict() if current_1m else None

        current_5m = mgr.aggregator.get_current_bar(symbol.upper(), "5m")
        serialized["current_5m_bar"] = current_5m.to_dict() if current_5m else None

        return Response(serialized, status=status.HTTP_200_OK)


class IntradaySectorsAPIView(APIView):
    """
    GET /api/v1/intraday/sectors/
    Ranked list of NIFTY 50 sectors by equal-weighted average return,
    breadth, above-VWAP percentage, and relative strength vs NIFTY.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        context = mgr.compute_current_context()

        serializable_sectors = []
        for sec in context.get("sectors", []):
            item = {}
            for k, v in sec.items():
                item[k] = float(v) if isinstance(v, Decimal) else v
            serializable_sectors.append(item)

        return Response({
            "as_of": context["as_of"],
            "freshness": context["freshness"],
            "sector_leader": context["sector_leader"],
            "sector_laggard": context["sector_laggard"],
            "count": len(serializable_sectors),
            "sectors": serializable_sectors,
        }, status=status.HTTP_200_OK)


class IntradayIndicesAPIView(APIView):
    """
    GET /api/v1/intraday/indices/
    Head-to-head comparison of NIFTY 50 and BANKNIFTY:
    Returns, VWAP alignment, momentum, day range, and index confirmation state.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        context = mgr.compute_current_context()

        return Response({
            "as_of": context["as_of"],
            "freshness": context["freshness"],
            "index_confirmation": context["index_confirmation"],
            "nifty": context["nifty"],
            "banknifty": context["banknifty"],
        }, status=status.HTTP_200_OK)


class IntradayDataHealthAPIView(APIView):
    """
    GET /api/v1/intraday/data-health/
    Detailed telemetry on intraday data layer health:
    Feed freshness, active vs missing NIFTY 50 constituents,
    suspicious timestamps count, and aggregation statistics.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        from market.services.kite_auth import KiteCredentialService
        from market.services.trading_session import TradingSessionService

        mgr = IntradayStateManager()
        freshness_info = mgr.get_freshness_status()
        auth_status = KiteCredentialService.get_safe_status()
        session = TradingSessionService.get_current_session()

        # Check universe coverage (memory with Redis cache fallback for multi-process deployments)
        total_universe = 50
        active_stocks = len(mgr._stock_states)
        from django.core.cache import cache
        if active_stocks == 0:
            from market.models import Instrument
            symbols = list(Instrument.objects.filter(
                universe_memberships__universe__name="NIFTY50",
                universe_memberships__is_active=True
            ).values_list("symbol", flat=True))
            stock_keys = [f"stock_state:{s}" for s in symbols]
            cached_states = cache.get_many(stock_keys)
            active_stocks = len(cached_states)
            if active_stocks < len(symbols):
                # Fallback check on live_tick keys for any not in stock_state
                missing_symbols = [s for s in symbols if f"stock_state:{s}" not in cached_states]
                tick_keys = [f"live_tick:{s}" for s in missing_symbols]
                active_stocks += len(cache.get_many(tick_keys))
        missing_count = max(0, total_universe - active_stocks)

        nifty_active = ("NIFTY" in mgr._index_states) or bool(cache.get("index_state:NIFTY") or cache.get("live_tick:^NSEI"))
        banknifty_active = ("BANKNIFTY" in mgr._index_states) or bool(cache.get("index_state:BANKNIFTY") or cache.get("live_tick:^NSEBANK"))

        active_1m = len([k for k in mgr.aggregator._current_bars.keys() if k[1] == "1m"])
        active_5m = len([k for k in mgr.aggregator._current_bars.keys() if k[1] == "5m"])
        active_15m = len([k for k in mgr.aggregator._current_bars.keys() if k[1] == "15m"])
        if active_1m == 0:
            from market.models import OHLCVBar
            today = timezone.now().date()
            active_1m = OHLCVBar.objects.filter(timestamp__date=today, timeframe="1m").values("instrument_id").distinct().count()
            active_5m = OHLCVBar.objects.filter(timestamp__date=today, timeframe="5m").values("instrument_id").distinct().count()
            active_15m = OHLCVBar.objects.filter(timestamp__date=today, timeframe="15m").values("instrument_id").distinct().count()

        return Response({
            "as_of": timezone.now().isoformat(),
            "market_session": session.value,
            "is_market_open": TradingSessionService.is_market_open(),
            "kite_authenticated": auth_status.get("authenticated", False),
            "kite_status": auth_status.get("status"),
            "freshness": freshness_info["freshness"],
            "freshness_age_seconds": freshness_info["age_seconds"],
            "last_tick_at": freshness_info["last_tick_at"],
            "universe_coverage": {
                "total_constituents": total_universe,
                "active_streaming": active_stocks,
                "missing": missing_count,
                "coverage_pct": round((active_stocks / total_universe) * 100.0, 1) if total_universe > 0 else 0.0,
            },
            "indices_active": {
                "nifty": nifty_active,
                "banknifty": banknifty_active,
            },
            "aggregation": {
                "active_1m_bars": active_1m,
                "active_5m_bars": active_5m,
                "active_15m_bars": active_15m,
            },
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 11. Intraday Opportunity Engine Views (Phase 17D)
# ==============================================================================

class IntradayOpportunitiesAPIView(APIView):
    """
    GET /api/v1/intraday/opportunities/
    Returns ranked, explainable intraday opportunities across the NIFTY 50 universe.
    Supports filters: limit, sector, opportunity_type, state, min_score, mode.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()

        limit = int(request.GET.get('limit', 10))
        sector = request.GET.get('sector')
        opp_type = request.GET.get('opportunity_type')
        state_filter = request.GET.get('state')
        min_score = request.GET.get('min_score')
        min_score_val = float(min_score) if min_score else None
        mode = request.GET.get('mode', 'RAW_RANKING').upper()
        if mode not in ('RAW_RANKING', 'SECTOR_DIVERSIFIED'):
            mode = 'RAW_RANKING'

        result = mgr.compute_current_opportunities(
            mode=mode,
            limit=limit,
            sector_filter=sector,
            opportunity_type_filter=opp_type,
            state_filter=state_filter,
            min_score=min_score_val,
        )

        return Response(result, status=status.HTTP_200_OK)


class IntradayOpportunityDetailAPIView(APIView):
    """
    GET /api/v1/intraday/opportunities/<str:symbol>/
    Returns single-stock opportunity evaluation including 8-dimensional scores,
    supporting factors, contradicting factors, warnings, and invalidation context.
    """
    def get(self, request, symbol: str):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        sym_clean = symbol.strip().upper()

        result = mgr.compute_current_opportunities(limit=50)
        matching = next((o for o in result.get("all_eligible_opportunities", []) if o.get("symbol") == sym_clean), None)

        if not matching:
            # Check if excluded
            excluded = next((e for e in result.get("excluded_candidates", []) if e.get("symbol") == sym_clean), None)
            if excluded:
                return Response({
                    "symbol": sym_clean,
                    "eligible": False,
                    "exclusion_reason": excluded.get("exclusion_reason"),
                    "market_context": result.get("market_context"),
                }, status=status.HTTP_200_OK)

            # Check database for latest persisted snapshot
            db_snap = IntradayOpportunitySnapshot.objects.filter(symbol=sym_clean).order_by('-timestamp').first()
            if db_snap:
                serializer = IntradayOpportunitySnapshotSerializer(db_snap)
                return Response({
                    "symbol": sym_clean,
                    "eligible": True,
                    "opportunity": serializer.data,
                    "source": "persisted_snapshot"
                }, status=status.HTTP_200_OK)

            raise NotFound(f"No active opportunity context found for '{sym_clean}'.")

        return Response({
            "symbol": sym_clean,
            "eligible": True,
            "opportunity": matching,
            "market_context": result.get("market_context"),
        }, status=status.HTTP_200_OK)


class IntradayOpportunityHistoryAPIView(APIView):
    """
    GET /api/v1/intraday/opportunities/<str:symbol>/history/
    Returns historical opportunity snapshots for that symbol to observe score
    transitions and lifecycle changes.
    """
    def get(self, request, symbol: str):
        sym_clean = symbol.strip().upper()
        limit = int(request.GET.get('limit', 20))
        snapshots = IntradayOpportunitySnapshot.objects.filter(symbol=sym_clean).order_by('-timestamp')[:limit]
        serializer = IntradayOpportunitySnapshotSerializer(snapshots, many=True)
        return Response({
            "symbol": sym_clean,
            "count": len(snapshots),
            "history": serializer.data,
        }, status=status.HTTP_200_OK)


class IntradayTopOpportunitiesAPIView(APIView):
    """
    GET /api/v1/intraday/opportunities/top/
    Lightweight endpoint returning top 5/10/20 opportunities for dashboard cards.
    """
    def get(self, request):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        limit = min(20, int(request.GET.get('limit', 5)))

        result = mgr.compute_current_opportunities(limit=limit)
        return Response({
            "timestamp": result["timestamp"],
            "market_regime": result["market_context"]["regime"],
            "breadth_state": result["market_context"]["breadth_state"],
            "top_opportunities": result["opportunities"],
        }, status=status.HTTP_200_OK)
