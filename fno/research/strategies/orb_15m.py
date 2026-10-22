"""
Nomad Analyst — NIFTY 15-Minute Opening Range Breakout Strategy Plugin
Reference: docs/architecture/strategy_interface_v1.md
"""

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fno.backtester.models import SessionQualification
from fno.research.interfaces import (
    BaseNiftyOptionStrategy,
    BaseStrategyConfig,
    SessionContext,
    SignalDirection,
    StrategySignal,
)


@dataclass(frozen=True)
class OrbStrategyConfig(BaseStrategyConfig):
    """Configuration for NIFTY 15-minute Opening Range Breakout."""
    strategy_id: str = "STRAT-ORB-15M"
    strategy_name: str = "NIFTY 15m Opening Range Breakout"
    strategy_version: str = "1.0.0"
    orb_period_minutes: int = 15
    min_orb_range_pts: Decimal = Decimal("15.00")
    max_orb_range_pts: Optional[Decimal] = Decimal("150.00")
    stop_loss_pct: Decimal = Decimal("0.15")
    profit_target_pct: Decimal = Decimal("0.20")
    max_holding_minutes: int = 45
    entry_window_start: time = time(9, 30, 0)
    entry_window_end: time = time(14, 30, 0)
    minimum_warmup_bars: int = 15


class NiftyOrbStrategyPlugin(BaseNiftyOptionStrategy):
    """
    Deterministic NIFTY 15-minute ORB strategy plugin.
    Evaluates index breakout above ORB High (CE) or below ORB Low (PE).
    """

    def __init__(self, config: Optional[OrbStrategyConfig] = None):
        super().__init__(config or OrbStrategyConfig())
        self.config: OrbStrategyConfig = self.config
        self._orb_high: Optional[Decimal] = None
        self._orb_low: Optional[Decimal] = None
        self._orb_range: Optional[Decimal] = None
        self._signal_emitted: bool = False

    def initialize_session(self, context: SessionContext) -> None:
        """Resets daily ORB tracking state."""
        self._orb_high = None
        self._orb_low = None
        self._orb_range = None
        self._signal_emitted = False

    @property
    def orb_high(self) -> Optional[Decimal]:
        return self._orb_high

    @property
    def orb_low(self) -> Optional[Decimal]:
        return self._orb_low

    @property
    def orb_range(self) -> Optional[Decimal]:
        return self._orb_range

    def evaluate_session_qualification(
        self,
        index_bars: List[Dict[str, Any]],
        context: SessionContext,
    ) -> Tuple[bool, Optional[str], Optional[SessionQualification]]:
        """
        Evaluates the 15-minute opening range (09:15:00 to 09:29:59 IST)
        and validates against min and max width filters.
        """
        orb_bars = [
            b for b in index_bars
            if time(9, 15) <= b["timestamp_ist"].time() < time(9, 30)
        ]
        if len(orb_bars) < self.config.orb_period_minutes:
            return (
                False,
                f"Missing bars in 15M ORB window ({len(orb_bars)} < {self.config.orb_period_minutes})",
                SessionQualification.EXCLUDED_DATA_GAP,
            )

        orb_high = max(b["high"] for b in orb_bars)
        orb_low = min(b["low"] for b in orb_bars)
        orb_range = orb_high - orb_low

        self._orb_high = orb_high
        self._orb_low = orb_low
        self._orb_range = orb_range

        if orb_range < self.config.min_orb_range_pts:
            return (
                False,
                f"ORB width {orb_range} < {self.config.min_orb_range_pts} pts",
                SessionQualification.EXCLUDED_RANGE_TOO_NARROW,
            )

        if self.config.max_orb_range_pts is not None and orb_range > self.config.max_orb_range_pts:
            return (
                False,
                f"ORB width {orb_range} > {self.config.max_orb_range_pts} pts",
                SessionQualification.EXCLUDED_RANGE_TOO_WIDE,
            )

        return True, None, None

    def on_index_bar(
        self,
        bar: Dict[str, Any],
        context: SessionContext,
    ) -> Optional[StrategySignal]:
        """
        Evaluates post-ORB index bars for opening range breakouts.
        """
        if self._signal_emitted:
            return None

        bar_time = bar["timestamp_ist"].time()
        if bar_time < self.config.entry_window_start:
            return None

        if self._orb_high is None or self._orb_low is None:
            return None

        close_price = bar["close"]

        if close_price > self._orb_high:
            self._signal_emitted = True
            return StrategySignal(
                signal_id=f"SIG-ORB-{context.trading_day.strftime('%Y%m%d')}-{bar['timestamp_ist'].strftime('%H%M')}",
                strategy_id=self.strategy_id,
                signal_timestamp_ist=bar["timestamp_ist"],
                direction=SignalDirection.BUY_CE,
                index_spot_price=close_price,
                stop_loss_pct=self.config.stop_loss_pct,
                profit_target_pct=self.config.profit_target_pct,
                max_holding_minutes=self.config.max_holding_minutes,
                entry_cutoff_time=self.config.entry_window_end,
                trigger_reason=f"ORB High Breakout: {close_price} > {self._orb_high}",
                metadata={
                    "orb_high": str(self._orb_high),
                    "orb_low": str(self._orb_low),
                    "orb_range": str(self._orb_range),
                },
            )

        if close_price < self._orb_low:
            self._signal_emitted = True
            return StrategySignal(
                signal_id=f"SIG-ORB-{context.trading_day.strftime('%Y%m%d')}-{bar['timestamp_ist'].strftime('%H%M')}",
                strategy_id=self.strategy_id,
                signal_timestamp_ist=bar["timestamp_ist"],
                direction=SignalDirection.BUY_PE,
                index_spot_price=close_price,
                stop_loss_pct=self.config.stop_loss_pct,
                profit_target_pct=self.config.profit_target_pct,
                max_holding_minutes=self.config.max_holding_minutes,
                entry_cutoff_time=self.config.entry_window_end,
                trigger_reason=f"ORB Low Breakout: {close_price} < {self._orb_low}",
                metadata={
                    "orb_high": str(self._orb_high),
                    "orb_low": str(self._orb_low),
                    "orb_range": str(self._orb_range),
                },
            )

        return None
