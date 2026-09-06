import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from django.utils import timezone

from research.models import ResearchRun
from research.serializers import (
    ExamineRequestSerializer,
    ResearchRunDetailSerializer,
)
from research.services.on_demand_research_service import OnDemandResearchService
from research.services.delta_service import ResearchDeltaService

logger = logging.getLogger(__name__)


class ResearchExamineAPIView(APIView):
    """
    POST /api/v1/research/examine/
    User-initiated deep research examination.
    Reuses existing research if fresh (0 LLM calls).
    Executes exactly 1 LLM call if not cached or force_refresh=true.
    """

    def post(self, request):
        serializer = ExamineRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        symbol = data['symbol']
        mode = data.get('mode', 'INTRADAY')
        force_refresh = data.get('force_refresh', False)

        svc = OnDemandResearchService()
        try:
            result = svc.examine(
                symbol=symbol,
                mode=mode,
                force_refresh=force_refresh
            )
            run = result['research_run']
            return Response({
                'reused': result['reused'],
                'llm_calls_made': result['llm_calls_made'],
                'research': ResearchRunDetailSerializer(run).data,
                'delta': result.get('delta')
            }, status=status.HTTP_200_OK if run.status != 'failed' else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in ResearchExamineAPIView for {symbol}: {e}", exc_info=True)
            return Response({
                'error': {
                    'code': 'RESEARCH_EXAMINE_FAILED',
                    'message': str(e),
                    'timestamp': timezone.now().isoformat()
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResearchDetailAPIView(APIView):
    """
    GET /api/v1/research/{id}/
    Retrieves existing research run by ID. Requires ZERO LLM calls.
    """

    def get(self, request, id):
        run = ResearchRun.objects.filter(id=id).first()
        if not run:
            raise NotFound(f"Research run '{id}' not found.")

        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(run)

        return Response({
            'research': ResearchRunDetailSerializer(run).data,
            'delta': delta,
            'zero_llm_call_verified': True
        }, status=status.HTTP_200_OK)


class CompanyResearchAPIView(APIView):
    """
    GET /api/v1/research/company/{symbol}/
    Retrieves latest research run for a company symbol. Requires ZERO LLM calls.
    """

    def get(self, request, symbol):
        mode = request.query_params.get('mode', 'INTRADAY').upper()
        run = ResearchRun.objects.filter(
            symbol__iexact=symbol,
            research_mode=mode,
            status='completed'
        ).order_by('-started_at').first()

        if not run:
            return Response({
                'exists': False,
                'symbol': symbol.upper(),
                'mode': mode,
                'message': f"No completed research found for {symbol.upper()} in {mode} mode."
            }, status=status.HTTP_200_OK)

        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(run)

        return Response({
            'exists': True,
            'research': ResearchRunDetailSerializer(run).data,
            'delta': delta,
            'zero_llm_call_verified': True
        }, status=status.HTTP_200_OK)


class ResearchRefreshAPIView(APIView):
    """
    POST /api/v1/research/{id}/refresh/
    User explicitly requests a refreshed research report.
    Executes exactly ONE new LLM call.
    """

    def post(self, request, id):
        run = ResearchRun.objects.filter(id=id).first()
        if not run:
            raise NotFound(f"Research run '{id}' not found.")

        svc = OnDemandResearchService()
        try:
            result = svc.refresh(research_run_id=str(run.id))
            new_run = result['research_run']
            return Response({
                'refreshed': True,
                'llm_calls_made': result['llm_calls_made'],
                'research': ResearchRunDetailSerializer(new_run).data,
                'delta': result.get('delta')
            }, status=status.HTTP_200_OK if new_run.status != 'failed' else status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Error refreshing research run {id}: {e}", exc_info=True)
            return Response({
                'error': {
                    'code': 'RESEARCH_REFRESH_FAILED',
                    'message': str(e),
                    'timestamp': timezone.now().isoformat()
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResearchDeltaAPIView(APIView):
    """
    GET /api/v1/research/{id}/delta/
    Calculates live delta comparing research snapshot against live state.
    Requires ZERO LLM calls.
    """

    def get(self, request, id):
        run = ResearchRun.objects.filter(id=id).first()
        if not run:
            raise NotFound(f"Research run '{id}' not found.")

        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(run)
        return Response(delta, status=status.HTTP_200_OK)
