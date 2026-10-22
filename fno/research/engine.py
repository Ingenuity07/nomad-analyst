"""
Nomad Analyst — Multi-Strategy Historical Research Backtest Engine
Reference: docs/architecture/multi_strategy_research_engine_v1.md
"""

import dataclasses
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

from fno.backtester.calendar import NiftyExpiryCalendar
from fno.backtester.contract_selector import OptionContractSelector
from fno.backtester.engine import CachedHistoricalReader
from fno.backtester.execution_simulator import HistoricalExecutionSimulator
from fno.backtester.metrics import HistoricalPerformanceMetrics
from fno.backtester.models import (
    BacktestConfig,
    BacktestResultSet,
    BacktestTradeRecord,
    DataQualityIncident,
    SessionExecutionSummary,
    SessionQualification,
)
from fno.research.interfaces import (
    BaseNiftyOptionStrategy,
    ExecutionOutcomeType,
    SessionContext,
    SignalDirection,
    StrategySignal,
)
from fno.services.historical_reader import HistoricalParquetReader

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")


class MultiStrategyBacktestEngine:
    """
    Modular historical backtest engine that evaluates deterministic strategy plugins
    through a single, standardized, shared execution, cost, and reporting framework.
    """

    def __init__(
        self,
        strategy: BaseNiftyOptionStrategy,
        config: Optional[BacktestConfig] = None,
        reader: Optional[HistoricalParquetReader] = None,
        calendar: Optional[NiftyExpiryCalendar] = None,
        contract_selector: Optional[OptionContractSelector] = None,
        execution_simulator: Optional[HistoricalExecutionSimulator] = None,
    ):
        self.strategy = strategy
        base_config = config or BacktestConfig()
        strat_cfg = getattr(strategy, "config", None)
        if strat_cfg is not None:
            overrides = {}
            for field_name in (
                "strategy_id",
                "strategy_name",
                "strategy_version",
                "stop_loss_pct",
                "profit_target_pct",
                "max_holding_minutes",
                "entry_window_start",
                "entry_window_end",
            ):
                if hasattr(strat_cfg, field_name):
                    overrides[field_name] = getattr(strat_cfg, field_name)
            self.config = dataclasses.replace(base_config, **overrides)
        else:
            self.config = base_config

        raw_reader = reader or HistoricalParquetReader()
        if self.config.enable_query_cache and not isinstance(raw_reader, CachedHistoricalReader):
            self.reader = CachedHistoricalReader(raw_reader)
        else:
            self.reader = raw_reader
        self.calendar = calendar or NiftyExpiryCalendar(reader=self.reader)
        self.contract_selector = contract_selector or OptionContractSelector(
            calendar=self.calendar,
            roll_cutoff_time=self.config.roll_cutoff_time,
        )
        self.execution_simulator = execution_simulator or HistoricalExecutionSimulator(config=self.config)

    def run(self, calculate_sensitivity: bool = True) -> BacktestResultSet:
        """
        Executes the historical backtest for the configured strategy across all trading days.
        """
        start_utc = datetime.now(UTC)

        all_trading_days = self.reader.get_trading_days(
            start_date=self.config.start_date,
            end_date=self.config.end_date,
        )

        all_trades: List[BacktestTradeRecord] = []
        all_incidents: List[DataQualityIncident] = []
        session_summaries: List[SessionExecutionSummary] = []

        qualified_count = 0
        excluded_count = 0
        current_capital = self.config.initial_capital

        for session_date in all_trading_days:
            session_str = str(session_date)

            # Step 1: Calendar & Local Data Gating (Hard Qualification Gate)
            if not self.calendar.is_session_eligible(session_date, has_rolled=False):
                excluded_count += 1
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=SessionQualification.EXCLUDED_MISSING_EXPIRY_DATA,
                        reason="Missing local option file for applicable scheduled expiry",
                    )
                )
                continue

            # Step 2: Query Index Bars
            index_bars = self.reader.query_index_bars(start_dt=session_date, end_dt=session_date)
            if len(index_bars) < 15:
                excluded_count += 1
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=SessionQualification.EXCLUDED_DATA_GAP,
                        reason=f"Insufficient index bars ({len(index_bars)} < 15)",
                    )
                )
                continue

            # Step 3: Initialize Strategy Session Context
            nearest_expiry = self.calendar.get_nearest_scheduled_expiry(session_date)
            is_expiry_session = (session_date == nearest_expiry)
            session_context = SessionContext(
                trading_day=session_date,
                is_expiry_day=is_expiry_session,
                nearest_expiry=nearest_expiry,
                initial_capital=current_capital,
                max_trades_per_session=self.config.max_trades_per_session,
            )
            self.strategy.initialize_session(session_context)

            # Step 4: Evaluate Strategy-Specific Session Qualification / Volatility Filters
            qualified, reason, qual_enum = self.strategy.evaluate_session_qualification(
                index_bars=index_bars,
                context=session_context,
            )
            if not qualified:
                excluded_count += 1
                orb_h = getattr(self.strategy, "orb_high", None)
                orb_l = getattr(self.strategy, "orb_low", None)
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=qual_enum or SessionQualification.EXCLUDED_SPECIAL_SESSION,
                        reason=reason or "Strategy session qualification rejected",
                        orb_high=orb_h,
                        orb_low=orb_l,
                    )
                )
                continue

            # Session is qualified
            qualified_count += 1
            qualification = SessionQualification.INCLUDED

            # Step 5: Replay Intraday Bars (from session open 09:15:00 IST)
            session_bars = [b for b in index_bars if b["timestamp_ist"].time() >= time(9, 15)]
            session_trades: List[BacktestTradeRecord] = []
            session_incidents: List[DataQualityIncident] = []
            cached_contract_bars: Dict[tuple, Dict[datetime, Dict[str, Any]]] = {}

            active_position: Optional[Dict[str, Any]] = None
            session_trades_count = 0
            breakout_detected = False
            rejection_reason: Optional[str] = None
            executed_trade_id: Optional[str] = None

            for k, current_bar in enumerate(session_bars):
                current_time = current_bar["timestamp_ist"]

                # A. Monitor & Evaluate Open Position Exits
                if active_position is not None:
                    contract_info = active_position["contract_info"]
                    opt_key = (contract_info["strike"], contract_info["option_type"], contract_info["expiry"])
                    opt_candle = cached_contract_bars.get(opt_key, {}).get(current_time)

                    official_index_close = (
                        current_bar["close"] if current_time.time() >= time(15, 29) else None
                    )

                    closed_trade, incident = self.execution_simulator.evaluate_active_position(
                        position=active_position,
                        current_candle=opt_candle,
                        current_time_ist=current_time,
                        is_expiry_day=is_expiry_session,
                        official_index_close=official_index_close,
                    )

                    if incident:
                        session_incidents.append(incident)

                    if closed_trade:
                        session_trades.append(closed_trade)
                        all_trades.append(closed_trade)
                        current_capital += closed_trade.net_pnl
                        executed_trade_id = closed_trade.trade_id
                        active_position = None

                # B. Signal & Entry Evaluation (if no open position and limit not reached)
                if active_position is None and session_trades_count < self.config.max_trades_per_session:
                    signal = self.strategy.on_index_bar(current_bar, session_context)
                    if signal is not None:
                        breakout_detected = True
                        signal_timestamp = current_time
                        session_trades_count += 1

                        # Next minute fill timestamp (T_fill)
                        if k + 1 < len(session_bars):
                            fill_timestamp = session_bars[k + 1]["timestamp_ist"]
                        else:
                            fill_timestamp = signal_timestamp + timedelta(minutes=1)

                        # Enforce fill cutoff (T_fill <= entry_cutoff_time)
                        if fill_timestamp.time() > signal.entry_cutoff_time:
                            rejection_reason = "REJECTED_FILL_PAST_ENTRY_CUTOFF"
                        else:
                            opt_type = "CE" if signal.direction == SignalDirection.BUY_CE else "PE"
                            contract_info = self.contract_selector.resolve_contract(
                                session_date=session_date,
                                spot_price=signal.index_spot_price,
                                option_type=opt_type,
                                current_time=fill_timestamp.time(),
                            )

                            if contract_info is None:
                                rejection_reason = "REJECTED_NO_ELIGIBLE_CONTRACT"
                            else:
                                opt_key = (
                                    contract_info["strike"],
                                    contract_info["option_type"],
                                    contract_info["expiry"],
                                )
                                if opt_key not in cached_contract_bars:
                                    raw_bars = self.reader.query_option_bars(
                                        start_dt=session_date,
                                        end_dt=session_date,
                                        strike=contract_info["strike"],
                                        option_type=contract_info["option_type"],
                                        expiry=contract_info["expiry"],
                                    )
                                    cached_contract_bars[opt_key] = {
                                        b["timestamp_ist"]: b for b in raw_bars
                                    }

                                fill_candle = cached_contract_bars[opt_key].get(fill_timestamp)

                                orb_h = getattr(self.strategy, "orb_high", None)
                                orb_l = getattr(self.strategy, "orb_low", None)

                                pos, rej, entry_incidents = self.execution_simulator.simulate_entry_fill(
                                    signal_timestamp=signal_timestamp,
                                    fill_candle=fill_candle,
                                    contract_info=contract_info,
                                    cash_balance=current_capital,
                                    spot_at_signal=signal.index_spot_price,
                                    orb_high=orb_h,
                                    orb_low=orb_l,
                                    )
                                session_incidents.extend(entry_incidents)

                                if pos:
                                    active_position = pos
                                else:
                                    rejection_reason = rej

            # End of session check: finalize any remaining position at session close
            if active_position is not None:
                last_bar = session_bars[-1]
                closed_trade = self.execution_simulator._finalize_unexecutable_or_settlement(
                    position=active_position,
                    exit_time_ist=last_bar["timestamp_ist"],
                    is_expiry_day=is_expiry_session,
                    official_index_close=last_bar["close"],
                )
                session_trades.append(closed_trade)
                all_trades.append(closed_trade)
                current_capital += closed_trade.net_pnl
                executed_trade_id = closed_trade.trade_id
                active_position = None

            all_incidents.extend(session_incidents)
            orb_h = getattr(self.strategy, "orb_high", None)
            orb_l = getattr(self.strategy, "orb_low", None)
            session_summaries.append(
                SessionExecutionSummary(
                    trading_day=session_str,
                    qualification=qualification,
                    reason="Session completed",
                    orb_high=orb_h,
                    orb_low=orb_l,
                    breakout_detected=breakout_detected,
                    trade_executed=(len(session_trades) > 0),
                    trade_id=executed_trade_id,
                    rejection_reason=rejection_reason,
                    incidents_count=len(session_incidents),
                )
            )
            self.strategy.on_session_complete(session_context)

        # Step 6: Segregate Ledgers
        normal_trades = [t for t in all_trades if not t.execution_liquidity_impaired and t.exit_reason != "CASH_SETTLEMENT_EMERGENCY"]
        quarantined_trades = [t for t in all_trades if t.execution_liquidity_impaired]
        emergency_settlement_trades = [t for t in all_trades if t.exit_reason == "CASH_SETTLEMENT_EMERGENCY"]

        # Step 7: Metrics Computation
        metrics = {
            "standard_clean_ledger": HistoricalPerformanceMetrics.calculate_ledger_metrics(
                normal_trades, self.config.initial_capital
            ),
            "quarantined_impaired_ledger": HistoricalPerformanceMetrics.calculate_ledger_metrics(
                quarantined_trades, self.config.initial_capital
            ),
            "emergency_settlement_ledger": HistoricalPerformanceMetrics.calculate_ledger_metrics(
                emergency_settlement_trades, self.config.initial_capital
            ),
            "combined_ledger_audit_only": HistoricalPerformanceMetrics.calculate_ledger_metrics(
                all_trades, self.config.initial_capital
            ),
        }

        split_analysis = HistoricalPerformanceMetrics.calculate_chronological_splits(
            normal_trades, self.config.initial_capital
        )

        sensitivity_analysis: Dict[str, Any] = {}
        if calculate_sensitivity:
            sensitivity_analysis = self._run_sensitivity_grid()

        end_utc = datetime.now(UTC)
        total_cal_days = 0
        if self.config.start_date and self.config.end_date:
            total_cal_days = (self.config.end_date - self.config.start_date).days + 1

        return BacktestResultSet(
            config=self.config,
            execution_start_utc=start_utc,
            execution_end_utc=end_utc,
            total_calendar_days=total_cal_days,
            total_trading_days=len(all_trading_days),
            qualified_sessions=qualified_count,
            excluded_sessions=excluded_count,
            normal_trades=normal_trades,
            quarantined_trades=quarantined_trades,
            emergency_settlement_trades=emergency_settlement_trades,
            session_summaries=session_summaries,
            data_quality_incidents=all_incidents,
            metrics=metrics,
            sensitivity_analysis=sensitivity_analysis,
            split_analysis=split_analysis,
        )

    def _run_sensitivity_grid(self) -> Dict[str, Any]:
        """
        Runs sensitivity analysis across both percentage-based and fixed-point slippage models.
        Percentage Grid: 0.0%, 0.5%, 1.0%, 1.5%
        Fixed Grid: ₹0.50/unit, ₹1.00/unit
        """
        percentage_grid = [
            ("0.0%", Decimal("0.000")),
            ("0.5%", Decimal("0.005")),
            ("1.0%", Decimal("0.010")),
            ("1.5%", Decimal("0.015")),
        ]
        fixed_grid = [
            ("₹0.50/unit", Decimal("0.50")),
            ("₹1.00/unit", Decimal("1.00")),
        ]

        results: Dict[str, Any] = {
            "percentage_models": {},
            "fixed_points_models": {},
        }

        # 1. Percentage Slippage Grid
        for label, rate in percentage_grid:
            cfg = dataclasses.replace(
                self.config,
                slippage_model="PERCENTAGE",
                slippage_rate=rate,
                fixed_slippage_pts=Decimal("0.00"),
            )
            sub_engine = MultiStrategyBacktestEngine(
                strategy=self.strategy,
                config=cfg,
                reader=self.reader,
                calendar=self.calendar,
                contract_selector=self.contract_selector,
                execution_simulator=HistoricalExecutionSimulator(config=cfg),
            )
            sub_res = sub_engine.run(calculate_sensitivity=False)
            results["percentage_models"][label] = {
                "model": "PERCENTAGE",
                "slippage_rate": str(rate),
                "total_trades": len(sub_res.normal_trades),
                "net_pnl": sub_res.metrics["standard_clean_ledger"]["total_net_pnl"],
                "win_rate_pct": sub_res.metrics["standard_clean_ledger"]["win_rate_pct"],
                "profit_factor": sub_res.metrics["standard_clean_ledger"]["profit_factor"],
                "max_drawdown_amount": sub_res.metrics["standard_clean_ledger"]["max_drawdown_amount"],
            }

        # 2. Fixed Points Slippage Grid
        for label, pts in fixed_grid:
            cfg = dataclasses.replace(
                self.config,
                slippage_model="FIXED_POINTS",
                slippage_rate=Decimal("0.000"),
                fixed_slippage_pts=pts,
            )
            sub_engine = MultiStrategyBacktestEngine(
                strategy=self.strategy,
                config=cfg,
                reader=self.reader,
                calendar=self.calendar,
                contract_selector=self.contract_selector,
                execution_simulator=HistoricalExecutionSimulator(config=cfg),
            )
            sub_res = sub_engine.run(calculate_sensitivity=False)
            results["fixed_points_models"][label] = {
                "model": "FIXED_POINTS",
                "fixed_slippage_pts": str(pts),
                "total_trades": len(sub_res.normal_trades),
                "net_pnl": sub_res.metrics["standard_clean_ledger"]["total_net_pnl"],
                "win_rate_pct": sub_res.metrics["standard_clean_ledger"]["win_rate_pct"],
                "profit_factor": sub_res.metrics["standard_clean_ledger"]["profit_factor"],
                "max_drawdown_amount": sub_res.metrics["standard_clean_ledger"]["max_drawdown_amount"],
            }

        return results
