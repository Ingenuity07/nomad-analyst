"""
ingest_nifty50_ohlcv.py — Django management command.

Fetches ~2 years of daily OHLCV history for all 50 NIFTY 50 constituents
and 2 benchmark indices (^NSEI, ^NSEBANK) using the existing
MarketService.fetch_and_save_historical_ohlcv() pipeline.

Design rules:
  - Reads universe from data/universe/nifty50_constituents_2026-09-03.json
  - Uses existing YFinanceMarketProvider via MarketService (no direct coupling)
  - Adds 2-second sleep between symbols to respect Yahoo Finance rate limits
  - One symbol failure does NOT abort the run — logged and counted as failed
  - Idempotent: re-running skips bars that already exist (existing timestamp exclusion)
  - Reports per-symbol bar counts and a final summary table

Price convention: unadjusted (Yahoo Finance Chart API, as per existing architecture)

Usage:
  python manage.py ingest_nifty50_ohlcv
  python manage.py ingest_nifty50_ohlcv --days-back 730
  python manage.py ingest_nifty50_ohlcv --symbol RELIANCE
  python manage.py ingest_nifty50_ohlcv --symbol "M&M"    # URL encoding handled internally
  python manage.py ingest_nifty50_ohlcv --benchmarks-only
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

CONSTITUENT_FILE = "data/universe/nifty50_constituents_2026-09-03.json"
DEFAULT_DAYS_BACK = 730       # 2 years
RATE_LIMIT_SLEEP = 2.0        # seconds between HTTP requests
BENCHMARK_SYMBOLS = ["^NSEI", "^NSEBANK"]


class Command(BaseCommand):
    help = "Ingest historical daily OHLCV for NIFTY 50 universe + benchmarks via MarketService."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-back",
            type=int,
            default=DEFAULT_DAYS_BACK,
            help=f"Number of calendar days to look back (default: {DEFAULT_DAYS_BACK})",
        )
        parser.add_argument(
            "--symbol",
            type=str,
            default=None,
            help="Ingest a single symbol only (for targeted re-runs)",
        )
        parser.add_argument(
            "--benchmarks-only",
            action="store_true",
            help="Ingest benchmark indices (^NSEI, ^NSEBANK) only",
        )
        parser.add_argument(
            "--skip-benchmarks",
            action="store_true",
            help="Skip benchmark indices, ingest equities only",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from market.services.market_service import MarketService

        days_back = options["days_back"]
        single_symbol = options["symbol"]
        benchmarks_only = options["benchmarks_only"]
        skip_benchmarks = options["skip_benchmarks"]

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)

        # Load constituent file
        constituent_path = os.path.join(settings.BASE_DIR, CONSTITUENT_FILE)
        if not os.path.exists(constituent_path):
            self.stderr.write(self.style.ERROR(
                f"Constituent file not found: {constituent_path}\n"
                "Run bootstrap_nifty50_universe first."
            ))
            return

        with open(constituent_path, "r") as f:
            data = json.load(f)

        constituent_symbols = [c["symbol"] for c in data["constituents"]]

        # Build symbol list
        if single_symbol:
            symbols = [single_symbol.strip().upper()]
            include_benchmarks = False
        elif benchmarks_only:
            symbols = []
            include_benchmarks = True
        else:
            symbols = constituent_symbols
            include_benchmarks = not skip_benchmarks

        if include_benchmarks:
            benchmark_list = BENCHMARK_SYMBOLS
        else:
            benchmark_list = []

        all_symbols = symbols + benchmark_list
        total = len(all_symbols)

        self.stdout.write("=" * 70)
        self.stdout.write("NIFTY 50 OHLCV INGESTION")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Start date:  {start_date.date()}")
        self.stdout.write(f"End date:    {end_date.date()}")
        self.stdout.write(f"Days back:   {days_back}")
        self.stdout.write(f"Symbols:     {len(symbols)} equities + {len(benchmark_list)} benchmarks = {total} total")
        self.stdout.write(f"Rate limit:  {RATE_LIMIT_SLEEP}s between requests")
        self.stdout.write("")

        svc = MarketService()
        results = {}

        for idx, symbol in enumerate(all_symbols, 1):
            self.stdout.write(f"[{idx:2d}/{total}] {symbol:<15}", ending=" ")

            try:
                bars = svc.fetch_and_save_historical_ohlcv(
                    symbol=symbol,
                    timeframe="1d",
                    start_date=start_date,
                    end_date=end_date,
                )

                # Count newly-ingested vs total existing after this run
                from market.models import Instrument, OHLCVBar
                try:
                    inst = Instrument.objects.get(symbol=symbol)
                    total_bars = OHLCVBar.objects.filter(
                        instrument=inst, timeframe="1d"
                    ).count()
                    earliest = OHLCVBar.objects.filter(
                        instrument=inst, timeframe="1d"
                    ).order_by("timestamp").values_list("timestamp", flat=True).first()
                    latest = OHLCVBar.objects.filter(
                        instrument=inst, timeframe="1d"
                    ).order_by("-timestamp").values_list("timestamp", flat=True).first()
                except Instrument.DoesNotExist:
                    total_bars, earliest, latest = 0, None, None

                results[symbol] = {
                    "status": "success",
                    "total_bars": total_bars,
                    "earliest": earliest.date() if earliest else None,
                    "latest": latest.date() if latest else None,
                    "error": None,
                }

                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK — {total_bars} total bars "
                        f"({results[symbol]['earliest']} → {results[symbol]['latest']})"
                    )
                )

            except Exception as exc:
                error_msg = str(exc)[:120]
                results[symbol] = {
                    "status": "failed",
                    "total_bars": 0,
                    "earliest": None,
                    "latest": None,
                    "error": error_msg,
                }
                self.stdout.write(self.style.ERROR(f"FAILED — {error_msg}"))
                logger.error(f"ingest_nifty50_ohlcv: failed for {symbol}: {exc}")

            # Rate-limit sleep (skip on last symbol)
            if idx < total:
                time.sleep(RATE_LIMIT_SLEEP)

        # ── Final Summary ─────────────────────────────────────────────────────
        success = [s for s, r in results.items() if r["status"] == "success"]
        failed = [s for s, r in results.items() if r["status"] == "failed"]
        total_bars_ingested = sum(r["total_bars"] for r in results.values())

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("INGESTION SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Requested:   {total}")
        self.stdout.write(f"Successful:  {len(success)}")
        self.stdout.write(f"Failed:      {len(failed)}")
        self.stdout.write(f"Total bars in DB (all timeframes combined): {total_bars_ingested}")

        if failed:
            self.stdout.write(self.style.ERROR("\nFailed symbols:"))
            for sym in failed:
                self.stdout.write(f"  {sym:<15} — {results[sym]['error']}")

        # ── Per-Symbol Detail Table ────────────────────────────────────────────
        self.stdout.write("\n" + "-" * 70)
        self.stdout.write(f"{'Symbol':<15} {'Status':<10} {'Bars':>6}  {'Earliest':>12}  {'Latest':>12}")
        self.stdout.write("-" * 70)
        for sym in all_symbols:
            r = results[sym]
            status_str = "OK" if r["status"] == "success" else "FAILED"
            self.stdout.write(
                f"{sym:<15} {status_str:<10} {r['total_bars']:>6}  "
                f"{str(r['earliest']):>12}  {str(r['latest']):>12}"
            )

        if len(failed) == 0:
            self.stdout.write(self.style.SUCCESS("\nAll symbols ingested successfully ✓"))
        elif len(failed) < len(all_symbols):
            self.stdout.write(self.style.WARNING(
                f"\nPartial success: {len(failed)} symbol(s) failed. "
                f"Re-run with --symbol <SYMBOL> to retry."
            ))
        else:
            self.stdout.write(self.style.ERROR("\nAll symbols failed. Check network connectivity and Yahoo Finance availability."))
