from django.db import models


class OptionOHLCVBar(models.Model):
    """
    Dedicated 1-minute (and higher timeframe) OHLCV + Open Interest storage for F&O contracts.
    Completely decoupled from the equity market_ohlcvbar table.
    """
    id = models.BigAutoField(primary_key=True)
    instrument_token = models.BigIntegerField(db_index=True, help_text="Kite instrument token")
    tradingsymbol = models.CharField(max_length=50, db_index=True, help_text="e.g. NIFTY26O1922600CE")
    underlying_symbol = models.CharField(max_length=20, default='^NSEI', db_index=True, help_text="Underlying symbol e.g. ^NSEI")
    option_type = models.CharField(max_length=2, help_text="CE or PE")
    strike_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Option strike price")
    expiry_date = models.DateField(db_index=True, help_text="Contract expiry date")
    timeframe = models.CharField(max_length=10, default='1m', help_text="Bar timeframe (default: 1m)")
    timestamp = models.DateTimeField(db_index=True, help_text="Bar opening timestamp (UTC-aware)")
    open = models.DecimalField(max_digits=10, decimal_places=2)
    high = models.DecimalField(max_digits=10, decimal_places=2)
    low = models.DecimalField(max_digits=10, decimal_places=2)
    close = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField(default=0, help_text="Volume traded within this bar interval")
    open_interest = models.BigIntegerField(null=True, blank=True, help_text="Reported OI at bar close (null if unpopulated)")
    oi_status = models.CharField(
        max_length=20, 
        default='VALID', 
        help_text="VALID, ZERO_ACTIVITY (oi=0), or UNPOPULATED (oi=null)"
    )
    is_partial_bar = models.BooleanField(
        default=False, 
        help_text="True if bar interval overlapped a network disconnection gap"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fno_option_ohlcvbar'
        verbose_name = 'Option OHLCV Bar'
        verbose_name_plural = 'Option OHLCV Bars'
        constraints = [
            models.UniqueConstraint(
                fields=['instrument_token', 'timeframe', 'timestamp'],
                name='unique_fno_ohlcv_token_tf_ts'
            )
        ]
        indexes = [
            models.Index(fields=['tradingsymbol', 'timeframe', 'timestamp']),
            models.Index(fields=['underlying_symbol', 'expiry_date', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.tradingsymbol} [{self.timeframe}] @ {self.timestamp} - O:{self.open} H:{self.high} L:{self.low} C:{self.close} V:{self.volume} OI:{self.open_interest}"


class OptionQuoteSnapshot(models.Model):
    """
    High-frequency quote snapshot storage for authentic taker execution evaluation.
    Stores best bid/ask, L1 quantities, and 5-level market depth.
    Maintained under a 5-day rolling retention policy.
    """
    id = models.BigAutoField(primary_key=True)
    instrument_token = models.BigIntegerField(db_index=True)
    tradingsymbol = models.CharField(max_length=50, db_index=True)
    exchange_timestamp_utc = models.DateTimeField(null=True, blank=True, help_text="Matching engine timestamp (UTC)")
    received_wall_clock_utc = models.DateTimeField(db_index=True, help_text="Nomad daemon arrival wall clock (UTC)")
    exchange_time_status = models.CharField(
        max_length=30,
        help_text="VALID, FALLBACK_TO_RECEIVED, INVALID, FUTURE_SKEW_REJECTED, HISTORICAL_SKEW_REJECTED"
    )
    best_bid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    best_ask = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bid_quantity_l1 = models.IntegerField(null=True, blank=True)
    ask_quantity_l1 = models.IntegerField(null=True, blank=True)
    depth = models.JSONField(default=dict, blank=True, help_text="5-level bid and ask depth")
    quote_status = models.CharField(
        max_length=20,
        help_text="VALID, EMPTY_BOOK, ZERO_BID, STALE, LOCKED, CROSSED, INVALID"
    )
    is_stale = models.BooleanField(default=False, help_text="True if quote age > 3.0s")
    is_locked = models.BooleanField(default=False, help_text="True if best_bid == best_ask")
    is_crossed = models.BooleanField(default=False, help_text="True if best_bid > best_ask")
    is_execution_eligible = models.BooleanField(
        default=False,
        help_text="True iff exchange_time_status == VALID and quote_status == VALID and not stale"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fno_option_quote_snapshot'
        verbose_name = 'Option Quote Snapshot'
        verbose_name_plural = 'Option Quote Snapshots'
        indexes = [
            models.Index(fields=['instrument_token', 'exchange_timestamp_utc']),
            models.Index(fields=['tradingsymbol', 'exchange_timestamp_utc']),
            models.Index(fields=['received_wall_clock_utc']),
        ]

    def __str__(self):
        return f"{self.tradingsymbol} Quote @ {self.exchange_timestamp_utc or self.received_wall_clock_utc} - Bid:{self.best_bid} Ask:{self.best_ask} [{self.quote_status}]"


class PaperTradeLedger(models.Model):
    """
    Independent paper trading ledger recording simulated order execution,
    taker fills with slippage, statutory fees/taxes, holding duration, and P&L.
    Reference: Phase 22D Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)
    """
    trade_id = models.BigAutoField(primary_key=True)
    strategy_id = models.CharField(max_length=50, db_index=True)
    strategy_version = models.CharField(max_length=20)
    signal_id = models.UUIDField(db_index=True)
    instrument_token = models.BigIntegerField(db_index=True)
    tradingsymbol = models.CharField(max_length=50, db_index=True)
    option_type = models.CharField(max_length=2, help_text="CE or PE")
    strike_price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(db_index=True)
    entry_timestamp = models.DateTimeField(db_index=True)
    entry_fill_price = models.DecimalField(max_digits=10, decimal_places=2)
    entry_slippage = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    exit_timestamp = models.DateTimeField(null=True, blank=True)
    exit_trigger_reason = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="TARGET, STOP_LOSS, TIME_STOP, POLICY_SQUAREOFF, EXPIRY_CASH_SETTLED"
    )
    fill_type = models.CharField(
        max_length=20,
        default='MARKET_TAKER',
        help_text="MARKET_TAKER, SETTLEMENT"
    )
    exit_fill_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exit_slippage = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gross_pnl = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_frictions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_pnl = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    friction_breakdown = models.JSONField(default=dict, blank=True)
    market_regime_at_entry = models.CharField(max_length=30, null=True, blank=True)
    vix_level_at_entry = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=35,
        default='OPEN',
        help_text="OPEN, CLOSED, REJECTED, PENDING_LIQUIDITY, PENDING_EXPIRY_SETTLEMENT, CLOSED_EXPIRED_WORTHLESS, CLOSED_EXPIRED_ITM_SETTLED, UNEXECUTABLE_OVERNIGHT_CARRY"
    )
    rejection_reason = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fno_paper_trade_ledger'
        verbose_name = 'Paper Trade Ledger'
        verbose_name_plural = 'Paper Trade Ledgers'
        indexes = [
            models.Index(fields=['strategy_id', 'status']),
            models.Index(fields=['entry_timestamp']),
            models.Index(fields=['tradingsymbol', 'entry_timestamp']),
        ]

    def __str__(self):
        return f"[{self.strategy_id}] Trade #{self.trade_id} {self.tradingsymbol} ({self.status}) - Net PnL: {self.net_pnl}"

