"""
Nomad Analyst — Conservative Historical Options Taker Execution Simulator
Reference: Sections 4, 5, 6 in docs/historical_options_backtester_architecture.md
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import zoneinfo

from fno.backtester.fee_model import HistoricalFeeCalculator
from fno.backtester.models import BacktestConfig, BacktestTradeRecord, DataQualityIncident
from fno.execution.paper_engine import round_to_tick

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class HistoricalExecutionSimulator:
    """
    Simulates realistic taker order execution over historical 1-minute OHLCV candles
    with tick-grid ceiling/floor rounding, fill-time cutoff gating, and missing candle tracking.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.tick_size = config.tick_size
        self.slippage_rate = config.slippage_rate
        self.fee_calculator = HistoricalFeeCalculator()

    def simulate_entry_fill(
        self,
        signal_timestamp: datetime,
        fill_candle: Optional[Dict[str, Any]],
        contract_info: Dict[str, Any],
        cash_balance: Decimal,
        spot_at_signal: Decimal,
        orb_high: Decimal,
        orb_low: Decimal,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[DataQualityIncident]]:
        """
        Simulates entry taker fill at candle open with tick-grid ceiling rounding.
        Enforces fill-timestamp entry window cutoff (T_fill <= 14:30:00 IST).
        Returns: (active_position_dict, rejection_reason, incident_list)
        """
        incidents: List[DataQualityIncident] = []

        # 1. Missing candle at entry time -> No phantom fills
        if fill_candle is None:
            return None, "EXPIRED_UNFILLED_NO_LIQUIDITY_BAR", incidents

        fill_time_ist = fill_candle["timestamp_ist"]

        # 2. Hard Gate: Simulated fill timestamp must be <= entry_window_end (14:30:00 IST)
        if fill_time_ist.time() > self.config.entry_window_end:
            return None, "REJECTED_FILL_PAST_ENTRY_CUTOFF", incidents

        # 3. Calculate Taker Buy Fill Price: round UP to next tick
        open_price = Decimal(str(fill_candle["open"]))
        if self.config.slippage_model == "FIXED_POINTS":
            base_fill = open_price + self.config.fixed_slippage_pts
        else:
            base_fill = open_price * (Decimal("1.0") + self.slippage_rate)
        entry_fill_price = round_to_tick(base_fill, tick_size=self.tick_size, direction="CEILING")

        lot_size = contract_info["lot_size"]
        quantity = lot_size * self.config.num_lots

        # 4. Affordability Gate
        premium_required = entry_fill_price * Decimal(str(quantity))
        estimated_frictions = Decimal("70.00")
        if cash_balance < (premium_required + estimated_frictions):
            return None, "REJECTED_INSUFFICIENT_CAPITAL", incidents

        # 5. Position Initialized
        stop_loss_price = round_to_tick(
            entry_fill_price * (Decimal("1.0") - self.config.stop_loss_pct),
            tick_size=self.tick_size,
            direction="FLOOR",
        )
        profit_target_price = round_to_tick(
            entry_fill_price * (Decimal("1.0") + self.config.profit_target_pct),
            tick_size=self.tick_size,
            direction="CEILING",
        )

        position = {
            "trade_id": str(uuid.uuid4()),
            "trading_day": str(fill_time_ist.date()),
            "contract_info": contract_info,
            "lot_size": lot_size,
            "quantity": quantity,
            "signal_timestamp_ist": signal_timestamp,
            "entry_timestamp_ist": fill_time_ist,
            "spot_at_signal": spot_at_signal,
            "spot_at_entry": Decimal(str(fill_candle.get("spot_price", spot_at_signal))),
            "orb_high": orb_high,
            "orb_low": orb_low,
            "entry_fill_price": entry_fill_price,
            "stop_loss_price": stop_loss_price,
            "profit_target_price": profit_target_price,
            "execution_liquidity_impaired": False,
            "data_quality_incidents": [],
            "pending_exit": None,
        }
        return position, None, incidents

    def evaluate_active_position(
        self,
        position: Dict[str, Any],
        current_candle: Optional[Dict[str, Any]],
        current_time_ist: datetime,
        is_expiry_day: bool,
        official_index_close: Optional[Decimal] = None,
    ) -> Tuple[Optional[BacktestTradeRecord], Optional[DataQualityIncident]]:
        """
        Monitors an open position across 1-minute intervals.
        Evaluates Stop Loss, Profit Target, Max Holding Duration, EOD square-off,
        and Emergency Expiry Cash Settlement.
        """
        incident: Optional[DataQualityIncident] = None

        # 1. Handle Missing Intermediate Option Candle
        if current_candle is None:
            position["execution_liquidity_impaired"] = True
            incident = DataQualityIncident(
                trading_day=position["trading_day"],
                timestamp_ist=current_time_ist.isoformat(),
                tradingsymbol=position["contract_info"]["tradingsymbol"],
                incident_type="DATA_QUALITY_INCIDENT_MISSING_CANDLES",
                details=f"Missing 1-minute candle during open position at {current_time_ist.strftime('%H:%M:%S')}. Risk checks unobserved.",
            )
            position["data_quality_incidents"].append("MISSING_INTERMEDIATE_CANDLE")

            # Check if pending exit is waiting for a fill candle
            if position.get("pending_exit"):
                # If market has closed without another candle:
                if current_time_ist.time() >= time(15, 30, 0):
                    return self._finalize_unexecutable_or_settlement(
                        position=position,
                        exit_time_ist=current_time_ist,
                        is_expiry_day=is_expiry_day,
                        official_index_close=official_index_close,
                    ), incident
            return None, incident

        candle_time = current_candle["timestamp_ist"]
        bar_open = Decimal(str(current_candle["open"]))
        bar_high = Decimal(str(current_candle["high"]))
        bar_low = Decimal(str(current_candle["low"]))
        bar_close = Decimal(str(current_candle["close"]))

        # 2. Check if a Pending Exit from previous gap can now fill on this bar's open
        if position.get("pending_exit"):
            exit_reason = position["pending_exit"]
            fill_price = self._compute_taker_exit_fill(bar_open)
            return self._build_trade_record(
                position=position,
                exit_time_ist=candle_time,
                exit_price=fill_price,
                exit_reason=exit_reason,
                spot_at_exit=Decimal(str(current_candle.get("spot_price", position["spot_at_entry"]))),
                is_emergency_settlement=False,
            ), incident

        # 3. Mandatory EOD Square-off (15:15 IST)
        if candle_time.time() >= self.config.eod_square_off_time:
            exit_price = self._compute_taker_exit_fill(bar_open)
            return self._build_trade_record(
                position=position,
                exit_time_ist=candle_time,
                exit_price=exit_price,
                exit_reason="EXIT_EOD",
                spot_at_exit=Decimal(str(current_candle.get("spot_price", position["spot_at_entry"]))),
                is_emergency_settlement=False,
            ), incident

        # 4. Max Holding Duration Check (45 Minutes)
        holding_sec = (candle_time - position["entry_timestamp_ist"]).total_seconds()
        if holding_sec >= (self.config.max_holding_minutes * 60):
            exit_price = self._compute_taker_exit_fill(bar_open)
            return self._build_trade_record(
                position=position,
                exit_time_ist=candle_time,
                exit_price=exit_price,
                exit_reason="EXIT_TIME",
                spot_at_exit=Decimal(str(current_candle.get("spot_price", position["spot_at_entry"]))),
                is_emergency_settlement=False,
            ), incident

        # 5. Stop Loss & Profit Target Evaluation
        stop_price = position["stop_loss_price"]
        target_price = position["profit_target_price"]

        touches_stop = (bar_low <= stop_price)
        touches_target = (bar_high >= target_price)

        # Simultaneous Touch: Worst-case priority -> Stop Loss triggers first
        if touches_stop:
            trigger_ref = min(bar_open, stop_price) if bar_open < stop_price else stop_price
            exit_price = self._compute_taker_exit_fill(trigger_ref)
            return self._build_trade_record(
                position=position,
                exit_time_ist=candle_time,
                exit_price=exit_price,
                exit_reason="EXIT_STOP",
                spot_at_exit=Decimal(str(current_candle.get("spot_price", position["spot_at_entry"]))),
                is_emergency_settlement=False,
            ), incident

        if touches_target:
            trigger_ref = max(bar_open, target_price) if bar_open > target_price else target_price
            exit_price = self._compute_taker_exit_fill(trigger_ref)
            return self._build_trade_record(
                position=position,
                exit_time_ist=candle_time,
                exit_price=exit_price,
                exit_reason="EXIT_TARGET",
                spot_at_exit=Decimal(str(current_candle.get("spot_price", position["spot_at_entry"]))),
                is_emergency_settlement=False,
            ), incident

        return None, incident

    def _compute_taker_exit_fill(self, base_price: Decimal) -> Decimal:
        """Computes taker sell fill price with slippage rounded DOWN (floor) to tick grid."""
        if self.config.slippage_model == "FIXED_POINTS":
            raw_price = base_price - self.config.fixed_slippage_pts
        else:
            raw_price = base_price * (Decimal("1.0") - self.slippage_rate)
        if raw_price < self.tick_size:
            raw_price = self.tick_size
        return round_to_tick(raw_price, tick_size=self.tick_size, direction="FLOOR")

    def _finalize_unexecutable_or_settlement(
        self,
        position: Dict[str, Any],
        exit_time_ist: datetime,
        is_expiry_day: bool,
        official_index_close: Optional[Decimal],
    ) -> BacktestTradeRecord:
        """Finalizes an unresolved position at 15:30:00 session close."""
        contract = position["contract_info"]
        strike = contract["strike"]
        opt_type = contract["option_type"]

        if is_expiry_day and official_index_close is not None:
            # Emergency Expiry Cash Settlement against official underlying index close
            if opt_type == "CE":
                intrinsic = max(Decimal("0.00"), official_index_close - Decimal(str(strike)))
            else:
                intrinsic = max(Decimal("0.00"), Decimal(str(strike)) - official_index_close)

            settlement_price = round_to_tick(intrinsic, tick_size=self.tick_size, direction="FLOOR")
            return self._build_trade_record(
                position=position,
                exit_time_ist=exit_time_ist,
                exit_price=settlement_price,
                exit_reason="SETTLED_EXPIRY_CASH_FALLBACK",
                spot_at_exit=official_index_close,
                is_emergency_settlement=True,
            )

        # Non-expiry unexecutable carry defect
        # Penalty assumption: marked at 0.05 or entry loss
        penalty_exit = self.tick_size
        position["execution_liquidity_impaired"] = True
        return self._build_trade_record(
            position=position,
            exit_time_ist=exit_time_ist,
            exit_price=penalty_exit,
            exit_reason="UNEXECUTABLE_OVERNIGHT_CARRY",
            spot_at_exit=official_index_close or position["spot_at_entry"],
            is_emergency_settlement=False,
        )

    def _build_trade_record(
        self,
        position: Dict[str, Any],
        exit_time_ist: datetime,
        exit_price: Decimal,
        exit_reason: str,
        spot_at_exit: Decimal,
        is_emergency_settlement: bool,
    ) -> BacktestTradeRecord:
        """Constructs an immutable BacktestTradeRecord with exact fee calculations."""
        contract = position["contract_info"]
        quantity = position["quantity"]
        entry_price = position["entry_fill_price"]
        trade_date = position["entry_timestamp_ist"].date()

        qty_dec = Decimal(str(quantity))
        gross_pnl = (exit_price - entry_price) * qty_dec

        # Statutory Fees & Levies
        fee_breakdown = self.fee_calculator.calculate_round_trip(
            buy_price=entry_price,
            sell_price=exit_price,
            quantity=quantity,
            trade_date=trade_date,
            is_exercise_settlement=is_emergency_settlement,
            custom_brokerage_per_order=self.config.brokerage_per_order,
        )

        net_pnl = gross_pnl - fee_breakdown.total_frictions
        capital_invested = entry_price * qty_dec
        net_return_pct = (net_pnl / capital_invested * Decimal("100.0")) if capital_invested > 0 else Decimal("0.00")

        holding_sec = (exit_time_ist - position["entry_timestamp_ist"]).total_seconds()
        stt_rate = self.fee_calculator.get_stt_rates_for_date(trade_date, is_exercise=is_emergency_settlement)

        return BacktestTradeRecord(
            trade_id=position["trade_id"],
            trading_day=position["trading_day"],
            strategy_id=self.config.strategy_id,
            strategy_version=self.config.strategy_version,
            tradingsymbol=contract.get("tradingsymbol", ""),
            underlying_symbol=contract.get("symbol", "NIFTY"),
            strike=contract["strike"],
            option_type=contract["option_type"],
            expiry=contract["expiry"],
            lot_size=position["lot_size"],
            quantity=quantity,
            signal_timestamp_ist=position["signal_timestamp_ist"],
            entry_timestamp_ist=position["entry_timestamp_ist"],
            exit_timestamp_ist=exit_time_ist,
            holding_duration_seconds=holding_sec,
            orb_high=position["orb_high"],
            orb_low=position["orb_low"],
            spot_at_signal=position["spot_at_signal"],
            spot_at_entry=position["spot_at_entry"],
            spot_at_exit=spot_at_exit,
            entry_fill_price=entry_price,
            exit_fill_price=exit_price,
            gross_pnl=gross_pnl,
            statutory_fees=fee_breakdown,
            net_pnl=net_pnl,
            net_return_pct=net_return_pct,
            exit_reason=exit_reason,
            session_qualification="QUALIFIED_FULL_SESSION",
            slippage_rate=self.slippage_rate,
            slippage_model=self.config.slippage_model,
            stt_rate_applied=stt_rate,
            is_emergency_expiry_settlement=is_emergency_settlement,
            execution_liquidity_impaired=position["execution_liquidity_impaired"],
            data_quality_incidents=position["data_quality_incidents"],
        )
