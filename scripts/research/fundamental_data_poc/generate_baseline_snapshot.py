import json
import os
import sys
from decimal import Decimal
from datetime import date, datetime, timedelta

# Import universe
with open("data/universe/nifty50_constituents_2026-09-03.json") as f:
    universe_data = json.load(f)

constituents = universe_data["constituents"]

# Taxonomy classification
BANKING_SYMBOLS = {"HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK"}
NBFC_SYMBOLS = {"BAJFINANCE", "BAJAJFINSV", "SHRIRAMFIN"}

def get_taxonomy(sym: str) -> str:
    if sym in BANKING_SYMBOLS:
        return "BANKING"
    elif sym in NBFC_SYMBOLS:
        return "NBFC_INDAS"
    return "INDAS"

print(f"Generating fundamental baseline snapshot for {len(constituents)} constituents...")
