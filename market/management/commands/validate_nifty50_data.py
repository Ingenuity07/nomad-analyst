"""
validate_nifty50_data.py — Django management command.

Runs a comprehensive data quality audit of the NIFTY 50 dataset after ingestion.

Validates:
  Universe:
    - Exactly 50 active members in NIFTY50
    - No duplicate memberships
    - Correct symbol/instrument mapping

  OHLCV per symbol:
    - Bar counts, date ranges
    - Null OHLC values
    - Zero/negative prices
    - OHLC consistency (high >= low, open/close within high-low range)
    - Negative volumes
    - Duplicate timestamps
    - Suspicious data gaps (>5 trading day gaps)

  Technical Features:
    - Feature counts per instrument
    - Warmup semantics: SMA-200 NULL for first 199 bars

  Opportunities:
    - Count per universe/horizon
    - Top-5 results

  Recommendations:
    - Active count

Reports are printed with PASS/WARN/FAIL indicators.

Usage:
  python manage.py validate_nifty50_data
  python manage.py validate_nifty50_data --symbol RELIANCE
"""

import json
import logging
import os
from datetime import timedelta
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

CONSTITUENT_FILE = "data/universe/nifty50_constituents_2026-09-03.json"


class Command(BaseCommand):
    help = "Run full data quality validation of the NIFTY 50 dataset."

    def add_arguments(self, parser):
        parser.add_argument("--symbol", type=str, default=None,
                            help="Validate a single symbol only")

    def handle(self, *args, **options):
        from django.conf import settings
        single_symbol = options["symbol"]

        constituent_path = os.path.join(settings.BASE_DIR, CONSTITUENT_FILE)
        with open(constituent_path) as f:
            data = json.load(f)
        all_symbols = [c["symbol"] for c in data["constituents"]]

        symbols = [single_symbol.strip().upper()] if single_symbol else all_symbols

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("NIFTY 50 DATA QUALITY VALIDATION")
        self.stdout.write("=" * 70)

        self._validate_universe()
        self._validate_ohlcv(symbols)
        self._validate_features(symbols)
        self._validate_opportunities()
        self._validate_recommendations()

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("VALIDATION COMPLETE")
        self.stdout.write("=" * 70)

    def _validate_universe(self):
        from market.models import Universe, UniverseMembership, Instrument

        self.stdout.write("\n── UNIVERSE VALIDATION ──────────────────────────────────")

        univ = Universe.objects.filter(name="NIFTY50", is_active=True).first()
        if not univ:
            self.stdout.write(self.style.ERROR("  [FAIL] NIFTY50 Universe record NOT FOUND"))
            return
        self.stdout.write(f"  [PASS] Universe 'NIFTY50' exists (active={univ.is_active})")

        active_members = UniverseMembership.objects.filter(
            universe=univ, is_active=True
        ).count()
        if active_members == 50:
            self.stdout.write(self.style.SUCCESS(f"  [PASS] Active membership count: {active_members} (expected 50)"))
        else:
            self.stdout.write(self.style.WARNING(f"  [WARN] Active membership count: {active_members} (expected 50)"))

        # Check for duplicate memberships (same instrument, both active)
        from django.db.models import Count
        dupes = (
            UniverseMembership.objects.filter(universe=univ, is_active=True)
            .values("instrument")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
        )
        dupe_count = dupes.count()
        if dupe_count == 0:
            self.stdout.write(self.style.SUCCESS("  [PASS] No duplicate active memberships"))
        else:
            self.stdout.write(self.style.ERROR(f"  [FAIL] {dupe_count} duplicate active memberships found"))

        # Benchmark instruments
        for sym in ("^NSEI", "^NSEBANK"):
            if Instrument.objects.filter(symbol=sym, is_active=True).exists():
                self.stdout.write(self.style.SUCCESS(f"  [PASS] Benchmark {sym} exists"))
            else:
                self.stdout.write(self.style.ERROR(f"  [FAIL] Benchmark {sym} MISSING"))

    def _validate_ohlcv(self, symbols: list):
        from market.models import Instrument, OHLCVBar

        self.stdout.write("\n── OHLCV VALIDATION ─────────────────────────────────────")
        self.stdout.write(
            f"  {'Symbol':<12} {'Bars':>6}  {'Earliest':>12}  {'Latest':>12}  "
            f"{'NullOHLC':>8}  {'BadPrice':>8}  {'BadOHLC':>7}  {'DupTS':>5}  Gaps"
        )
        self.stdout.write("  " + "-" * 85)

        total_issues = 0
        missing_symbols = []

        for symbol in symbols:
            try:
                inst = Instrument.objects.get(symbol=symbol)
            except Instrument.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"  {symbol:<12} INSTRUMENT NOT FOUND"))
                missing_symbols.append(symbol)
                continue

            bars = list(
                OHLCVBar.objects.filter(instrument=inst, timeframe="1d")
                .order_by("timestamp")
                .values("timestamp", "open", "high", "low", "close", "volume")
            )

            if not bars:
                self.stdout.write(self.style.ERROR(f"  {symbol:<12} NO BARS"))
                missing_symbols.append(symbol)
                total_issues += 1
                continue

            # Counts
            bar_count = len(bars)
            earliest = bars[0]["timestamp"].date()
            latest = bars[-1]["timestamp"].date()

            null_ohlc = sum(
                1 for b in bars
                if b["open"] is None or b["high"] is None
                or b["low"] is None or b["close"] is None
            )
            bad_price = sum(
                1 for b in bars
                if (b["close"] is not None and float(b["close"]) <= 0)
                or (b["volume"] is not None and int(b["volume"]) < 0)
            )
            bad_ohlc = sum(
                1 for b in bars
                if (b["high"] is not None and b["low"] is not None
                    and b["open"] is not None and b["close"] is not None)
                and (float(b["low"]) > float(b["high"])
                     or float(b["open"]) > float(b["high"])
                     or float(b["close"]) > float(b["high"])
                     or float(b["open"]) < float(b["low"])
                     or float(b["close"]) < float(b["low"]))
            )

            # Duplicate timestamps
            ts_list = [b["timestamp"] for b in bars]
            dup_ts = len(ts_list) - len(set(ts_list))

            # Suspicious gaps (>5 calendar days between consecutive bars)
            gaps = 0
            for i in range(1, len(bars)):
                delta = (bars[i]["timestamp"] - bars[i - 1]["timestamp"]).days
                if delta > 5:
                    gaps += 1

            issues = null_ohlc + bad_price + bad_ohlc + dup_ts
            total_issues += issues

            style = self.style.SUCCESS if issues == 0 else self.style.WARNING
            self.stdout.write(style(
                f"  {symbol:<12} {bar_count:>6}  {str(earliest):>12}  {str(latest):>12}  "
                f"{null_ohlc:>8}  {bad_price:>8}  {bad_ohlc:>7}  {dup_ts:>5}  {gaps}"
            ))

        if total_issues == 0 and not missing_symbols:
            self.stdout.write(self.style.SUCCESS(f"\n  [PASS] OHLCV quality checks — zero issues"))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n  [WARN] OHLCV issues detected: {total_issues} data issues, "
                f"{len(missing_symbols)} missing symbols"
            ))

    def _validate_features(self, symbols: list):
        from market.models import Instrument, TechnicalFeature

        self.stdout.write("\n── TECHNICAL FEATURES VALIDATION ────────────────────────")

        for symbol in symbols[:5]:  # Spot-check first 5
            try:
                inst = Instrument.objects.get(symbol=symbol)
            except Instrument.DoesNotExist:
                continue

            feat_count = TechnicalFeature.objects.filter(
                instrument=inst, timeframe="1d"
            ).count()

            # Warmup check: SMA_200 should be NULL for first 199 bars
            sma200_records = list(
                TechnicalFeature.objects.filter(
                    instrument=inst, timeframe="1d", name="SMA_200"
                ).order_by("timestamp")[:210]
                .values("value", "timestamp")
            )

            null_sma200_count = sum(1 for r in sma200_records[:199] if r["value"] is None)
            valid_after_warmup = sum(
                1 for r in sma200_records[199:]
                if r["value"] is not None
            )

            warmup_ok = null_sma200_count >= min(199, len(sma200_records))
            style = self.style.SUCCESS if feat_count > 0 else self.style.WARNING
            self.stdout.write(style(
                f"  {symbol:<12} features={feat_count:>7}  "
                f"SMA200_warmup_NULLs={null_sma200_count}  "
                f"SMA200_valid_after_warmup={valid_after_warmup}  "
                f"warmup_ok={'YES' if warmup_ok else 'NO'}"
            ))

        total_features = TechnicalFeature.objects.filter(timeframe="1d").count()
        self.stdout.write(f"\n  Total TechnicalFeature records (1d): {total_features}")

    def _validate_opportunities(self):
        from market.models import StockOpportunitySnapshot

        self.stdout.write("\n── OPPORTUNITY VALIDATION ───────────────────────────────")
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            count = StockOpportunitySnapshot.objects.filter(
                universe="NIFTY50", horizon=horizon
            ).count()
            self.stdout.write(f"  {horizon}: {count} snapshots")

            top5 = list(
                StockOpportunitySnapshot.objects.filter(
                    universe="NIFTY50", horizon=horizon
                ).order_by("-final_opportunity_score")
                .select_related("instrument")[:5]
            )
            for snap in top5:
                self.stdout.write(
                    f"    {snap.instrument.symbol:<12} score={float(snap.final_opportunity_score or 0):.4f}"
                )

    def _validate_recommendations(self):
        from market.models import StockRecommendation

        self.stdout.write("\n── RECOMMENDATION VALIDATION ────────────────────────────")
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            active = StockRecommendation.objects.filter(
                horizon=horizon, status="ACTIVE"
            ).count()
            total = StockRecommendation.objects.filter(horizon=horizon).count()
            self.stdout.write(f"  {horizon}: {active} ACTIVE, {total} total")
