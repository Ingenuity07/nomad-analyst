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

