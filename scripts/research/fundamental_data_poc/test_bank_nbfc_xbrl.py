import requests
import xml.etree.ElementTree as ET

urls = {
    "HDFCBANK": "https://nsearchives.nseindia.com/corporate/xbrl/BANKING_117525_1359016_23012025122721.xml",
    "BAJFINANCE": "https://nsearchives.nseindia.com/corporate/xbrl/NBFC_INDAS_118072_1365160_29012025074915.xml",
    "TCS": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117182_1341298_09012025093940.xml"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

for name, url in urls.items():
    print(f"\n=== TESTING XBRL FOR {name} ===")
    r = requests.get(url, headers=headers, timeout=15)
    print(f"Status: {r.status_code}, Length: {len(r.text)} bytes")
    if r.status_code == 200:
        root = ET.fromstring(r.text)
        sample_facts = {}
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if elem.text and elem.text.strip():
                # Store sample facts related to income, interest, profit, advances, npa
                for kw in ["interest", "revenue", "income", "profit", "expense", "tax", "eps", "npa", "advances", "deposit"]:
                    if kw in tag_name.lower():
                        sample_facts[tag_name] = elem.text.strip()
                        break
        print(f"Total matching facts found: {len(sample_facts)}")
        for k in list(sample_facts.keys())[:12]:
            print(f"  {k}: {sample_facts[k]}")
