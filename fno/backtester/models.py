"""
Nomad Analyst — Historical Options Backtester Models & Configuration Dataclasses
Reference: docs/historical_options_backtester_architecture.md
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import zoneinfo

from fno.execution.fee_calculator import StatutoryFeeBreakdown

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class SessionQualification(str, Enum):
    QUALIFIED_FULL_SESSION = "QUALIFIED_FULL_SESSION"
    INCLUDED = "QUALIFIED_FULL_SESSION"
    EXCLUDED_DATA_GAP = "EXCLUDED_DATA_GAP"
    EXCLUDED_MISSING_EXPIRY_DATA = "EXCLUDED_MISSING_EXPIRY_DATA"
    EXCLUDED_SPECIAL_SESSION = "EXCLUDED_SPECIAL_SESSION"
    EXCLUDED_INCOMPLETE_ORB = "EXCLUDED_INCOMPLETE_ORB"
    EXCLUDED_MISSING_OPTIONS = "EXCLUDED_MISSING_OPTIONS"
    EXCLUDED_RANGE_TOO_NARROW = "EXCLUDED_RANGE_TOO_NARROW"
    EXCLUDED_RANGE_TOO_WIDE = "EXCLUDED_RANGE_TOO_WIDE"


@dataclass(frozen=True)
class DataQualityIncident:
    trading_day: str
    timestamp_ist: str
    tradingsymbol: str
    incident_type: str  # e.g., "DATA_QUALITY_INCIDENT_MISSING_CANDLES"
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestConfig:
    strategy_id: str = "STRAT-ORB-15M"
    strategy_name: str = "NIFTY 15m Opening Range Breakout"
    strategy_version: str = "1.0.0"
    start_date: date = date(2025, 7, 1)
    end_date: date = date(2026, 7, 2)
    initial_capital: Decimal = Decimal("200000.00")
    num_lots: int = 1
    orb_period_minutes: int = 15
    entry_window_start: time = time(9, 30, 0)
    entry_window_end: time = time(14, 30, 0)       # Cutoff applies to simulated fill timestamp
    eod_square_off_time: time = time(15, 15, 0)
    max_holding_minutes: int = 45
    stop_loss_pct: Decimal = Decimal("0.15")        # 15%
    profit_target_pct: Decimal = Decimal("0.20")    # 20%
    slippage_rate: Decimal = Decimal("0.005")       # 0.5% default taker slippage
    slippage_model: str = "PERCENTAGE"              # "PERCENTAGE" or "FIXED_POINTS"
    fixed_slippage_pts: Decimal = Decimal("0.00")   # e.g. 0.50 or 1.00 INR/unit
    tick_size: Decimal = Decimal("0.05")            # ₹0.05 tick grid
    brokerage_per_order: Decimal = Decimal("20.00") # ₹20.00 / order leg
    allow_zero_dte_after_1300: bool = False         # Roll to next weekly on expiry day after 13:00
    roll_cutoff_time: time = time(13, 0, 0)
    max_trades_per_session: int = 1                 # Default 1 trade per session
    max_trades_per_day: int = 1
    min_orb_range_pts: Decimal = Decimal("15.00")   # Minimum range width filter
    max_orb_range_pts: Optional[Decimal] = Decimal("150.00")  # Maximum range width filter (None = no upper limit)
    enable_query_cache: bool = True                 # In-memory query caching across sensitivity runs
    dataset_dir: str = "data/historical/fno/nifty"

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["start_date"] = str(self.start_date)
        res["end_date"] = str(self.end_date)
        res["initial_capital"] = str(self.initial_capital)
        res["entry_window_start"] = str(self.entry_window_start)
        res["entry_window_end"] = str(self.entry_window_end)
        res["eod_square_off_time"] = str(self.eod_square_off_time)
        res["roll_cutoff_time"] = str(self.roll_cutoff_time)
        res["min_orb_range_pts"] = str(self.min_orb_range_pts)
        res["max_orb_range_pts"] = str(self.max_orb_range_pts) if self.max_orb_range_pts is not None else None
        res["enable_query_cache"] = self.enable_query_cache
        res["stop_loss_pct"] = str(self.stop_loss_pct)
        res["profit_target_pct"] = str(self.profit_target_pct)
        res["slippage_rate"] = str(self.slippage_rate)
        res["slippage_model"] = self.slippage_model
        res["fixed_slippage_pts"] = str(self.fixed_slippage_pts)
        res["tick_size"] = str(self.tick_size)
        res["brokerage_per_order"] = str(self.brokerage_per_order)
        return res


@dataclass(frozen=True)
class BacktestTradeRecord:
    trade_id: str
    trading_day: str
    strategy_id: str
    strategy_version: str
    tradingsymbol: str
    underlying_symbol: str
    strike: int
    option_type: str
    expiry: str
    lot_size: int
    quantity: int

    # Timing & Spot Barriers
    signal_timestamp_ist: datetime
    entry_timestamp_ist: datetime
    exit_timestamp_ist: datetime
    holding_duration_seconds: float
    orb_high: Decimal
    orb_low: Decimal
    spot_at_signal: Decimal
    spot_at_entry: Decimal
    spot_at_exit: Decimal

    # Pricing & P&L
    entry_fill_price: Decimal
    exit_fill_price: Decimal
    gross_pnl: Decimal
    statutory_fees: StatutoryFeeBreakdown
    net_pnl: Decimal
    net_return_pct: Decimal

    # Lifecycle, Status & Quarantine
    exit_reason: str
    session_qualification: str
    slippage_rate: Decimal
    slippage_model: str = "PERCENTAGE"
    stt_rate_applied: Decimal = Decimal("0.001")
    is_emergency_expiry_settlement: bool = False
    execution_liquidity_impaired: bool = False
    data_quality_incidents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "trading_day": self.trading_day,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "tradingsymbol": self.tradingsymbol,
            "underlying_symbol": self.underlying_symbol,
            "strike": self.strike,
            "option_type": self.option_type,
            "expiry": self.expiry,
            "lot_size": self.lot_size,
            "quantity": self.quantity,
            "signal_timestamp_ist": self.signal_timestamp_ist.isoformat(),
            "entry_timestamp_ist": self.entry_timestamp_ist.isoformat(),
            "exit_timestamp_ist": self.exit_timestamp_ist.isoformat(),
            "holding_duration_seconds": self.holding_duration_seconds,
            "orb_high": str(self.orb_high),
            "orb_low": str(self.orb_low),
            "spot_at_signal": str(self.spot_at_signal),
            "spot_at_entry": str(self.spot_at_entry),
            "spot_at_exit": str(self.spot_at_exit),
            "entry_fill_price": str(self.entry_fill_price),
            "exit_fill_price": str(self.exit_fill_price),
            "gross_pnl": str(self.gross_pnl),
            "statutory_fees": self.statutory_fees.to_dict(),
            "net_pnl": str(self.net_pnl),
            "net_return_pct": str(self.net_return_pct),
            "exit_reason": self.exit_reason,
            "session_qualification": self.session_qualification,
            "slippage_rate": str(self.slippage_rate),
            "slippage_model": self.slippage_model,
            "stt_rate_applied": str(self.stt_rate_applied),
            "is_emergency_expiry_settlement": self.is_emergency_expiry_settlement,
            "execution_liquidity_impaired": self.execution_liquidity_impaired,
            "data_quality_incidents": list(self.data_quality_incidents),
        }


@dataclass
class SessionExecutionSummary:
    trading_day: str
    qualification: SessionQualification
    reason: str
    orb_high: Optional[Decimal] = None
    orb_low: Optional[Decimal] = None
    breakout_detected: bool = False
    trade_executed: bool = False
    trade_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    incidents_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trading_day": self.trading_day,
            "qualification": self.qualification.value,
            "reason": self.reason,
            "orb_high": str(self.orb_high) if self.orb_high is not None else None,
            "orb_low": str(self.orb_low) if self.orb_low is not None else None,
            "breakout_detected": self.breakout_detected,
            "trade_executed": self.trade_executed,
            "trade_id": self.trade_id,
            "rejection_reason": self.rejection_reason,
            "incidents_count": self.incidents_count,
        }


@dataclass
class BacktestResultSet:
    config: BacktestConfig
    execution_start_utc: datetime
    execution_end_utc: datetime
    total_calendar_days: int
    total_trading_days: int
    qualified_sessions: int
    excluded_sessions: int
    normal_trades: List[BacktestTradeRecord]
    quarantined_trades: List[BacktestTradeRecord]
    emergency_settlement_trades: List[BacktestTradeRecord]
    session_summaries: List[SessionExecutionSummary]
    data_quality_incidents: List[DataQualityIncident]
    metrics: Dict[str, Any] = field(default_factory=dict)
    sensitivity_analysis: Dict[str, Any] = field(default_factory=dict)
    split_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "execution_metadata": {
                "execution_start_utc": self.execution_start_utc.isoformat(),
                "execution_end_utc": self.execution_end_utc.isoformat(),
                "runtime_seconds": (self.execution_end_utc - self.execution_start_utc).total_seconds(),
            },
            "session_accounting": {
                "total_calendar_days": self.total_calendar_days,
                "total_trading_days": self.total_trading_days,
                "qualified_sessions": self.qualified_sessions,
                "excluded_sessions": self.excluded_sessions,
            },
            "metrics": self.metrics,
            "sensitivity_analysis": self.sensitivity_analysis,
            "split_analysis": self.split_analysis,
            "normal_trades": [t.to_dict() for t in self.normal_trades],
            "quarantined_trades": [t.to_dict() for t in self.quarantined_trades],
            "emergency_settlement_trades": [t.to_dict() for t in self.emergency_settlement_trades],
            "session_summaries": [s.to_dict() for s in self.session_summaries],
            "data_quality_incidents": [i.to_dict() for i in self.data_quality_incidents],
        }
