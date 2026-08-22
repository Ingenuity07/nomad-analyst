from django.contrib import admin
from .models import Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature

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
