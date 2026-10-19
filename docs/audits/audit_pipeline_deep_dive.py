"""
Thorough Audit Script for Section A, B, C, D of Phase 20A.
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
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

print("=" * 100)
print("PHASE 20A: COMPREHENSIVE PIPELINE AUDIT")
print("=" * 100)

KiteInstrumentRegistry.load_master()

# 1. Universe & Constituents
u = Universe.objects.get(name="NIFTY50")
members = list(UniverseMembership.objects.filter(universe=u, is_active=True).select_related("instrument", "instrument__company").order_by("instrument__symbol"))
print(f"\n[A. UNIVERSE COVERAGE]")
print(f"Universe Name: {u.name} (id={u.id})")
print(f"Active Constituents Count: {len(members)}")

symbols = [m.instrument.symbol for m in members]
print(f"Constituent Symbols ({len(symbols)}): {symbols}")

# Check benchmarks
benchmarks = ["^NSEI", "^NSEBANK", "^BSESN", "^CNXIT"]
bench_insts = {b.symbol: b for b in Instrument.objects.filter(symbol__in=benchmarks)}
print(f"\nBenchmarks in DB ({len(bench_insts)}): {list(bench_insts.keys())}")

# 2. Token mapping & Redis Coverage & Bars Coverage for 2026-10-15
print("\n" + "=" * 100)
print(f"[B. SYMBOL TRACE & COVERAGE MATRIX (2026-10-15)]")
print(f"{'Symbol':<15} | {'Token':<8} | {'RevSym':<12} | {'Redis Last':<10} | {'Redis Vol':<12} | {'1m Bars':<8} | {'5m Bars':<8} | {'15m Bars':<8}")
print("-" * 100)

unmapped_tokens = []
cold_redis = []
missing_1m_bars = []
missing_5m_bars = []

for sym in symbols:
    token = KiteInstrumentRegistry.get_token(sym)
    rev_sym = KiteInstrumentRegistry.get_symbol(token) if token else "None"
    
    # Redis state
    state = cache.get(f"stock_state:{sym}")
    last_price = f"{state.get('last_price', 0):.2f}" if state else "COLD"
    vol = f"{state.get('volume', 0)}" if state else "COLD"
    if not state:
        cold_redis.append(sym)
    if not token:
        unmapped_tokens.append(sym)
        
    # Bars for 2026-10-15
    b_1m = OHLCVBar.objects.filter(instrument__symbol=sym, timeframe="1m", timestamp__date="2026-10-15").count()
    b_5m = OHLCVBar.objects.filter(instrument__symbol=sym, timeframe="5m", timestamp__date="2026-10-15").count()
    b_15m = OHLCVBar.objects.filter(instrument__symbol=sym, timeframe="15m", timestamp__date="2026-10-15").count()
    
    if b_1m == 0:
        missing_1m_bars.append(sym)
    if b_5m == 0:
        missing_5m_bars.append(sym)
        
    print(f"{sym:<15} | {str(token):<8} | {rev_sym:<12} | {last_price:<10} | {vol:<12} | {b_1m:<8} | {b_5m:<8} | {b_15m:<8}")

print("-" * 100)
print(f"Summary for 50 NIFTY 50 Equities:")
print(f"  Unmapped tokens: {len(unmapped_tokens)} {unmapped_tokens}")
print(f"  Cold Redis:      {len(cold_redis)} {cold_redis}")
print(f"  Missing 1m bars: {len(missing_1m_bars)} {missing_1m_bars}")
print(f"  Missing 5m bars: {len(missing_5m_bars)} {missing_5m_bars}")

print("\nBenchmarks Coverage:")
for b in benchmarks:
    token = KiteInstrumentRegistry.get_token(b)
    rev_sym = KiteInstrumentRegistry.get_symbol(token) if token else "None"
    state = cache.get(f"index_state:{b}")
    last_p = f"{state.get('last_price', 0):.2f}" if state else "COLD"
    chg = f"{state.get('change_pct', 0):.2f}%" if state else "COLD"
    b_1m = OHLCVBar.objects.filter(instrument__symbol=b, timeframe="1m", timestamp__date="2026-10-15").count()
    b_5m = OHLCVBar.objects.filter(instrument__symbol=b, timeframe="5m", timestamp__date="2026-10-15").count()
    b_15m = OHLCVBar.objects.filter(instrument__symbol=b, timeframe="15m", timestamp__date="2026-10-15").count()
    print(f"{b:<15} | {str(token):<8} | {rev_sym:<12} | {last_p:<10} | {chg:<12} | {b_1m:<8} | {b_5m:<8} | {b_15m:<8}")

# 3. TATAMOTORS vs TMPV.NS deep dive
print("\n" + "=" * 100)
print("[C. TATAMOTORS / TMPV CANONICAL MAPPING VERIFICATION]")
print(f"TATAMOTORS in Universe: {'TATAMOTORS' in symbols}")
print(f"TMPV in Universe: {'TMPV' in symbols or 'TMPV.NS' in symbols}")

tm_token = KiteInstrumentRegistry.get_token("TATAMOTORS")
tmpv_token = KiteInstrumentRegistry.get_token("TMPV")
tmpv_ns_token = KiteInstrumentRegistry.get_token("TMPV.NS")
print(f"KiteRegistry token for TATAMOTORS: {tm_token}")
print(f"KiteRegistry token for TMPV:       {tmpv_token}")
print(f"KiteRegistry token for TMPV.NS:    {tmpv_ns_token}")
print(f"KiteRegistry reverse for 884737:   {KiteInstrumentRegistry.get_symbol(884737)}")
meta_tm = KiteInstrumentRegistry.get_meta(884737)
print(f"Token 884737 metadata: {meta_tm.get('tradingsymbol')} / {meta_tm.get('name')} / {meta_tm.get('exchange')}")

# Check Redis state for TATAMOTORS vs TMPV
print(f"Redis stock_state:TATAMOTORS: {cache.get('stock_state:TATAMOTORS') is not None}")
print(f"Redis stock_state:TMPV:       {cache.get('stock_state:TMPV') is not None}")
print(f"Redis stock_state:TMPV.NS:    {cache.get('stock_state:TMPV.NS') is not None}")

# 4. Investigate Opportunity Snapshots for 2026-10-15
print("\n" + "=" * 100)
print("[D. OPPORTUNITY SNAPSHOTS FOR 2026-10-15]")
opps_today = IntradayOpportunitySnapshot.objects.filter(timestamp__date="2026-10-15").order_by("-timestamp", "-score")
total_opps = opps_today.count()
distinct_timestamps = opps_today.values_list("timestamp", flat=True).distinct()
print(f"Total opportunity snapshots today: {total_opps}")
print(f"Distinct snapshot timestamps count: {distinct_timestamps.count()}")
for ts in distinct_timestamps[:5]:
    batch = opps_today.filter(timestamp=ts)
    print(f"  Snapshot @ {ts.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S IST')} -> {batch.count()} records. Top: {batch.first().symbol} score={batch.first().score} type={batch.first().opportunity_type}")

# 5. Check Celery task results / logs / Scan Execution details
print("\n" + "=" * 100)
print("[E. SCAN EXECUTION & SKIP REASON INVESTIGATION]")
# Let's inspect run_intraday_strategy_scan code and run it directly to observe return dict
from market.tasks import run_intraday_strategy_scan
print("Running run_intraday_strategy_scan.apply().get():")
res = run_intraday_strategy_scan.apply().get()
print("Scan Result:", res)
