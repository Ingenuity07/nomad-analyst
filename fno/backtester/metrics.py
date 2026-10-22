"""
Nomad Analyst — Isolated Historical Performance Metrics Engine
Reference: Section 7 in docs/historical_options_backtester_architecture.md
"""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional

from fno.backtester.models import BacktestTradeRecord


class HistoricalPerformanceMetrics:
    """
    Computes rigorous trading performance statistics for clean and quarantined ledgers,
    including friction breakdown, equity drawdowns, Sharpe, Sortino, and chronological splits.
    """

    @staticmethod
    def calculate_ledger_metrics(
        trades: List[BacktestTradeRecord],
        initial_capital: Decimal = Decimal("100000.00"),
    ) -> Dict[str, Any]:
        """
        Calculates all standard trading metrics over a list of trade records.
        """
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "win_rate_pct": "0.00",
                "profit_factor": "0.00",
                "total_gross_pnl": "0.00",
                "total_net_pnl": "0.00",
                "total_frictions": "0.00",
                "frictions_breakdown": {
                    "brokerage": "0.00",
                    "stt": "0.00",
                    "exchange_txn_charge": "0.00",
                    "sebi_turnover_fee": "0.00",
                    "stamp_duty": "0.00",
                    "gst": "0.00",
                },
                "friction_drag_pct": "0.00",
                "expectancy_per_trade": "0.00",
                "max_drawdown_amount": "0.00",
                "max_drawdown_pct": "0.00",
                "sharpe_ratio": "0.00",
                "sortino_ratio": "0.00",
                "avg_holding_duration_minutes": "0.00",
            }

        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl < 0]
        breakeven_trades = [t for t in trades if t.net_pnl == 0]

        win_rate_pct = (Decimal(len(winning_trades)) / Decimal(total_trades) * Decimal("100")).quantize(Decimal("0.01"))

        gross_profit = sum((t.gross_pnl for t in trades if t.gross_pnl > 0), Decimal("0.00"))
        gross_loss = sum((abs(t.gross_pnl) for t in trades if t.gross_pnl < 0), Decimal("0.00"))

        if gross_loss > 0:
            profit_factor = (gross_profit / gross_loss).quantize(Decimal("0.0001"))
        elif gross_profit > 0:
            profit_factor = Decimal("999.0000")
        else:
            profit_factor = Decimal("0.0000")

        total_gross_pnl = sum((t.gross_pnl for t in trades), Decimal("0.00"))
        total_net_pnl = sum((t.net_pnl for t in trades), Decimal("0.00"))

        brokerage = sum((t.statutory_fees.brokerage for t in trades), Decimal("0.00"))
        stt = sum((t.statutory_fees.stt for t in trades), Decimal("0.00"))
        exchange = sum((t.statutory_fees.exchange_charges for t in trades), Decimal("0.00"))
        sebi = sum((t.statutory_fees.sebi_charges for t in trades), Decimal("0.00"))
        stamp = sum((t.statutory_fees.stamp_duty for t in trades), Decimal("0.00"))
        gst = sum((t.statutory_fees.gst for t in trades), Decimal("0.00"))
        total_frictions = sum((t.statutory_fees.total_frictions for t in trades), Decimal("0.00"))

        if total_gross_pnl > 0:
            friction_drag = (total_frictions / total_gross_pnl * Decimal("100")).quantize(Decimal("0.01"))
        else:
            friction_drag = Decimal("0.00")

        expectancy = (total_net_pnl / Decimal(total_trades)).quantize(Decimal("0.01"))

        # Equity Curve and Max Drawdown
        current_equity = initial_capital
        peak_equity = initial_capital
        max_dd_amount = Decimal("0.00")
        max_dd_pct = Decimal("0.00")

        # Daily returns for Sharpe / Sortino
        daily_net_pnl: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

        for t in trades:
            current_equity += t.net_pnl
            if current_equity > peak_equity:
                peak_equity = current_equity
            dd = peak_equity - current_equity
            if dd > max_dd_amount:
                max_dd_amount = dd
                if peak_equity > 0:
                    max_dd_pct = (dd / peak_equity * Decimal("100")).quantize(Decimal("0.01"))

            daily_net_pnl[t.trading_day] += t.net_pnl

        # Sharpe & Sortino (daily returns relative to initial capital)
        # Assuming 252 trading days per year
        daily_returns = [float(pnl / initial_capital) for pnl in daily_net_pnl.values()]
        if len(daily_returns) > 1:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0.0

            sharpe = (mean_return / std_dev * math.sqrt(252)) if std_dev > 0 else 0.0

            downside_returns = [min(0.0, r) for r in daily_returns]
            downside_variance = sum(dr ** 2 for dr in downside_returns) / len(downside_returns)
            downside_std_dev = math.sqrt(downside_variance) if downside_variance > 0 else 0.0

            sortino = (mean_return / downside_std_dev * math.sqrt(252)) if downside_std_dev > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        avg_holding = (
            Decimal(sum(t.holding_duration_seconds for t in trades)) / Decimal(total_trades * 60)
        ).quantize(Decimal("0.01"))

        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "breakeven_trades": len(breakeven_trades),
            "win_rate_pct": str(win_rate_pct),
            "profit_factor": str(profit_factor),
            "total_gross_pnl": str(total_gross_pnl),
            "total_net_pnl": str(total_net_pnl),
            "total_frictions": str(total_frictions),
            "frictions_breakdown": {
                "brokerage": str(brokerage),
                "stt": str(stt),
                "exchange_txn_charge": str(exchange),
                "sebi_turnover_fee": str(sebi),
                "stamp_duty": str(stamp),
                "gst": str(gst),
            },
            "friction_drag_pct": str(friction_drag),
            "expectancy_per_trade": str(expectancy),
            "max_drawdown_amount": str(max_dd_amount),
            "max_drawdown_pct": str(max_dd_pct),
            "sharpe_ratio": f"{sharpe:.2f}",
            "sortino_ratio": f"{sortino:.2f}",
            "avg_holding_duration_minutes": str(avg_holding),
        }

    @classmethod
    def calculate_chronological_splits(
        cls,
        trades: List[BacktestTradeRecord],
        initial_capital: Decimal = Decimal("100000.00"),
    ) -> Dict[str, Any]:
        """
        Partitions clean trades into In-Sample (IS), Validation, and Out-of-Sample (OOS) splits.
        - In-Sample: 2025-07-01 to 2025-11-30
        - Validation: 2025-12-01 to 2026-03-31
        - Holdout / Out-of-Sample: 2026-04-01 to 2026-07-02
        """
        is_trades: List[BacktestTradeRecord] = []
        val_trades: List[BacktestTradeRecord] = []
        oos_trades: List[BacktestTradeRecord] = []

        for t in trades:
            t_date = date.fromisoformat(t.trading_day)
            if t_date <= date(2025, 11, 30):
                is_trades.append(t)
            elif t_date <= date(2026, 3, 31):
                val_trades.append(t)
            else:
                oos_trades.append(t)

        return {
            "in_sample": {
                "date_range": "2025-07-01 to 2025-11-30",
                "metrics": cls.calculate_ledger_metrics(is_trades, initial_capital),
            },
            "validation": {
                "date_range": "2025-12-01 to 2026-03-31",
                "metrics": cls.calculate_ledger_metrics(val_trades, initial_capital),
            },
            "holdout_oos": {
                "date_range": "2026-04-01 to 2026-07-02",
                "metrics": cls.calculate_ledger_metrics(oos_trades, initial_capital),
            },
        }
