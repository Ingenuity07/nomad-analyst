"""
bootstrap_nifty50_universe.py — Django management command.

Creates the NIFTY 50 universe registry in the database:
  - 50 Company records (with sector/industry metadata)
  - 50 Instrument records (NSE EQUITY)
  - 1 Universe record (name='NIFTY50')
  - 50 UniverseMembership records
  - 2 Benchmark Instrument records (^NSEI, ^NSEBANK as INDEX)

Data source: data/universe/nifty50_constituents_2026-09-03.json
  - Static versioned snapshot as of 2026-09-03
  - Based on NSE NIFTY 50 index composition
  - Verify against current NSE constituent list for production refresh

Idempotent: safe to run multiple times.
  - Uses update_or_create / get_or_create throughout.
  - Will NOT delete existing instruments outside the NIFTY 50 set.

Usage:
  python manage.py bootstrap_nifty50_universe
  python manage.py bootstrap_nifty50_universe --dry-run
"""

import json
import logging
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Path to the versioned constituent snapshot file, relative to Django project root.
CONSTITUENT_FILE = "data/universe/nifty50_constituents_2026-09-03.json"


class Command(BaseCommand):
    help = "Bootstrap NIFTY 50 universe registry from versioned constituent snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be created without making any changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Resolve the constituent file path from Django BASE_DIR
        from django.conf import settings
        constituent_path = os.path.join(settings.BASE_DIR, CONSTITUENT_FILE)

        if not os.path.exists(constituent_path):
            self.stderr.write(
                self.style.ERROR(
                    f"Constituent file not found: {constituent_path}\n"
                    f"Run from the project root directory."
                )
            )
            return

        with open(constituent_path, "r") as f:
            data = json.load(f)

        metadata = data["metadata"]
        constituents = data["constituents"]
        benchmarks = data["benchmarks"]

        self.stdout.write("=" * 60)
        self.stdout.write("NIFTY 50 UNIVERSE BOOTSTRAP")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Snapshot date:  {metadata['snapshot_date']}")
        self.stdout.write(f"Source:         {metadata['source']}")
        self.stdout.write(f"Constituents:   {metadata['constituent_count']}")
        self.stdout.write(f"Benchmarks:     {len(benchmarks)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN — no changes will be made.\n"))
            self._preview(constituents, benchmarks)
            return

        summary = {
            "companies_created": 0,
            "companies_updated": 0,
            "instruments_created": 0,
            "instruments_updated": 0,
            "memberships_created": 0,
            "memberships_already_active": 0,
            "benchmarks_created": 0,
            "benchmarks_updated": 0,
        }

        with transaction.atomic():
            # 1. Create/update the NIFTY50 Universe record
            universe, univ_created = self._get_or_create_universe("NIFTY50", metadata)
            if univ_created:
                self.stdout.write(f"\nCreated Universe: NIFTY50")
            else:
                self.stdout.write(f"\nUniverse already exists: NIFTY50 (active={universe.is_active})")
                if not universe.is_active:
                    universe.is_active = True
                    universe.save()
                    self.stdout.write("  → Reactivated universe.")

            # 2. Process all 50 equity constituents
            self.stdout.write(f"\nProcessing {len(constituents)} constituents...")
            now = timezone.now()

            for entry in constituents:
                company, inst, created_co, created_inst = self._upsert_constituent(entry)

                summary["companies_created" if created_co else "companies_updated"] += 1
                summary["instruments_created" if created_inst else "instruments_updated"] += 1

                # Create or reactivate membership
                from market.models import UniverseMembership
                membership, mem_created = UniverseMembership.objects.get_or_create(
                    universe=universe,
                    instrument=inst,
                    defaults={"added_at": now, "is_active": True}
                )
                if mem_created:
                    summary["memberships_created"] += 1
                else:
                    if not membership.is_active:
                        membership.is_active = True
                        membership.removed_at = None
                        membership.save()
                        summary["memberships_created"] += 1
                    else:
                        summary["memberships_already_active"] += 1

                status = "NEW" if created_inst else "OK"
                self.stdout.write(
                    f"  [{status}] {entry['symbol']:15s} — {entry['company_name'][:45]}"
                )

            # 3. Process benchmark indices (not added to NIFTY50 universe membership)
            self.stdout.write(f"\nProcessing {len(benchmarks)} benchmark instruments...")
            for bench in benchmarks:
                created = self._upsert_benchmark(bench)
                summary["benchmarks_created" if created else "benchmarks_updated"] += 1
                self.stdout.write(f"  {'[NEW]' if created else '[OK] '} {bench['symbol']} — {bench['name']}")

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("BOOTSTRAP COMPLETE")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Companies created:           {summary['companies_created']}")
        self.stdout.write(f"  Companies updated:           {summary['companies_updated']}")
        self.stdout.write(f"  Instruments created:         {summary['instruments_created']}")
        self.stdout.write(f"  Instruments updated:         {summary['instruments_updated']}")
        self.stdout.write(f"  Memberships created:         {summary['memberships_created']}")
        self.stdout.write(f"  Memberships already active:  {summary['memberships_already_active']}")
        self.stdout.write(f"  Benchmark instruments new:   {summary['benchmarks_created']}")

        # Verification counts
        from market.models import Universe, UniverseMembership, Instrument
        total_members = UniverseMembership.objects.filter(
            universe__name="NIFTY50", is_active=True
        ).count()
        total_eq = Instrument.objects.filter(is_active=True, instrument_type="EQUITY").count()

        self.stdout.write(f"\nVerification:")
        self.stdout.write(f"  Active NIFTY50 memberships:  {total_members} (expected 50)")
        self.stdout.write(f"  Total active EQUITY instruments: {total_eq}")

        if total_members == 50:
            self.stdout.write(self.style.SUCCESS("\nUniverse bootstrap PASSED ✓"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nUniverse member count is {total_members}, expected 50. "
                    f"Check for any failed upserts above."
                )
            )

    def _get_or_create_universe(self, name: str, metadata: dict):
        from market.models import Universe
        return Universe.objects.get_or_create(
            name=name,
            defaults={
                "description": (
                    f"NIFTY 50 Index constituent universe. "
                    f"Snapshot: {metadata['snapshot_date']}. "
                    f"Source: {metadata['source_reference']}"
                ),
                "is_active": True,
            }
        )

    def _upsert_constituent(self, entry: dict):
        from market.models import Company, Instrument

        company, created_co = Company.objects.update_or_create(
            short_name=entry["symbol"],
            defaults={
                "name": entry["company_name"],
                "isin": entry.get("isin"),
                "sector": entry.get("sector"),
                "industry": entry.get("industry"),
                "sub_industry": entry.get("sub_industry"),
                "is_active": True,
            }
        )

        instrument, created_inst = Instrument.objects.update_or_create(
            symbol=entry["symbol"],
            defaults={
                "company": company,
                "exchange": entry.get("exchange", "NSE"),
                "isin": entry.get("isin"),
                "instrument_type": "EQUITY",
                "currency": entry.get("currency", "INR"),
                "lot_size": 1,
                "is_active": True,
            }
        )

        return company, instrument, created_co, created_inst

    def _upsert_benchmark(self, bench: dict) -> bool:
        """Create or update a benchmark index instrument. Returns True if newly created."""
        from market.models import Company, Instrument

        company, created_co = Company.objects.update_or_create(
            short_name=bench["symbol"],
            defaults={
                "name": bench["name"],
                "sector": "Index",
                "industry": "Index",
                "is_active": True,
            }
        )

        instrument, created_inst = Instrument.objects.update_or_create(
            symbol=bench["symbol"],
            defaults={
                "company": company,
                "exchange": bench.get("exchange", "NSE"),
                "instrument_type": "INDEX",
                "currency": bench.get("currency", "INR"),
                "is_active": True,
            }
        )
        return created_inst

    def _preview(self, constituents: list, benchmarks: list):
        self.stdout.write(f"\n{'Symbol':<15} {'Company':<50} {'Sector'}")
        self.stdout.write("-" * 85)
        for entry in constituents:
            self.stdout.write(
                f"{entry['symbol']:<15} {entry['company_name'][:48]:<50} {entry['sector']}"
            )
        self.stdout.write("\nBenchmarks:")
        for bench in benchmarks:
            self.stdout.write(f"  {bench['symbol']} — {bench['name']}")
