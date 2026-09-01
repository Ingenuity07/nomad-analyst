"""
performance_metrics.py — Deterministic strategy performance aggregation.

Module 11: Backtesting Foundation

CRITICAL DESIGN RULES:
  1. Never call win rate "probability of success." It is a historical frequency.
  2. Always report sample_count. Never omit it.
  3. Add SMALL_SAMPLE_WARNING when n_triggered < SMALL_SAMPLE_WARNING_THRESHOLD.
  4. Never report expectancy or drawdown from fewer than MIN_SAMPLE_FOR_STATS triggered trades.
  5. Never automate parameter optimisation based on these metrics.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from market.signal_enums import (
    MIN_SAMPLE_FOR_STATS,
    SMALL_SAMPLE_WARNING_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Statistical warning labels
SMALL_SAMPLE_WARNING = "SMALL_SAMPLE_WARNING"
INSUFFICIENT_SAMPLE  = "INSUFFICIENT_SAMPLE"


@dataclass
class PerformanceSlice:
    """Performance for one slice dimension (e.g. one setup_type, one regime)."""
    dimension_key: str
    dimension_value: str
    total: int
    triggered: int
    untriggered: int
    wins: int
    losses: int
    ambiguous: int
    expired: int
    win_rate: Optional[float]       # wins / triggered (null if n_triggered < threshold)
    avg_return_pct: Optional[float]
    median_return_pct: Optional[float]
    avg_r: Optional[float]
    expectancy: Optional[float]     # avg_r (net, per trade attempted)
    profit_factor: Optional[float]  # sum(wins_r) / abs(sum(losses_r))
    avg_holding_bars: Optional[float]
    warnings: List[str] = field(default_factory=list)


@dataclass
class PerformanceReport:
    """
    Full strategy performance report computed from RecommendationOutcome records.

    Fields:
      - All counts are integers.
      - All percentages are floats (e.g. 55.3 = 55.3%).
      - All R values are floats (e.g. 1.5 = 1.5R).
      - win_rate is null when n_triggered < SMALL_SAMPLE_WARNING_THRESHOLD.
      - statistical_warnings: list of string warnings about sample size.
    """
    # Counts
    total_signals: int
    triggered: int
    untriggered: int
    wins: int
    losses: int
    ambiguous: int
    expired_no_entry: int    # expired before entry triggered
    expired_after_entry: int # expired after entry, before stop/target

    # Rates (null when sample too small)
    win_rate: Optional[float]        # wins / triggered
    trigger_rate: Optional[float]    # triggered / total_signals

    # Return metrics (only over triggered trades)
    avg_return_pct: Optional[float]
    median_return_pct: Optional[float]
    std_return_pct: Optional[float]

    # R metrics
    avg_r: Optional[float]
    median_r: Optional[float]
    expectancy: Optional[float]      # avg net P&L per triggered trade (in R)
    profit_factor: Optional[float]   # sum_wins_gross / abs(sum_losses_gross)

    # Drawdown (running peak-to-trough in R-multiple)
    max_drawdown_r: Optional[float]

    # Holding duration (in bars)
    avg_holding_bars: Optional[float]
    median_holding_bars: Optional[float]

    # Statistical metadata
    sample_count: int                # same as triggered
    statistical_warnings: List[str]

    # Dimension slices
    by_setup_type: Dict[str, PerformanceSlice] = field(default_factory=dict)
    by_timeframe: Dict[str, PerformanceSlice] = field(default_factory=dict)
    by_direction: Dict[str, PerformanceSlice] = field(default_factory=dict)
    by_regime: Dict[str, PerformanceSlice] = field(default_factory=dict)
    by_sector: Dict[str, PerformanceSlice] = field(default_factory=dict)

    # Date range and version info
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    strategy_version: Optional[str] = None
    data_quality_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise for storage in BacktestRun.result (JSONField)."""
        def _slice_to_dict(s: PerformanceSlice) -> dict:
            return {
                "dimension_key": s.dimension_key,
                "dimension_value": s.dimension_value,
                "total": s.total,
                "triggered": s.triggered,
                "untriggered": s.untriggered,
                "wins": s.wins,
                "losses": s.losses,
                "ambiguous": s.ambiguous,
                "expired": s.expired,
                "win_rate": s.win_rate,
                "avg_return_pct": s.avg_return_pct,
                "median_return_pct": s.median_return_pct,
                "avg_r": s.avg_r,
                "expectancy": s.expectancy,
                "profit_factor": s.profit_factor,
                "avg_holding_bars": s.avg_holding_bars,
                "warnings": s.warnings,
            }

        return {
            "total_signals": self.total_signals,
            "triggered": self.triggered,
            "untriggered": self.untriggered,
            "wins": self.wins,
            "losses": self.losses,
            "ambiguous": self.ambiguous,
            "expired_no_entry": self.expired_no_entry,
            "expired_after_entry": self.expired_after_entry,
            "win_rate": self.win_rate,
            "trigger_rate": self.trigger_rate,
            "avg_return_pct": self.avg_return_pct,
            "median_return_pct": self.median_return_pct,
            "std_return_pct": self.std_return_pct,
            "avg_r": self.avg_r,
            "median_r": self.median_r,
            "expectancy": self.expectancy,
            "profit_factor": self.profit_factor,
            "max_drawdown_r": self.max_drawdown_r,
            "avg_holding_bars": self.avg_holding_bars,
            "median_holding_bars": self.median_holding_bars,
            "sample_count": self.sample_count,
            "statistical_warnings": self.statistical_warnings,
            "by_setup_type": {k: _slice_to_dict(v) for k, v in self.by_setup_type.items()},
            "by_timeframe": {k: _slice_to_dict(v) for k, v in self.by_timeframe.items()},
            "by_direction": {k: _slice_to_dict(v) for k, v in self.by_direction.items()},
            "by_regime": {k: _slice_to_dict(v) for k, v in self.by_regime.items()},
            "by_sector": {k: _slice_to_dict(v) for k, v in self.by_sector.items()},
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "strategy_version": self.strategy_version,
            "data_quality_warnings": self.data_quality_warnings,
        }


