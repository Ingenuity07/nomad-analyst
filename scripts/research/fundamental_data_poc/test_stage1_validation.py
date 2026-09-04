import json
from decimal import Decimal
from market.providers.xbrl_provider import XBRLFundamentalProvider

stage1_targets = [
    {
        "symbol": "RELIANCE",
        "taxonomy": "INDAS",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117297_1348248_16012025081520.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-16",
        "period_end": "2024-12-31"
    },
    {
        "symbol": "TCS",
        "taxonomy": "INDAS",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117182_1341298_09012025093940.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-09",
        "period_end": "2024-12-31"
    },
    {
        "symbol": "HDFCBANK",
        "taxonomy": "BANKING",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/BANKING_117525_1359016_23012025122721.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-23",
        "period_end": "2024-12-31"
    },
    {
        "symbol": "BAJFINANCE",
        "taxonomy": "NBFC_INDAS",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/NBFC_INDAS_118072_1365160_29012025074915.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-29",
        "period_end": "2024-12-31"
    },
    {
        "symbol": "COALINDIA",
        "taxonomy": "INDAS",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117764_1361971_27012025042033.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-27",
        "period_end": "2024-12-31"
    },
    {
        "symbol": "TMPV",
        "taxonomy": "INDAS",
        "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_118027_1364768_29012025052000.xml",
        "period": "Q3 FY25",
        "filing_date": "2025-01-29",
        "period_end": "2024-12-31"
    }
]

provider = XBRLFundamentalProvider()

print("=== STAGE 1 VALIDATION OF REPRESENTATIVE COMPANIES ===")
results = []
for t in stage1_targets:
    sym = t["symbol"]
    tax = t["taxonomy"]
    url = t["url"]
    print(f"\nProcessing {sym} ({tax})...")
    xml_data = provider.fetch_xbrl_file(url)
    parsed = provider.parse_filing(xml_data, taxonomy=tax, metadata=t)
    inc = parsed["income_statement"]
    print(f"  Revenue (₹ Cr): {inc['revenue']}")
    print(f"  Expenses (₹ Cr): {inc['expenses']}")
    print(f"  EBITDA (₹ Cr): {inc['ebitda']}")
    print(f"  PBT (₹ Cr): {inc['pbt']}")
    print(f"  PAT (₹ Cr): {inc['pat']}")
    print(f"  EPS (₹): {inc['eps']}")
    print(f"  Filing Date: {parsed['filing_date']}")
    print(f"  Raw facts extracted: {parsed['raw_facts_count']}")
    results.append({
        "symbol": sym,
        "taxonomy": tax,
        "revenue": str(inc["revenue"]),
        "ebitda": str(inc["ebitda"]),
        "pat": str(inc["pat"]),
        "eps": str(inc["eps"]),
        "filing_date": parsed["filing_date"]
    })

with open("scripts/research/fundamental_data_poc/stage1_validation_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nValidation results saved successfully.")
