"""
run_feature_engine.py — Django management command.

Runs TechnicalFeatureEngine.calculate_and_save_features() for all NIFTY 50
instruments (and optionally benchmarks).

Indicators computed (by existing engine):
  SMA 20, 50, 200 | EMA 20, 50, 200 | RSI 14 | MACD (12,26,9)
  ATR 14 | Rolling Volatility 20 | Volume SMA 20 | Relative Volume
  Rolling High/Low 20 | Daily Return | Cumulative Return

Warmup semantics (existing engine):
  - Bars within warmup window produce NaN, stored as NULL in TechnicalFeature.value
  - SMA-200 is NULL for first 199 bars — this is CORRECT, not an error
  - Do not fill warmup NaN values

Idempotent: engine does DELETE + bulk_create per instrument/timeframe.

Usage:
  python manage.py run_feature_engine
  python manage.py run_feature_engine --symbol RELIANCE
  python manage.py run_feature_engine --include-benchmarks
"""

import json
import logging
import os
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

CONSTITUENT_FILE = "data/universe/nifty50_constituents_2026-09-03.json"


class Command(BaseCommand):
    help = "Run TechnicalFeatureEngine for all NIFTY 50 instruments."

    def add_arguments(self, parser):
        parser.add_argument("--symbol", type=str, default=None)
        parser.add_argument("--timeframe", type=str, default="1d")
        parser.add_argument(
            "--include-benchmarks",
            action="store_true",
            help="Also run feature engine for ^NSEI and ^NSEBANK",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from market.models import Instrument
        from market.services.market_service import MarketService

        timeframe = options["timeframe"]
        single_symbol = options["symbol"]
        include_benchmarks = options["include_benchmarks"]

        if single_symbol:
            symbols = [single_symbol.strip().upper()]
        else:
            constituent_path = os.path.join(settings.BASE_DIR, CONSTITUENT_FILE)
            with open(constituent_path) as f:
                data = json.load(f)
            symbols = [c["symbol"] for c in data["constituents"]]
            if include_benchmarks:
                symbols += ["^NSEI", "^NSEBANK"]

        svc = MarketService()
        total = len(symbols)
        results = {}

        self.stdout.write("=" * 60)
        self.stdout.write(f"TECHNICAL FEATURE ENGINE — {total} instrument(s), timeframe={timeframe}")
        self.stdout.write("=" * 60)

        for idx, symbol in enumerate(symbols, 1):
            self.stdout.write(f"[{idx:2d}/{total}] {symbol:<15}", ending=" ")
            try:
                count = svc.calculate_features(symbol, timeframe)
                results[symbol] = {"status": "success", "features": count}
                self.stdout.write(self.style.SUCCESS(f"OK — {count} feature records"))
            except Exception as exc:
                results[symbol] = {"status": "failed", "features": 0, "error": str(exc)[:100]}
                self.stdout.write(self.style.ERROR(f"FAILED — {exc}"))
                logger.error(f"run_feature_engine: {symbol}: {exc}")

        success = [s for s, r in results.items() if r["status"] == "success"]
        failed = [s for s, r in results.items() if r["status"] == "failed"]
        total_features = sum(r["features"] for r in results.values())

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("FEATURE ENGINE SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Instruments processed: {len(success)}/{total}")
        self.stdout.write(f"Total feature records: {total_features}")
        self.stdout.write(f"Failed: {len(failed)}")
        if failed:
            self.stdout.write(self.style.ERROR("Failed symbols: " + ", ".join(failed)))

        if len(failed) == 0:
            self.stdout.write(self.style.SUCCESS("Feature engine run COMPLETE ✓"))
