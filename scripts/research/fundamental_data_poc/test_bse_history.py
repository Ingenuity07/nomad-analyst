import requests
import json

headers_bse = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/"
}

# BSE has an announcement API that accepts date ranges:
# strPrevDate=YYYYMMDD&strToDate=YYYYMMDD&strScrip=500325&strType=C
# Let's test querying 2023 announcements for Reliance (500325)
url_ann = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
params = {
    "pageno": 1,
    "strCat": "-1", # All categories or Financial Results
    "strPrevDate": "20230101",
    "strToDate": "20231231",
    "strScrip": "500325",
    "strType": "C"
}

r = requests.get(url_ann, params=params, headers=headers_bse, timeout=10)
print("BSE 2023 Announcements status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    table = data.get("Table", [])
    print(f"Total 2023 announcements for Reliance: {len(table)}")
    fin_ann = [a for a in table if "result" in a.get("NEWSSUB", "").lower() or "financial" in a.get("CATEGORYNAME", "").lower()]
    print(f"Financial results announcements: {len(fin_ann)}")
    for a in fin_ann[:5]:
        print(f"  Date: {a.get('DT_TM')} | Headline: {a.get('NEWSSUB')[:60]}... | PDF: {a.get('ATTACHMENTNAME')} | XBRL: {a.get('XBRL')}")
