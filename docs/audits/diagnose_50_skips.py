"""
Script to evaluate all 50 NIFTY 50 instruments through IntradaySignalEngine and IntradayReadinessService
to establish the exact skip reasons for all 50 instruments.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from market.models import Universe, UniverseMembership, Instrument, OHLCVBar
from market.services.intraday_signal_engine import IntradaySignalEngine
from market.services.intraday_readiness import IntradayReadinessService

IST = ZoneInfo("Asia/Kolkata")
u = Universe.objects.get(name="NIFTY50")
members = list(UniverseMembership.objects.filter(universe=u, is_active=True).select_related("instrument"))
instruments = [m.instrument for m in members]

engine = IntradaySignalEngine()
readiness_svc = IntradayReadinessService()

# Evaluate at 12:00:00 IST on 2026-10-15 (mid-session)
test_as_of_mid = datetime(2026, 10, 15, 12, 0, 0, tzinfo=IST).astimezone(timezone.utc)
# Evaluate at 15:25:00 IST on 2026-10-15 (near market close)
test_as_of_close = datetime(2026, 10, 15, 15, 25, 0, tzinfo=IST).astimezone(timezone.utc)

print("=" * 100)
print("INTRADAY READINESS & SIGNAL ENGINE DIAGNOSTIC FOR 50 NIFTY 50 EQUITIES")
print("=" * 100)

for label, test_dt in [("MID-SESSION (12:00 IST)", test_as_of_mid), ("NEAR-CLOSE (15:25 IST)", test_as_of_close)]:
    print(f"\n--- EVALUATION AT {label} ---")
    readiness_reasons = Counter()
    draft_signals = Counter()
    draft_reasons = Counter()
    
    for inst in instruments:
        r = readiness_svc.check_readiness(inst, "5m", as_of=test_dt)
        readiness_reasons[r.reason] += 1
        
        draft = engine.generate_recommendation(inst, timeframe="5m", as_of=test_dt)
        draft_signals[draft.signal] += 1
        draft_reasons[draft.invalidation_reason or draft.entry_condition or "NO_REASON"] += 1
        
    print(f"Readiness breakdown (Total={len(instruments)}):")
    for reason, count in readiness_reasons.most_common():
        print(f"  [{count:2d}]: {reason}")
        
    print(f"\nDraft Signals breakdown:")
    for sig, count in draft_signals.most_common():
        print(f"  [{count:2d}]: {sig}")
        
    print(f"\nDraft Reasons sample breakdown:")
    for reason, count in draft_reasons.most_common()[:5]:
        print(f"  [{count:2d}]: {reason}")
