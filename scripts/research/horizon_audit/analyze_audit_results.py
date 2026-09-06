import json
import numpy as np

with open("scripts/research/horizon_audit/nifty50_audit_data.json") as f:
    data = json.load(f)

with open("scripts/research/horizon_audit/statistical_summary.json") as f:
    stats = json.load(f)

print("=== 1. TOP 10 LONG_TERM OPPORTUNITIES ===")
sorted_by_lt = sorted([d for d in data if d["long_term_score"] is not None], key=lambda x: x["long_term_score"], reverse=True)
for i, d in enumerate(sorted_by_lt[:10]):
    print(f"{i+1:<2}. {d['symbol']:<12} | LT Score: {d['long_term_score']:<5.2f} | Fund: {d['fundamental_score']:<5.2f} | Tech: {d['component_scores'].get('technical'):<5.1f} | Sec: {d['component_scores'].get('sector'):<5.1f} | Type: {d['opportunity_type']}")
    print(f"    Metrics: ROE={d['roe']} | ROCE={d['roce']} | D/E={d['debt_equity']} | RevG={d['rev_growth']} | PATG={d['pat_growth']} | PE={d['pe_ratio']}")

print("\n=== 2. BOTTOM 10 LONG_TERM OPPORTUNITIES ===")
for i, d in enumerate(sorted_by_lt[-10:]):
    print(f"{len(sorted_by_lt)-9+i:<2}. {d['symbol']:<12} | LT Score: {d['long_term_score']:<5.2f} | Fund: {d['fundamental_score']:<5.2f} | Tech: {d['component_scores'].get('technical'):<5.1f} | Sec: {d['component_scores'].get('sector'):<5.1f} | Type: {d['opportunity_type']}")
    print(f"    Metrics: ROE={d['roe']} | ROCE={d['roce']} | D/E={d['debt_equity']} | RevG={d['rev_growth']} | PATG={d['pat_growth']} | PE={d['pe_ratio']}")

print("\n=== 3. TOP 10 FUNDAMENTAL SCORE ===")
sorted_by_fun = sorted([d for d in data if d["fundamental_score"] is not None], key=lambda x: x["fundamental_score"], reverse=True)
for i, d in enumerate(sorted_by_fun[:10]):
    print(f"{i+1:<2}. {d['symbol']:<12} ({d['sector']}) | Fund: {d['fundamental_score']:<5.2f} | ROE: {d['roe']} | ROCE: {d['roce']} | D/E: {d['debt_equity']} | RevG: {d['rev_growth']}")

print("\n=== 4. BOTTOM 10 FUNDAMENTAL SCORE ===")
for i, d in enumerate(sorted_by_fun[-10:]):
    print(f"{len(sorted_by_fun)-9+i:<2}. {d['symbol']:<12} ({d['sector']}) | Fund: {d['fundamental_score']:<5.2f} | ROE: {d['roe']} | ROCE: {d['roce']} | D/E: {d['debt_equity']} | RevG: {d['rev_growth']}")

print("\n=== 5. BANKING & NBFC METRICS ===")
financials = [d for d in data if d["taxonomy"] in ("BANKING", "NBFC_INDAS")]
for d in financials:
    print(f"{d['symbol']:<12} ({d['taxonomy']}) | Fund: {d['fundamental_score']} | LT: {d['long_term_score']} | ROE: {d['roe']} | ROCE: {d['roce']} | D/E: {d['debt_equity']} | Margin: {d['net_margin']}")

print("\n=== 6. CYCLICAL COMPANIES EVALUATION ===")
cyclicals = [d for d in data if d["symbol"] in ("COALINDIA", "TATASTEEL", "JSWSTEEL", "HINDALCO", "ONGC", "BPCL")]
for d in cyclicals:
    print(f"{d['symbol']:<12} ({d['sector']}) | Fund: {d['fundamental_score']} | LT: {d['long_term_score']} | Rank: {d['long_term_rank']} | ROE: {d['roe']} | ROCE: {d['roce']} | D/E: {d['debt_equity']}")

print("\n=== 7. CORRELATIONS ===")
for k, v in stats["correlations"].items():
    print(f"  {k:<25}: {v:.3f}" if v is not None else f"  {k:<25}: None")
