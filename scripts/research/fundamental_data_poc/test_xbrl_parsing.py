import requests
import xml.etree.ElementTree as ET

url = "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117297_1348248_16012025081520.xml"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

print(f"Downloading XBRL file: {url}")
r = requests.get(url, headers=headers, timeout=15)
print(f"HTTP Status: {r.status_code}, Length: {len(r.text)} bytes")

if r.status_code == 200:
    with open("scripts/research/fundamental_data_poc/sample_xbrl_reliance.xml", "w") as f:
        f.write(r.text)
    
    # Parse XML
    root = ET.fromstring(r.text)
    print("Root tag:", root.tag)
    
    # Collect tags and namespaces
    tags = set()
    sample_facts = {}
    for elem in root.iter():
        # strip namespace
        tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        tags.add(tag_name)
        
        # Look for core financial tags
        key_tags = [
            "RevenueFromOperations", "Income", "Expenses", "FinanceCosts",
            "DepreciationDepletionAndAmortisationExpense", "ProfitBeforeTax",
            "TaxExpense", "ProfitLossForPeriod", "ComprehensiveIncomeForThePeriod",
            "BasicEarningsLossPerShareFromContinuingOperations",
            "DilutedEarningsLossPerShareFromContinuingOperations",
            "EquityShareCapital", "OtherEquity", "Borrowings",
            "TotalAssets", "TotalLiabilities", "CashAndCashEquivalents"
        ]
        for kt in key_tags:
            if kt.lower() in tag_name.lower() and elem.text and elem.text.strip():
                sample_facts[tag_name] = (elem.text.strip(), elem.attrib)
                
    print(f"\nTotal distinct tags found: {len(tags)}")
    print("\nSample Financial Facts extracted:")
    for k, v in list(sample_facts.items())[:20]:
        print(f"  {k}: {v[0]} (context: {v[1].get('contextRef', 'none')})")
