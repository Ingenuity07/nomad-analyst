"""
Nomad Analyst — F&O Strategy Manager
Reference: Phase 22C Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Orchestrates strategy registration, feature snapshot distribution, signal validation,
and rejection auditing across independent strategy modules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Callable, Dict, List, Optional

from fno.services.feature_engine import OptionFeatureSnapshot
from fno.strategies.base import BaseStrategy, OptionSignal, PaperTradeEvent
from fno.strategies.validator import SignalValidationResult, SignalValidator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignalAuditEntry:
    timestamp: datetime
    strategy_id: str
    signal_id: Optional[str]
    tradingsymbol: str
    action: str
    status: str  # "ACCEPTED", "REJECTED"
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None


class StrategyManager:
    """
    Coordinates execution of multiple isolated strategy modules.
    """

    def __init__(
        self,
        validator: Optional[SignalValidator] = None,
        on_signal_accepted: Optional[Callable[[OptionSignal], None]] = None,
    ):
        self.validator = validator or SignalValidator()
        self.on_signal_accepted = on_signal_accepted
        self.strategies: Dict[str, BaseStrategy] = {}
        self.audit_log: List[SignalAuditEntry] = []

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """Registers an independent strategy instance."""
        if strategy.strategy_id in self.strategies:
            logger.warning("Overwriting existing strategy registration: %s", strategy.strategy_id)
        self.strategies[strategy.strategy_id] = strategy
        logger.info("Registered F&O strategy: %s (%s v%s)", strategy.strategy_id, strategy.strategy_name, strategy.strategy_version)

    def unregister_strategy(self, strategy_id: str) -> None:
        """Removes a strategy from execution."""
        self.strategies.pop(strategy_id, None)

    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Retrieves a registered strategy."""
        return self.strategies.get(strategy_id)

    def process_feature_snapshot(
        self,
        snapshot: OptionFeatureSnapshot,
    ) -> List[OptionSignal]:
        """
        Enforces data quality & freshness before strategy evaluation.
        Distributes feature snapshot to registered, enabled strategies.
        Validates generated signals and returns accepted signals.
        """
        # 1. Enforce data-quality and freshness eligibility before evaluation
        snap_val = self.validator.validate_snapshot_eligibility(snapshot)
        if not snap_val.is_valid:
            audit = SignalAuditEntry(
                timestamp=datetime.now(timezone.utc),
                strategy_id="ALL",
                signal_id=None,
                tradingsymbol=snapshot.tradingsymbol,
                action="EVALUATION",
                status="REJECTED",
                rejection_code=snap_val.rejection_code,
                rejection_reason=snap_val.rejection_reason,
            )
            self.audit_log.append(audit)
            logger.info(
                "Snapshot %s (%s) ineligible for strategy evaluation: [%s] %s",
                snapshot.snapshot_id,
                snapshot.tradingsymbol,
                snap_val.rejection_code,
                snap_val.rejection_reason,
            )
            return []

        # 2. Distribute to enabled strategies
        accepted_signals: List[OptionSignal] = []

        for strat_id, strategy in self.strategies.items():
            if not strategy.is_enabled:
                continue

            try:
                signal = strategy.on_feature_snapshot(snapshot)
            except Exception as e:
                logger.error("Strategy %s raised an unhandled exception: %s", strat_id, e, exc_info=True)
                continue

            if signal is None:
                continue

            # 3. Validate signal through strict validation gate
            val_res = self.validator.validate_signal(signal, snapshot)

            if val_res.is_valid:
                audit = SignalAuditEntry(
                    timestamp=datetime.now(timezone.utc),
                    strategy_id=strat_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    action=signal.action,
                    status="ACCEPTED",
                )
                self.audit_log.append(audit)
                accepted_signals.append(signal)

                if self.on_signal_accepted:
                    try:
                        self.on_signal_accepted(signal)
                    except Exception as e:
                        logger.error("Error executing on_signal_accepted callback for %s: %s", signal.signal_id, e)
            else:
                audit = SignalAuditEntry(
                    timestamp=datetime.now(timezone.utc),
                    strategy_id=strat_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    action=signal.action,
                    status="REJECTED",
                    rejection_code=val_res.rejection_code,
                    rejection_reason=val_res.rejection_reason,
                )
                self.audit_log.append(audit)
                logger.info(
                    "Signal %s from %s rejected: [%s] %s",
                    signal.signal_id,
                    strat_id,
                    val_res.rejection_code,
                    val_res.rejection_reason,
                )

        return accepted_signals

    def broadcast_trade_event(self, event: PaperTradeEvent) -> None:
        """Dispatches execution event to the target strategy."""
        strategy = self.strategies.get(event.strategy_id)
        if strategy:
            try:
                strategy.on_trade_event(event)
            except Exception as e:
                logger.error("Error handling trade event in %s: %s", event.strategy_id, e)
