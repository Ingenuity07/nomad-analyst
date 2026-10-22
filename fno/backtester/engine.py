"""
Nomad Analyst — Isolated Historical Options Backtest Engine (ORB-15M)
Reference: Sections 2, 3, 5, 8 in docs/historical_options_backtester_architecture.md
"""

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
import zoneinfo

from fno.backtester.calendar import NiftyExpiryCalendar
from fno.backtester.contract_selector import OptionContractSelector
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
from fno.services.historical_reader import HistoricalParquetReader

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")


class CachedHistoricalReader:
    """
    Transparent in-memory caching wrapper for HistoricalParquetReader.
    Caches immutable historical query results (index and option bars) to avoid
    redundant DuckDB Parquet disk scans across backtest sensitivity passes.
    """

    def __init__(self, inner_reader: HistoricalParquetReader):
        self._inner = inner_reader
        self._index_cache: Dict[tuple, List[Dict[str, Any]]] = {}
        self._option_cache: Dict[tuple, List[Dict[str, Any]]] = {}
        self._trading_days_cache: Dict[tuple, List[date]] = {}

    @property
    def base_dir(self):
        return self._inner.base_dir

    def has_index_data(self) -> bool:
        return self._inner.has_index_data()

    def get_available_expiries(self) -> List[str]:
        return self._inner.get_available_expiries()

    def get_index_parquet_path(self):
        return self._inner.get_index_parquet_path()

    def get_option_parquet_paths(self, expiry: Optional[str] = None):
        return self._inner.get_option_parquet_paths(expiry=expiry)

    def get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        key = (start_date, end_date)
        if key not in self._trading_days_cache:
            self._trading_days_cache[key] = self._inner.get_trading_days(start_date=start_date, end_date=end_date)
        return list(self._trading_days_cache[key])

    def query_index_bars(self, start_dt: Any, end_dt: Any) -> List[Dict[str, Any]]:
        key = (str(start_dt), str(end_dt))
        if key not in self._index_cache:
            self._index_cache[key] = self._inner.query_index_bars(start_dt=start_dt, end_dt=end_dt)
        return [dict(b) for b in self._index_cache[key]]

    def query_option_bars(
        self,
        start_dt: Any,
        end_dt: Any,
        strike: Optional[Union[int, float, Decimal]] = None,
        option_type: Optional[str] = None,
        expiry: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        key = (
            str(start_dt),
            str(end_dt),
            int(strike) if strike is not None else None,
            str(option_type).upper() if option_type is not None else None,
            str(expiry) if expiry is not None else None,
        )
        if key not in self._option_cache:
            self._option_cache[key] = self._inner.query_option_bars(
                start_dt=start_dt,
                end_dt=end_dt,
                strike=strike,
                option_type=option_type,
                expiry=expiry,
            )
        return [dict(b) for b in self._option_cache[key]]

    def clear_cache(self) -> None:
        self._index_cache.clear()
        self._option_cache.clear()
        self._trading_days_cache.clear()


class HistoricalBacktestEngine:
    """
    Orchestrates the replay of authentic 1-minute historical Parquet data,
    re-running the ORB-15M strategy deterministically without look-ahead bias,
    enforcing hard session gating, fill-time cutoffs, and dual-ledger quarantine.
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        reader: Optional[HistoricalParquetReader] = None,
        calendar: Optional[NiftyExpiryCalendar] = None,
        contract_selector: Optional[OptionContractSelector] = None,
        execution_simulator: Optional[HistoricalExecutionSimulator] = None,
    ):
        self.config = config or BacktestConfig()
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
        Executes the full historical backtest over the configured date range.
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

            # Step 3: Evaluate ORB 15-Minute Range (09:15:00 to 09:29:59 IST)
            orb_bars = [b for b in index_bars if time(9, 15) <= b["timestamp_ist"].time() < time(9, 30)]
            if len(orb_bars) < 15:
                excluded_count += 1
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=SessionQualification.EXCLUDED_DATA_GAP,
                        reason=f"Missing bars in 15M ORB window ({len(orb_bars)} < 15)",
                    )
                )
                continue

            orb_high = max(b["high"] for b in orb_bars)
            orb_low = min(b["low"] for b in orb_bars)
            orb_range = orb_high - orb_low

            if orb_range < self.config.min_orb_range_pts:
                excluded_count += 1
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=SessionQualification.EXCLUDED_RANGE_TOO_NARROW,
                        reason=f"ORB width {orb_range} < {self.config.min_orb_range_pts} pts",
                        orb_high=orb_high,
                        orb_low=orb_low,
                    )
                )
                continue

            if self.config.max_orb_range_pts is not None and orb_range > self.config.max_orb_range_pts:
                excluded_count += 1
                session_summaries.append(
                    SessionExecutionSummary(
                        trading_day=session_str,
                        qualification=SessionQualification.EXCLUDED_RANGE_TOO_WIDE,
                        reason=f"ORB width {orb_range} > {self.config.max_orb_range_pts} pts",
                        orb_high=orb_high,
                        orb_low=orb_low,
                    )
                )
                continue

            # Session is qualified
            qualified_count += 1
            qualification = SessionQualification.INCLUDED

            # Step 4: Replay Post-ORB Session (09:30:00 to 15:30:00 IST)
            post_orb_bars = [b for b in index_bars if b["timestamp_ist"].time() >= time(9, 30)]
            session_trades: List[BacktestTradeRecord] = []
            session_incidents: List[DataQualityIncident] = []
            cached_contract_bars: Dict[tuple, Dict[datetime, Dict[str, Any]]] = {}

            active_position: Optional[Dict[str, Any]] = None
            session_trades_count = 0
            breakout_detected = False
            rejection_reason: Optional[str] = None
            executed_trade_id: Optional[str] = None

            nearest_expiry = self.calendar.get_nearest_scheduled_expiry(session_date)
            is_expiry_session = (session_date == nearest_expiry)

            for k, current_bar in enumerate(post_orb_bars):
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

                # B. Signal & Entry Evaluation (if no position and trade limit not reached)
                if active_position is None and session_trades_count < self.config.max_trades_per_session:
                    is_bullish = current_bar["close"] > orb_high
                    is_bearish = current_bar["close"] < orb_low

                    if is_bullish or is_bearish:
                        breakout_detected = True
                        signal_timestamp = current_time
                        session_trades_count += 1

                        # Next minute fill timestamp (T_fill)
                        if k + 1 < len(post_orb_bars):
                            fill_timestamp = post_orb_bars[k + 1]["timestamp_ist"]
                        else:
                            fill_timestamp = signal_timestamp + timedelta(minutes=1)

                        # Enforce fill cutoff (T_fill <= 14:30:00 IST)
                        if fill_timestamp.time() > self.config.entry_window_end:
                            rejection_reason = "REJECTED_FILL_PAST_ENTRY_CUTOFF"
                        else:
                            opt_type = "CE" if is_bullish else "PE"
                            contract_info = self.contract_selector.resolve_contract(
                                session_date=session_date,
                                spot_price=current_bar["close"],
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

                                pos, rej, entry_incidents = self.execution_simulator.simulate_entry_fill(
                                    signal_timestamp=signal_timestamp,
                                    fill_candle=fill_candle,
                                    contract_info=contract_info,
                                    cash_balance=current_capital,
                                    spot_at_signal=current_bar["close"],
                                    orb_high=orb_high,
                                    orb_low=orb_low,
                                )
                                session_incidents.extend(entry_incidents)

                                if pos:
                                    active_position = pos
                                else:
                                    rejection_reason = rej

            # End of session check: finalize any remaining position at session close
            if active_position is not None:
                last_bar = post_orb_bars[-1]
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
            session_summaries.append(
                SessionExecutionSummary(
                    trading_day=session_str,
                    qualification=qualification,
                    reason="Session completed",
                    orb_high=orb_high,
                    orb_low=orb_low,
                    breakout_detected=breakout_detected,
                    trade_executed=(len(session_trades) > 0),
                    trade_id=executed_trade_id,
                    rejection_reason=rejection_reason,
                    incidents_count=len(session_incidents),
                )
            )

        # Segregate Ledgers
        normal_trades = [
            t for t in all_trades
            if not t.execution_liquidity_impaired and not t.is_emergency_expiry_settlement
        ]
        quarantined_trades = [
            t for t in all_trades if t.execution_liquidity_impaired
        ]
        emergency_settlement_trades = [
            t for t in all_trades if t.is_emergency_expiry_settlement
        ]

        # Compute Metrics
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
        import dataclasses

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
            sub_engine = HistoricalBacktestEngine(
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
            sub_engine = HistoricalBacktestEngine(
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
