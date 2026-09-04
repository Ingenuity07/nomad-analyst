"""
run_recommendation_scan.py — Django management command.

Runs RecommendationService.scan_and_recommend() against the NIFTY50 universe.
Uses the existing deterministic SignalEngine — no LLM calls are made.

Usage:
  python manage.py run_recommendation_scan
  python manage.py run_recommendation_scan --horizon DELIVERY_SWING
  python manage.py run_recommendation_scan --horizon LONG_TERM
  python manage.py run_recommendation_scan --universe NIFTY50
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run RecommendationService scan for NIFTY50 universe."

    def add_arguments(self, parser):
        parser.add_argument("--universe", type=str, default="NIFTY50")
        parser.add_argument(
            "--horizon",
            type=str,
            default="DELIVERY_SWING",
            choices=["DELIVERY_SWING", "LONG_TERM"],
        )

    def handle(self, *args, **options):
        from market.services.recommendation_service import RecommendationService
        from market.models import StockRecommendation

        universe = options["universe"]
        horizon = options["horizon"]

        self.stdout.write("=" * 70)
        self.stdout.write(f"RECOMMENDATION SCAN — Universe={universe}, Horizon={horizon}")
        self.stdout.write("=" * 70)

        svc = RecommendationService()

        try:
            result = svc.scan_and_recommend(universe, horizon)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Recommendation scan FAILED: {exc}"))
            logger.error(f"run_recommendation_scan: {exc}")
            return

        generated = result.get("generated", 0)
        errors = result.get("errors", 0)

        self.stdout.write(
            self.style.SUCCESS(f"Scan complete — generated={generated}, errors={errors}")
        )

        # Show sample active recommendations
        active = list(
            StockRecommendation.objects.filter(
                horizon=horizon, status="ACTIVE"
            ).select_related("instrument").order_by("-as_of")[:10]
        )

        if not active:
            self.stdout.write(self.style.WARNING(
                "\nNo ACTIVE recommendations generated. "
                "This is valid if signal engine requires stronger setups than current data provides."
            ))
            return

        self.stdout.write(f"\nSample active recommendations ({len(active)}):\n")
        self.stdout.write(
            f"{'Symbol':<12} {'Signal':<6} {'Setup':<25} {'Entry':>10} {'Stop':>10} {'Target':>10} {'R:R':>6}"
        )
        self.stdout.write("-" * 85)

        for rec in active:
            entry = f"{float(rec.entry_price):.1f}" if rec.entry_price else "—"
            stop = f"{float(rec.stop_price):.1f}" if rec.stop_price else "—"
            target = f"{float(rec.target_price):.1f}" if rec.target_price else "—"
            rr = f"{float(rec.risk_reward_ratio):.2f}" if rec.risk_reward_ratio else "—"
            self.stdout.write(
                f"{rec.instrument.symbol:<12} {rec.signal:<6} {(rec.setup_type or '—')[:24]:<25} "
                f"{entry:>10} {stop:>10} {target:>10} {rr:>6}"
            )

        total_recs = StockRecommendation.objects.filter(horizon=horizon).count()
        self.stdout.write(f"\nTotal {horizon} recommendations in DB: {total_recs}")
