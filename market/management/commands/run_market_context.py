"""
run_market_context.py — Django management command.

Runs the existing MarketContextService to compute and save a
MarketContextSnapshot from the real NIFTY 50 data.

Requires:
  - ^NSEI and ^NSEBANK OHLCVBar records populated
  - TechnicalFeatures for ^NSEI populated

Usage:
  python manage.py run_market_context
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run MarketContextService and save a MarketContextSnapshot."

    def handle(self, *args, **options):
        from market.services.context_service import MarketContextService
        from market.models import MarketContextSnapshot

        self.stdout.write("=" * 60)
        self.stdout.write("MARKET CONTEXT COMPUTATION")
        self.stdout.write("=" * 60)

        svc = MarketContextService()

        try:
            context = svc.get_market_context()
            snapshot = svc.save_market_context_snapshot(context)

            self.stdout.write(self.style.SUCCESS(
                f"MarketContextSnapshot saved — as_of: {snapshot.as_of}"
            ))

            # Print key context fields if available
            if hasattr(context, "index_regimes") and context.index_regimes:
                self.stdout.write(f"\nIndex regimes: {context.index_regimes}")
            if hasattr(context, "breadth") and context.breadth:
                self.stdout.write(f"Breadth: {context.breadth}")

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Market context computation FAILED: {exc}"))
            logger.error(f"run_market_context: {exc}")

        # Report snapshot count
        count = MarketContextSnapshot.objects.count()
        self.stdout.write(f"\nTotal MarketContextSnapshot records: {count}")
