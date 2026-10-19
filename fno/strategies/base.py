"""
Nomad Analyst — F&O Generic Strategy Framework: Base Contracts
Reference: Phase 22C Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Pure, decoupled, versioned interface for all independent option strategy modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, Field

from fno.services.feature_engine import OptionFeatureSnapshot


class StrategyConfig(BaseModel):
    """Configuration container for strategy modules."""
    model_config = {"extra": "allow"}
    is_enabled: bool = True
    max_active_positions: int = 1
    default_lot_size: int = 65  # NIFTY lot size
    default_lot_count: int = 1
    max_acceptable_slippage_pct: Decimal = Decimal("0.015")  # 1.5%
    stop_loss_pct: Decimal = Decimal("0.15")  # 15% premium stop loss
    profit_target_pct: Decimal = Decimal("0.20")  # 20% premium profit target
    max_holding_minutes: int = 45
    eod_square_off_time: time = time(15, 15)


class OptionSignal(BaseModel):
    """
    Standardized, immutable signal emitted by an independent strategy module.
    Consumed by the shared Paper Execution Lab.
    """
    model_config = {"frozen": True}

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    strategy_version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Target Instrument
    tradingsymbol: str
    instrument_token: int
    underlying_symbol: str = "^NSEI"
    option_type: str  # "CE" or "PE"
    strike_price: Decimal
    expiry_date: date

    # Action & Urgency
    action: str  # "BUY_TO_OPEN", "EXIT_TARGET", "EXIT_STOP", "EXIT_TIME", "EXIT_EOD"
    suggested_lot_count: int = 1
    limit_price_hint: Optional[Decimal] = None
    max_acceptable_slippage_pct: Decimal = Decimal("0.015")

    # Risk Envelope
    stop_loss_premium: Optional[Decimal] = None
    profit_target_premium: Optional[Decimal] = None
    max_holding_minutes: Optional[int] = 45
    eod_square_off_time: time = time(15, 15)

    # Audit Trail & Provenance
    trigger_rule_name: str
    trigger_rationale: str
    snapshot_reference_id: str


@dataclass(frozen=True)
class PaperTradeEvent:
    """Event emitted by the paper execution engine back to the strategy module."""
    event_id: str
    event_type: str  # "ORDER_FILLED", "ORDER_REJECTED", "POSITION_CLOSED", "SETTLEMENT"
    strategy_id: str
    signal_id: str
    tradingsymbol: str
    fill_price: Optional[Decimal]
    fill_quantity: int
    slippage: Decimal
    timestamp: datetime
    message: str = ""


class BaseStrategy(ABC):
    """
    Abstract Base Class for all Nomad Analyst F&O Strategies.
    Strategies are isolated, versioned, and stateless with respect to other strategies.
    """
    strategy_id: str
    strategy_name: str
    strategy_version: str = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_dict = config or {}
        self.config = StrategyConfig(**cfg_dict)
        self.is_enabled = self.config.is_enabled
        self.positions: Dict[str, Dict[str, Any]] = {}

    def enable(self) -> None:
        """Enables strategy signal generation."""
        self.is_enabled = True

    def disable(self) -> None:
        """Disables strategy signal generation."""
        self.is_enabled = False

    @abstractmethod
    def on_feature_snapshot(
        self,
        snapshot: OptionFeatureSnapshot,
    ) -> Optional[OptionSignal]:
        """
        Evaluates a validated feature snapshot.
        Pure and deterministic: returns an OptionSignal if entry/exit rules are met, else None.
        Must check snapshot.is_valid_for_signal before triggering entries.
        """
        pass

    @abstractmethod
    def on_trade_event(self, event: PaperTradeEvent) -> None:
        """Receives updates regarding fills, exits, and ledger mutations."""
        pass
