import uuid
from decimal import Decimal
from typing import Optional
from django.db import models
from django.utils import timezone

class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    short_name = models.CharField(max_length=100, blank=True, null=True)
    isin = models.CharField(max_length=12, blank=True, null=True, unique=True)
    sector = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    sub_industry = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class Instrument(models.Model):
    EXCHANGE_CHOICES = (
        ('NSE', 'National Stock Exchange'),
        ('BSE', 'Bombay Stock Exchange'),
        ('GLOBAL', 'Global Markets'),
        ('INDEX', 'Index Exchange'),
    )

    TYPE_CHOICES = (
        ('EQUITY', 'Equity'),
        ('ETF', 'ETF'),
        ('INDEX', 'Index'),
        ('FUTURE', 'Future'),
        ('OPTION', 'Option'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='instruments')
    symbol = models.CharField(max_length=50, unique=True)
    exchange = models.CharField(max_length=10, choices=EXCHANGE_CHOICES, default='NSE')
    isin = models.CharField(max_length=12, blank=True, null=True)
    instrument_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='EQUITY')
    currency = models.CharField(max_length=3, default='INR')
    lot_size = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol}:{self.exchange}"


class MarketSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='snapshots')
    timestamp = models.DateTimeField()
    open = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    close = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    previous_close = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    change = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    change_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=50)
    source_timestamp = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['instrument', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.instrument.symbol} @ {self.timestamp.isoformat()}"


class OHLCVBar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='ohlcv_bars')
    timeframe = models.CharField(max_length=10, default='1d', help_text="Timeframe (e.g. 1d, 1h, 5m)")
    timestamp = models.DateTimeField(help_text="Time of the bar opening (timezone-aware)")
    open = models.DecimalField(max_digits=12, decimal_places=2)
    high = models.DecimalField(max_digits=12, decimal_places=2)
    low = models.DecimalField(max_digits=12, decimal_places=2)
    close = models.DecimalField(max_digits=12, decimal_places=2)
    volume = models.BigIntegerField()
    source = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['instrument', 'timeframe', 'timestamp'],
                name='unique_instrument_timeframe_timestamp'
            )
        ]
        indexes = [
            models.Index(fields=['instrument', 'timeframe', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.instrument.symbol} [{self.timeframe}] @ {self.timestamp.isoformat()}"


class TechnicalFeature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='technical_features')
    timeframe = models.CharField(max_length=10, default='1d')
    timestamp = models.DateTimeField(help_text="Timestamp corresponding to the calculations source bar")
    name = models.CharField(max_length=100, help_text="Name of the technical indicator (e.g. RSI, SMA)")
    parameters = models.JSONField(default=dict, help_text="Parameter dictionary used for calculation")
    param_key = models.CharField(max_length=100, help_text="Sorted serialized parameters string for indexing")
    value = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['instrument', 'timeframe', 'name', 'param_key', 'timestamp'],
                name='unique_instrument_timeframe_feature_param_timestamp'
            )
        ]
        indexes = [
            models.Index(fields=['instrument', 'timeframe', 'name', 'param_key', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.instrument.symbol} [{self.timeframe}] {self.name}({self.param_key}) @ {self.timestamp.isoformat()} = {self.value}"


class RawFundamentalData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='raw_financials')
    source = models.CharField(max_length=50, default='screener')
    source_url = models.URLField(max_length=500, null=True, blank=True)
    fiscal_period = models.CharField(max_length=20, help_text="Fiscal period label (e.g. FY2025, Q3_2025)")
    reporting_type = models.CharField(max_length=20, default='ANNUAL', help_text="ANNUAL or QUARTERLY")
    retrieved_at = models.DateTimeField(auto_now_add=True)
    raw_payload = models.JSONField(help_text="Unmodified parsed JSON structure from provider")
    status = models.CharField(max_length=20, default='RAW')

    class Meta:
        indexes = [
            models.Index(fields=['company', 'reporting_type', 'fiscal_period']),
        ]

    def __str__(self):
        return f"{self.company.short_name} Raw {self.reporting_type} {self.fiscal_period}"


class IncomeStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='income_statements')
    fiscal_year = models.IntegerField(help_text="Financial Year ending (e.g. 2025)")
    period_type = models.CharField(max_length=20, default='ANNUAL', help_text="ANNUAL or QUARTERLY")
    period_string = models.CharField(max_length=20, help_text="Reporting period label (e.g. Mar 2025, TTM)")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    filing_date = models.DateField(null=True, blank=True)

    # Core normalized statement fields
    revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    expenses = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ebitda = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ebit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    depreciation = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    interest = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    pbt = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    pat = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    eps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_type', 'period_string'],
                name='unique_company_income_period'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'period_type', 'period_string']),
            models.Index(fields=['fiscal_year']),
        ]

    def __str__(self):
        return f"{self.company.short_name} Income Statement [{self.period_type}] {self.period_string}"


class BalanceSheetStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='balance_sheets')
    fiscal_year = models.IntegerField()
    period_type = models.CharField(max_length=20, default='ANNUAL')
    period_string = models.CharField(max_length=20)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    filing_date = models.DateField(null=True, blank=True)

    # Core normalized statement fields
    equity_capital = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    reserves = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    borrowings = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    other_liabilities = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_liabilities = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fixed_assets = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cwip = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    investments = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    other_assets = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_assets = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_type', 'period_string'],
                name='unique_company_balance_period'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'period_type', 'period_string']),
            models.Index(fields=['fiscal_year']),
        ]

    def __str__(self):
        return f"{self.company.short_name} Balance Sheet [{self.period_type}] {self.period_string}"


class CashFlowStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='cash_flows')
    fiscal_year = models.IntegerField()
    period_type = models.CharField(max_length=20, default='ANNUAL')
    period_string = models.CharField(max_length=20)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    filing_date = models.DateField(null=True, blank=True)

    # Core normalized statement fields
    operating_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    investing_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    financing_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    free_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_type', 'period_string'],
                name='unique_company_cash_flow_period'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'period_type', 'period_string']),
            models.Index(fields=['fiscal_year']),
        ]

    def __str__(self):
        return f"{self.company.short_name} Cash Flow [{self.period_type}] {self.period_string}"


class DerivedFundamentalMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fundamental_metrics')
    period_type = models.CharField(max_length=20, default='ANNUAL')
    period_string = models.CharField(max_length=20)
    name = models.CharField(max_length=100, help_text="Name of the fundamental metric (e.g. ROE, Debt_Equity)")
    value = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_type', 'period_string', 'name'],
                name='unique_company_period_metric_name'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'period_type', 'period_string', 'name']),
        ]

    def __str__(self):
        return f"{self.company.short_name} [{self.period_type}] {self.name} @ {self.period_string} = {self.value}"


class CorporateEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='corporate_events')
    event_type = models.CharField(max_length=20, help_text="SPLIT, BONUS, DIVIDEND, MERGER")
    announcement_date = models.DateField(null=True, blank=True)
    ex_date = models.DateField(null=True, blank=True)
    details = models.JSONField(default=dict, help_text="Split/Bonus ratios or Dividend amounts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'event_type', 'ex_date']),
        ]

    def __str__(self):
        return f"{self.company.short_name} {self.event_type} Ex-Date {self.ex_date}"


class NewsItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='news_items', null=True, blank=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='news_items', null=True, blank=True)
    headline = models.CharField(max_length=500)
    summary = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=50, default='yahoo_rss')
    source_id = models.CharField(max_length=200, null=True, blank=True)
    url = models.URLField(max_length=500, null=True, blank=True)
    published_at = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=50, default='other')
    raw_metadata = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content_hash'],
                name='unique_news_item_content_hash'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'published_at']),
            models.Index(fields=['published_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        company_name = self.company.short_name if self.company else "MarketWide"
        return f"[{company_name}] {self.headline} ({self.published_at.isoformat()})"


class CorporateDisclosure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='corporate_disclosures')
    headline = models.CharField(max_length=500)
    category = models.CharField(max_length=100)
    source = models.CharField(max_length=50, default='NSE')
    announcement_id = models.CharField(max_length=100)
    url = models.URLField(max_length=500, null=True, blank=True)
    published_at = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content_hash'],
                name='unique_corporate_disclosure_content_hash'
            )
        ]
        indexes = [
            models.Index(fields=['company', 'published_at']),
            models.Index(fields=['published_at']),
        ]

    def __str__(self):
        return f"{self.company.short_name} Disclosure: {self.headline} @ {self.published_at.isoformat()}"


class MarketContextSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    as_of = models.DateTimeField(db_index=True)
    universe = models.CharField(max_length=50, default="NIFTY50")
    calculations_version = models.IntegerField(default=1)
    
    # Intraday summary columns for rapid querying
    market_direction = models.CharField(max_length=20, default='NEUTRAL')
    market_regime = models.CharField(max_length=30, default='UNKNOWN')
    nifty_return = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    banknifty_return = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    advance_count = models.IntegerField(default=0)
    decline_count = models.IntegerField(default=0)
    unchanged_count = models.IntegerField(default=0)
    advance_decline_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    above_vwap_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    below_vwap_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sector_leader = models.CharField(max_length=50, blank=True, null=True)
    sector_laggard = models.CharField(max_length=50, blank=True, null=True)
    market_volatility = models.CharField(max_length=20, default='NORMAL')
    breadth_state = models.CharField(max_length=30, default='NEUTRAL')
    index_confirmation = models.CharField(max_length=30, default='NEUTRAL')

    index_regimes = models.JSONField(default=dict)
    breadth = models.JSONField(default=dict)
    sector_rankings = models.JSONField(default=list)
    global_cues = models.JSONField(default=dict)
    cross_market_features = models.JSONField(default=dict)
    macro_events = models.JSONField(default=list)
    data_quality = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['as_of', 'universe']),
        ]
        verbose_name_plural = "Market Context Snapshots"

    def __str__(self):
        return f"Market Context Snapshot [{self.universe}] @ {self.as_of.isoformat()}"


