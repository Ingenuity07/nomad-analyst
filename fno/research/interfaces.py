"""
Nomad Analyst — Strategy Interface Specification & Dataclasses
Reference: docs/architecture/strategy_interface_v1.md
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

from fno.backtester.models import SessionQualification

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class SignalDirection(str, Enum):
    """Direction of the option buying intent."""
    BUY_CE = "BUY_CE"  # Bullish index intent -> Buy Near-the-Money Call Option
    BUY_PE = "BUY_PE"  # Bearish index intent -> Buy Near-the-Money Put Option


class ExecutionOutcomeType(str, Enum):
    """Categorization of intraday execution resolution."""
    NO_SIGNAL = "NO_SIGNAL"
    REJECTED_ENTRY = "REJECTED_ENTRY"                     # Cutoff breached, contract selector failed
    UNFILLED_ENTRY = "UNFILLED_ENTRY"                     # Option bar missing at T+1 (EXPIRED_UNFILLED_NO_LIQUIDITY_BAR)
    EXECUTED_CLEAN = "EXECUTED_CLEAN"                     # Standard clean trade
    EXECUTED_QUARANTINED = "EXECUTED_QUARANTINED"         # Trade with missing intermediate candles


@dataclass(frozen=True)
class StrategySignal:
    """
    Standardized, immutable trade signal emitted by a strategy plugin.
    """
    signal_id: str                      # Unique identifier (e.g., "SIG-ORB-20251001-0935")
    strategy_id: str                    # Registered strategy code (e.g., "STRAT-ORB-15M")
    signal_timestamp_ist: datetime      # Timestamp of the closed index bar that generated the signal
    direction: SignalDirection          # BUY_CE or BUY_PE
    index_spot_price: Decimal           # Closing price of the signal index bar
    
    # Risk and Exit Parameters (Configured per Strategy)
    stop_loss_pct: Decimal = Decimal("0.15")              # Option stop-loss threshold (e.g., Decimal("0.15") for 15%)
    profit_target_pct: Decimal = Decimal("0.20")          # Option profit target threshold (e.g., Decimal("0.20") for 20%)
    max_holding_minutes: int = 45                         # Maximum duration before forced time-based exit
    entry_cutoff_time: time = time(14, 30, 0)             # Hard time cutoff for simulated entry fill (e.g., 14:30:00)
    
    # Metadata & Auditing
    trigger_reason: str = ""                              # Human-readable trigger explanation
    metadata: Dict[str, Any] = field(default_factory=dict) # Strategy-specific indicator values at trigger minute


@dataclass(frozen=True)
class SessionContext:
    """
    Contextual information provided to the strategy at session start and during bar evaluation.
    """
    trading_day: date                   # Active session date
    is_expiry_day: bool                 # True if today is the scheduled weekly expiry
    nearest_expiry: date                # Current active weekly expiry date
    initial_capital: Decimal            # Available capital at session open
    max_trades_per_session: int = 1     # Global platform restriction


@dataclass(frozen=True)
class BaseStrategyConfig:
    """Base dataclass for strategy configuration."""
    strategy_id: str
    strategy_name: str
    strategy_version: str = "1.0.0"
    minimum_warmup_bars: int = 15
    entry_window_start: time = time(9, 30, 0)
    entry_window_end: time = time(14, 30, 0)
    stop_loss_pct: Decimal = Decimal("0.15")
    profit_target_pct: Decimal = Decimal("0.20")
    max_holding_minutes: int = 45


class BaseNiftyOptionStrategy(ABC):
    """
    Abstract base class for all deterministic NIFTY options-buying research strategies.
    """

    def __init__(self, config: BaseStrategyConfig):
        self.config = config
        self.strategy_id: str = config.strategy_id
        self.strategy_name: str = config.strategy_name
        self.strategy_version: str = config.strategy_version

    @abstractmethod
    def initialize_session(self, context: SessionContext) -> None:
        """
        Called at 09:15:00 IST before the first bar of each trading session.
        Resets all intraday indicator accumulators, rolling windows, and state flags.
        """
        pass

    def evaluate_session_qualification(
        self,
        index_bars: List[Dict[str, Any]],
        context: SessionContext,
    ) -> Tuple[bool, Optional[str], Optional[SessionQualification]]:
        """
        Evaluates pre-trading strategy-specific session qualifications or filters.
        Returns:
            Tuple of (is_qualified, rejection_reason, qualification_enum)
        Default implementation qualifies all sessions that passed core data gating.
        """
        return True, None, None

    @abstractmethod
    def on_index_bar(
        self,
        bar: Dict[str, Any],
        context: SessionContext,
    ) -> Optional[StrategySignal]:
        """
        Processes a single closed 1-minute NIFTY index bar.
        
        Args:
            bar: Dict containing 'timestamp_ist', 'open', 'high', 'low', 'close', 'volume'.
            context: SessionContext for the current trading day.
            
        Returns:
            StrategySignal if an entry trigger condition is satisfied; otherwise None.
        """
        pass

    def on_session_complete(self, context: SessionContext) -> None:
        """
        Optional teardown hook called at 15:30:00 IST after session replay finishes.
        """
        pass
