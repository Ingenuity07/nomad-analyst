from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any

from .models import (
    Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature,
    IncomeStatement, BalanceSheetStatement, CashFlowStatement, DerivedFundamentalMetric,
    NewsItem, CorporateDisclosure, MarketContextSnapshot,
    StockOpportunitySnapshot, StockRecommendation, RecommendationOutcome, BacktestRun
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Company & Instrument Serializers
# ─────────────────────────────────────────────────────────────────────────────

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'legal_name', 'short_name', 'isin',
            'sector', 'industry', 'sub_industry', 'description',
            'website', 'is_active', 'created_at', 'updated_at'
        ]

class InstrumentSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Instrument
        fields = [
            'id', 'company', 'symbol', 'exchange', 'isin',
            'instrument_type', 'currency', 'lot_size', 'is_active',
            'created_at', 'updated_at'
        ]

class InstrumentSearchSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    sector = serializers.CharField(source='company.sector', read_only=True)
    industry = serializers.CharField(source='company.industry', read_only=True)

    class Meta:
        model = Instrument
        fields = [
            'id', 'symbol', 'exchange', 'instrument_type',
            'company_name', 'sector', 'industry'
        ]

class MarketSnapshotSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source='instrument.symbol', read_only=True)

    class Meta:
        model = MarketSnapshot
        fields = [
            'id', 'symbol', 'timestamp', 'open', 'high', 'low', 'close',
            'volume', 'previous_close', 'change', 'change_percent',
            'source', 'source_timestamp'
        ]

class StockSummarySerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    latest_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = Instrument
        fields = [
            'id', 'symbol', 'exchange', 'instrument_type', 'currency',
            'company', 'latest_snapshot'
        ]

    def get_latest_snapshot(self, obj):
        snapshot = obj.snapshots.order_by('-timestamp').first()
        if snapshot:
            return MarketSnapshotSerializer(snapshot).data
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 2. Historical Market Data & Technical Features
# ─────────────────────────────────────────────────────────────────────────────

class OHLCVBarSerializer(serializers.ModelSerializer):
    class Meta:
        model = OHLCVBar
        fields = ['timeframe', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'source']

class TechnicalFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicalFeature
        fields = ['timeframe', 'timestamp', 'name', 'parameters', 'param_key', 'value']

# ─────────────────────────────────────────────────────────────────────────────
# 3. Fundamentals & Financial Statements
# ─────────────────────────────────────────────────────────────────────────────

class IncomeStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeStatement
        fields = [
            'id', 'fiscal_year', 'period_type', 'period_string', 'period_start',
            'period_end', 'filing_date', 'revenue', 'expenses', 'ebitda',
            'ebit', 'depreciation', 'interest', 'pbt', 'tax', 'pat', 'eps'
        ]

class BalanceSheetStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSheetStatement
        fields = [
            'id', 'fiscal_year', 'period_type', 'period_string', 'period_start',
            'period_end', 'filing_date', 'equity_capital', 'reserves',
            'borrowings', 'other_liabilities', 'total_liabilities', 'fixed_assets',
            'cwip', 'investments', 'other_assets', 'total_assets'
        ]

class CashFlowStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashFlowStatement
        fields = [
            'id', 'fiscal_year', 'period_type', 'period_string', 'period_start',
            'period_end', 'filing_date', 'operating_cash_flow', 'investing_cash_flow',
            'financing_cash_flow', 'free_cash_flow'
        ]

class DerivedFundamentalMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivedFundamentalMetric
        fields = [
            'id', 'period_type', 'period_string', 'name', 'value', 'created_at'
        ]

# ─────────────────────────────────────────────────────────────────────────────
# 4. News & Corporate Disclosures
# ─────────────────────────────────────────────────────────────────────────────

class NewsItemSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True, default=None)
    symbol = serializers.CharField(source='instrument.symbol', read_only=True, default=None)

    class Meta:
        model = NewsItem
        fields = [
            'id', 'company_name', 'symbol', 'headline', 'summary',
            'source', 'source_id', 'url', 'published_at', 'event_type',
            'raw_metadata'
        ]

class CorporateDisclosureSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CorporateDisclosure
        fields = [
            'id', 'company_name', 'headline', 'category', 'source',
            'announcement_id', 'url', 'published_at', 'details'
        ]

# ─────────────────────────────────────────────────────────────────────────────
# 5. Market Context & Overview
# ─────────────────────────────────────────────────────────────────────────────

class MarketContextSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketContextSnapshot
        fields = [
            'id', 'as_of', 'universe', 'breadth', 'index_regimes',
            'fii_dii_flow', 'cross_market_cues', 'macro_events',
            'calculation_version', 'created_at'
        ]

# ─────────────────────────────────────────────────────────────────────────────
# 6. Opportunities & Recommendations
# ─────────────────────────────────────────────────────────────────────────────

class StockOpportunitySnapshotSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source='instrument.symbol', read_only=True)
    company_name = serializers.CharField(source='instrument.company.name', read_only=True)
    sector = serializers.CharField(source='instrument.company.sector', read_only=True)

    class Meta:
        model = StockOpportunitySnapshot
        fields = [
            'id', 'symbol', 'company_name', 'sector', 'as_of', 'universe',
            'horizon', 'opportunity_type', 'component_scores',
            'final_opportunity_score', 'supporting_features', 'risks',
            'data_quality', 'calculation_version', 'created_at'
        ]

class StockRecommendationSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source='instrument.symbol', read_only=True)
    company_name = serializers.CharField(source='instrument.company.name', read_only=True)
    sector = serializers.CharField(source='instrument.company.sector', read_only=True)

    class Meta:
        model = StockRecommendation
        fields = [
            'id', 'symbol', 'company_name', 'sector', 'as_of', 'horizon',
            'signal', 'setup_type', 'timeframe', 'confidence', 'status',
            'entry_type', 'entry_price', 'entry_condition',
            'stop_price', 'stop_method', 'invalidation_reason',
            'target_price', 'target_method', 'target_2_price', 'target_2_method',
            'risk', 'reward', 'risk_reward_ratio',
            'session_window', 'expires_at', 'supporting_factors', 'risk_factors',
            'setup_details', 'market_context', 'sector_context',
            'data_quality', 'calculation_version', 'status_updated_at',
            'generated_at'
        ]

# ─────────────────────────────────────────────────────────────────────────────
# 7. Recommendation Outcomes & Backtesting
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationOutcomeSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source='recommendation.instrument.symbol', read_only=True)
    signal = serializers.CharField(source='recommendation.signal', read_only=True)
    setup_type = serializers.CharField(source='recommendation.setup_type', read_only=True)
    timeframe = serializers.CharField(source='recommendation.timeframe', read_only=True)
    horizon = serializers.CharField(source='recommendation.horizon', read_only=True)

    class Meta:
        model = RecommendationOutcome
        fields = [
            'id', 'recommendation', 'symbol', 'signal', 'setup_type', 'timeframe',
            'horizon', 'evaluation_version', 'evaluated_at', 'entry_triggered',
            'entry_timestamp', 'actual_entry_price', 'exit_reason',
            'exit_timestamp', 'actual_exit_price', 'net_pnl_percent',
            'r_multiple', 'target_hit', 'stop_hit', 'ambiguous_intrabar',
            'max_favorable_excursion', 'max_adverse_excursion',
            'holding_duration_bars', 'holding_duration_seconds', 'bars_evaluated',
            'data_quality_warnings'
        ]

class BacktestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestRun
        fields = [
            'id', 'run_id', 'status', 'started_at', 'completed_at',
            'universe_name', 'timeframe', 'horizon', 'start_date',
            'end_date', 'strategy_version', 'result', 'data_quality_warnings',
            'error_message'
        ]

class BacktestRunRequestSerializer(serializers.Serializer):
    universe_name = serializers.CharField(default='NIFTY50')
    timeframe = serializers.CharField(default='1d')
    horizon = serializers.CharField(default='DELIVERY_SWING')
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    cost_mode = serializers.ChoiceField(choices=['NO_COST', 'REALISTIC', 'CUSTOM'], default='REALISTIC')
    brokerage_pct = serializers.FloatField(required=False, default=0.03)
    stt_pct = serializers.FloatField(required=False, default=0.1)
    slippage_bps = serializers.FloatField(required=False, default=5.0)
    ambiguity_policy = serializers.ChoiceField(choices=['CONSERVATIVE', 'OPTIMISTIC', 'EXCLUDE'], default='CONSERVATIVE')

# ─────────────────────────────────────────────────────────────────────────────
# 8. AI Research Request Serializers
# ─────────────────────────────────────────────────────────────────────────────

class ResearchQueryRequestSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=50, required=True)
    question = serializers.CharField(max_length=1000, required=True)
    depth = serializers.ChoiceField(choices=['quick', 'standard', 'deep', 'QUICK', 'STANDARD', 'DEEP'], default='standard')
    as_of = serializers.CharField(required=False, allow_null=True, default=None)
