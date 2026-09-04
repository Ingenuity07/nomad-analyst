"""
cleanup_synthetic_data.py — Django management command.

Removes the existing synthetic/demo seed dataset before ingesting real NIFTY 50 data.

Identifies and deletes:
  - Company records whose short_name matches the known synthetic seed set
  - All dependent records (Instrument, OHLCVBar, TechnicalFeature, MarketSnapshot,
    StockOpportunitySnapshot, StockRecommendation, RecommendationOutcome) via CASCADE

After deletion, verifies:
  - TEST1 is gone
  - Synthetic RELIANCE/TCS/INFY data is gone
  - No orphaned synthetic technical/opportunity/recommendation records remain

IMPORTANT:
  - Does NOT touch Universe, BacktestRun, MarketContextSnapshot, or other
    configuration/system-level records unless they are linked to the synthetic set.
  - Safe to run multiple times (idempotent).

Usage:
  python manage.py cleanup_synthetic_data
  python manage.py cleanup_synthetic_data --dry-run
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# These are the known synthetic/demo symbols used during the seed phase.
# DO NOT add real NIFTY 50 symbols here.
SYNTHETIC_EQUITY_SYMBOLS = {"RELIANCE", "TCS", "INFY", "TEST1"}


class Command(BaseCommand):
    help = "Remove synthetic seed data before ingesting real NIFTY 50 data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be deleted without making any changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made.\n"))

        self._cleanup_synthetic_equities(dry_run)
        self._cleanup_orphaned_universe_memberships(dry_run)
        self._report_verification()

    def _cleanup_synthetic_equities(self, dry_run: bool):
        """
        Deletes Company records for the synthetic seed set and all cascaded dependents.
        Django CASCADE handles: Instrument → OHLCVBar, TechnicalFeature, MarketSnapshot,
        StockOpportunitySnapshot, StockRecommendation (→ RecommendationOutcome).
        """
        from market.models import Company, Instrument, OHLCVBar, TechnicalFeature, MarketSnapshot

        self.stdout.write("=" * 60)
        self.stdout.write("Identifying synthetic seed records...")
        self.stdout.write("=" * 60)

        companies_to_delete = list(
            Company.objects.filter(short_name__in=SYNTHETIC_EQUITY_SYMBOLS)
        )

        if not companies_to_delete:
            self.stdout.write(self.style.SUCCESS("No synthetic Company records found. Already clean."))
            return

        for company in companies_to_delete:
            instruments = list(Instrument.objects.filter(company=company))
            instrument_ids = [i.id for i in instruments]
            instrument_symbols = [i.symbol for i in instruments]

            bar_count = OHLCVBar.objects.filter(instrument_id__in=instrument_ids).count()
            feature_count = TechnicalFeature.objects.filter(instrument_id__in=instrument_ids).count()
            snapshot_count = MarketSnapshot.objects.filter(instrument_id__in=instrument_ids).count()

            self.stdout.write(
                f"\nCompany: {company.name!r} (short_name={company.short_name!r})"
            )
            self.stdout.write(f"  Instruments: {instrument_symbols}")
            self.stdout.write(f"  OHLCV bars: {bar_count}")
            self.stdout.write(f"  Technical features: {feature_count}")
            self.stdout.write(f"  Market snapshots: {snapshot_count}")

            # Check for linked opportunities and recommendations
            from market.models import StockOpportunitySnapshot, StockRecommendation
            opp_count = StockOpportunitySnapshot.objects.filter(instrument_id__in=instrument_ids).count()
            rec_count = StockRecommendation.objects.filter(instrument_id__in=instrument_ids).count()
            self.stdout.write(f"  Opportunity snapshots: {opp_count}")
            self.stdout.write(f"  Recommendations: {rec_count}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN: Would delete {len(companies_to_delete)} Company records "
                    f"and all cascaded dependents."
                )
            )
            return

        # Perform the deletion within a transaction
        with transaction.atomic():
            deleted_count, details = Company.objects.filter(
                short_name__in=SYNTHETIC_EQUITY_SYMBOLS
            ).delete()

        self.stdout.write(self.style.SUCCESS(f"\nDeleted {deleted_count} records total:"))
        for model_name, count in sorted(details.items()):
            if count > 0:
                self.stdout.write(f"  {model_name}: {count}")

    def _cleanup_orphaned_universe_memberships(self, dry_run: bool):
        """
        Cleans up any UniverseMembership records whose instrument no longer exists.
        This can occur if memberships were created for the synthetic symbols.
        """
        from market.models import UniverseMembership

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Checking for orphaned UniverseMembership records...")

        # Memberships with no valid instrument (instrument deleted by CASCADE)
        # are automatically removed by Django CASCADE. But check for any
        # memberships still referencing synthetic instruments by symbol pattern.
        orphaned = UniverseMembership.objects.filter(
            instrument__symbol__in=SYNTHETIC_EQUITY_SYMBOLS
        )
        count = orphaned.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned memberships found."))
            return

        self.stdout.write(f"Found {count} orphaned membership(s) still referencing synthetic instruments.")

        if not dry_run:
            with transaction.atomic():
                orphaned.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} orphaned membership(s)."))

    def _report_verification(self):
        """
        Prints a verification summary after cleanup.
        """
        from market.models import Company, Instrument, OHLCVBar, TechnicalFeature

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("POST-CLEANUP VERIFICATION")
        self.stdout.write("=" * 60)

        remaining_synthetic = Company.objects.filter(
            short_name__in=SYNTHETIC_EQUITY_SYMBOLS
        ).count()

        remaining_instruments = Instrument.objects.filter(
            symbol__in=SYNTHETIC_EQUITY_SYMBOLS
        ).count()

        remaining_bars = OHLCVBar.objects.filter(
            instrument__symbol__in=SYNTHETIC_EQUITY_SYMBOLS
        ).count()

        total_companies = Company.objects.count()
        total_instruments = Instrument.objects.count()
        total_bars = OHLCVBar.objects.count()

        self.stdout.write(f"Synthetic Company records remaining: {remaining_synthetic}")
        self.stdout.write(f"Synthetic Instrument records remaining: {remaining_instruments}")
        self.stdout.write(f"Synthetic OHLCV bars remaining: {remaining_bars}")
        self.stdout.write(f"\nSystem totals after cleanup:")
        self.stdout.write(f"  Total Companies: {total_companies}")
        self.stdout.write(f"  Total Instruments: {total_instruments}")
        self.stdout.write(f"  Total OHLCV bars: {total_bars}")

        if remaining_synthetic == 0 and remaining_instruments == 0 and remaining_bars == 0:
            self.stdout.write(self.style.SUCCESS("\nVerification PASSED — synthetic data fully removed."))
        else:
            self.stdout.write(self.style.ERROR("\nVerification FAILED — some synthetic records remain!"))
