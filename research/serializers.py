from rest_framework import serializers
from research.models import ResearchRun


class ExamineRequestSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=50, required=True)
    mode = serializers.ChoiceField(choices=['INTRADAY', 'LONG_TERM', 'GENERAL'], default='INTRADAY')
    force_refresh = serializers.BooleanField(default=False)


class ResearchRunDetailSerializer(serializers.ModelSerializer):
    mode = serializers.CharField(source='research_mode')
    output = serializers.JSONField(source='research_output')
    basis = serializers.SerializerMethodField()

    class Meta:
        model = ResearchRun
        fields = [
            'id',
            'symbol',
            'mode',
            'status',
            'started_at',
            'completed_at',
            'evidence_hash',
            'output',
            'basis',
            'model_name',
            'provider',
            'tokens_used',
            'duration_ms',
            'error_message',
            'error_category'
        ]

    def get_basis(self, obj: ResearchRun):
        snap_opp = (obj.evidence_snapshot or {}).get("opportunity", {})
        snap_mkt = (obj.evidence_snapshot or {}).get("market_context", {})
        snap_sec = (obj.evidence_snapshot or {}).get("sector_context", {})
        return {
            "score": obj.opportunity_score_at_research or snap_opp.get("score"),
            "rank": snap_opp.get("rank"),
            "state": obj.opportunity_state_at_research or snap_opp.get("state"),
            "market_regime": snap_mkt.get("regime"),
            "sector_name": snap_sec.get("sector"),
            "sector_rank": snap_sec.get("rank"),
            "timestamp": obj.started_at.isoformat() if obj.started_at else None
        }


class ResearchExamineResponseSerializer(serializers.Serializer):
    reused = serializers.BooleanField()
    llm_calls_made = serializers.IntegerField()
    research = ResearchRunDetailSerializer()
    delta = serializers.JSONField(required=False, allow_null=True)