class StockIntradayContext(models.Model):
    """
    Intraday stock-level context snapshot capturing technical, relative strength,
    volume confirmation, opening range, and foundation context features.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='intraday_contexts')
    timestamp = models.DateTimeField(db_index=True)
    last_price = models.DecimalField(max_digits=12, decimal_places=2)
    change_pct = models.DecimalField(max_digits=6, decimal_places=2)
    vwap = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    distance_from_vwap = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    volume = models.BigIntegerField(default=0)
    relative_volume = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    momentum_5m = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    momentum_15m = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    momentum_30m = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    relative_strength_vs_market = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    relative_strength_vs_sector = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    sector = models.CharField(max_length=100, default='Unknown')
    sector_return = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    volume_confirmation = models.CharField(max_length=30, default='NEUTRAL')
    opening_range_state = models.CharField(max_length=30, default='INSIDE_ORB')
    intraday_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    intraday_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    component_scores = models.JSONField(default=dict)
    context_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['instrument', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        verbose_name_plural = "Stock Intraday Contexts"

    def __str__(self):
        return f"{self.instrument.symbol} IntradayContext @ {self.timestamp.isoformat()}"


class Universe(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UniverseMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    universe = models.ForeignKey(Universe, on_delete=models.CASCADE, related_name='memberships')
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='universe_memberships')
    added_at = models.DateTimeField(default=timezone.now)
    removed_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['universe', 'is_active']),
            models.Index(fields=['instrument', 'is_active']),
        ]
        unique_together = ('universe', 'instrument', 'is_active')

    def __str__(self):
        return f"{self.instrument.symbol} in {self.universe.name}"


class StockOpportunitySnapshot(models.Model):
    HORIZON_CHOICES = (
        ('INTRADAY', 'Intraday'),
        ('DELIVERY_SWING', 'Delivery / Swing'),
        ('LONG_TERM', 'Long-term'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='opportunity_snapshots')
    as_of = models.DateTimeField(db_index=True)
    universe = models.CharField(max_length=100)
    horizon = models.CharField(max_length=20, choices=HORIZON_CHOICES)
    opportunity_type = models.CharField(max_length=50)
    component_scores = models.JSONField(default=dict)
    final_opportunity_score = models.DecimalField(max_digits=12, decimal_places=4)
    supporting_features = models.JSONField(default=dict)
    risks = models.JSONField(default=list)
    data_quality = models.JSONField(default=dict)
    calculation_version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['as_of', 'universe', 'horizon']),
            models.Index(fields=['instrument', 'as_of']),
        ]
        verbose_name_plural = "Stock Opportunity Snapshots"

    def __str__(self):
        return f"{self.instrument.symbol} [{self.horizon}] ({self.opportunity_type}) @ {self.as_of.isoformat()}"


class StockRecommendation(models.Model):
    """
    Append-only recommendation record generated by the SignalEngine.

    CRITICAL DESIGN RULES:
      1. Records are NEVER overwritten. Every generation creates a new row.
      2. Deterministic fields (entry_price, stop_price, target_price, signal) are
         written once at creation and NEVER updated by the LLM or any service.
      3. The only mutable fields are: status, status_updated_at, llm_explanation.
      4. Historical records preserve a full audit trail for backtesting.
    """
    SIGNAL_CHOICES = (
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('NO_ACTION', 'No Action'),
        ('INSUFFICIENT_DATA', 'Insufficient Data'),
        ('NOT_READY', 'Not Ready'),
    )
    HORIZON_CHOICES = (
        ('INTRADAY', 'Intraday'),
        ('DELIVERY_SWING', 'Delivery / Swing'),
        ('LONG_TERM', 'Long-term'),
    )
    CONFIDENCE_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    )
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('TRIGGERED', 'Triggered'),
        ('TARGET_HIT', 'Target Hit'),
        ('STOPPED', 'Stopped'),
        ('EXPIRED', 'Expired'),
        ('INVALIDATED', 'Invalidated'),
        ('CANCELLED', 'Cancelled'),
        # Module 11: stop AND target both touched in same OHLC bar
        ('AMBIGUOUS_INTRABAR', 'Ambiguous Intrabar'),
    )
    ENTRY_TYPE_CHOICES = (
        ('BREAKOUT_CONFIRMATION', 'Breakout Confirmation'),
        ('SUPPORT_RETEST', 'Support Retest'),
        ('MOMENTUM_CONFIRMATION', 'Momentum Confirmation'),
        ('CURRENT_MARKET_PRICE', 'Current Market Price'),
        ('LIMIT_ORDER_ZONE', 'Limit Order Zone'),
    )
    STOP_METHOD_CHOICES = (
        ('STRUCTURAL', 'Structural'),
        ('ATR_BASED', 'ATR-Based'),
        ('SWING_HIGH_LOW', 'Swing High / Low'),
        ('PERCENTAGE_FALLBACK', 'Percentage Fallback'),
    )
    TARGET_METHOD_CHOICES = (
        ('RESISTANCE_LEVEL', 'Resistance Level'),
        ('MEASURED_MOVE', 'Measured Move'),
        ('ATR_MULTIPLE', 'ATR Multiple'),
        ('RISK_REWARD_DERIVED', 'Risk/Reward Derived'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(
        Instrument, on_delete=models.CASCADE, related_name='recommendations'
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    horizon = models.CharField(max_length=20, choices=HORIZON_CHOICES)
    signal = models.CharField(max_length=20, choices=SIGNAL_CHOICES)
    setup_type = models.CharField(max_length=30)

    # ── PIT anchor ───────────────────────────────────────────────────────────
    as_of = models.DateTimeField(db_index=True, help_text="Point-in-time anchor. Immutable.")
    generated_at = models.DateTimeField(auto_now_add=True)

    # ── Entry ─────────────────────────────────────────────────────────────────
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPE_CHOICES)
    entry_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    entry_condition = models.TextField()

    # ── Stop Loss ─────────────────────────────────────────────────────────────
    stop_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stop_method = models.CharField(max_length=25, choices=STOP_METHOD_CHOICES)
    invalidation_reason = models.TextField()

    # ── Target ───────────────────────────────────────────────────────────────
    target_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_method = models.CharField(max_length=25, choices=TARGET_METHOD_CHOICES)

    # ── Risk / Reward ─────────────────────────────────────────────────────────
    risk = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reward = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    risk_reward_ratio = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # ── Confidence ────────────────────────────────────────────────────────────
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES)
    confidence_components = models.JSONField(default=dict)

    # ── Context snapshots (frozen at generation time) ─────────────────────────
    market_context = models.JSONField(default=dict)
    sector_context = models.JSONField(default=dict)

    # ── Explanatory evidence ──────────────────────────────────────────────────
    supporting_factors = models.JSONField(default=list)
    risk_factors = models.JSONField(default=list)
    setup_details = models.JSONField(default=dict)
    data_quality = models.JSONField(default=dict)

    # ── Lifecycle (only mutable fields) ──────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    status_updated_at = models.DateTimeField(null=True, blank=True)

    # ── LLM explanation (written separately, after deterministic fields are frozen) ─
    llm_explanation = models.TextField(null=True, blank=True)

    calculation_version = models.IntegerField(default=1)

    # ── Intraday-specific fields (Module 10) ──────────────────────────────────
    # null=True, blank=True on all — zero impact on existing daily records.

    # Which timeframe generated this recommendation (e.g. '5m', '15m', '1d')
    timeframe = models.CharField(
        max_length=10, null=True, blank=True,
        help_text="Generating timeframe. Null for daily/delivery recommendations."
    )

    # Second target for intraday partial exits
    target_2_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Optional second target for intraday partial exit."
    )
    target_2_method = models.CharField(
        max_length=25, null=True, blank=True,
        help_text="Method used to derive target 2."
    )

    # Intraday session window at generation time
    SESSION_WINDOW_CHOICES = (
        ('OPENING',   'Opening (09:15-09:45)'),
        ('MORNING',   'Morning (09:45-11:30)'),
        ('MIDDAY',    'Midday (11:30-13:00)'),
        ('AFTERNOON', 'Afternoon (13:00-14:30)'),
        ('CLOSING',   'Closing (14:30-15:30)'),
        ('OUTSIDE',   'Outside Session'),
    )
    session_window = models.CharField(
        max_length=15, null=True, blank=True, choices=SESSION_WINDOW_CHOICES,
        help_text="Session window at the time of recommendation generation."
    )

    # Strategy configuration version (for backtesting traceability)
    strategy_version = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="Intraday strategy config version that generated this recommendation."
    )

    # Explicit session-close expiry for intraday recommendations
    expires_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="UTC datetime when this intraday recommendation expires (market close). "
                  "Null for non-intraday recommendations."
    )

    class Meta:
        indexes = [
            models.Index(fields=['instrument', 'as_of']),
            models.Index(fields=['horizon', 'signal', 'status']),
            models.Index(fields=['as_of', 'status']),
            # Intraday lifecycle — efficient expiry batch queries
            models.Index(fields=['instrument', 'horizon', 'status', 'expires_at'],
                         name='rec_intraday_lifecycle_idx'),
        ]
        ordering = ['-generated_at']
        verbose_name_plural = "Stock Recommendations"

    def __str__(self):
        return (
            f"{self.instrument.symbol} [{self.horizon}] "
            f"{self.signal} ({self.confidence}) @ {self.as_of.date()}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module 11 — Recommendation Outcome Tracking & Backtesting
# ─────────────────────────────────────────────────────────────────────────────


class RecommendationOutcome(models.Model):
    """
    Immutable outcome record for a recommendation. Created once after the
    recommendation lifecycle completes (entry triggered or not, exit reached).

    CRITICAL DESIGN RULES:
      1. NEVER update a row after it is written. Create a new row with an
         incremented evaluation_version if re-evaluation is needed.
      2. All price fields are ACTUAL market prices (from bar OHLC), not
         theoretical prices.
      3. pnl fields are post-cost (net). gross_pnl fields are pre-cost.
      4. This model is the source of truth for backtesting and live tracking.
    """
    EXIT_REASON_CHOICES = (
        ('TARGET_HIT',           'Target Hit'),
        ('TARGET_2_HIT',         'Target 2 Hit'),
        ('STOP_HIT',             'Stop Hit'),
        ('EXPIRED_SESSION',      'Expired: Session Close'),
        ('EXPIRED_MAX_DURATION', 'Expired: Max Duration'),
        ('AMBIGUOUS_INTRABAR',   'Ambiguous: Same-Bar Stop+Target'),
        ('CANCELLED',            'Cancelled'),
        ('NO_ENTRY',             'No Entry Triggered'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to the recommendation being evaluated (1:1 per evaluation version)
    recommendation = models.ForeignKey(
        StockRecommendation, on_delete=models.CASCADE,
        related_name='outcomes'
    )
    evaluation_version = models.IntegerField(
        default=1,
        help_text="Allows re-evaluation without destroying prior outcome records."
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)

    # ── Entry ───────────────────────────────────────────────────────────────
    entry_triggered     = models.BooleanField()
    entry_timestamp     = models.DateTimeField(null=True, blank=True)
    actual_entry_price  = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Actual bar price at which entry was triggered."
    )

    # ── Exit ───────────────────────────────────────────────────────────────
    exit_reason         = models.CharField(
        max_length=25, choices=EXIT_REASON_CHOICES, null=True, blank=True
    )
    exit_timestamp      = models.DateTimeField(null=True, blank=True)
    actual_exit_price   = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )

    # ── P&L (null when entry not triggered) ─────────────────────────────────
    gross_pnl_absolute  = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        help_text="Pre-cost P&L in currency units."
    )
    gross_pnl_percent   = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Pre-cost P&L as percent of entry price."
    )
    cost_absolute       = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        help_text="Total transaction cost (brokerage + STT + slippage)."
    )
    net_pnl_absolute    = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        help_text="Post-cost P&L in currency units."
    )
    net_pnl_percent     = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Post-cost P&L as percent of entry price."
    )

    # ── R-multiple ────────────────────────────────────────────────────────────
    risk_amount         = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Actual risk = |actual_entry_price - stop_price|."
    )
    r_multiple          = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Net P&L divided by risk amount. Positive = winner."
    )

    # ── Outcome flags ─────────────────────────────────────────────────────────
    target_hit          = models.BooleanField(
        null=True, help_text="True=target hit, False=not hit, None=ambiguous."
    )
    stop_hit            = models.BooleanField(
        null=True, help_text="True=stop hit, False=not hit, None=ambiguous."
    )
    ambiguous_intrabar  = models.BooleanField(
        default=False,
        help_text="True when stop and target were both touched in the same bar."
    )

    # ── Excursion (percent of entry) ──────────────────────────────────────
    max_favorable_excursion = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Max favorable excursion as % of entry. Always positive."
    )
    max_adverse_excursion = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Max adverse excursion as % of entry. Always positive."
    )

    # ── Duration ─────────────────────────────────────────────────────────────
    holding_duration_bars    = models.IntegerField(
        null=True, blank=True,
        help_text="Number of bars from entry trigger to exit."
    )
    holding_duration_seconds = models.BigIntegerField(
        null=True, blank=True,
        help_text="Wall-clock duration from entry to exit in seconds."
    )

    # ── Metadata ─────────────────────────────────────────────────────────────
    bars_evaluated           = models.IntegerField(
        default=0, help_text="Total bars processed during evaluation."
    )
    data_quality_warnings    = models.JSONField(
        default=list,
        help_text="List of data quality warnings encountered during evaluation."
    )

    class Meta:
        indexes = [
            models.Index(fields=['recommendation', 'evaluation_version'],
                         name='outcome_rec_version_idx'),
            models.Index(fields=['exit_reason'], name='outcome_exit_reason_idx'),
            models.Index(fields=['evaluated_at'], name='outcome_evaluated_at_idx'),
        ]
        # One outcome per (recommendation, evaluation_version)
        constraints = [
            models.UniqueConstraint(
                fields=['recommendation', 'evaluation_version'],
                name='unique_outcome_rec_version'
            )
        ]
        ordering = ['-evaluated_at']

    def __str__(self):
        rec = self.recommendation
        return (
            f"Outcome({rec.instrument.symbol} {rec.signal} "
            f"exit={self.exit_reason} r={self.r_multiple})"
        )


class BacktestRun(models.Model):
    """
    Persisted record of a backtest execution.

    A BacktestRun captures the full configuration used, date range,
    strategy version, and serialised results. Re-running with the same
    configuration must produce identical results (determinism guarantee).

    BacktestRuns are NEVER auto-scheduled. They must be explicitly triggered.
    """
    STATUS_CHOICES = (
        ('PENDING',  'Pending'),
        ('RUNNING',  'Running'),
        ('COMPLETE', 'Complete'),
        ('FAILED',   'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_id = models.CharField(
        max_length=100, unique=True,
        help_text="Human-readable slug identifying this backtest run."
    )

    # Configuration snapshot — frozen at run start
    config = models.JSONField(help_text="Serialised BacktestConfig used for this run.")

    # Run metadata
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    started_at  = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Dimension slices (denormalised for easy querying)
    universe_name    = models.CharField(max_length=100)
    timeframe        = models.CharField(max_length=10)
    horizon          = models.CharField(max_length=20)
    start_date       = models.DateField()
    end_date         = models.DateField()
    strategy_version = models.CharField(max_length=20)

    # Results (written on completion)
    result                = models.JSONField(
        null=True, blank=True,
        help_text="Serialised PerformanceReport produced by this run."
    )
    data_quality_warnings = models.JSONField(
        default=list,
        help_text="Data quality warnings encountered during the run."
    )
    error_message = models.TextField(
        null=True, blank=True,
        help_text="Error details if status=FAILED."
    )

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['universe_name', 'timeframe', 'horizon']),
            models.Index(fields=['started_at']),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f"BacktestRun({self.run_id} status={self.status})"


def _get_kite_cipher():
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    from django.conf import settings

    key_material = getattr(settings, 'SECRET_KEY', 'nomad-analyst-secure-encryption-key').encode('utf-8')
    key_32 = hashlib.sha256(key_material).digest()
    return Fernet(base64.urlsafe_b64encode(key_32))


class KiteCredential(models.Model):
    """
    Secure persistence for Zerodha Kite Connect credentials and authentication lifecycle.
    Encrypts access token at rest using Fernet with Django SECRET_KEY.
    """
    STATUS_CHOICES = (
        ('NOT_CONFIGURED', 'Not Configured'),
        ('AUTHENTICATION_REQUIRED', 'Authentication Required'),
        ('AUTHENTICATING', 'Authenticating'),
        ('CONNECTED', 'Connected'),
        ('EXPIRED', 'Expired'),
        ('ERROR', 'Error'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.CharField(max_length=50, default='default', unique=True)
    user_id = models.CharField(max_length=50, blank=True, null=True, help_text="Zerodha User ID / Client ID")
    user_name = models.CharField(max_length=100, blank=True, null=True)
    encrypted_access_token = models.TextField(blank=True, null=True)
    public_token = models.CharField(max_length=255, blank=True, null=True)
    request_token = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_CONFIGURED')
    authenticated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['account_id']),
            models.Index(fields=['status']),
        ]

    def set_access_token(self, token: str):
        if not token:
            self.encrypted_access_token = None
        else:
            cipher = _get_kite_cipher()
            self.encrypted_access_token = cipher.encrypt(token.encode('utf-8')).decode('utf-8')

    def get_access_token(self) -> Optional[str]:
        if not self.encrypted_access_token:
            return None
        try:
            cipher = _get_kite_cipher()
            return cipher.decrypt(self.encrypted_access_token.encode('utf-8')).decode('utf-8')
        except Exception:
            return None

    def __str__(self):
        return f"KiteCredential({self.account_id} status={self.status} user={self.user_id})"


class IntradayOpportunitySnapshot(models.Model):
    """
    Point-in-time snapshot of an intraday stock opportunity evaluation.
    Provides complete dimensional score decomposition, deterministic classifications,
    and structured explainability factors.
    """
    OPPORTUNITY_TYPE_CHOICES = (
        ('MOMENTUM_CONTINUATION', 'Momentum Continuation'),
        ('RELATIVE_STRENGTH', 'Relative Strength'),
        ('VWAP_TREND', 'VWAP Trend'),
        ('OPENING_RANGE_BREAKOUT', 'Opening Range Breakout'),
        ('OPENING_RANGE_BREAKDOWN', 'Opening Range Breakdown'),
        ('SECTOR_LEADERSHIP', 'Sector Leadership'),
        ('MEAN_REVERSION_CONTEXT', 'Mean Reversion Context'),
        ('NO_CLEAR_OPPORTUNITY', 'No Clear Opportunity'),
    )

    STATE_CHOICES = (
        ('EMERGING', 'Emerging'),
        ('CONFIRMED', 'Confirmed'),
        ('WEAKENING', 'Weakening'),
        ('INVALIDATED', 'Invalidated'),
        ('STALE', 'Stale'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey(
        Instrument, on_delete=models.CASCADE, related_name='intraday_opportunities'
    )
    symbol = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    opportunity_type = models.CharField(max_length=50, choices=OPPORTUNITY_TYPE_CHOICES)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default='EMERGING')

    # Scores
    score = models.DecimalField(max_digits=6, decimal_places=2, help_text="Composite quality score 0-100")
    confidence = models.DecimalField(max_digits=4, decimal_places=2, help_text="Evidence completeness 0.0-1.0")

    # Dimensional Component Scores (0-100 each)
    momentum_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    relative_strength_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    volume_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    vwap_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    market_alignment_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    sector_alignment_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    orb_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))
    data_quality_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.0'))

    # Structured Explanations
    supporting_factors = models.JSONField(default=list)
    contradicting_factors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    penalties = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)

    # Metadata & Context
    rank = models.IntegerField(null=True, blank=True)
    sector = models.CharField(max_length=100, default='Unknown')
    market_alignment = models.CharField(max_length=30, default='NEUTRAL')
    sector_alignment = models.CharField(max_length=30, default='NEUTRAL')
    data_quality = models.CharField(max_length=20, default='HIGH')
    freshness = models.CharField(max_length=20, default='FRESH')

    # Lifecycle tracking
    first_detected_at = models.DateTimeField(null=True, blank=True)
    last_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'timestamp']),
            models.Index(fields=['timestamp', 'rank']),
            models.Index(fields=['opportunity_type', 'state']),
            models.Index(fields=['state', 'score']),
        ]
        verbose_name_plural = "Intraday Opportunity Snapshots"

    def __str__(self):
        return f"{self.symbol} [{self.opportunity_type}] score={self.score} state={self.state} @ {self.timestamp.isoformat()}"
