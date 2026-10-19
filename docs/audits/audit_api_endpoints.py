"""
Script to test API endpoints for Section F: Frontend/API consistency.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
import json

client = Client()

endpoints = [
    "/api/v1/market/overview/",
    "/api/v1/intraday/context/",
    "/api/v1/intraday/opportunities/",
    "/api/v1/intraday/sectors/",
]

print("=" * 100)
print("AUDIT: SECTION F — API CONSISTENCY AND FRESHNESS INSPECTION")
print("=" * 100)

for ep in endpoints:
    resp = client.get(ep)
    print(f"\nEndpoint: {ep} -> Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if ep == "/api/v1/market/overview/":
            print(f"  as_of: {data.get('as_of')}")
            print(f"  market_regime: {data.get('market_regime')}")
            print(f"  data_freshness: {data.get('data_freshness')}")
            print(f"  index_regimes keys: {list(data.get('index_regimes', {}).keys())}")
        elif ep == "/api/v1/intraday/context/":
            print(f"  source: {data.get('source')}")
            print(f"  as_of: {data.get('as_of')}")
            print(f"  freshness: {data.get('freshness')}")
            print(f"  is_fresh: {data.get('is_fresh')}")
            print(f"  freshness_age_seconds: {data.get('freshness_age_seconds')}")
            print(f"  stocks count: {len(data.get('stocks', []))}")
        elif ep == "/api/v1/intraday/opportunities/":
            print(f"  opportunities count: {len(data.get('opportunities', []))}")
            if data.get('opportunities'):
                top = data['opportunities'][0]
                print(f"  Top opp: symbol={top.get('symbol')}, score={top.get('score')}, type={top.get('opportunity_type')}")
        elif ep == "/api/v1/intraday/sectors/":
            print(f"  sectors count: {len(data.get('sectors', []))}")
            if data.get('sectors'):
                print(f"  Top sector: {data['sectors'][0].get('sector')} ({data['sectors'][0].get('average_return')}%)")
    else:
        print(f"  Response: {resp.content[:200]}")
