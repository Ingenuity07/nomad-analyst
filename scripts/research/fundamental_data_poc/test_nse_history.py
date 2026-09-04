import requests
import json

headers_nse = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

session = requests.Session()
session.headers.update(headers_nse)

# Test various parameter combinations on NSE financial results
endpoints = [
    ("Annual Equities", "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Annual"),
    ("Symbol Filter RELIANCE", "https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol=RELIANCE"),
    ("Symbol Filter TCS", "https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol=TCS"),
    ("Date Range 2023", "https://www.nseindia.com/api/corporates-financial-results?index=equities&from_date=01-01-2023&to_date=31-12-2023"),
    ("Date Range 2022", "https://www.nseindia.com/api/corporates-financial-results?index=equities&from_date=01-01-2022&to_date=31-12-2022"),
]

for label, url in endpoints:
    try:
        r = session.get(url, timeout=10)
        print(f"{label}: HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            cnt = len(data) if isinstance(data, list) else len(data.get("data", []))
            print(f"  Count returned: {cnt}")
            if cnt > 0:
                sample = data[0] if isinstance(data, list) else data.get("data", [])[0]
                print(f"  Sample: {sample.get('symbol')} | {sample.get('period')} | FY: {sample.get('financialYear')} | toDate: {sample.get('toDate')}")
    except Exception as e:
        print(f"  Error on {label}: {e}")