class StrategyPerformanceService:
    """
    Computes PerformanceReport from a list of RecommendationOutcome instances.

    Filterable by: setup_type, timeframe, direction, sector, regime,
                   strategy_version, start_date, end_date.

    Statistical rules:
      - win_rate is null when n_triggered < SMALL_SAMPLE_WARNING_THRESHOLD (10).
      - expectancy/profit_factor require n_triggered >= MIN_SAMPLE_FOR_STATS (30).
      - SMALL_SAMPLE_WARNING is appended to statistical_warnings.
    """

    def compute(
        self,
        outcomes: Sequence,           # Sequence[RecommendationOutcome]
        ambiguity_policy: str = "CONSERVATIVE",
        strategy_version: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        data_quality_warnings: Optional[List[str]] = None,
    ) -> PerformanceReport:
        """
        Build a full PerformanceReport from outcome records.

        Args:
            outcomes:            QuerySet or list of RecommendationOutcome.
            ambiguity_policy:    How AMBIGUOUS_INTRABAR counts in win/loss.
                                 CONSERVATIVE → loss, OPTIMISTIC → win, EXCLUDE → neither.
            strategy_version:    Tag written into the report.
            start_date/end_date: Date window for the report.
            data_quality_warnings: Pre-existing warnings to carry through.
        """
        # Convert to list if queryset
        outcome_list = list(outcomes)
        n_total = len(outcome_list)

        # --- Aggregate core counts ------------------------------------------
        n_triggered = 0
        n_untriggered = 0
        n_wins = 0
        n_losses = 0
        n_ambiguous = 0
        n_expired_no_entry = 0
        n_expired_after_entry = 0

        returns_pct: List[float] = []
        r_values: List[float] = []
        holding_bars: List[int] = []

        for out in outcome_list:
            if not out.entry_triggered:
                n_untriggered += 1
                if out.exit_reason in ("EXPIRED_SESSION", "EXPIRED_MAX_DURATION", "NO_ENTRY"):
                    n_expired_no_entry += 1
                continue

            n_triggered += 1

            if out.exit_reason in ("EXPIRED_SESSION", "EXPIRED_MAX_DURATION"):
                n_expired_after_entry += 1

            if out.ambiguous_intrabar:
                n_ambiguous += 1
                if ambiguity_policy == "CONSERVATIVE":
                    n_losses += 1
                elif ambiguity_policy == "OPTIMISTIC":
                    n_wins += 1
                # EXCLUDE: count neither win nor loss
            elif out.exit_reason == "TARGET_HIT" or out.exit_reason == "TARGET_2_HIT":
                n_wins += 1
            elif out.exit_reason == "STOP_HIT":
                n_losses += 1
            # EXPIRED / NO_ENTRY after entry: not win or loss

            if out.net_pnl_percent is not None:
                returns_pct.append(float(out.net_pnl_percent))
            if out.r_multiple is not None:
                r_values.append(float(out.r_multiple))
            if out.holding_duration_bars is not None:
                holding_bars.append(out.holding_duration_bars)

        # --- Statistical warnings -------------------------------------------
        stat_warnings: List[str] = []
        if n_triggered < SMALL_SAMPLE_WARNING_THRESHOLD:
            stat_warnings.append(
                f"{SMALL_SAMPLE_WARNING}: only {n_triggered} triggered trades. "
                f"Results have very limited statistical significance."
            )
        elif n_triggered < MIN_SAMPLE_FOR_STATS:
            stat_warnings.append(
                f"{SMALL_SAMPLE_WARNING}: {n_triggered} triggered trades is "
                f"below the recommended minimum of {MIN_SAMPLE_FOR_STATS}. "
                f"Interpret results cautiously."
            )

        # --- Rate metrics ---------------------------------------------------
        win_rate = None
        if n_triggered >= SMALL_SAMPLE_WARNING_THRESHOLD:
            eligible = n_wins + n_losses  # excludes ambiguous when EXCLUDE
            if ambiguity_policy != "EXCLUDE":
                eligible = n_wins + n_losses + n_ambiguous
            win_rate = round(n_wins / eligible * 100, 2) if eligible > 0 else None

        trigger_rate = (
            round(n_triggered / n_total * 100, 2) if n_total > 0 else None
        )

        # --- Return / R statistics ------------------------------------------
        avg_ret = _mean(returns_pct)
        med_ret = _median(returns_pct)
        std_ret = _stdev(returns_pct)
        avg_r   = _mean(r_values)
        med_r   = _median(r_values)

        # Expectancy: mean R over all triggered trades
        expectancy = None
        profit_factor = None
        if n_triggered >= MIN_SAMPLE_FOR_STATS:
            expectancy = avg_r
            pos_r = [r for r in r_values if r > 0]
            neg_r = [r for r in r_values if r < 0]
            sum_pos = sum(pos_r)
            sum_neg = abs(sum(neg_r))
            profit_factor = round(sum_pos / sum_neg, 4) if sum_neg > 0 else None

        # Max drawdown in R (running peak-to-trough)
        max_dd_r = _max_drawdown(r_values) if len(r_values) >= 2 else None

        # Holding durations
        avg_hold = _mean(holding_bars)
        med_hold = _median(holding_bars)

        # --- Dimension slices -----------------------------------------------
        by_setup   = self._slice_by(outcome_list, "setup_type", ambiguity_policy)
        by_tf      = self._slice_by(outcome_list, "timeframe", ambiguity_policy)
        by_dir     = self._slice_by(outcome_list, "direction", ambiguity_policy)
        by_regime  = self._slice_by_market_regime(outcome_list, ambiguity_policy)
        by_sector  = self._slice_by(outcome_list, "sector", ambiguity_policy)

        return PerformanceReport(
            total_signals=n_total,
            triggered=n_triggered,
            untriggered=n_untriggered,
            wins=n_wins,
            losses=n_losses,
            ambiguous=n_ambiguous,
            expired_no_entry=n_expired_no_entry,
            expired_after_entry=n_expired_after_entry,
            win_rate=win_rate,
            trigger_rate=trigger_rate,
            avg_return_pct=avg_ret,
            median_return_pct=med_ret,
            std_return_pct=std_ret,
            avg_r=avg_r,
            median_r=med_r,
            expectancy=expectancy,
            profit_factor=profit_factor,
            max_drawdown_r=max_dd_r,
            avg_holding_bars=avg_hold,
            median_holding_bars=med_hold,
            sample_count=n_triggered,
            statistical_warnings=stat_warnings,
            by_setup_type=by_setup,
            by_timeframe=by_tf,
            by_direction=by_dir,
            by_regime=by_regime,
            by_sector=by_sector,
            start_date=start_date,
            end_date=end_date,
            strategy_version=strategy_version,
            data_quality_warnings=data_quality_warnings or [],
        )

    def _slice_by(
        self, outcomes: List, attr: str, ambiguity_policy: str
    ) -> Dict[str, PerformanceSlice]:
        """Group outcomes by a recommendation attribute and compute a PerformanceSlice per group.

        Note: 'direction' is stored as 'signal' on StockRecommendation.
        """
        # Map logical dimension name → actual model field name
        field_map = {"direction": "signal"}
        actual_attr = field_map.get(attr, attr)

        groups: Dict[str, List] = {}
        for out in outcomes:
            try:
                rec = out.recommendation
                val = getattr(rec, actual_attr, "UNKNOWN") or "UNKNOWN"
            except Exception:
                val = "UNKNOWN"
            groups.setdefault(str(val), []).append(out)

        result = {}
        for val, group_outs in groups.items():
            result[val] = self._compute_slice(attr, val, group_outs, ambiguity_policy)
        return result

    def _slice_by_market_regime(
        self, outcomes: List, ambiguity_policy: str
    ) -> Dict[str, PerformanceSlice]:
        """Group by market_context.regime from the recommendation's frozen context."""
        groups: Dict[str, List] = {}
        for out in outcomes:
            try:
                regime = (out.recommendation.market_context or {}).get("regime", "UNKNOWN")
            except Exception:
                regime = "UNKNOWN"
            groups.setdefault(str(regime), []).append(out)

        result = {}
        for regime, group_outs in groups.items():
            result[regime] = self._compute_slice(
                "market_regime", regime, group_outs, ambiguity_policy
            )
        return result

    def _compute_slice(
        self,
        dim_key: str, dim_val: str,
        outcomes: List,
        ambiguity_policy: str,
    ) -> PerformanceSlice:
        n_total = len(outcomes)
        n_trig = n_wins = n_losses = n_ambig = n_exp = n_untrig = 0
        r_vals: List[float] = []
        ret_pct: List[float] = []
        hold: List[float] = []
        warnings: List[str] = []

        for out in outcomes:
            if not out.entry_triggered:
                n_untrig += 1
                continue
            n_trig += 1
            if out.ambiguous_intrabar:
                n_ambig += 1
                if ambiguity_policy == "CONSERVATIVE":
                    n_losses += 1
                elif ambiguity_policy == "OPTIMISTIC":
                    n_wins += 1
            elif out.exit_reason in ("TARGET_HIT", "TARGET_2_HIT"):
                n_wins += 1
            elif out.exit_reason == "STOP_HIT":
                n_losses += 1
            elif out.exit_reason in ("EXPIRED_SESSION", "EXPIRED_MAX_DURATION"):
                n_exp += 1
            if out.r_multiple is not None:
                r_vals.append(float(out.r_multiple))
            if out.net_pnl_percent is not None:
                ret_pct.append(float(out.net_pnl_percent))
            if out.holding_duration_bars is not None:
                hold.append(out.holding_duration_bars)

        win_rate = None
        if n_trig >= SMALL_SAMPLE_WARNING_THRESHOLD:
            eligible = n_wins + n_losses + (n_ambig if ambiguity_policy != "EXCLUDE" else 0)
            win_rate = round(n_wins / eligible * 100, 2) if eligible > 0 else None
        else:
            warnings.append(f"{SMALL_SAMPLE_WARNING}: n={n_trig}")

        expectancy = None
        pf = None
        if n_trig >= MIN_SAMPLE_FOR_STATS:
            expectancy = _mean(r_vals)
            pos_r = [r for r in r_vals if r > 0]
            neg_r = abs(sum(r for r in r_vals if r < 0))
            pf = round(sum(pos_r) / neg_r, 4) if neg_r > 0 else None

        return PerformanceSlice(
            dimension_key=dim_key,
            dimension_value=dim_val,
            total=n_total,
            triggered=n_trig,
            untriggered=n_untrig,
            wins=n_wins,
            losses=n_losses,
            ambiguous=n_ambig,
            expired=n_exp,
            win_rate=win_rate,
            avg_return_pct=_mean(ret_pct),
            median_return_pct=_median(ret_pct),
            avg_r=_mean(r_vals),
            expectancy=expectancy,
            profit_factor=pf,
            avg_holding_bars=_mean(hold),
            warnings=warnings,
        )


# ── Statistics helpers ────────────────────────────────────────────────────────

def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return round((s[mid - 1] + s[mid]) / 2, 4)
    return round(s[mid], 4)


def _stdev(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return round(math.sqrt(variance), 4)


def _max_drawdown(r_values: List[float]) -> Optional[float]:
    """Running peak-to-trough max drawdown in R-multiple (cumulative R series)."""
    if len(r_values) < 2:
        return None
    cum_r = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in r_values:
        cum_r += r
        if cum_r > peak:
            peak = cum_r
        dd = peak - cum_r
        if dd > max_dd:
            max_dd = dd
    return round(-max_dd, 4)  # negative = drawdown
