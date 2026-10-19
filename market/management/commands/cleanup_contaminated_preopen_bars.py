"""
cleanup_contaminated_preopen_bars.py — Django management command.

Safely removes pre-open contaminated intraday OHLCV bars (< 09:15:00 IST)
recorded during morning testing prior to continuous market opening.

Scope & Safety Constraints:
  - Strictly targets intraday timeframes ('1m', '5m', '15m').
  - NEVER touches daily bars ('1d'), regular-session bars, or other trading dates.
  - Defaults to --dry-run (preview only).
  - Requires explicit --confirm flag to execute transactional deletion.
  - Idempotent: safe to run multiple times.

Usage:
  # Dry-run preview (default):
  python manage.py cleanup_contaminated_preopen_bars
  python manage.py cleanup_contaminated_preopen_bars --date 2026-10-15 --dry-run

  # Confirmed execution:
  python manage.py cleanup_contaminated_preopen_bars --date 2026-10-15 --confirm
"""

import logging
from collections import defaultdict
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from market.models import OHLCVBar
from market.services.trading_session import REGULAR_SESSION_START, IST_TIMEZONE

logger = logging.getLogger(__name__)

INTRADAY_TIMEFRAMES = ["1m", "5m", "15m"]


class Command(BaseCommand):
    help = "Safely clean up pre-open contaminated intraday OHLCV bars (< 09:15:00 IST)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="2026-10-15",
            help="Session date in YYYY-MM-DD format (IST). Defaults to 2026-10-15.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm and execute transactional deletion of contaminated bars.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicitly request dry-run preview (default behavior if --confirm is not passed).",
        )

    def handle(self, *args, **options):
        session_date_str = options["date"]
        try:
            target_date = date.fromisoformat(session_date_str)
        except ValueError:
            self.stderr.write(self.style.ERROR(f"Invalid date format: {session_date_str}. Expected YYYY-MM-DD."))
            return

        is_confirmed = options["confirm"]
        is_dry_run = options["dry_run"] or not is_confirmed

        self.stdout.write("=" * 80)
        self.stdout.write(f"CONTAMINATED PRE-OPEN BARS CLEANUP AUDIT")
        self.stdout.write(f"Target Session Date (IST): {target_date.isoformat()}")
        self.stdout.write(f"Mode: {'CONFIRMED DELETION' if not is_dry_run else 'DRY RUN (PREVIEW ONLY)'}")
        self.stdout.write("=" * 80)

        # 1. Fetch potential intraday bars within the 24-hour window for target_date IST
        # Convert target_date start and end to UTC
        start_ist = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=IST_TIMEZONE)
        end_ist = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=IST_TIMEZONE)
        start_utc = start_ist.astimezone(ZoneInfo("UTC"))
        end_utc = end_ist.astimezone(ZoneInfo("UTC"))

        intraday_qs = OHLCVBar.objects.filter(
            timeframe__in=INTRADAY_TIMEFRAMES,
            timestamp__gte=start_utc,
            timestamp__lte=end_utc,
        ).select_related("instrument").order_by("timestamp")

        # 2. Filter strictly for bars whose IST timestamp is < 09:15:00
        target_bars = []
        regular_count = 0
        post_count = 0

        for bar in intraday_qs:
            bar_ist = bar.timestamp.astimezone(IST_TIMEZONE)
            if bar_ist.date() != target_date:
                continue
            bar_time = bar_ist.time()
            if bar_time < REGULAR_SESSION_START:
                target_bars.append(bar)
            else:
                regular_count += 1

        total_contaminated = len(target_bars)

        # 3. Verify safety constraints
        # Ensure no daily bars ('1d') are in the target list
        non_intraday = [b for b in target_bars if b.timeframe not in INTRADAY_TIMEFRAMES]
        if non_intraday:
            self.stderr.write(self.style.ERROR(f"FATAL: Non-intraday bars found in target list: {len(non_intraday)}! Aborting."))
            return

        # 4. Group by timeframe and symbol
        by_tf = defaultdict(list)
        symbols = set()
        sources = set()
        timestamps_by_tf = defaultdict(set)

        for b in target_bars:
            by_tf[b.timeframe].append(b)
            symbols.add(b.instrument.symbol)
            sources.add(b.source)
            timestamps_by_tf[b.timeframe].add(b.timestamp.astimezone(IST_TIMEZONE).strftime("%H:%M:%S"))

        self.stdout.write(f"\n[Audit Results for {target_date.isoformat()}]:")
        self.stdout.write(f"  Valid regular-session intraday bars (PRESERVED): {regular_count}")
        self.stdout.write(f"  Contaminated pre-open intraday bars (TARGETED):   {total_contaminated}")
        self.stdout.write(f"  Distinct Instruments Affected:                   {len(symbols)}")
        self.stdout.write(f"  Sources:                                         {', '.join(sorted(sources)) or 'None'}")

        self.stdout.write("\n[Breakdown by Timeframe]:")
        for tf in INTRADAY_TIMEFRAMES:
            bars_for_tf = by_tf.get(tf, [])
            distinct_ts = sorted(timestamps_by_tf.get(tf, []))
            self.stdout.write(
                f"  - Timeframe {tf:3s}: {len(bars_for_tf):4d} bars "
                f"across {len(set(b.instrument_id for b in bars_for_tf)):2d} instruments. "
                f"Timestamps (IST): {distinct_ts}"
            )

        if total_contaminated == 0:
            self.stdout.write(self.style.SUCCESS("\nNo contaminated pre-open bars found. Database is already clean."))
            return

        # 5. Execute or report dry-run
        if is_dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n[DRY RUN SUMMARY]: {total_contaminated} bars WOULD BE DELETED.\n"
                f"No changes were made to the database.\n"
                f"To execute transactional deletion, rerun with: --date {session_date_str} --confirm"
            ))
        else:
            target_ids = [b.id for b in target_bars]
            with transaction.atomic():
                deleted_count, deleted_breakdown = OHLCVBar.objects.filter(id__in=target_ids).delete()
            self.stdout.write(self.style.SUCCESS(
                f"\n[EXECUTION SUMMARY]: Successfully deleted {deleted_count} contaminated bars from database.\n"
                f"Breakdown: {deleted_breakdown}"
            ))
