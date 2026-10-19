"""
Nomad Analyst — Strategy Performance Evaluator & Comparison Matrix
Reference: Phase 22D Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Calculates rigorous statistical performance metrics from fno_paper_trade_ledger:
- Net P&L, Expectancy, Win Rate, Profit Factor, Max Drawdown
- Friction Drag Ratio (Total Frictions / Gross P&L)
- Regime-decomposed performance (bullish/bearish/sideways/high VIX)
- Side-by-side multi-strategy comparative evaluation
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from fno.models import PaperTradeLedger


@dataclass(frozen=True)
class StrategyPerformanceMetrics:
    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: Decimal
    gross_pnl: Decimal
    total_frictions: Decimal
    net_pnl: Decimal
    friction_drag_pct: Decimal
    expectancy_per_trade: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    regime_breakdown: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = str(v)
        return d


class StrategyComparisonMatrix:
    """Side-by-side comparison matrix across multiple candidate strategies."""

    def __init__(self, metrics_list: List[StrategyPerformanceMetrics]):
        self.metrics_list = metrics_list

    def to_dict(self) -> Dict[str, Any]:
        return {m.strategy_id: m.to_dict() for m in self.metrics_list}

    def to_markdown_table(self) -> str:
        headers = [
            "Strategy ID", "Trades", "Win Rate %", "Gross P&L",
            "Frictions", "Net P&L", "Drag %", "Expectancy", "Profit Factor", "Max DD"
        ]
        rows = [
            f"| {' | '.join(headers)} |",
            f"| {' | '.join(['---'] * len(headers))} |",
        ]
        for m in self.metrics_list:
            row = [
                m.strategy_id,
                str(m.total_trades),
                f"{m.win_rate_pct:.1f}%",
                f"₹{m.gross_pnl:,.2f}",
                f"₹{m.total_frictions:,.2f}",
                f"₹{m.net_pnl:,.2f}",
                f"{m.friction_drag_pct:.1f}%",
                f"₹{m.expectancy_per_trade:,.2f}",
                f"{m.profit_factor:.2f}",
                f"₹{m.max_drawdown:,.2f}",
            ]
            rows.append(f"| {' | '.join(row)} |")
        return "\n".join(rows)


class StrategyPerformanceEvaluator:
    """
    Evaluates paper trades from database into reproducible performance metrics.
    """

    @classmethod
    def evaluate_strategy(
        cls,
        strategy_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> StrategyPerformanceMetrics:
        """Evaluates closed and settled trades for a specific strategy."""
        qs = PaperTradeLedger.objects.filter(
            strategy_id=strategy_id,
            status__in=["CLOSED", "CLOSED_EXPIRED_WORTHLESS", "CLOSED_EXPIRED_ITM_SETTLED"],
        ).order_by("entry_timestamp")

        if start_date:
            qs = qs.filter(entry_timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(entry_timestamp__date__lte=end_date)

        trades = list(qs)
        total_trades = len(trades)

        if total_trades == 0:
            return StrategyPerformanceMetrics(
                strategy_id=strategy_id,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate_pct=Decimal("0.00"),
                gross_pnl=Decimal("0.00"),
                total_frictions=Decimal("0.00"),
                net_pnl=Decimal("0.00"),
                friction_drag_pct=Decimal("0.00"),
                expectancy_per_trade=Decimal("0.00"),
                profit_factor=Decimal("0.00"),
                max_drawdown=Decimal("0.00"),
                regime_breakdown={},
            )

        winning_trades = 0
        losing_trades = 0
        breakeven_trades = 0
        total_gross_pnl = Decimal("0.00")
        total_frictions = Decimal("0.00")
        total_net_pnl = Decimal("0.00")
        total_gross_gains = Decimal("0.00")
        total_gross_losses = Decimal("0.00")

        cumulative_net = Decimal("0.00")
        peak_net = Decimal("0.00")
        max_drawdown = Decimal("0.00")

        regime_stats: Dict[str, Dict[str, Any]] = {}

        for t in trades:
            net = t.net_pnl or Decimal("0.00")
            gross = t.gross_pnl or Decimal("0.00")
            frictions = t.total_frictions or Decimal("0.00")

            total_gross_pnl += gross
            total_frictions += frictions
            total_net_pnl += net

            if net > Decimal("0.00"):
                winning_trades += 1
            elif net < Decimal("0.00"):
                losing_trades += 1
            else:
                breakeven_trades += 1

            if gross > Decimal("0.00"):
                total_gross_gains += gross
            elif gross < Decimal("0.00"):
                total_gross_losses += abs(gross)

            # Drawdown calculation
            cumulative_net += net
            if cumulative_net > peak_net:
                peak_net = cumulative_net
            dd = peak_net - cumulative_net
            if dd > max_drawdown:
                max_drawdown = dd

            # Regime Breakdown
            regime = t.market_regime_at_entry or "UNKNOWN"
            if regime not in regime_stats:
                regime_stats[regime] = {
                    "trades": 0,
                    "wins": 0,
                    "net_pnl": Decimal("0.00"),
                }
            regime_stats[regime]["trades"] += 1
            if net > Decimal("0.00"):
                regime_stats[regime]["wins"] += 1
            regime_stats[regime]["net_pnl"] += net

        win_rate = Decimal(str(round((winning_trades / total_trades) * 100.0, 2)))
        expectancy = Decimal(str(round(total_net_pnl / total_trades, 2)))

        if total_gross_losses > Decimal("0.00"):
            profit_factor = Decimal(str(round(total_gross_gains / total_gross_losses, 2)))
        else:
            profit_factor = Decimal("99.99") if total_gross_gains > 0 else Decimal("0.00")

        if total_gross_pnl != Decimal("0.00"):
            drag_pct = Decimal(str(round(abs(total_frictions / total_gross_pnl) * Decimal("100.0"), 2)))
        else:
            drag_pct = Decimal("0.00")

        # Format regime breakdown
        formatted_regimes = {}
        for reg, stats in regime_stats.items():
            cnt = stats["trades"]
            wr = Decimal(str(round((stats["wins"] / cnt) * 100.0, 1))) if cnt > 0 else Decimal("0.0")
            formatted_regimes[reg] = {
                "trades": cnt,
                "win_rate_pct": str(wr),
                "net_pnl": str(stats["net_pnl"]),
            }

        return StrategyPerformanceMetrics(
            strategy_id=strategy_id,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate_pct=win_rate,
            gross_pnl=total_gross_pnl,
            total_frictions=total_frictions,
            net_pnl=total_net_pnl,
            friction_drag_pct=drag_pct,
            expectancy_per_trade=expectancy,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            regime_breakdown=formatted_regimes,
        )

    @classmethod
    def compare_strategies(cls, strategy_ids: List[str]) -> StrategyComparisonMatrix:
        """Generates side-by-side comparison matrix for multiple strategies."""
        metrics = [cls.evaluate_strategy(sid) for sid in strategy_ids]
        return StrategyComparisonMatrix(metrics)
