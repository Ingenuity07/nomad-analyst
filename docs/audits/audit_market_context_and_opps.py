"""
Script to audit Section C: Market Context & Opportunity Generation.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from market.models import MarketContextSnapshot, IntradayOpportunitySnapshot
from django.db.models import Count

print("=" * 100)
print("AUDIT: SECTION C — MARKET CONTEXT & OPPORTUNITY SNAPSHOTS")
print("=" * 100)

# 1. MarketContextSnapshot inspection
latest_snap = MarketContextSnapshot.objects.filter(as_of__date="2026-10-15").order_by("-as_of").first()
if latest_snap:
    print(f"Latest MarketContextSnapshot @ {latest_snap.as_of}:")
    print(f"  Regime: {latest_snap.market_regime}, Direction: {latest_snap.market_direction}")
    print(f"  NIFTY return: {latest_snap.nifty_return}%, BANKNIFTY return: {latest_snap.banknifty_return}%")
    print(f"  Breadth: Advances={latest_snap.advance_count}, Declines={latest_snap.decline_count}, A/D ratio={latest_snap.advance_decline_ratio}")
    print(f"  Sector Leader: {latest_snap.sector_leader}, Laggard: {latest_snap.sector_laggard}")
    print(f"  Index Regimes in JSON: {latest_snap.index_regimes}")
    print(f"  Breadth JSON: {latest_snap.breadth}")
    print(f"  Sector Rankings (top 3): {latest_snap.sector_rankings[:3] if latest_snap.sector_rankings else 'None'}")
    print(f"  Data quality: {latest_snap.data_quality}")

# 2. Check all 4 indices in index_regimes
if latest_snap and latest_snap.index_regimes:
    print("\nIndex routing verification in index_regimes:")
    for idx_key in ["nifty", "banknifty", "sensex", "nifty_it"]:
        info = latest_snap.index_regimes.get(idx_key)
        print(f"  {idx_key}: {info}")

# 3. Opportunity Snapshots deduplication inspection
print("\n" + "-" * 100)
print("OPPORTUNITY SNAPSHOT DEDUPLICATION CHECK")
duplicates = (
    IntradayOpportunitySnapshot.objects
    .filter(timestamp__date="2026-10-15")
    .values("symbol", "timestamp")
    .annotate(count=Count("id"))
    .filter(count__gt=1)
)
dup_count = duplicates.count()
print(f"Duplicate (symbol, timestamp) pairs on 2026-10-15: {dup_count}")
if dup_count > 0:
    print("Sample duplicate entries:")
    for d in duplicates[:5]:
        print(f"  Symbol: {d['symbol']}, Timestamp: {d['timestamp']}, Count: {d['count']}")

# 4. Distribution of opportunity types and scores today
print("\n" + "-" * 100)
print("OPPORTUNITY TYPES & SCORES DISTRIBUTION ON 2026-10-15")
opp_types = (
    IntradayOpportunitySnapshot.objects
    .filter(timestamp__date="2026-10-15")
    .values("opportunity_type")
    .annotate(c=Count("id"))
    .order_by("-c")
)
for ot in opp_types:
    print(f"  Type: {ot['opportunity_type']:<25} | Count: {ot['c']}")

top_5_opps = (
    IntradayOpportunitySnapshot.objects
    .filter(timestamp__date="2026-10-15")
    .order_by("-score")[:5]
)
print("\nTop 5 Scored Opportunities Today:")
for o in top_5_opps:
    print(f"  {o.symbol:<12} | Score: {o.score:5.2f} | Type: {o.opportunity_type:<20} | Time: {o.timestamp.strftime('%H:%M:%S')}")
