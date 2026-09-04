import requests
import json

headers_bse = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/"
}

# 1. Detailed inspection of BSE FinancialResult endpoint
scrip_code = "500325" # Reliance
url_bse = f"https://api.bseindia.com/BseIndiaAPI/api/FinancialResult/w?scrip_code={scrip_code}"
r_bse = requests.get(url_bse, headers=headers_bse, timeout=10)

if r_bse.status_code == 200:
    data_bse = r_bse.json()
    print("=== BSE FINANCIAL RESULT FOR RELIANCE (500325) ===")
    print("Qtr:", data_bse.get("Qtr"))
    print("Consolidate_File:", data_bse.get("Consolidate_File"))
    print("Standalone_File:", data_bse.get("Standalone_File"))
    print("Console_Header:", data_bse.get("Console_Header"))
    print("Standalone_Header:", data_bse.get("Standalone_Header"))
    data_rows = data_bse.get("Data", [])
    print(f"Data rows count: {len(data_rows)}")
    if data_rows:
        print("Sample 5 data rows:")
        for row in data_rows[:8]:
            print("  ", row)

# 2. Detailed inspection of NSE financial results for representative stocks
headers_nse = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

session = requests.Session()
session.headers.update(headers_nse)

# Get NSE financial results
nse_fin_url = "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly"
r_nse = session.get(nse_fin_url, timeout=10)

if r_nse.status_code == 200:
    records = r_nse.json()
    print(f"\n=== NSE FINANCIAL RESULTS: {len(records)} RECORDS TOTAL ===")
    
    symbols_to_check = ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "COALINDIA", "TATAMOTORS"]
    found = {}
    for rec in records:
        sym = rec.get("symbol")
        if sym in symbols_to_check:
            found.setdefault(sym, []).append(rec)
            
    for sym in symbols_to_check:
        recs = found.get(sym, [])
        print(f"\nSymbol: {sym} -> Found {len(recs)} filings in recent quarterly stream")
        for idx, rec in enumerate(recs[:2]):
            print(f"  [{idx+1}] Period: {rec.get('period')}, FY: {rec.get('financialYear')}, fromDate: {rec.get('fromDate')}, toDate: {rec.get('toDate')}")
            print(f"      FilingDate: {rec.get('filingDate')}, broadCastDate: {rec.get('broadCastDate')}, exchdisstime: {rec.get('exchdisstime')}")
            print(f"      Consolidated: {rec.get('consolidated')}, Audited: {rec.get('audited')}, Bank: {rec.get('bank')}")
            print(f"      XBRL link: {rec.get('xbrl')}")
            print(f"      resultDetailedDataLink: {rec.get('resultDetailedDataLink')}")

with open("scripts/research/fundamental_data_poc/nse_sample_filings.json", "w") as f:
    json.dump({s: found.get(s, []) for s in symbols_to_check}, f, indent=2)
