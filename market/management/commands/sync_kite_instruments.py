"""
sync_kite_instruments.py — Django management command.

Downloads the official Zerodha Kite instrument master and produces the verified
mapping audit for all 50 NIFTY 50 constituents and benchmark indices (^NSEI, ^NSEBANK).

Usage:
  python manage.py sync_kite_instruments
  python manage.py sync_kite_instruments --force-refresh
"""

import logging
from django.core.management.base import BaseCommand
from market.services.kite_registry import KiteInstrumentRegistry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Download Kite instrument master and verify NIFTY 50 symbol-to-token mappings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Force re-downloading master CSV from Zerodha Kite endpoint.",
        )

    def handle(self, *args, **options):
        force_refresh = options["force_refresh"]

        self.stdout.write("=" * 70)
        self.stdout.write("ZERODHA KITE INSTRUMENT MASTER & NIFTY 50 MAPPING AUDIT")
        self.stdout.write("=" * 70)

        try:
            audit = KiteInstrumentRegistry.build_nifty50_mapping()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to build Kite mapping: {e}"))
            raise

        meta = audit["metadata"]
        benchmarks = audit["benchmarks"]
        constituents = audit["constituents"]
        unmapped = audit["unmapped"]

        self.stdout.write(f"Generated at:       {meta['generated_at']}")
        self.stdout.write(f"Source URL:         {meta['master_source']}")
        self.stdout.write(f"NIFTY 50 Total:     {meta['nifty50_constituents_total']}")
        self.stdout.write(f"Mapped Count:       {meta['nifty50_mapped_count']}")
        self.stdout.write(f"Unmapped Count:     {meta['nifty50_unmapped_count']}")
        self.stdout.write(f"Coverage:           {meta['coverage_percent']:.1f}%")

        self.stdout.write("\n" + "-" * 70)
        self.stdout.write("BENCHMARK INDICES MAPPING:")
        self.stdout.write("-" * 70)
        for b in benchmarks:
            self.stdout.write(
                f"  {b['nomad_symbol']:<10} -> {b['kite_tradingsymbol']:<15} "
                f"Token: {b['kite_instrument_token']:<10} Segment: {b['segment']}"
            )

        self.stdout.write("\n" + "-" * 70)
        self.stdout.write(f"NIFTY 50 CONSTITUENTS MAPPING (SAMPLE FIRST 10 OF {len(constituents)}):")
        self.stdout.write("-" * 70)
        for c in constituents[:10]:
            self.stdout.write(
                f"  {c['nomad_symbol']:<12} -> {c['nse_tradingsymbol']:<12} "
                f"Token: {c['kite_instrument_token']:<10} Exchange: {c['exchange']} Type: {c['instrument_type']}"
            )

        if len(constituents) > 10:
            self.stdout.write(f"  ... and {len(constituents) - 10} more constituents mapped.")

        # Check Tata Motors specifically
        tata_entry = next((c for c in constituents if c["nomad_symbol"] in ("TMPV", "TATAMOTORS")), None)
        if tata_entry:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("TATA MOTORS DEMERGER VERIFICATION:")
            self.stdout.write(
                f"  Nomad: {tata_entry['nomad_symbol']} -> Kite: {tata_entry['nse_tradingsymbol']} "
                f"(Token: {tata_entry['kite_instrument_token']}) | Note: {tata_entry.get('notes', 'None')}"
            )
            self.stdout.write("-" * 70)

        if unmapped:
            self.stdout.write(self.style.ERROR(f"\nWARNING: {len(unmapped)} unmapped constituents:"))
            for u in unmapped:
                self.stdout.write(f"  {u['nomad_symbol']} ({u['company_name']})")
        else:
            self.stdout.write(self.style.SUCCESS(f"\nPERFECT: 100% (50/50) NIFTY 50 constituents mapped to valid Kite tokens!"))
