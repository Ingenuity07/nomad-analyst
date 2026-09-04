import requests
import json
import time

session = requests.Session()
# Proper browser headers for Yahoo
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1"
})

symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BAJFINANCE.NS", "COALINDIA.NS", "TATAMOTORS.NS"]

print("=== TESTING YAHOO FINANCE FUNDAMENTALS & PIT CAPABILITY ===")

# Test 1: Get cookie from Yahoo Finance home
try:
    r_home = session.get("https://finance.yahoo.com/quote/RELIANCE.NS", timeout=10)
    print(f"Yahoo quote page status: {r_home.status_code}, cookies set: {len(session.cookies)}")
except Exception as e:
    print(f"Yahoo quote page failed: {e}")

# Test 2: Query quoteSummary endpoint with standard modules
modules = "financialData,defaultKeyStatistics,incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,incomeStatementHistoryQuarterly,balanceSheetHistoryQuarterly,cashflowStatementHistoryQuarterly,calendarEvents,earnings"

# Test direct API without crumb vs with crumb
for sym in symbols:
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules={modules}"
    try:
        r = session.get(url, timeout=10)
        print(f"\n{sym}: HTTP {r.status_code}")
        if r.status_code == 200:
            res = r.json().get("quoteSummary", {}).get("result", [{}])[0]
            # Inspect annual income statements
            ish = res.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
            ish_q = res.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])
            print(f"  Annual statements count: {len(ish)}")
            print(f"  Quarterly statements count: {len(ish_q)}")
            if ish:
                print(f"  Annual dates: {[s.get('endDate', {}).get('fmt') for s in ish]}")
                # Check for filing / publication date
                first_stmt = ish[0]
                has_filing_date = any('filing' in k.lower() or 'report' in k.lower() or 'publish' in k.lower() or 'announce' in k.lower() for k in first_stmt.keys())
                print(f"  Has filing/publication date field in annual stmt: {has_filing_date}")
                print(f"  Annual sample keys: {list(first_stmt.keys())[:10]}")
            if ish_q:
                print(f"  Quarterly dates: {[s.get('endDate', {}).get('fmt') for s in ish_q]}")
        elif r.status_code in (401, 403, 429):
            print(f"  Authentication / rate-limit block: HTTP {r.status_code}")
    except Exception as e:
        print(f"  {sym} query error: {e}")
