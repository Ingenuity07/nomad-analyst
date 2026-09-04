import json

with open("scripts/research/fundamental_data_poc/nse_sample_filings.json") as f:
    filings = json.load(f)

print("=== POINT-IN-TIME (PIT) EVIDENCE TABLE ===")
print(f"{'Company':<12} | {'Period Type':<10} | {'Period Start':<12} | {'Period End':<12} | {'Statutory Filing Date':<20} | {'Lookahead Gap':<15}")
print("-" * 95)

from datetime import datetime

for sym in ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "COALINDIA"]:
    records = filings.get(sym, [])
    # pick the consolidated record
    cons_rec = next((r for r in records if r.get("consolidated") == "Consolidated"), None)
    if cons_rec:
        p_start = cons_rec.get("fromDate")
        p_end = cons_rec.get("toDate")
        f_date_str = cons_rec.get("filingDate")
        # calculate days between period end and filing date
        dt_end = datetime.strptime(p_end, "%d-%b-%Y")
        dt_file = datetime.strptime(f_date_str.split()[0], "%d-%b-%Y")
        gap_days = (dt_file - dt_end).days
        print(f"{sym:<12} | {cons_rec.get('period'):<10} | {p_start:<12} | {p_end:<12} | {f_date_str:<20} | {gap_days} days after end")
