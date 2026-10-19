"""
ingest_kite_historical.py — Django management command.

Idempotently ingests and backfills historical candles from Kite Connect into OHLCVBar.

Usage:
  python manage.py ingest_kite_historical --stocks RELIANCE,TCS,INFY --timeframe 1d --days 30
  python manage.py ingest_kite_historical --stocks RELIANCE --timeframe 5m --days 5 --mock
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings

from market.models import Instrument
from market.providers.kite import KiteMarketDataProvider
from market.services.kite_historical import KiteHistoricalIngestionService
from market.services.trading_session import TradingSessionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest historical OHLCV bars from Kite into OHLCVBar idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stocks",
            type=str,
            default="RELIANCE,TCS,INFY",
            help="Comma-separated stock symbols.",
        )
        parser.add_argument(
            "--universe",
            type=str,
            default=None,
            help="Name of universe to ingest (e.g. NIFTY50). Overrides --stocks if set.",
        )
        parser.add_argument(
            "--benchmarks",
            action="store_true",
            help="Include benchmark indices (^NSEI, ^NSEBANK, ^BSESN, ^CNXIT).",
        )
        parser.add_argument(
            "--timeframe",
            type=str,
            default="1d",
            choices=["1d", "1m", "5m", "15m", "60m"],
            help="Candle timeframe.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days back to ingest.",
        )
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Use mock Kite provider for deterministic offline testing.",
        )

    def handle(self, *args, **options):
        import time as _time
        from market.models import UniverseMembership

        timeframe = options["timeframe"]
        days_back = options["days"]
        use_mock = options["mock"]

        if options.get("universe"):
            univ_name = options["universe"].strip()
            stock_symbols = list(
                UniverseMembership.objects.filter(
                    universe__name=univ_name, is_active=True
                )
                .order_by("instrument__symbol")
                .values_list("instrument__symbol", flat=True)
            )
            if not stock_symbols:
                self.stdout.write(self.style.ERROR(f"No active instruments found in universe '{univ_name}'."))
                return
            self.stdout.write(f"Resolved {len(stock_symbols)} instruments from universe '{univ_name}'.")
        else:
            stock_symbols = [s.strip().upper() for s in options["stocks"].split(",") if s.strip()]

        if options.get("benchmarks"):
            for b in ("^NSEI", "^NSEBANK", "^BSESN", "^CNXIT"):
                if b not in stock_symbols:
                    stock_symbols.append(b)

        self.stdout.write("=" * 70)
        self.stdout.write(f"KITE HISTORICAL CANDLE INGESTION [{timeframe.upper()}] — {len(stock_symbols)} SYMBOLS")
        self.stdout.write("=" * 70)

        now_ist = TradingSessionService.to_ist()
        start_date = now_ist - timedelta(days=days_back)

        provider = self._get_provider(use_mock)
        service = KiteHistoricalIngestionService(provider=provider)

        total_created = 0
        total_existing = 0

        for sym in stock_symbols:
            inst = Instrument.objects.filter(symbol=sym).first()
            if not inst:
                self.stdout.write(self.style.WARNING(f"Skipping {sym}: Instrument not in database."))
                continue

            try:
                res = service.ingest_symbol(
                    symbol=sym,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=now_ist,
                )
                total_created += res["created"]
                total_existing += res["existing"]

                self.stdout.write(
                    f"  {sym:<10} [{timeframe}] -> Fetched: {res['total_fetched']:<4} | "
                    f"Created: {res['created']:<4} | Existing: {res['existing']:<4} | Errors: {res['errors']}"
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {sym:<10} [{timeframe}] -> FAILED: {e}"))

            if not use_mock:
                _time.sleep(0.35)

        self.stdout.write("-" * 70)
        self.stdout.write(
            f"Summary: Total Created = {total_created}, Total Existing/Skipped = {total_existing}"
        )
        self.stdout.write(self.style.SUCCESS("Ingestion completed idempotently."))

    def _get_provider(self, use_mock: bool):
        if not use_mock:
            return KiteMarketDataProvider()

        class MockKiteClient:
            def historical_data(self, instrument_token, from_date, to_date, interval, continuous=False, oi=False):
                candles = []
                curr = from_date.replace(second=0, microsecond=0)
                base_price = Decimal("2500.00")
                delta_mins = 1 if interval == "minute" else (5 if interval == "5minute" else (15 if interval == "15minute" else 1440))

                while curr <= to_date and len(candles) < 50:
                    if interval == "day" and curr.weekday() >= 5:
                        curr += timedelta(days=1)
                        continue

                    o = base_price + Decimal(str(len(candles) % 10))
                    h = o + Decimal("15.50")
                    l = o - Decimal("12.25")
                    c = o + Decimal("5.00")
                    v = 150000 + (len(candles) * 1000)

                    candles.append([curr.isoformat(), float(o), float(h), float(l), float(c), v])
                    curr += timedelta(minutes=delta_mins)
                return candles

        return KiteMarketDataProvider(kite_client=MockKiteClient())
