import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ir_targets = {
    "RELIANCE": "https://www.ril.com/investors/financial-reporting",
    "TCS": "https://www.tcs.com/investor-relations/financial-statements",
    "HDFCBANK": "https://www.hdfcbank.com/personal/about-us/investor-relations/financial-results",
    "BAJFINANCE": "https://www.bajajfinserv.in/investor-relations-financial-results",
    "COALINDIA": "https://www.coalindia.in/financial-results/",
    "TATAMOTORS": "https://www.tatamotors.com/investors/financials/"
}

print("=== TESTING COMPANY IR PORTALS ===")
for name, url in ir_targets.items():
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"\n{name} ({url}): HTTP {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Look for xls, xlsx, zip, xbrl, pdf links
            links = soup.find_all("a", href=True)
            excel_links = [a["href"] for a in links if re.search(r'\.(xlsx?|csv)', a["href"], re.I)]
            pdf_links = [a["href"] for a in links if re.search(r'\.pdf', a["href"], re.I)]
            xbrl_links = [a["href"] for a in links if re.search(r'xbrl|\.xml', a["href"], re.I)]
            
            print(f"  Page title: {soup.title.string.strip() if soup.title else 'No title'}")
            print(f"  Found {len(excel_links)} Excel/CSV links, {len(pdf_links)} PDF links, {len(xbrl_links)} XBRL links")
            if excel_links:
                print(f"  Sample Excel: {excel_links[0]}")
            if pdf_links:
                print(f"  Sample PDF: {pdf_links[0]}")
    except Exception as e:
        print(f"  {name} failed: {e}")
