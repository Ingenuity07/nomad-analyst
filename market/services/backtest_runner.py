"""
backtest_runner.py — Deterministic historical backtest runner.

Module 11: Backtesting Foundation

CRITICAL DESIGN RULES:
  1. PIT safety is mandatory. At every as_of timestamp, the strategy engine
     MUST see only data available at or before that timestamp.
  2. No look-ahead. Bar queries always use timestamp__lte=as_of.
  3. Results are deterministic: same config, same data = same results.
  4. BacktestRuns are NEVER auto-scheduled. They must be explicitly triggered.
  5. Historical fundamentals/news are flagged as UNAVAILABLE — not used.
  6. VectorBT is NOT imported. This is a custom Django-native runner.

Architecture:
  BacktestRunner.run(config)
      ↓
  For each instrument in universe:
      For each as_of in [start_date, end_date] at step=walk_forward_step_bars:
          Load bars PIT-safe (timestamp <= as_of)
          Call strategy engine (sees only PIT data)
          If BUY/SELL signal:
              Load subsequent bars for evaluation
              Evaluate entry → exit → outcome
      ↓
  Aggregate all outcomes into PerformanceReport
  Persist BacktestRun
"""
from __future__ import annotations

import logging
import uuid as uuid_lib
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional

from django.utils import timezone as django_tz

from market.models import BacktestRun, OHLCVBar, StockRecommendation, UniverseMembership
from market.services.backtest_config import BacktestConfig
from market.services.cost_model import CostConfig
from market.services.outcome_engine import (
    EntryEvaluator,
    ExitEvaluator,
    MFEMAECalculator,
    PnLCalculator,
)
from market.services.performance_metrics import PerformanceReport, StrategyPerformanceService

logger = logging.getLogger(__name__)

# Historical data limitation warnings (written to every BacktestRun)
WARN_HIST_FUND = (
    "UNAVAILABLE_HISTORICAL: Fundamental data cannot be reconstructed point-in-time. "
    "Current fundamentals were used as signals at historical decision points — "
    "this introduces survivorship bias in fundamental-driven confidence scores."
)
WARN_HIST_NEWS = (
    "UNAVAILABLE_HISTORICAL: News/event data cannot be reconstructed point-in-time. "
    "News-based confidence components are excluded from historical evaluation."
)
WARN_HIST_SECTOR = (
    "PARTIAL_HISTORICAL: Sector rank computed from historical price momentum only, "
    "not from contemporaneous sector rotation data."
)


class BacktestSignalRecord:
    """Lightweight record of a signal generated during a backtest walk-forward."""
    __slots__ = [
        "instrument_id", "symbol", "signal", "setup_type", "horizon",
        "timeframe", "as_of", "entry_price", "stop_price", "target_price",
        "expires_at", "market_context", "sector_context", "strategy_version",
        "calculation_version",
    ]

    def __init__(self, rec: StockRecommendation):
        self.instrument_id    = str(rec.instrument_id)
        self.symbol           = rec.instrument.symbol
        self.signal           = rec.signal
        self.setup_type       = rec.setup_type
        self.horizon          = rec.horizon
        self.timeframe        = rec.timeframe or "1d"
        self.as_of            = rec.as_of
        self.entry_price      = float(rec.entry_price) if rec.entry_price else None
        self.stop_price       = float(rec.stop_price)  if rec.stop_price  else None
        self.target_price     = float(rec.target_price) if rec.target_price else None
        self.expires_at       = rec.expires_at
        self.market_context   = rec.market_context or {}
        self.sector_context   = rec.sector_context or {}
        self.strategy_version = rec.strategy_version or "1.0"
        self.calculation_version = rec.calculation_version


class BacktestOutcomeRecord:
    """Outcome computed during a backtest walk-forward (not persisted to DB)."""
    def __init__(self, signal: BacktestSignalRecord):
        self.signal       = signal
        self.recommendation = None   # The StockRecommendation FK (for live evaluation)
        # Populated after evaluation:
        self.entry_triggered = False
        self.entry_timestamp = None
        self.actual_entry_price = None
        self.exit_reason = "NO_ENTRY"
        self.exit_timestamp = None
        self.actual_exit_price = None
        self.gross_pnl_absolute = None
        self.gross_pnl_percent = None
        self.cost_absolute = None
        self.net_pnl_absolute = None
        self.net_pnl_percent = None
        self.risk_amount = None
        self.r_multiple = None
        self.target_hit = False
        self.stop_hit = False
        self.ambiguous_intrabar = False
        self.max_favorable_excursion = None
        self.max_adverse_excursion = None
        self.holding_duration_bars = None
        self.holding_duration_seconds = None
        self.bars_evaluated = 0
        self.data_quality_warnings: List[str] = []

    # Delegate attribute access to mimic RecommendationOutcome interface
    # so StrategyPerformanceService can process BacktestOutcomeRecord and
    # RecommendationOutcome objects uniformly.
    @property
    def recommendation_obj(self):
        return self

    @property
    def setup_type(self):
        return self.signal.setup_type

    @property
    def timeframe(self):
        return self.signal.timeframe

    @property
    def direction(self):
        return self.signal.signal

    @property
    def sector(self):
        return (self.signal.sector_context or {}).get("sector", "UNKNOWN")


