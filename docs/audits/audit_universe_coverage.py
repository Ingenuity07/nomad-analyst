"""
Audit script: detailed database inspection of Universe, UniverseMembership, Instrument, Company.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from market.models import Universe, UniverseMembership, Instrument, Company, OHLCVBar, IntradayOpportunitySnapshot
from market.services.kite_registry import KiteInstrumentRegistry
from django.core.cache import cache

print("=" * 80)
print("DATABASE INVENTORY: UNIVERSES & MEMBERSHIPS")
print("=" * 80)

for u in Universe.objects.all():
    total_m = UniverseMembership.objects.filter(universe=u).count()
    active_m = UniverseMembership.objects.filter(universe=u, is_active=True).count()
    print(f"Universe: id={u.id}, name='{u.name}', description='{u.description}', total_members={total_m}, active_members={active_m}")
    if total_m > 0:
        sample = list(UniverseMembership.objects.filter(universe=u).values_list("instrument__symbol", "is_active")[:10])
        print(f"  Sample members: {sample}")

print("\nTotal Companies in DB:", Company.objects.count())
print("Total Instruments in DB:", Instrument.objects.count())

# Let's inspect instruments with instrument_type='EQUITY' or similar
inst_types = list(Instrument.objects.values_list("instrument_type", flat=True).distinct())
print("Instrument types in DB:", inst_types)

nse_eq_count = Instrument.objects.filter(exchange="NSE").count()
print("NSE instruments count:", nse_eq_count)
nse_symbols = sorted(list(Instrument.objects.filter(exchange="NSE").values_list("symbol", flat=True)))
print(f"NSE symbols count ({len(nse_symbols)}): {nse_symbols[:20]} ... (showing first 20)")

# Check if there's NIFTY 50 constituent JSON or static list
from market.services.kite_registry import CONSTITUENT_SNAPSHOT_FILE
import json
if CONSTITUENT_SNAPSHOT_FILE.exists():
    with open(CONSTITUENT_SNAPSHOT_FILE, "r") as f:
        data = json.load(f)
        constituents = data.get("constituents", [])
        print(f"\nConstituent snapshot file exists: {CONSTITUENT_SNAPSHOT_FILE} with {len(constituents)} constituents")
        print("First 10 snapshot constituents:", [c.get("symbol") for c in constituents[:10]])

# Check Kite registry token resolution
print("\n--- KITE REGISTRY RESOLUTION ---")
KiteInstrumentRegistry.load_master()
benchmarks = ["^NSEI", "^NSEBANK", "^BSESN", "^CNXIT"]
for b in benchmarks:
    token = KiteInstrumentRegistry.get_token(b)
    meta = KiteInstrumentRegistry.get_metadata(token) if token else None
    print(f"Benchmark {b} -> token: {token}, meta: {meta.get('tradingsymbol') if meta else None}")

for s in ["RELIANCE", "TCS", "HDFCBANK", "INFY", "TATAMOTORS", "TMPV.NS", "TMPV"]:
    token = KiteInstrumentRegistry.get_token(s)
    rev_sym = KiteInstrumentRegistry.get_symbol(token) if token else None
    print(f"Symbol {s} -> token: {token}, reverse symbol: {rev_sym}")
