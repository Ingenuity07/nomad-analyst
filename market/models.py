import uuid
from django.db import models

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