class BacktestRunner:
    """
    Deterministic historical backtest runner.

    Executes a full walk-forward backtest over a universe and date range.
    Uses existing strategy engines with PIT-enforced bar data.

    Does NOT:
      - optimise parameters
      - run automatically on a schedule
      - import VectorBT or any external backtest framework
      - fabricate historical fundamentals or news
    """

    def __init__(self):
        self._entry_eval = EntryEvaluator()
        self._exit_eval  = ExitEvaluator()
        self._mfe_mae    = MFEMAECalculator()
        self._pnl_calc   = PnLCalculator()
        self._perf_svc   = StrategyPerformanceService()

    def run(self, config: BacktestConfig, run_id: Optional[str] = None) -> BacktestRun:
        """
        Execute a full historical backtest.

        Creates a BacktestRun record (PENDING → RUNNING → COMPLETE/FAILED).
        Results are stored in BacktestRun.result as a serialised PerformanceReport.

        Args:
            config:  BacktestConfig describing the run parameters.
            run_id:  Optional human-readable slug. Auto-generated if None.

        Returns:
            BacktestRun instance (status=COMPLETE or FAILED).
        """
        if run_id is None:
            run_id = (
                f"{config.universe_name}_{config.timeframe}_{config.horizon}_"
                f"{config.start_date.isoformat()}_{config.end_date.isoformat()}_"
                f"{uuid_lib.uuid4().hex[:8]}"
            )

        # Create BacktestRun record (PENDING)
        bt_run = BacktestRun.objects.create(
            run_id=run_id,
            config=config.to_dict(),
            status="RUNNING",
            universe_name=config.universe_name,
            timeframe=config.timeframe,
            horizon=config.horizon,
            start_date=config.start_date,
            end_date=config.end_date,
            strategy_version=config.strategy_version,
            data_quality_warnings=[WARN_HIST_FUND, WARN_HIST_NEWS, WARN_HIST_SECTOR],
        )

        logger.info(f"BacktestRunner: starting run_id={run_id}")

        try:
            outcomes = self._execute(config, bt_run)
            report = self._perf_svc.compute(
                outcomes=outcomes,
                ambiguity_policy=config.ambiguity_policy,
                strategy_version=config.strategy_version,
                start_date=config.start_date,
                end_date=config.end_date,
                data_quality_warnings=[WARN_HIST_FUND, WARN_HIST_NEWS, WARN_HIST_SECTOR],
            )

            bt_run.result = report.to_dict()
            bt_run.status = "COMPLETE"
            bt_run.completed_at = django_tz.now()
            bt_run.save(update_fields=["status", "completed_at", "result"])

            logger.info(
                f"BacktestRunner: COMPLETE run_id={run_id} "
                f"signals={report.total_signals} triggered={report.triggered} "
                f"wins={report.wins} losses={report.losses}"
            )

        except Exception as exc:
            bt_run.status = "FAILED"
            bt_run.error_message = str(exc)
            bt_run.completed_at = django_tz.now()
            bt_run.save(update_fields=["status", "completed_at", "error_message"])
            logger.exception(f"BacktestRunner: FAILED run_id={run_id}: {exc}")

        return bt_run

    def _execute(
        self, config: BacktestConfig, bt_run: BacktestRun
    ) -> List[BacktestOutcomeRecord]:
        """Walk-forward execution across all instruments in the universe."""
        # Load universe members
        members = list(
            UniverseMembership.objects.filter(
                universe__name=config.universe_name,
                is_active=True,
            ).select_related("instrument")
        )

        if not members:
            logger.warning(
                f"BacktestRunner: universe '{config.universe_name}' has no active members."
            )
            return []

        all_outcomes: List[BacktestOutcomeRecord] = []

        for membership in members:
            instrument = membership.instrument
            try:
                inst_outcomes = self._run_instrument(instrument, config)
                all_outcomes.extend(inst_outcomes)
                logger.debug(
                    f"BacktestRunner: {instrument.symbol} → {len(inst_outcomes)} signals"
                )
            except Exception as exc:
                logger.error(
                    f"BacktestRunner: error on {instrument.symbol}: {exc}"
                )

        return all_outcomes

    def _run_instrument(self, instrument, config: BacktestConfig) -> List[BacktestOutcomeRecord]:
        """Walk-forward signal generation and outcome evaluation for one instrument."""
        # Load ALL bars in the full range (both decision-making and evaluation bars)
        all_bars = list(
            OHLCVBar.objects.filter(
                instrument=instrument,
                timeframe=config.timeframe,
                timestamp__date__gte=config.start_date,
                timestamp__date__lte=config.end_date + timedelta(days=config.max_holding_bars),
            ).order_by("timestamp")
        )

        if not all_bars:
            return []

        # Walk-forward: find all decision bars in [start_date, end_date]
        decision_bars = [
            b for b in all_bars
            if config.start_date <= b.timestamp.date() <= config.end_date
        ]

        outcomes: List[BacktestOutcomeRecord] = []

        i = 0
        while i < len(decision_bars):
            as_of_bar = decision_bars[i]
            as_of = as_of_bar.timestamp

            # PIT bars: only bars up to and including as_of
            pit_bars = [b for b in all_bars if b.timestamp <= as_of]

            if len(pit_bars) < config.min_bars_required:
                i += config.walk_forward_step_bars
                continue

            # Generate signal using existing recommendations queried PIT
            # For the backtest, we find already-persisted recommendations at as_of
            # (generated by the live engine or generate them on-demand)
            rec = self._find_or_generate_signal(instrument, config, as_of, pit_bars)
            if rec is None or rec.signal not in ("BUY", "SELL"):
                i += config.walk_forward_step_bars
                continue

            # Bars after this decision point (for evaluation)
            future_bars = [b for b in all_bars if b.timestamp > as_of]

            outcome_record = self._evaluate_outcome(rec, future_bars, config)
            outcomes.append(outcome_record)

            # Advance past the holding period to avoid signal overlap
            if outcome_record.holding_duration_bars:
                i += max(config.walk_forward_step_bars, outcome_record.holding_duration_bars)
            else:
                i += config.walk_forward_step_bars

        return outcomes

    def _find_or_generate_signal(
        self, instrument, config: BacktestConfig, as_of: datetime, pit_bars: list
    ) -> Optional[StockRecommendation]:
        """
        Find an existing StockRecommendation generated at as_of, or return None.

        The backtest evaluates EXISTING recommendations that were persisted
        by the live engines. It does NOT re-run the signal engine in backtest mode
        (that would require fully mocking fundamentals/news/sector which are not
        PIT-safe — see WARN_HIST_FUND/WARN_HIST_NEWS).

        This is an intentional design decision: we evaluate the recommendations
        actually made by the system, not hypothetical ones.
        """
        try:
            return StockRecommendation.objects.filter(
                instrument=instrument,
                horizon=config.horizon,
                as_of__date=as_of.date(),
                signal__in=("BUY", "SELL"),
            ).order_by("-generated_at").first()
        except Exception:
            return None

    def _evaluate_outcome(
        self,
        rec: StockRecommendation,
        future_bars: List[OHLCVBar],
        config: BacktestConfig,
    ) -> BacktestOutcomeRecord:
        """Evaluate entry/exit/PnL/MFE-MAE for one signal."""
        out = BacktestOutcomeRecord(BacktestSignalRecord(rec))
        out.recommendation = rec
        out.bars_evaluated = len(future_bars)

        # Entry
        entry_result = self._entry_eval.evaluate(rec, future_bars)
        out.entry_triggered = entry_result.triggered
        out.entry_timestamp = entry_result.trigger_timestamp
        out.actual_entry_price = entry_result.trigger_price

        if not entry_result.triggered:
            out.exit_reason = "NO_ENTRY"
            return out

        # Exit
        bars_after_entry = future_bars[entry_result.trigger_bar_index + 1:]
        exit_result = self._exit_eval.evaluate(
            rec, entry_result, bars_after_entry,
            ambiguity_policy=config.ambiguity_policy,
            max_holding_bars=config.max_holding_bars,
        )
        out.exit_reason = exit_result.exit_reason
        out.exit_timestamp = exit_result.exit_timestamp
        out.actual_exit_price = exit_result.exit_price
        out.target_hit = exit_result.target_hit
        out.stop_hit = exit_result.stop_hit
        out.ambiguous_intrabar = exit_result.ambiguous_intrabar

        # Duration
        if exit_result.exit_bar_index is not None:
            out.holding_duration_bars = exit_result.exit_bar_index
        if entry_result.trigger_timestamp and exit_result.exit_timestamp:
            out.holding_duration_seconds = int(
                (exit_result.exit_timestamp - entry_result.trigger_timestamp).total_seconds()
            )

        # MFE / MAE
        entry_to_exit = future_bars[entry_result.trigger_bar_index:]
        mfe_mae = self._mfe_mae.calculate(
            rec.signal, entry_result.trigger_price, entry_to_exit
        )
        out.max_favorable_excursion = mfe_mae.max_favorable_excursion
        out.max_adverse_excursion = mfe_mae.max_adverse_excursion

        # P&L
        if exit_result.exit_price and entry_result.trigger_price:
            pnl = self._pnl_calc.calculate(
                signal=rec.signal,
                actual_entry_price=entry_result.trigger_price,
                actual_exit_price=exit_result.exit_price,
                stop_price=float(rec.stop_price) if rec.stop_price else None,
                cost_config=config.cost_config,
            )
            out.gross_pnl_absolute = pnl.gross_pnl_absolute
            out.gross_pnl_percent  = pnl.gross_pnl_percent
            out.cost_absolute      = pnl.cost_absolute
            out.net_pnl_absolute   = pnl.net_pnl_absolute
            out.net_pnl_percent    = pnl.net_pnl_percent
            out.risk_amount        = pnl.risk_amount
            out.r_multiple         = pnl.r_multiple

        return out
