"""
Nomad Analyst — Management Command to execute Phase 2.4 Historical Options Backtester.
Reference: docs/historical_options_backtester_architecture.md
"""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import time

from django.core.management.base import BaseCommand

from fno.backtester.engine import HistoricalBacktestEngine
from fno.backtester.models import BacktestConfig


class Command(BaseCommand):
    help = "Executes the isolated historical options backtester over authentic Parquet data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            type=str,
            default="2025-07-01",
            help="Start date YYYY-MM-DD (default: 2025-07-01)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default="2026-07-02",
            help="End date YYYY-MM-DD (default: 2026-07-02)",
        )
        parser.add_argument(
            "--initial-capital",
            type=str,
            default="200000.00",
            help="Initial capital in INR (default: 200000.00)",
        )
        parser.add_argument(
            "--slippage",
            type=str,
            default="0.005",
            help="Baseline slippage rate (default: 0.005 = 0.5%%)",
        )
        parser.add_argument(
            "--max-orb-range",
            type=str,
            default="150.00",
            help="Maximum ORB range in index points. Pass a positive number (default: 150.00) or 'none'/'0' for no upper limit.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="docs/audits/fno_backtest_report_orb15m.json",
            help="Path to save backtest JSON report",
        )
        parser.add_argument(
            "--no-sensitivity",
            action="store_true",
            help="Skip slippage sensitivity grid",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable in-memory query caching across sensitivity grid passes",
        )

    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        from fno.backtester.models import SessionQualification

        start_d = date.fromisoformat(options["start_date"])
        end_d = date.fromisoformat(options["end_date"])
        capital = Decimal(options["initial_capital"])
        slippage = Decimal(options["slippage"])
        output_path = Path(options["output"])
        skip_sens = options["no_sensitivity"]
        use_cache = not options["no_cache"]

        max_orb_input = options["max_orb_range"].strip()
        if max_orb_input.lower() in ("none", "0", "null", "no-limit", "nolimit"):
            max_orb_range_pts = None
            max_orb_label = "None (No upper limit)"
        else:
            try:
                max_orb_range_pts = Decimal(max_orb_input)
                if max_orb_range_pts <= Decimal("0"):
                    raise CommandError(f"Invalid --max-orb-range: '{max_orb_input}'. Must be a positive number or 'none'.")
                max_orb_label = f"{max_orb_range_pts} pts"
            except (ArithmeticError, ValueError):
                raise CommandError(f"Invalid --max-orb-range: '{max_orb_input}'. Must be a valid positive number or 'none'.")

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("NOMAD ANALYST — HISTORICAL OPTIONS BACKTESTER (PHASE 2.4.2)"))
        self.stdout.write(self.style.NOTICE("Strategy: NIFTY 15-Minute Opening Range Breakout (ORB-15M)"))
        self.stdout.write(self.style.NOTICE(f"Date Range: {start_d} to {end_d}"))
        self.stdout.write(
            self.style.NOTICE(
                f"Initial Capital: ₹{capital:,.2f} | Base Slippage: {slippage * 100}% | "
                f"Max ORB: {max_orb_label} | Caching: {'ENABLED' if use_cache else 'DISABLED'}"
            )
        )
        self.stdout.write(self.style.NOTICE("=" * 70))

        config = BacktestConfig(
            start_date=start_d,
            end_date=end_d,
            initial_capital=capital,
            slippage_rate=slippage,
            max_orb_range_pts=max_orb_range_pts,
            enable_query_cache=use_cache,
        )

        engine = HistoricalBacktestEngine(config=config)

        t0 = time.perf_counter()
        results = engine.run(calculate_sensitivity=not skip_sens)
        t_elapsed = time.perf_counter() - t0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        results_dict = results.to_dict()
        results_dict["execution_metadata"]["cli_wall_clock_seconds"] = round(t_elapsed, 3)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"\nBacktest completed in {t_elapsed:.2f} seconds."))
        self.stdout.write(self.style.SUCCESS(f"Report saved to: {output_path}"))

        clean_metrics = results.metrics.get("standard_clean_ledger", {})
        quarantined_metrics = results.metrics.get("quarantined_impaired_ledger", {})
        emergency_metrics = results.metrics.get("emergency_settlement_ledger", {})

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("EXECUTIVE SUMMARY (ISOLATED LEDGERS)")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total Trading Sessions:     {results.total_trading_days}")
        self.stdout.write(f"Qualified Sessions:         {results.qualified_sessions}")
        self.stdout.write(f"Excluded Sessions:          {results.excluded_sessions}")

        # Breakdown of exclusions
        excl_reasons: dict = {}
        for s in results.session_summaries:
            if s.qualification not in (SessionQualification.INCLUDED, SessionQualification.QUALIFIED_FULL_SESSION):
                q_name = s.qualification.value if hasattr(s.qualification, "value") else str(s.qualification)
                excl_reasons[q_name] = excl_reasons.get(q_name, 0) + 1
        for q_val, count in sorted(excl_reasons.items()):
            self.stdout.write(f"   • {q_val}: {count}")

        self.stdout.write("-" * 70)
        self.stdout.write("1. Standard Clean Ledger:")
        self.stdout.write(f"   Total Trades:            {clean_metrics.get('total_trades', 0)}")
        self.stdout.write(f"   Win Rate:                {clean_metrics.get('win_rate_pct', '0.00')}%")
        self.stdout.write(f"   Profit Factor:           {clean_metrics.get('profit_factor', '0.00')}")
        self.stdout.write(f"   Net P&L:                 ₹{clean_metrics.get('total_net_pnl', '0.00')}")
        self.stdout.write(f"   Total Frictions:         ₹{clean_metrics.get('total_frictions', '0.00')}")
        self.stdout.write(f"   Max Drawdown:            ₹{clean_metrics.get('max_drawdown_amount', '0.00')} ({clean_metrics.get('max_drawdown_pct', '0.00')}%)")
        self.stdout.write(f"   Sharpe Ratio:            {clean_metrics.get('sharpe_ratio', '0.00')}")
        self.stdout.write("-" * 70)
        self.stdout.write("2. Quarantined & Liquidity-Impaired Ledger:")
        self.stdout.write(f"   Impaired Trades:         {quarantined_metrics.get('total_trades', 0)}")
        self.stdout.write(f"   Net P&L:                 ₹{quarantined_metrics.get('total_net_pnl', '0.00')}")
        self.stdout.write("-" * 70)
        self.stdout.write("3. Emergency Expiry Settlement Ledger:")
        self.stdout.write(f"   Settlement Trades:       {emergency_metrics.get('total_trades', 0)}")
        self.stdout.write(f"   Net P&L:                 ₹{emergency_metrics.get('total_net_pnl', '0.00')}")
        self.stdout.write("-" * 70)
        self.stdout.write(f"Data Quality Incidents:     {len(results.data_quality_incidents)}")
        self.stdout.write("=" * 70)

        if results.sensitivity_analysis:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("SLIPPAGE SENSITIVITY GRID (DUAL MODELS)")
            self.stdout.write("=" * 70)
            pct_models = results.sensitivity_analysis.get("percentage_models", {})
            if pct_models:
                self.stdout.write("A. Percentage Slippage Grid:")
                for lbl, data in pct_models.items():
                    self.stdout.write(
                        f"   [{lbl:8s}] Net P&L: ₹{data['net_pnl']:>12s} | Win Rate: {data['win_rate_pct']:>5s}% | "
                        f"PF: {data['profit_factor']:>6s} | MaxDD: ₹{data['max_drawdown_amount']}"
                    )
            fixed_models = results.sensitivity_analysis.get("fixed_points_models", {})
            if fixed_models:
                self.stdout.write("-" * 70)
                self.stdout.write("B. Fixed Points Slippage Grid:")
                for lbl, data in fixed_models.items():
                    self.stdout.write(
                        f"   [{lbl:10s}] Net P&L: ₹{data['net_pnl']:>12s} | Win Rate: {data['win_rate_pct']:>5s}% | "
                        f"PF: {data['profit_factor']:>6s} | MaxDD: ₹{data['max_drawdown_amount']}"
                    )
            self.stdout.write("=" * 70)

