import os
import json
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from market.models import Company, IncomeStatement, BalanceSheetStatement, CashFlowStatement, DerivedFundamentalMetric, RawFundamentalData
from market.services.fundamental_service import FundamentalDataService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingests official regulatory fundamental data for NIFTY 50 constituents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/fundamentals/nifty50_fundamentals_2026-09-03.json",
            help="Path to the fundamental snapshot JSON file."
        )
        parser.add_argument(
            "--symbol",
            type=str,
            default=None,
            help="Optional comma-separated list of symbols to ingest (e.g. RELIANCE,TCS)."
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        symbol_filter = options["symbol"]

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        self.stdout.write(f"Loading fundamental snapshot from {file_path}...")
        with open(file_path) as f:
            snapshot = json.load(f)

        companies_dict = snapshot.get("companies", {})
        self.stdout.write(f"Snapshot contains {len(companies_dict)} companies. Provenance: {snapshot.get('provenance', {}).get('source')}")

        target_symbols = None
        if symbol_filter:
            target_symbols = {s.strip().upper() for s in symbol_filter.split(",")}
            self.stdout.write(f"Filtering to symbols: {', '.join(target_symbols)}")

        service = FundamentalDataService()

        total_companies_ingested = 0
        total_statements_ingested = 0
        skipped_companies = 0

        for sym, comp_data in companies_dict.items():
            if target_symbols and sym not in target_symbols:
                continue

            try:
                count = service.ingest_company_financials_from_snapshot(comp_data)
                if count > 0:
                    total_companies_ingested += 1
                    total_statements_ingested += count
                    self.stdout.write(self.style.SUCCESS(f"  [OK] {sym:<12}: {count} statements ingested & metrics computed."))
                else:
                    skipped_companies += 1
                    self.stdout.write(self.style.WARNING(f"  [SKIP] {sym:<12}: 0 statements or company missing."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  [ERROR] {sym:<12}: Failed ({e})"))

        self.stdout.write(self.style.SUCCESS("\n=== FUNDAMENTALS INGESTION SUMMARY ==="))
        self.stdout.write(f"Total companies ingested: {total_companies_ingested}")
        self.stdout.write(f"Total statements ingested: {total_statements_ingested}")
        self.stdout.write(f"Skipped companies: {skipped_companies}")
        self.stdout.write(f"Total IncomeStatement records: {IncomeStatement.objects.count()}")
        self.stdout.write(f"Total BalanceSheetStatement records: {BalanceSheetStatement.objects.count()}")
        self.stdout.write(f"Total CashFlowStatement records: {CashFlowStatement.objects.count()}")
        self.stdout.write(f"Total DerivedFundamentalMetric records: {DerivedFundamentalMetric.objects.count()}")
        self.stdout.write(f"Total RawFundamentalData records: {RawFundamentalData.objects.count()}")
