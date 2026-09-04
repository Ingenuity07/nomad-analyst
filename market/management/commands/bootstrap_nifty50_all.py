"""
bootstrap_nifty50_all.py — Django management command.

Orchestrates the complete Phase 15B NIFTY 50 data foundation bootstrap in order:

  1. cleanup_synthetic_data      — Remove TEST1, synthetic RELIANCE/TCS/INFY
  2. bootstrap_nifty50_universe  — Create 50 instruments + Universe + memberships
  3. ingest_nifty50_ohlcv        — Fetch ~2y daily OHLCV for 50 stocks + 2 benchmarks
  4. run_feature_engine          — Compute technical features for all 50
  5. run_market_context          — Compute MarketContextSnapshot
  6. run_opportunity_scan (x2)   — DELIVERY_SWING + LONG_TERM
  7. run_recommendation_scan (x2)— DELIVERY_SWING + LONG_TERM
  8. validate_nifty50_data       — Full quality audit

Usage:
  python manage.py bootstrap_nifty50_all
  python manage.py bootstrap_nifty50_all --skip-cleanup   # skip step 1
  python manage.py bootstrap_nifty50_all --skip-ingestion # skip OHLCV fetch
  python manage.py bootstrap_nifty50_all --dry-run        # preview only
"""

import logging
import sys
from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Full NIFTY 50 Phase 15B bootstrap — runs all stages in order."

    def add_arguments(self, parser):
        parser.add_argument("--skip-cleanup", action="store_true",
                            help="Skip synthetic data cleanup (step 1)")
        parser.add_argument("--skip-ingestion", action="store_true",
                            help="Skip OHLCV ingestion (step 3) — use if data already present")
        parser.add_argument("--skip-features", action="store_true",
                            help="Skip feature engine (step 4)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Preview cleanup and universe bootstrap; skip network calls")
        parser.add_argument("--days-back", type=int, default=730,
                            help="Days of OHLCV history to fetch (default 730 = ~2 years)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_cleanup = options["skip_cleanup"]
        skip_ingestion = options["skip_ingestion"]
        skip_features = options["skip_features"]
        days_back = options["days_back"]

        self.stdout.write("\n" + "█" * 70)
        self.stdout.write("  NOMAD ANALYST — PHASE 15B NIFTY 50 BOOTSTRAP")
        self.stdout.write("█" * 70)

        stage_results = {}

        # ── Stage 1: Cleanup ──────────────────────────────────────────────────
        if not skip_cleanup:
            self._run_stage(
                "1. Synthetic data cleanup",
                stage_results,
                lambda: call_command("cleanup_synthetic_data", dry_run=dry_run,
                                     stdout=self.stdout, stderr=self.stderr)
            )
        else:
            self.stdout.write("\n[SKIP] Stage 1: Synthetic data cleanup")

        # ── Stage 2: Universe registry ────────────────────────────────────────
        self._run_stage(
            "2. NIFTY50 Universe registry",
            stage_results,
            lambda: call_command("bootstrap_nifty50_universe", dry_run=dry_run,
                                 stdout=self.stdout, stderr=self.stderr)
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN: Stopping after Stage 2. No network calls made."))
            return

        # ── Stage 3: OHLCV Ingestion ──────────────────────────────────────────
        if not skip_ingestion:
            self._run_stage(
                "3. Historical OHLCV ingestion (~2y, 50 stocks + 2 benchmarks)",
                stage_results,
                lambda: call_command("ingest_nifty50_ohlcv", days_back=days_back,
                                     stdout=self.stdout, stderr=self.stderr)
            )
        else:
            self.stdout.write("\n[SKIP] Stage 3: OHLCV ingestion")

        # ── Stage 4: Feature Engine ───────────────────────────────────────────
        if not skip_features:
            self._run_stage(
                "4. Technical feature engine",
                stage_results,
                lambda: call_command("run_feature_engine",
                                     stdout=self.stdout, stderr=self.stderr)
            )
        else:
            self.stdout.write("\n[SKIP] Stage 4: Feature engine")

        # ── Stage 5: Market Context ───────────────────────────────────────────
        self._run_stage(
            "5. Market context computation",
            stage_results,
            lambda: call_command("run_market_context",
                                 stdout=self.stdout, stderr=self.stderr)
        )

        # ── Stage 6: Opportunity Scans ────────────────────────────────────────
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            self._run_stage(
                f"6. Opportunity scan [{horizon}]",
                stage_results,
                lambda h=horizon: call_command("run_opportunity_scan", horizon=h,
                                               stdout=self.stdout, stderr=self.stderr)
            )

        # ── Stage 7: Recommendation Scans ────────────────────────────────────
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            self._run_stage(
                f"7. Recommendation scan [{horizon}]",
                stage_results,
                lambda h=horizon: call_command("run_recommendation_scan", horizon=h,
                                               stdout=self.stdout, stderr=self.stderr)
            )

        # ── Stage 8: Validation ───────────────────────────────────────────────
        self._run_stage(
            "8. Data quality validation",
            stage_results,
            lambda: call_command("validate_nifty50_data",
                                 stdout=self.stdout, stderr=self.stderr)
        )

        # ── Final Report ──────────────────────────────────────────────────────
        self.stdout.write("\n" + "█" * 70)
        self.stdout.write("  PHASE 15B BOOTSTRAP — STAGE SUMMARY")
        self.stdout.write("█" * 70)
        for stage, status in stage_results.items():
            if status == "OK":
                self.stdout.write(self.style.SUCCESS(f"  [OK]   {stage}"))
            elif status == "FAILED":
                self.stdout.write(self.style.ERROR(f"  [FAIL] {stage}"))
            else:
                self.stdout.write(f"  [{status}] {stage}")

        failed = [s for s, st in stage_results.items() if st == "FAILED"]
        if not failed:
            self.stdout.write(self.style.SUCCESS("\n  Phase 15B bootstrap COMPLETE ✓"))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n  Phase 15B bootstrap PARTIAL — {len(failed)} stage(s) failed."
            ))

    def _run_stage(self, label: str, results: dict, fn):
        self.stdout.write(f"\n{'─' * 70}")
        self.stdout.write(f"  STAGE: {label}")
        self.stdout.write("─" * 70)
        try:
            fn()
            results[label] = "OK"
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  Stage FAILED: {exc}"))
            logger.error(f"bootstrap_nifty50_all: stage '{label}' failed: {exc}")
            results[label] = "FAILED"
