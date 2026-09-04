"""
run_opportunity_scan.py — Django management command.

Runs OpportunityDiscoveryService.scan_universe() against the NIFTY50 universe
using real populated data.

NOTE: Fundamentals are OUT OF SCOPE for Phase 15B.
  - fundamental component will score 0 for all stocks
  - this is CORRECT behaviour — no fake values are inserted
  - the engine still produces valid opportunities driven by
    technical (40%), sector (20%), market (10%), news (10%) components

Usage:
  python manage.py run_opportunity_scan
  python manage.py run_opportunity_scan --horizon DELIVERY_SWING
  python manage.py run_opportunity_scan --horizon LONG_TERM
  python manage.py run_opportunity_scan --universe NIFTY50
  python manage.py run_opportunity_scan --top 10
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run OpportunityDiscoveryService for the NIFTY50 universe."

    def add_arguments(self, parser):
        parser.add_argument("--universe", type=str, default="NIFTY50")
        parser.add_argument(
            "--horizon",
            type=str,
            default="DELIVERY_SWING",
            choices=["DELIVERY_SWING", "LONG_TERM"],
        )
        parser.add_argument(
            "--top",
            type=int,
            default=10,
            help="Number of top-ranked opportunities to display",
        )

    def handle(self, *args, **options):
        from market.services.discovery_service import OpportunityDiscoveryService
        from market.models import StockOpportunitySnapshot

        universe = options["universe"]
        horizon = options["horizon"]
        top_n = options["top"]

        self.stdout.write("=" * 70)
        self.stdout.write(f"OPPORTUNITY SCAN — Universe={universe}, Horizon={horizon}")
        self.stdout.write("=" * 70)
        self.stdout.write("")

        svc = OpportunityDiscoveryService()

        try:
            snapshots = svc.scan_universe(universe, horizon)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Opportunity scan FAILED: {exc}"))
            logger.error(f"run_opportunity_scan: {exc}")
            return

        if not snapshots:
            self.stdout.write(self.style.WARNING(
                "Zero opportunities generated. This may be valid if:\n"
                "  - Market data is insufficient for scoring\n"
                "  - No stocks pass liquidity filters\n"
                "  - Universe has no active members\n"
                "Check logs for details."
            ))
            return

        # Sort by score descending
        snapshots_sorted = sorted(
            snapshots,
            key=lambda s: float(s.final_opportunity_score or 0),
            reverse=True
        )

        self.stdout.write(
            self.style.SUCCESS(f"Generated {len(snapshots)} opportunity snapshots.")
        )
        self.stdout.write(f"\nTop {min(top_n, len(snapshots_sorted))} opportunities:\n")
        self.stdout.write(
            f"{'#':<4} {'Symbol':<12} {'Score':>7}  {'Type':<20}  {'Setup':<25}"
        )
        self.stdout.write("-" * 75)

        for rank, snap in enumerate(snapshots_sorted[:top_n], 1):
            symbol = snap.instrument.symbol
            score = float(snap.final_opportunity_score or 0)
            opp_type = snap.opportunity_type or "—"
            component_scores = snap.component_scores or {}
            tech_score = component_scores.get("technical", 0)
            self.stdout.write(
                f"{rank:<4} {symbol:<12} {score:>7.3f}  {opp_type:<20}  "
                f"tech={tech_score:.3f}"
            )

        # Component breakdown for top 3
        self.stdout.write(f"\nComponent score breakdown (top 3):")
        for snap in snapshots_sorted[:3]:
            cs = snap.component_scores or {}
            self.stdout.write(
                f"  {snap.instrument.symbol}: "
                f"tech={cs.get('technical', 0):.3f} | "
                f"fund={cs.get('fundamental', 0):.3f} | "
                f"sector={cs.get('sector', 0):.3f} | "
                f"market={cs.get('market', 0):.3f} | "
                f"news={cs.get('news', 0):.3f}"
            )

        total_snapshots = StockOpportunitySnapshot.objects.filter(
            universe=universe, horizon=horizon
        ).count()
        self.stdout.write(f"\nTotal {horizon} snapshots in DB for {universe}: {total_snapshots}")
