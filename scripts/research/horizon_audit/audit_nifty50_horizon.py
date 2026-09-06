import os
import sys
import json
import django
import numpy as np
from datetime import datetime, date, timezone
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from market.models import (
    Company, Instrument, Universe, UniverseMembership,
    IncomeStatement, BalanceSheetStatement, CashFlowStatement,
    DerivedFundamentalMetric, StockOpportunitySnapshot, MarketContextSnapshot,
    OHLCVBar, TechnicalFeature
)
from market.services.discovery_service import OpportunityDiscoveryService
from market.providers.xbrl_provider import SYMBOL_ALIASES, REVERSE_SYMBOL_ALIASES

def run_audit():
    print("=== STARTING PHASE 16C HORIZON INTELLIGENCE VALIDATION AUDIT ===")
    
    # 1. Load universe
    with open("data/universe/nifty50_constituents_2026-09-03.json") as f:
        univ_data = json.load(f)
    constituents = univ_data["constituents"]
    symbols = [c["symbol"] for c in constituents]
    print(f"Loaded {len(symbols)} NIFTY 50 constituents.")

    # 2. Run Opportunity Scan for LONG_TERM to get latest fresh snapshots
    discovery = OpportunityDiscoveryService()
    snapshots = discovery.scan_universe("NIFTY50", "LONG_TERM")
    snap_map = {s.instrument.symbol: s for s in snapshots}
    print(f"Generated {len(snapshots)} LONG_TERM snapshots.")

    # 3. Sort snapshots by score to establish current ranks
    sorted_snaps = sorted(snapshots, key=lambda s: float(s.final_opportunity_score), reverse=True)
    ranks = {s.instrument.symbol: idx + 1 for idx, s in enumerate(sorted_snaps)}

    audit_records = []
    
    for c in constituents:
        sym = c["symbol"]
        clean_sym = REVERSE_SYMBOL_ALIASES.get(sym, sym)
        company = Company.objects.filter(short_name__in=[sym, clean_sym]).first()
        inst = Instrument.objects.filter(symbol__in=[sym, clean_sym], is_active=True).first()

        # Taxonomy
        BANKING = {"HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK"}
        NBFC = {"BAJFINANCE", "BAJAJFINSV", "SHRIRAMFIN"}
        if sym in BANKING:
            tax = "BANKING"
        elif sym in NBFC:
            tax = "NBFC_INDAS"
        else:
            tax = "INDAS"

        # Statements availability
        annual_stmts = list(IncomeStatement.objects.filter(company=company, period_type="ANNUAL").order_by("fiscal_year"))
        quarterly_stmts = list(IncomeStatement.objects.filter(company=company, period_type="QUARTERLY").order_by("period_end"))
        
        latest_ann = annual_stmts[-1] if annual_stmts else None
        latest_q = quarterly_stmts[-1] if quarterly_stmts else None

        # Metrics for latest annual period
        metrics = {}
        if company and latest_ann:
            m_qs = DerivedFundamentalMetric.objects.filter(company=company, period_type="ANNUAL", period_string=latest_ann.period_string)
            for m in m_qs:
                metrics[m.name] = float(m.value) if m.value is not None else None

        # Opportunity snapshot info
        snap = snap_map.get(sym)
        fun_score = float(snap.component_scores.get("fundamental", 0.0)) if snap else None
        lt_score = float(snap.final_opportunity_score) if snap else None
        rank = ranks.get(sym, 999)

        # Balances & Cashflows
        bal = BalanceSheetStatement.objects.filter(company=company, period_type="ANNUAL", period_string=latest_ann.period_string).first() if latest_ann else None
        cf = CashFlowStatement.objects.filter(company=company, period_type="ANNUAL", period_string=latest_ann.period_string).first() if latest_ann else None

        rec = {
            "symbol": sym,
            "company_name": c["company_name"],
            "sector": c["sector"],
            "taxonomy": tax,
            "annual_count": len(annual_stmts),
            "quarterly_count": len(quarterly_stmts),
            "latest_annual": latest_ann.period_string if latest_ann else None,
            "latest_quarter": latest_q.period_string if latest_q else None,
            "latest_filing_date": str(latest_ann.filing_date) if latest_ann else None,
            "consolidated": True,
            "revenue": float(latest_ann.revenue) if latest_ann and latest_ann.revenue else None,
            "pat": float(latest_ann.pat) if latest_ann and latest_ann.pat else None,
            "eps": float(latest_ann.eps) if latest_ann and latest_ann.eps else None,
            "roe": metrics.get("return_on_equity"),
            "roce": metrics.get("return_on_capital_employed"),
            "debt_equity": metrics.get("debt_equity"),
            "cfo_pat": metrics.get("cfo_pat"),
            "pe_ratio": metrics.get("pe_ratio"),
            "rev_growth": metrics.get("revenue_growth_yoy"),
            "pat_growth": metrics.get("pat_growth_yoy"),
            "ebitda_margin": metrics.get("ebitda_margin"),
            "net_margin": metrics.get("net_margin"),
            "fundamental_score": fun_score,
            "long_term_score": lt_score,
            "long_term_rank": rank,
            "component_scores": snap.component_scores if snap else {},
            "opportunity_type": snap.opportunity_type if snap else "NONE",
            "data_quality": snap.data_quality if snap else {}
        }
        audit_records.append(rec)

    # Save detailed audit dataset
    with open("scripts/research/horizon_audit/nifty50_audit_data.json", "w") as f:
        json.dump(audit_records, f, indent=2)
    print("Saved nifty50_audit_data.json.")

    # 4. Compute Statistical Summary
    fun_scores = [r["fundamental_score"] for r in audit_records if r["fundamental_score"] is not None]
    lt_scores = [r["long_term_score"] for r in audit_records if r["long_term_score"] is not None]

    stats = {
        "total_companies": len(audit_records),
        "scored_companies": len(lt_scores),
        "fundamental_score": {
            "min": float(np.min(fun_scores)),
            "max": float(np.max(fun_scores)),
            "mean": float(np.mean(fun_scores)),
            "std": float(np.std(fun_scores)),
            "median": float(np.median(fun_scores)),
            "p25": float(np.percentile(fun_scores, 25)),
            "p75": float(np.percentile(fun_scores, 75)),
        },
        "long_term_score": {
            "min": float(np.min(lt_scores)),
            "max": float(np.max(lt_scores)),
            "mean": float(np.mean(lt_scores)),
            "std": float(np.std(lt_scores)),
            "median": float(np.median(lt_scores)),
            "p25": float(np.percentile(lt_scores, 25)),
            "p75": float(np.percentile(lt_scores, 75)),
        }
    }

    # Correlations
    def calc_corr(field1, field2):
        pairs = [(r[field1], r[field2]) for r in audit_records if r.get(field1) is not None and r.get(field2) is not None]
        if len(pairs) < 5:
            return None
        x = [p[0] for p in pairs]
        y = [p[1] for p in pairs]
        return float(np.corrcoef(x, y)[0, 1])

    stats["correlations"] = {
        "fun_vs_lt_score": calc_corr("fundamental_score", "long_term_score"),
        "rev_growth_vs_fun_score": calc_corr("rev_growth", "fundamental_score"),
        "pat_growth_vs_fun_score": calc_corr("pat_growth", "fundamental_score"),
        "roe_vs_fun_score": calc_corr("roe", "fundamental_score"),
        "roce_vs_fun_score": calc_corr("roce", "fundamental_score"),
        "de_vs_fun_score": calc_corr("debt_equity", "fundamental_score"),
        "pe_vs_fun_score": calc_corr("pe_ratio", "fundamental_score"),
    }

    with open("scripts/research/horizon_audit/statistical_summary.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("Saved statistical_summary.json.")

    print("\n=== SUMMARY STATISTICS ===")
    print(f"Fundamental Score: Min={stats['fundamental_score']['min']:.1f}, Max={stats['fundamental_score']['max']:.1f}, Mean={stats['fundamental_score']['mean']:.1f}, Median={stats['fundamental_score']['median']:.1f}, Std={stats['fundamental_score']['std']:.1f}")
    print(f"LONG_TERM Score:   Min={stats['long_term_score']['min']:.1f}, Max={stats['long_term_score']['max']:.1f}, Mean={stats['long_term_score']['mean']:.1f}, Median={stats['long_term_score']['median']:.1f}, Std={stats['long_term_score']['std']:.1f}")
    print(f"Correlation Fun Score vs LONG_TERM Score: {stats['correlations']['fun_vs_lt_score']:.3f}")

if __name__ == "__main__":
    run_audit()
