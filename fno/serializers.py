"""
Nomad Analyst — F&O Presentation Layer Serializers
Reference: Phase FNO-1 Implementation
"""

from decimal import Decimal
from rest_framework import serializers
from fno.models import OptionQuoteSnapshot, OptionOHLCVBar, PaperTradeLedger


class OptionQuoteSnapshotSerializer(serializers.ModelSerializer):
    spread_pct = serializers.SerializerMethodField()
    spread_abs = serializers.SerializerMethodField()

    strike_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    option_type = serializers.CharField(max_length=2, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = OptionQuoteSnapshot
        fields = [
            'id',
            'instrument_token',
            'tradingsymbol',
            'strike_price',
            'option_type',
            'expiry_date',
            'exchange_timestamp_utc',
            'received_wall_clock_utc',
            'exchange_time_status',
            'best_bid',
            'best_ask',
            'bid_quantity_l1',
            'ask_quantity_l1',
            'depth',
            'quote_status',
            'is_stale',
            'is_locked',
            'is_crossed',
            'is_execution_eligible',
            'spread_pct',
            'spread_abs',
            'created_at',
        ]

    def get_spread_abs(self, obj) -> str | None:
        if obj.best_ask is not None and obj.best_bid is not None:
            return str(round(obj.best_ask - obj.best_bid, 2))
        return None

    def get_spread_pct(self, obj) -> str | None:
        if obj.best_ask is not None and obj.best_bid is not None and obj.best_ask > 0:
            spread = (obj.best_ask - obj.best_bid) / obj.best_ask * Decimal("100")
            return str(round(spread, 2))
        return None


class OptionOHLCVBarSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionOHLCVBar
        fields = [
            'id',
            'instrument_token',
            'tradingsymbol',
            'underlying_symbol',
            'option_type',
            'strike_price',
            'expiry_date',
            'timeframe',
            'timestamp',
            'open',
            'high',
            'low',
            'close',
            'volume',
            'open_interest',
            'oi_status',
            'is_partial_bar',
            'created_at',
        ]


class PaperTradeLedgerSerializer(serializers.ModelSerializer):
    statutory_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = PaperTradeLedger
        fields = [
            'trade_id',
            'strategy_id',
            'strategy_version',
            'signal_id',
            'instrument_token',
            'tradingsymbol',
            'option_type',
            'strike_price',
            'expiry_date',
            'entry_timestamp',
            'entry_fill_price',
            'entry_slippage',
            'quantity',
            'exit_timestamp',
            'exit_trigger_reason',
            'fill_type',
            'exit_fill_price',
            'exit_slippage',
            'gross_pnl',
            'total_frictions',
            'net_pnl',
            'friction_breakdown',
            'statutory_breakdown',
            'market_regime_at_entry',
            'vix_level_at_entry',
            'status',
            'rejection_reason',
            'created_at',
        ]

    def get_statutory_breakdown(self, obj) -> dict:
        return obj.friction_breakdown or {}
