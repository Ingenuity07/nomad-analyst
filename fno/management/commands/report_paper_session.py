from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import zoneinfo
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from fno.execution.evaluator import StrategyPerformanceEvaluator
from fno.execution.fee_calculator import StatutoryFeeCalculator
from fno.models import OptionOHLCVBar, OptionQuoteSnapshot, PaperTradeLedger

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class Command(BaseCommand):
    help = "Generates daily prospective paper-trading session audit report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Session date to report (YYYY-MM-DD). Defaults to today in IST.",
        )
        parser.add_argument(
            "--strategy",
            type=str,
            default=None,
            help="Optional strategy ID to filter (e.g. STRAT-ORB-15M). Defaults to all.",
        )
        parser.add_argument(
            "--format",
            type=str,
            default="markdown",
            choices=["markdown", "text"],
            help="Output format: markdown (default) or text.",
        )

    def handle(self, *args, **options):
        # 1. Resolve Session Date & Strict IST Day Boundaries
        date_str = options.get("date")
        if date_str:
            session_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            session_date = datetime.now(IST).date()

        strategy_id = options.get("strategy")

        ist_start = datetime(session_date.year, session_date.month, session_date.day, 0, 0, 0, tzinfo=IST)
        ist_end = ist_start + timedelta(days=1)

        self.stdout.write("=" * 80)
        self.stdout.write(f"PROSPECTIVE PAPER EVALUATION DAILY REPORT — {session_date} (IST)")
        self.stdout.write(f"Session Bounds: {ist_start.isoformat()} to {ist_end.isoformat()}")
        self.stdout.write("=" * 80)

        # 2. Market-Data Ingestion Health (Strict IST range)
        bar_qs = OptionOHLCVBar.objects.filter(timestamp__gte=ist_start, timestamp__lt=ist_end)
        total_bars = bar_qs.count()
        partial_bars = bar_qs.filter(is_partial_bar=True).count()

        quote_qs = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__gte=ist_start, received_wall_clock_utc__lt=ist_end
        )
        total_quotes = quote_qs.count()
        stale_quotes = quote_qs.filter(is_stale=True).count()
        eligible_quotes = quote_qs.filter(is_execution_eligible=True).count()

        # 3. Query Paper Trade Ledger for Session (Strict IST range)
        qs = PaperTradeLedger.objects.filter(entry_timestamp__gte=ist_start, entry_timestamp__lt=ist_end)
        if strategy_id:
            qs = qs.filter(strategy_id=strategy_id)

        status_counts = dict(qs.values_list("status").annotate(count=Count("status")))
        total_signals = sum(status_counts.values())
        rejected_count = status_counts.get("REJECTED", 0)
        open_count = status_counts.get("OPEN", 0)
        pending_liq_count = status_counts.get("PENDING_LIQUIDITY", 0)
        unexec_carry_count = status_counts.get("UNEXECUTABLE_OVERNIGHT_CARRY", 0)
        pending_settle_count = status_counts.get("PENDING_EXPIRY_SETTLEMENT", 0)
        closed_count = (
            status_counts.get("CLOSED", 0)
            + status_counts.get("CLOSED_EXPIRED_WORTHLESS", 0)
            + status_counts.get("CLOSED_EXPIRED_ITM_SETTLED", 0)
        )
        fills_count = open_count + pending_liq_count + unexec_carry_count + pending_settle_count + closed_count

        # Rejection reasons breakdown
        rejections = (
            qs.filter(status="REJECTED")
            .values("rejection_reason")
            .annotate(count=Count("trade_id"))
            .order_by("-count")
        )

        # 4. All-Time Cumulative vs Session-Scoped Data
        all_time_qs = PaperTradeLedger.objects.all()
        if strategy_id:
            all_time_qs = all_time_qs.filter(strategy_id=strategy_id)
        all_time_total_trades = all_time_qs.count()

        # 5. Output Markdown Report
        self.stdout.write(f"\n### 1. Market-Data Ingestion Health (Session {session_date})")
        if total_bars == 0 and total_quotes == 0:
            self.stdout.write(self.style.WARNING("  [DATA STATUS: NO DATA] Zero option bars and zero quote snapshots found for this session date."))
        else:
            self.stdout.write(f"- **Option 1m OHLCV Bars:** {total_bars:,} total | **Partial Bars:** {partial_bars:,} ({((partial_bars / max(1, total_bars)) * 100):.2f}%)")
            self.stdout.write(f"- **Option Quote Snapshots:** {total_quotes:,} total | **Execution-Eligible:** {eligible_quotes:,} | **Stale Quotes:** {stale_quotes:,}")

        self.stdout.write(f"\n### 2. Signal Funnel & Paper Fills (Session {session_date})")
        self.stdout.write(f"- **Total Signals Recorded:** {total_signals}")
        self.stdout.write(f"- **Executed Fills (Taker):** {fills_count}")
        self.stdout.write(f"- **Rejected Signals:** {rejected_count}")
        if rejections:
            self.stdout.write("  **Rejection Breakdown:**")
            for r in rejections:
                self.stdout.write(f"  - `{r['rejection_reason'] or 'UNSPECIFIED'}`: {r['count']}")
        self.stdout.write(f"- **Pending Liquidity Traps:** {pending_liq_count}")
        self.stdout.write(f"- **Unexecutable Overnight Carry:** {unexec_carry_count}")

        self.stdout.write(f"\n### 3. Open Exposure & Risk")
        self.stdout.write(f"- **Currently Open Positions:** {open_count}")
        self.stdout.write(f"- **Pending Expiry Settlement:** {pending_settle_count}")

        # 6. Per-Strategy Statistical Performance
        strat_ids = [strategy_id] if strategy_id else list(qs.values_list("strategy_id", flat=True).distinct())
        if not strat_ids:
            strat_ids = ["STRAT-ORB-15M"]

        self.stdout.write(f"\n### 4. Per-Strategy Statistical Performance")
        for sid in strat_ids:
            self.stdout.write(f"\n**Strategy: {sid}**")
            
            # Determine health status of the strategy on this session
            from django.core.cache import cache
            health_cache_key = f"fno_strategy_health:{session_date}:{sid}"
            cached_health = cache.get(health_cache_key)

            if total_bars == 0:
                self.stdout.write(self.style.WARNING("  Strategy Execution Status: NO DATA (No market data ingested for this session)"))
            elif total_signals == 0:
                if cached_health and cached_health.get("evaluations_count", 0) > 0:
                    evals = cached_health.get("evaluations_count", 0)
                    or_high = cached_health.get("opening_range_high")
                    or_low = cached_health.get("opening_range_low")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Strategy Execution Status: ACTIVE / VALID NO-SETUP SESSION\n"
                            f"  (Strategy evaluated {evals:,} completed bar events. 15m Opening Range: High ₹{or_high or 'N/A'} | Low ₹{or_low or 'N/A'}. "
                            f"Zero breakout conditions met during this session.)"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "  Strategy Execution Status: NOT EVALUATED / UN-WIRED RUNTIME\n"
                            "  (Active market data was ingested, but 0 signals or audit entries were recorded. "
                            "The strategy orchestrator is not yet wired into the live ticker daemon or runtime scheduler.)"
                        )
                    )
            else:
                self.stdout.write(self.style.SUCCESS("  Strategy Execution Status: ACTIVE / EVALUATED"))

            metrics = StrategyPerformanceEvaluator.evaluate_strategy(
                strategy_id=sid,
                start_date=str(session_date),
                end_date=str(session_date),
            )
            self.stdout.write(f"- **Session Completed Trades:** {metrics.total_trades} (Wins: {metrics.winning_trades}, Losses: {metrics.losing_trades}, Breakeven: {metrics.breakeven_trades})")
            self.stdout.write(f"- **Win Rate:** {metrics.win_rate_pct:.2f}% | **Profit Factor:** {metrics.profit_factor:.2f}")
            self.stdout.write(f"- **Gross P&L:** ₹{metrics.gross_pnl:,.2f}")
            self.stdout.write(f"- **Total Statutory Frictions:** ₹{metrics.total_frictions:,.2f} (Friction Drag: {metrics.friction_drag_pct:.2f}%)")
            self.stdout.write(f"- **Net P&L:** ₹{metrics.net_pnl:,.2f}")
            self.stdout.write(f"- **Expectancy Per Trade:** ₹{metrics.expectancy_per_trade:,.2f}")
            self.stdout.write(f"- **Session Max Drawdown:** ₹{metrics.max_drawdown:,.2f}")

        self.stdout.write(f"\n### 5. Cumulative Trial Context")
        self.stdout.write(f"- **All-Time Ledger Records:** {all_time_total_trades:,}")
        self.stdout.write(f"- **Evaluation Mode:** STRICT SIMULATED PAPER TRADING (`is_paper_trading = True`)")
        self.stdout.write(f"- **Fee Schedule Applied:** {StatutoryFeeCalculator.SCHEDULE_LABEL}")
        self.stdout.write(f"- **Statutory STT Baseline:** {StatutoryFeeCalculator.STATUTORY_STT_SELL_RATE * 100:.2f}% (Sell-side options, Finance (No. 2) Act 2024)")
        self.stdout.write(f"- **Stress STT Rate Modeled:** {StatutoryFeeCalculator.STRESS_STT_SELL_RATE * 100:.2f}% (Sell-side options, +50% conservative stress buffer)")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"Daily paper session report for {session_date} generated successfully."))

