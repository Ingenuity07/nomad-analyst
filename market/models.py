import uuid
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
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    status_updated_at = models.DateTimeField(null=True, blank=True)

    # ── LLM explanation (written separately, after deterministic fields are frozen) ─
    llm_explanation = models.TextField(null=True, blank=True)

    calculation_version = models.IntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['instrument', 'as_of']),
            models.Index(fields=['horizon', 'signal', 'status']),
            models.Index(fields=['as_of', 'status']),
        ]
        ordering = ['-generated_at']
        verbose_name_plural = "Stock Recommendations"

    def __str__(self):
        return (
            f"{self.instrument.symbol} [{self.horizon}] "
            f"{self.signal} ({self.confidence}) @ {self.as_of.date()}"
        )


