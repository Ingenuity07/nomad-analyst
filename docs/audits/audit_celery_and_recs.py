"""
Audit script: Deep dive into today's (2026-10-15) Celery task executions, MarketContextSnapshots,
and the Strategy Scan execution details.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from market.models import (
    MarketContextSnapshot, StockIntradayContext, IntradayOpportunitySnapshot,
    OHLCVBar, Instrument
)
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

print("=" * 100)
print("AUDIT: CELERY BEAT SCHEDULE & SNAPSHOTS & RECOMMENDATIONS")
print("=" * 100)

# 1. Periodic Tasks configured
print("\n[1. PERIODIC TASKS CONFIGURED IN CELERY BEAT]")
for pt in PeriodicTask.objects.all():
    sched = pt.interval or pt.crontab
    print(f"  Task: {pt.name:<40} | Enabled: {str(pt.enabled):<5} | Schedule: {str(sched):<25} | Last Run: {pt.last_run_at} | Total Run Count: {pt.total_run_count}")

# 2. MarketContextSnapshots for today
print("\n[2. MARKET CONTEXT SNAPSHOTS TODAY (2026-10-15)]")
snaps = MarketContextSnapshot.objects.filter(as_of__date="2026-10-15").order_by("as_of")
print(f"Total MarketContextSnapshots today: {snaps.count()}")
if snaps.exists():
    first_snap = snaps.first()
    last_snap = snaps.last()
    print(f"  First Snapshot: {first_snap.as_of.astimezone(IST).strftime('%H:%M:%S IST')} | Regime: {first_snap.market_regime} | A/D: {first_snap.advance_count}/{first_snap.decline_count} | Leader: {first_snap.sector_leader}")
    print(f"  Last Snapshot:  {last_snap.as_of.astimezone(IST).strftime('%H:%M:%S IST')} | Regime: {last_snap.market_regime} | A/D: {last_snap.advance_count}/{last_snap.decline_count} | Leader: {last_snap.sector_leader}")

# 3. StockIntradayContext for today
print("\n[3. STOCK INTRADAY CONTEXT TODAY (2026-10-15)]")
stock_ctxs = StockIntradayContext.objects.filter(timestamp__date="2026-10-15")
print(f"Total StockIntradayContext rows today: {stock_ctxs.count()}")
if stock_ctxs.exists():
    distinct_symbols = stock_ctxs.values_list("instrument__symbol", flat=True).distinct()
    print(f"  Distinct symbols represented: {distinct_symbols.count()}")
    distinct_timestamps = stock_ctxs.values_list("timestamp", flat=True).distinct()
    print(f"  Distinct timestamps: {distinct_timestamps.count()}")

# 4. Check all Recommendation models / records in database
print("\n[4. RECOMMENDATIONS IN DATABASE]")
try:
    from market.models import RecommendationDraft
    print("RecommendationDraft count:", RecommendationDraft.objects.count())
except Exception as e:
    print("RecommendationDraft model:", e)

# Let's inspect all models in market app
from django.apps import apps
market_models = apps.get_app_config("market").get_models()
print("Market app models:", [m.__name__ for m in market_models])

for model_name in ["Recommendation", "RecommendationRecord", "RecommendationDraft", "IntradaySignal"]:
    model = apps.get_model("market", model_name) if model_name in [m.__name__ for m in market_models] else None
    if model:
        count_all = model.objects.count()
        today_field = "created_at" if hasattr(model, "created_at") else ("generated_at" if hasattr(model, "generated_at") else "timestamp")
        kwargs = {f"{today_field}__date": "2026-10-15"} if hasattr(model, today_field) else {}
        count_today = model.objects.filter(**kwargs).count() if kwargs else "N/A"
        print(f"  Model {model_name}: total={count_all}, today={count_today}")
        if count_all > 0:
            sample = list(model.objects.order_by("-id").values()[:2])
            print(f"    Latest sample: {sample}")
