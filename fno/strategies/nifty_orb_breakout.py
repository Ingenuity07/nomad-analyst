"""
Nomad Analyst — NIFTY 15-Minute Opening Range Breakout (ORB) Option Buying Strategy
Reference: Phase 22C Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Strategy Rules & Quantitative Assumptions:
1. Target Scope: NIFTY 50 Index ATM/near-ITM weekly CE/PE buying only.
2. Opening Range: High and Low established between 09:15:00 and 09:30:00 IST.
3. Bullish Breakout: Spot > Opening Range High -> Buy ATM CE.
4. Bearish Breakout: Spot < Opening Range Low -> Buy ATM PE.
5. Permitted Entry Window: 09:30:00 to 14:30:00 IST.
6. Risk Envelope:
   - Stop Loss: Entry Ask - 15%.
   - Profit Target: Entry Ask + 20%.
   - Max Holding Duration: 45 minutes.
   - Mandatory EOD Square-off: 15:15:00 IST.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, Optional
import zoneinfo

from fno.services.feature_engine import OptionFeatureSnapshot
from fno.strategies.base import BaseStrategy, OptionSignal, PaperTradeEvent

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class NiftyOrbBreakoutStrategy(BaseStrategy):
    """
    Isolated 15-Minute Opening Range Breakout buyer for NIFTY Index Options.
    """
    strategy_id = "STRAT-ORB-15M"
    strategy_name = "NIFTY 15m Opening Range Breakout"
    strategy_version = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.opening_range_high: Optional[Decimal] = None
        self.opening_range_low: Optional[Decimal] = None
        self.opening_range_established: bool = False
        self.opening_range_session_date: Optional[date] = None
        self.active_position: Optional[Dict[str, Any]] = None
        self.entry_window_start = time(9, 30, 0)
        self.entry_window_end = time(14, 30, 0)
        self.sync_active_position_from_db()

    def sync_active_position_from_db(self) -> Optional[Dict[str, Any]]:
        """
        Synchronizes in-memory active position state from PaperTradeLedger.
        Recovers any unresolved trade upon startup/restart to prevent duplicate entries.
        """
        try:
            from fno.models import PaperTradeLedger
            trade = PaperTradeLedger.objects.filter(
                strategy_id=self.strategy_id,
                status__in=[
                    "OPEN",
                    "PENDING_LIQUIDITY",
                    "UNEXECUTABLE_OVERNIGHT_CARRY",
                    "PENDING_EXPIRY_SETTLEMENT",
                ]
            ).order_by("-entry_timestamp").first()
            if trade and trade.entry_fill_price is not None:
                ref_fill = trade.entry_fill_price
                self.active_position = {
                    "tradingsymbol": trade.tradingsymbol,
                    "entry_fill_price": ref_fill,
                    "quantity": trade.quantity,
                    "entry_time": trade.entry_timestamp.astimezone(IST),
                    "stop_loss": ref_fill * (Decimal("1.0") - self.config.stop_loss_pct),
                    "profit_target": ref_fill * (Decimal("1.0") + self.config.profit_target_pct),
                }
                return self.active_position
            else:
                self.active_position = None
                return None
        except Exception:
            return None

    def set_opening_range(self, high: Decimal, low: Decimal, session_date: Optional[date] = None) -> None:
        """Manually or externally seeds the 15-minute opening range boundaries for a session date."""
        self.opening_range_high = high
        self.opening_range_low = low
        self.opening_range_established = True
        self.opening_range_session_date = session_date

    def on_feature_snapshot(
        self,
        snapshot: OptionFeatureSnapshot,
    ) -> Optional[OptionSignal]:
        """
        Evaluates incoming feature snapshot for entry and exit signals.
        """
        if not self.is_enabled:
            return None

        # Convert snapshot calculation time to IST
        now_ist = snapshot.calculation_timestamp_utc.astimezone(IST)
        current_time = now_ist.time()

        # Update opening range during 09:15 to 09:30 IST if not pre-seeded
        if time(9, 15, 0) <= current_time < self.entry_window_start:
            spot = snapshot.underlying_spot_price
            if self.opening_range_high is None or spot > self.opening_range_high:
                self.opening_range_high = spot
            if self.opening_range_low is None or spot < self.opening_range_low:
                self.opening_range_low = spot
            return None

        if current_time >= self.entry_window_start and not self.opening_range_established:
            if self.opening_range_high is not None and self.opening_range_low is not None:
                self.opening_range_established = True

        # --- Exit Rules Evaluation for Active Position ---
        if self.active_position is not None:
            if self.active_position["tradingsymbol"] == snapshot.tradingsymbol:
                curr_bid = snapshot.best_bid or snapshot.premium_close
                entry_fill = self.active_position["entry_fill_price"]
                entry_time = self.active_position["entry_time"]
                stop_loss = self.active_position["stop_loss"]
                profit_target = self.active_position["profit_target"]

                # 1. EOD Square-off
                if current_time >= self.config.eod_square_off_time:
                    return self._create_exit_signal(
                        snapshot,
                        action="EXIT_EOD",
                        rationale="Mandatory 15:15 IST policy square-off reached.",
                    )

                # 2. Max holding time
                holding_minutes = (now_ist - entry_time).total_seconds() / 60.0
                if holding_minutes >= self.config.max_holding_minutes:
                    return self._create_exit_signal(
                        snapshot,
                        action="EXIT_TIME",
                        rationale=f"Max holding duration ({self.config.max_holding_minutes}m) exceeded.",
                    )

                # 3. Stop Loss
                if curr_bid <= stop_loss:
                    return self._create_exit_signal(
                        snapshot,
                        action="EXIT_STOP",
                        rationale=f"Current bid {curr_bid} breached stop loss {stop_loss}.",
                    )

                # 4. Profit Target
                if curr_bid >= profit_target:
                    return self._create_exit_signal(
                        snapshot,
                        action="EXIT_TARGET",
                        rationale=f"Current bid {curr_bid} reached profit target {profit_target}.",
                    )

            # Do not generate entries while holding an active position
            return None

        # --- Entry Rules Evaluation ---
        if not (self.entry_window_start <= current_time <= self.entry_window_end):
            return None

        if not self.opening_range_established or self.opening_range_high is None or self.opening_range_low is None:
            return None

        # Gating: must be valid for signal
        if not snapshot.is_valid_for_signal:
            return None

        # Only evaluate ATM or near ITM strikes
        if snapshot.moneyness_category not in ("ATM", "ITM"):
            return None

        spot = snapshot.underlying_spot_price
        opt_type = snapshot.option_type.upper()

        # Bullish Breakout -> Buy CE
        is_bullish_entry = (spot > self.opening_range_high) and (opt_type == "CE")

        # Bearish Breakout -> Buy PE
        is_bearish_entry = (spot < self.opening_range_low) and (opt_type == "PE")

        if not (is_bullish_entry or is_bearish_entry):
            return None

        ref_price = snapshot.best_ask or snapshot.premium_close
        stop_loss = ref_price * (Decimal("1.0") - self.config.stop_loss_pct)
        profit_target = ref_price * (Decimal("1.0") + self.config.profit_target_pct)

        rule_name = "ORB_BULLISH_CE_BREAKOUT" if is_bullish_entry else "ORB_BEARISH_PE_BREAKOUT"
        breakout_barrier = self.opening_range_high if is_bullish_entry else self.opening_range_low
        rationale = f"{rule_name}: Spot {spot} breached 15m range boundary {breakout_barrier}."

        return OptionSignal(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            tradingsymbol=snapshot.tradingsymbol,
            instrument_token=snapshot.instrument_token,
            underlying_symbol=snapshot.underlying_symbol,
            option_type=snapshot.option_type,
            strike_price=snapshot.strike_price,
            expiry_date=snapshot.expiry_date,
            action="BUY_TO_OPEN",
            suggested_lot_count=self.config.default_lot_count,
            limit_price_hint=ref_price,
            max_acceptable_slippage_pct=self.config.max_acceptable_slippage_pct,
            stop_loss_premium=Decimal(str(round(stop_loss, 2))),
            profit_target_premium=Decimal(str(round(profit_target, 2))),
            max_holding_minutes=self.config.max_holding_minutes,
            eod_square_off_time=self.config.eod_square_off_time,
            trigger_rule_name=rule_name,
            trigger_rationale=rationale,
            snapshot_reference_id=snapshot.snapshot_id,
        )

    def _create_exit_signal(
        self,
        snapshot: OptionFeatureSnapshot,
        action: str,
        rationale: str,
    ) -> OptionSignal:
        return OptionSignal(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            tradingsymbol=snapshot.tradingsymbol,
            instrument_token=snapshot.instrument_token,
            underlying_symbol=snapshot.underlying_symbol,
            option_type=snapshot.option_type,
            strike_price=snapshot.strike_price,
            expiry_date=snapshot.expiry_date,
            action=action,
            suggested_lot_count=self.config.default_lot_count,
            limit_price_hint=snapshot.best_bid,
            max_acceptable_slippage_pct=self.config.max_acceptable_slippage_pct,
            trigger_rule_name=action,
            trigger_rationale=rationale,
            snapshot_reference_id=snapshot.snapshot_id,
        )

    def on_trade_event(self, event: PaperTradeEvent) -> None:
        """Handles execution and ledger feedback."""
        if event.strategy_id != self.strategy_id:
            return

        if event.event_type == "ORDER_FILLED":
            if self.active_position is None and event.fill_price is not None:
                ref_fill = event.fill_price
                self.active_position = {
                    "tradingsymbol": event.tradingsymbol,
                    "entry_fill_price": ref_fill,
                    "quantity": event.fill_quantity,
                    "entry_time": event.timestamp.astimezone(IST),
                    "stop_loss": ref_fill * (Decimal("1.0") - self.config.stop_loss_pct),
                    "profit_target": ref_fill * (Decimal("1.0") + self.config.profit_target_pct),
                }
        elif event.event_type in ("POSITION_CLOSED", "SETTLEMENT"):
            self.active_position = None
        elif event.event_type == "ORDER_REJECTED":
            # Explicit confirmation: rejected orders never create or alter active position
            pass
