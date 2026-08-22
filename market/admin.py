from django.contrib import admin
from .models import (
    Company,
    Instrument,
    MarketSnapshot,
    OHLCVBar,
    TechnicalFeature,
    RawFundamentalData,
    IncomeStatement,
    BalanceSheetStatement,
    CashFlowStatement,
    DerivedFundamentalMetric,
    CorporateEvent
)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'isin', 'sector', 'industry', 'is_active')
    search_fields = ('name', 'isin', 'sector', 'industry')
    list_filter = ('is_active', 'sector')

@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'exchange', 'instrument_type', 'currency', 'is_active')
    search_fields = ('symbol', 'isin')
    list_filter = ('exchange', 'instrument_type', 'is_active')

@admin.register(MarketSnapshot)
class MarketSnapshotAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'timestamp', 'close', 'volume', 'source')
    search_fields = ('instrument__symbol', 'source')
    list_filter = ('source', 'timestamp')

@admin.register(OHLCVBar)
class OHLCVBarAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'timeframe', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'source')
    search_fields = ('instrument__symbol', 'source')
    list_filter = ('timeframe', 'source', 'timestamp')
    raw_id_fields = ('instrument',)

@admin.register(TechnicalFeature)
class TechnicalFeatureAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'timeframe', 'timestamp', 'name', 'param_key', 'value')
    search_fields = ('instrument__symbol', 'name', 'param_key')
    list_filter = ('timeframe', 'name', 'timestamp')
    raw_id_fields = ('instrument',)

@admin.register(RawFundamentalData)
class RawFundamentalDataAdmin(admin.ModelAdmin):
    list_display = ('company', 'source', 'reporting_type', 'fiscal_period', 'retrieved_at', 'status')
    search_fields = ('company__name', 'company__short_name', 'fiscal_period')
    list_filter = ('source', 'reporting_type', 'status')
    raw_id_fields = ('company',)

@admin.register(IncomeStatement)
class IncomeStatementAdmin(admin.ModelAdmin):
    list_display = ('company', 'period_type', 'period_string', 'fiscal_year', 'revenue', 'pat', 'eps')
    search_fields = ('company__name', 'company__short_name', 'period_string')
    list_filter = ('period_type', 'fiscal_year')
    raw_id_fields = ('company',)

@admin.register(BalanceSheetStatement)
class BalanceSheetStatementAdmin(admin.ModelAdmin):
    list_display = ('company', 'period_type', 'period_string', 'fiscal_year', 'total_assets', 'total_liabilities')
    search_fields = ('company__name', 'company__short_name', 'period_string')
    list_filter = ('period_type', 'fiscal_year')
    raw_id_fields = ('company',)

@admin.register(CashFlowStatement)
class CashFlowStatementAdmin(admin.ModelAdmin):
    list_display = ('company', 'period_type', 'period_string', 'fiscal_year', 'operating_cash_flow', 'free_cash_flow')
    search_fields = ('company__name', 'company__short_name', 'period_string')
    list_filter = ('period_type', 'fiscal_year')
    raw_id_fields = ('company',)

@admin.register(DerivedFundamentalMetric)
class DerivedFundamentalMetricAdmin(admin.ModelAdmin):
    list_display = ('company', 'period_type', 'period_string', 'name', 'value')
    search_fields = ('company__name', 'company__short_name', 'name', 'period_string')
    list_filter = ('period_type', 'name')
    raw_id_fields = ('company',)

@admin.register(CorporateEvent)
class CorporateEventAdmin(admin.ModelAdmin):
    list_display = ('company', 'event_type', 'announcement_date', 'ex_date')
    search_fields = ('company__name', 'company__short_name', 'event_type')
    list_filter = ('event_type',)
    raw_id_fields = ('company',)
