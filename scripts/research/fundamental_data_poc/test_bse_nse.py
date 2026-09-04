import requests
import json
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/"
}

# Representative scrip codes on BSE:
# RELIANCE: 500325
# TCS: 532540
# HDFCBANK: 500180
# BAJFINANCE: 500034
# COALINDIA: 533278
# TATAMOTORS: 500570

bse_samples = {
    "RELIANCE": "500325",
    "TCS": "532540",
    "HDFCBANK": "500180",
    "BAJFINANCE": "500034",
    "COALINDIA": "533278",
    "TATAMOTORS": "500570"
}

print("=== TESTING BSE INDIA APIS ===")

# 1. Test BSE Corporate Announcements for Financial Results
url_ann = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
params_ann = {
    "pageno": 1,
    "strCat": "Financial Results",
    "strPrevDate": "20240101",
    "strToDate": "20240901",
    "strScrip": "500325",
    "strType": "C"
}

try:
    r = requests.get(url_ann, params=params_ann, headers=headers, timeout=10)
    print(f"BSE Announcements status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        table = data.get("Table", [])
        print(f"Announcements returned: {len(table)}")
        if table:
            sample = table[0]
            print("Sample announcement keys:", list(sample.keys()))
            print(f"  Broadcast Time (DT_TM): {sample.get('DT_TM')}")
            print(f"  Headline (NEWSSUB): {sample.get('NEWSSUB')}")
            print(f"  Category (CATEGORYNAME): {sample.get('CATEGORYNAME')}")
            print(f"  Attachment (ATTACHMENTNAME): {sample.get('ATTACHMENTNAME')}")
            print(f"  XBRL file link: {sample.get('XBRL')}")
except Exception as e:
    print(f"BSE Announcement error: {e}")

# 2. Test BSE Financial Results / Financial Statements API
# BSE has a direct financial result endpoint:
# https://api.bseindia.com/BseIndiaAPI/api/FinResult/w or similar
for test_url in [
    "https://api.bseindia.com/BseIndiaAPI/api/FinancialResult/w?scrip_code=500325",
    "https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?scrip_code=500325&flag=0&from_date=&to_date=&seriesid=",
    "https://api.bseindia.com/BseIndiaAPI/api/CorpResultDetails/w?scrip_code=500325",
    "https://api.bseindia.com/BseIndiaAPI/api/GetCorpResultData/w?scrip_code=500325&period=Quarterly",
]:
    try:
        r = requests.get(test_url, headers=headers, timeout=5)
        print(f"Testing BSE endpoint {test_url.split('/')[-1].split('?')[0]}: HTTP {r.status_code} (len: {len(r.text)})")
        if r.status_code == 200 and len(r.text) > 20:
            try:
                js = r.json()
                print("  Response preview keys:", list(js.keys()) if isinstance(js, dict) else f"List with {len(js)} items")
            except:
                print("  Non-JSON response text snippet:", r.text[:100])
    except Exception as e:
        print(f"  Endpoint {test_url} failed: {e}")

print("\n=== TESTING NSE APIS ===")
nse_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
}

session = requests.Session()
session.headers.update(nse_headers)

try:
    # NSE requires initial visit to set cookies
    r_init = session.get("https://www.nseindia.com", timeout=10)
    print(f"NSE homepage status: {r_init.status_code}, cookies: {list(session.cookies.get_dict().keys())}")
    
    # Try financial results endpoint
    nse_fin_url = "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly"
    r_fin = session.get(nse_fin_url, timeout=10)
    print(f"NSE Financial Results status: {r_fin.status_code}")
    if r_fin.status_code == 200:
        data = r_fin.json()
        print(f"NSE Financial Results count: {len(data) if isinstance(data, list) else len(data.get('data', []))}")
        if data:
            sample = data[0] if isinstance(data, list) else data.get('data', [{}])[0]
            print("NSE Sample keys:", list(sample.keys()))
except Exception as e:
    print(f"NSE test error: {e}")
