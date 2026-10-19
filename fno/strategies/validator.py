"""
Nomad Analyst — F&O Strategy Signal Validation Engine
Reference: Phase 22C Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Validates data quality, quote freshness, bar completeness, and signal risk constraints
before signals can be forwarded to the paper execution engine.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from fno.services.feature_engine import OptionFeatureSnapshot
from fno.strategies.base import OptionSignal


@dataclass(frozen=True)
class SignalValidationResult:
    is_valid: bool
    rejection_code: Optional[str] = None  # e.g., "REJECTED_STALE_QUOTE", "REJECTED_LOCKED_QUOTE", etc.
    rejection_reason: Optional[str] = None


class SignalValidator:
    """
    Enforces strict risk, microstructure, and freshness gates on signals.
    """

    ALLOWED_ACTIONS = {
        "BUY_TO_OPEN",
        "EXIT_TARGET",
        "EXIT_STOP",
        "EXIT_TIME",
        "EXIT_EOD",
    }
    ALLOWED_OPTION_TYPES = {"CE", "PE"}

    def validate_snapshot_eligibility(
        self,
        snapshot: OptionFeatureSnapshot,
    ) -> SignalValidationResult:
        """
        Validates feature snapshot before a strategy can use it for signal generation.
        """
        if snapshot.is_partial_bar:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_PARTIAL_BAR",
                rejection_reason="Bar interval overlapped a reconnect gap or partial bar interval.",
            )

        if snapshot.is_stale:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_STALE_QUOTE",
                rejection_reason=f"Quote age ({snapshot.quote_age_seconds}s) exceeds 3.0s freshness limit.",
            )

        if snapshot.is_locked:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_LOCKED_QUOTE",
                rejection_reason="Best bid and ask are equal (locked book).",
            )

        if snapshot.is_crossed:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_CROSSED_BOOK",
                rejection_reason="Best bid exceeds best ask (crossed book arbitrage anomaly).",
            )

        if snapshot.exchange_time_status != "VALID":
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_UNVERIFIED_TIMESTAMP",
                rejection_reason=f"Exchange time status is {snapshot.exchange_time_status}.",
            )

        if snapshot.quote_status == "ZERO_BID":
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_ZERO_BID",
                rejection_reason="Quote order book has zero bid liquidity.",
            )

        if snapshot.quote_status == "EMPTY_BOOK":
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_EMPTY_BOOK",
                rejection_reason="Quote book is completely empty.",
            )

        if snapshot.spread_percentage is not None and snapshot.spread_percentage > Decimal("0.025"):
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_EXCESSIVE_SPREAD",
                rejection_reason=f"Bid-ask spread ({snapshot.spread_percentage * 100:.2f}%) exceeds 2.5% max threshold.",
            )

        if not snapshot.is_valid_for_signal:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_FEATURE_INVALID",
                rejection_reason="Snapshot failed core engine feature validity criteria.",
            )

        return SignalValidationResult(is_valid=True)

    def validate_signal(
        self,
        signal: OptionSignal,
        snapshot: OptionFeatureSnapshot,
    ) -> SignalValidationResult:
        """
        Validates emitted signal against scope rules and snapshot consistency.
        Initial authorized scope: Long NIFTY index CE/PE buying only.
        """
        # 1. Action & Option Type Scope
        if signal.action not in self.ALLOWED_ACTIONS:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_UNSUPPORTED_ACTION",
                rejection_reason=f"Action '{signal.action}' is outside authorized trading scope.",
            )

        if signal.option_type not in self.ALLOWED_OPTION_TYPES:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_UNSUPPORTED_OPTION_TYPE",
                rejection_reason=f"Option type '{signal.option_type}' must be CE or PE.",
            )

        # 2. Lot Count Gate
        if signal.suggested_lot_count < 1:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_INVALID_QUANTITY",
                rejection_reason=f"Lot count must be >= 1 (got {signal.suggested_lot_count}).",
            )

        # 3. Snapshot linkage check
        if signal.snapshot_reference_id != snapshot.snapshot_id:
            return SignalValidationResult(
                is_valid=False,
                rejection_code="REJECTED_SNAPSHOT_MISMATCH",
                rejection_reason="Signal reference ID does not match current snapshot ID.",
            )

        # 4. Entry-Specific Gating
        if signal.action == "BUY_TO_OPEN":
            # Must validate snapshot eligibility
            snap_val = self.validate_snapshot_eligibility(snapshot)
            if not snap_val.is_valid:
                return snap_val

            # Price hint validation
            entry_ref = signal.limit_price_hint or snapshot.best_ask or snapshot.premium_close
            if entry_ref <= Decimal("0.0"):
                return SignalValidationResult(
                    is_valid=False,
                    rejection_code="REJECTED_INVALID_PRICE",
                    rejection_reason="Reference entry price must be greater than zero.",
                )

            # Stop loss must be below entry for long options
            if signal.stop_loss_premium is not None:
                if signal.stop_loss_premium >= entry_ref:
                    return SignalValidationResult(
                        is_valid=False,
                        rejection_code="REJECTED_INVALID_STOP_LOSS",
                        rejection_reason=f"Stop loss ({signal.stop_loss_premium}) must be below entry ({entry_ref}).",
                    )
                if signal.stop_loss_premium <= Decimal("0.0"):
                    return SignalValidationResult(
                        is_valid=False,
                        rejection_code="REJECTED_INVALID_STOP_LOSS",
                        rejection_reason="Stop loss must be strictly positive.",
                    )

            # Profit target must be above entry for long options
            if signal.profit_target_premium is not None:
                if signal.profit_target_premium <= entry_ref:
                    return SignalValidationResult(
                        is_valid=False,
                        rejection_code="REJECTED_INVALID_PROFIT_TARGET",
                        rejection_reason=f"Profit target ({signal.profit_target_premium}) must be above entry ({entry_ref}).",
                    )

        return SignalValidationResult(is_valid=True)
