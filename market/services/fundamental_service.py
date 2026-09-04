import logging
import json
from datetime import datetime, timezone, date
from decimal import Decimal
import re
from typing import Dict, Any, List, Optional
from django.db import transaction

from market.models import (
    Company,
    Instrument,
    MarketSnapshot,
    OHLCVBar,
    RawFundamentalData,
    IncomeStatement,
    BalanceSheetStatement,
    CashFlowStatement,
    DerivedFundamentalMetric
)
from market.providers.xbrl_provider import XBRLFundamentalProvider, SYMBOL_ALIASES, REVERSE_SYMBOL_ALIASES

logger = logging.getLogger(__name__)


class FundamentalDataService:
    """
    Handles ingestion of raw and normalized fundamental data from official XBRL
    filings or local baseline snapshot artifacts, preserving raw provenance logs
    and upserting Income, Balance Sheet, and Cash Flow statements.
    """

    def __init__(self, provider: Optional[Any] = None):
        if provider is None:
            # Default to ScreenerFundamentalProvider for backwards compatibility if available
            try:
                from market.providers.screener import ScreenerFundamentalProvider
                self.provider = ScreenerFundamentalProvider()
            except ImportError:
                self.provider = XBRLFundamentalProvider()
        else:
            self.provider = provider

    def _parse_period_end(self, period_str: str) -> Optional[date]:
        parts = period_str.strip().split()
        if len(parts) != 2:
            return None
        month_str, year_str = parts[0][:3].lower(), parts[1]
        try:
            year = int(year_str)
        except ValueError:
            return None
        if month_str == "mar":
            return date(year, 3, 31)
        elif month_str == "dec":
            return date(year, 12, 31)
        elif month_str == "sep":
            return date(year, 9, 30)
        elif month_str == "jun":
            return date(year, 6, 30)
        return None

    def ingest_company_financials(self, symbol: str) -> Dict[str, Any]:
        """Legacy method for fetching and normalizing via provider (e.g. Screener mock in unit tests)."""
        logger.info(f"Ingesting fundamentals for symbol: {symbol}")
        raw_data = self.provider.get_fundamental_data(symbol)
        clean_symbol = raw_data.get("symbol", symbol)
        company = Company.objects.get(short_name=clean_symbol)

        raw_record = RawFundamentalData.objects.create(
            company=company,
            source=raw_data.get("source", "screener"),
            source_url=raw_data.get("source_url"),
            fiscal_period=raw_data["profit_loss"].get("periods", ["Latest"])[-1] if raw_data.get("profit_loss") else "Latest",
            reporting_type="ANNUAL",
            raw_payload=raw_data,
            status="RAW"
        )

        pl_data = raw_data.get("profit_loss", {})
        bs_data = raw_data.get("balance_sheet", {})
        cf_data = raw_data.get("cash_flow", {})

        def get_val(dataset, row_name, period_str):
            if not dataset or "rows" not in dataset:
                return None
            row = dataset["rows"].get(row_name, [])
            for item in row:
                if item["period"] == period_str:
                    return Decimal(str(item["value"])) if item["value"] is not None else None
            return None

        # Annual
        periods = pl_data.get("periods", [])
        with transaction.atomic():
            for period in periods:
                if period == "TTM":
                    continue
                year_match = re.search(r'\d{4}', period)
                fiscal_year = int(year_match.group()) if year_match else datetime.now().year
                period_end_date = self._parse_period_end(period)
                rev = get_val(pl_data, "Sales", period)
                exp = get_val(pl_data, "Expenses", period)
                ebitda = get_val(pl_data, "Operating Profit", period)
                dep = get_val(pl_data, "Depreciation", period)
                interest = get_val(pl_data, "Interest", period)
                pbt = get_val(pl_data, "Profit before tax", period)
                pat = get_val(pl_data, "Net Profit", period)
                eps = get_val(pl_data, "EPS in Rs", period)

                ebit = None
                if ebitda is not None and dep is not None:
                    ebit = ebitda - dep
                elif pbt is not None and interest is not None:
                    ebit = pbt + interest

                tax = None
                if pbt is not None and pat is not None:
                    tax = pbt - pat

                IncomeStatement.objects.update_or_create(
                    company=company,
                    period_type="ANNUAL",
                    period_string=period,
                    defaults={
                        "fiscal_year": fiscal_year,
                        "period_end": period_end_date,
                        "filing_date": period_end_date,
                        "revenue": rev, "expenses": exp, "ebitda": ebitda, "ebit": ebit,
                        "depreciation": dep, "interest": interest, "pbt": pbt, "tax": tax,
                        "pat": pat, "eps": eps
                    }
                )

                eq_cap = get_val(bs_data, "Equity Capital", period) or get_val(bs_data, "Share Capital", period)
                reserves = get_val(bs_data, "Reserves", period)
                borrowings = get_val(bs_data, "Borrowings", period)
                tot_liab = get_val(bs_data, "Total Liabilities", period)
                tot_assets = get_val(bs_data, "Total Assets", period)
                fixed_assets = get_val(bs_data, "Fixed Assets", period)
                cwip = get_val(bs_data, "CWIP", period)
                investments = get_val(bs_data, "Investments", period)
                other_assets = get_val(bs_data, "Other Assets", period)

                BalanceSheetStatement.objects.update_or_create(
                    company=company,
                    period_type="ANNUAL",
                    period_string=period,
                    defaults={
                        "fiscal_year": fiscal_year,
                        "period_end": period_end_date,
                        "filing_date": period_end_date,
                        "equity_capital": eq_cap, "reserves": reserves, "borrowings": borrowings,
                        "total_liabilities": tot_liab, "fixed_assets": fixed_assets, "cwip": cwip,
                        "investments": investments, "other_assets": other_assets, "total_assets": tot_assets
                    }
                )

                cfo = get_val(cf_data, "Cash from Operating Activity", period) or get_val(cf_data, "Operating Cash Flow", period)
                cfi = get_val(cf_data, "Cash from Investing Activity", period)
                cff = get_val(cf_data, "Cash from Financing Activity", period)
                fcf = get_val(cf_data, "Free Cash Flow", period)

                CashFlowStatement.objects.update_or_create(
                    company=company,
                    period_type="ANNUAL",
                    period_string=period,
                    defaults={
                        "fiscal_year": fiscal_year,
                        "period_end": period_end_date,
                        "filing_date": period_end_date,
                        "operating_cash_flow": cfo, "investing_cash_flow": cfi, "financing_cash_flow": cff,
                        "free_cash_flow": fcf
                    }
                )

        # Quarterly
        q_data = raw_data.get("quarters", {})
        q_periods = q_data.get("periods", [])
        with transaction.atomic():
            for period in q_periods:
                year_match = re.search(r'\d{4}', period)
                fiscal_year = int(year_match.group()) if year_match else datetime.now().year
                period_end_date = self._parse_period_end(period)
                rev = get_val(q_data, "Sales", period)
                exp = get_val(q_data, "Expenses", period)
                ebitda = get_val(q_data, "Operating Profit", period)
                dep = get_val(q_data, "Depreciation", period)
                interest = get_val(q_data, "Interest", period)
                pbt = get_val(q_data, "Profit before tax", period)
                pat = get_val(q_data, "Net Profit", period)
                eps = get_val(q_data, "EPS in Rs", period)

                ebit = None
                if ebitda is not None and dep is not None:
                    ebit = ebitda - dep
                elif pbt is not None and interest is not None:
                    ebit = pbt + interest

                tax = None
                if pbt is not None and pat is not None:
                    tax = pbt - pat

                IncomeStatement.objects.update_or_create(
                    company=company,
                    period_type="QUARTERLY",
                    period_string=period,
                    defaults={
                        "fiscal_year": fiscal_year,
                        "period_end": period_end_date,
                        "filing_date": period_end_date,
                        "revenue": rev, "expenses": exp, "ebitda": ebitda, "ebit": ebit,
                        "depreciation": dep, "interest": interest, "pbt": pbt, "tax": tax,
                        "pat": pat, "eps": eps
                    }
                )

        raw_record.status = "NORMALIZED"
        raw_record.save()

        metric_service = FundamentalMetricService()
        metric_service.calculate_and_save_metrics(company)

        return raw_data

    def ingest_company_financials_from_snapshot(self, company_payload: Dict[str, Any]) -> int:
        """
        Ingests statements from a structured company snapshot dictionary
        (e.g., from data/fundamentals/nifty50_fundamentals_YYYY-MM-DD.json).
        """
        sym = company_payload["symbol"]
        # Resolve company (handle alias like TATAMOTORS / TMPV)
        clean_sym = REVERSE_SYMBOL_ALIASES.get(sym, sym)
        company = Company.objects.filter(short_name__in=[sym, clean_sym]).first()
        if not company:
            logger.warning(f"Company for symbol '{sym}' not found in database. Skipping.")
            return 0

        statements = company_payload.get("statements", [])
        if not statements:
            return 0

        # 1. Log provenance in RawFundamentalData
        RawFundamentalData.objects.create(
            company=company,
            source=company_payload.get("source", "OFFICIAL_REGULATORY_XBRL"),
            source_url=company_payload.get("source_url", f"https://nsearchives.nseindia.com/corporate/xbrl/{sym}"),
            fiscal_period=statements[-1].get("period_string", "Latest"),
            reporting_type=statements[-1].get("period_type", "ANNUAL"),
            raw_payload={
                "symbol": sym,
                "isin": company_payload.get("isin"),
                "taxonomy": company_payload.get("taxonomy"),
                "statements_count": len(statements),
                "sample_filing_date": statements[-1].get("filing_date")
            },
            status="NORMALIZED"
        )

        # 2. Ingest Statements
        with transaction.atomic():
            for stmt in statements:
                period_type = stmt.get("period_type", "ANNUAL")
                period_string = stmt.get("period_string")
                fiscal_year = stmt.get("fiscal_year")
                p_start = stmt.get("period_start")
                p_end = stmt.get("period_end")
                filing_date = stmt.get("filing_date")

                # Income Statement
                inc = stmt.get("income_statement")
                if inc:
                    IncomeStatement.objects.update_or_create(
                        company=company,
                        period_type=period_type,
                        period_string=period_string,
                        defaults={
                            "fiscal_year": fiscal_year,
                            "period_start": p_start,
                            "period_end": p_end,
                            "filing_date": filing_date,
                            "revenue": Decimal(str(inc["revenue"])) if inc.get("revenue") is not None else None,
                            "expenses": Decimal(str(inc["expenses"])) if inc.get("expenses") is not None else None,
                            "ebitda": Decimal(str(inc["ebitda"])) if inc.get("ebitda") is not None else None,
                            "ebit": Decimal(str(inc["ebit"])) if inc.get("ebit") is not None else None,
                            "depreciation": Decimal(str(inc["depreciation"])) if inc.get("depreciation") is not None else None,
                            "interest": Decimal(str(inc["interest"])) if inc.get("interest") is not None else None,
                            "pbt": Decimal(str(inc["pbt"])) if inc.get("pbt") is not None else None,
                            "tax": Decimal(str(inc["tax"])) if inc.get("tax") is not None else None,
                            "pat": Decimal(str(inc["pat"])) if inc.get("pat") is not None else None,
                            "eps": Decimal(str(inc["eps"])) if inc.get("eps") is not None else None,
                        }
                    )

                # Balance Sheet (may be None for Q1/Q3 under SEBI LODR exemption)
                bal = stmt.get("balance_sheet")
                if bal:
                    BalanceSheetStatement.objects.update_or_create(
                        company=company,
                        period_type=period_type,
                        period_string=period_string,
                        defaults={
                            "fiscal_year": fiscal_year,
                            "period_start": p_start,
                            "period_end": p_end,
                            "filing_date": filing_date,
                            "equity_capital": Decimal(str(bal["equity_capital"])) if bal.get("equity_capital") is not None else None,
                            "reserves": Decimal(str(bal["reserves"])) if bal.get("reserves") is not None else None,
                            "borrowings": Decimal(str(bal["borrowings"])) if bal.get("borrowings") is not None else None,
                            "other_liabilities": Decimal(str(bal["other_liabilities"])) if bal.get("other_liabilities") is not None else None,
                            "total_liabilities": Decimal(str(bal["total_liabilities"])) if bal.get("total_liabilities") is not None else None,
                            "fixed_assets": Decimal(str(bal["fixed_assets"])) if bal.get("fixed_assets") is not None else None,
                            "cwip": Decimal(str(bal["cwip"])) if bal.get("cwip") is not None else None,
                            "investments": Decimal(str(bal["investments"])) if bal.get("investments") is not None else None,
                            "other_assets": Decimal(str(bal["other_assets"])) if bal.get("other_assets") is not None else None,
                            "total_assets": Decimal(str(bal["total_assets"])) if bal.get("total_assets") is not None else None,
                        }
                    )

                # Cash Flow (may be None for Q1/Q3)
                cf = stmt.get("cash_flow")
                if cf:
                    CashFlowStatement.objects.update_or_create(
                        company=company,
                        period_type=period_type,
                        period_string=period_string,
                        defaults={
                            "fiscal_year": fiscal_year,
                            "period_start": p_start,
                            "period_end": p_end,
                            "filing_date": filing_date,
                            "operating_cash_flow": Decimal(str(cf["operating_cash_flow"])) if cf.get("operating_cash_flow") is not None else None,
                            "investing_cash_flow": Decimal(str(cf["investing_cash_flow"])) if cf.get("investing_cash_flow") is not None else None,
                            "financing_cash_flow": Decimal(str(cf["financing_cash_flow"])) if cf.get("financing_cash_flow") is not None else None,
                            "free_cash_flow": Decimal(str(cf["free_cash_flow"])) if cf.get("free_cash_flow") is not None else None,
                        }
                    )

        # 3. Calculate derived metrics
        metric_service = FundamentalMetricService()
        metric_service.calculate_and_save_metrics(company)

        logger.info(f"Ingested {len(statements)} statements for {company.name}.")
        return len(statements)


class FundamentalMetricService:
    """
    Calculates derived fundamental indicators: Growth, Margins, Returns (ROE/ROCE),
    Leverage (Debt/Equity), and Point-in-Time Valuation (P/E).
    """

    def calculate_and_save_metrics(self, company: Company):
        """
        Loads Income, Balance Sheet, and Cash Flow statements, calculates growth rates,
        margins, return metrics, debt leverage, and persists them.
        """
        incomes = list(IncomeStatement.objects.filter(company=company, period_type="ANNUAL").order_by('fiscal_year'))
        balances = {b.period_string: b for b in BalanceSheetStatement.objects.filter(company=company, period_type="ANNUAL")}
        cash_flows = {c.period_string: c for c in CashFlowStatement.objects.filter(company=company, period_type="ANNUAL")}

        metrics_to_create = []

        for idx, inc in enumerate(incomes):
            period = inc.period_string
            bal = balances.get(period)
            cf = cash_flows.get(period)

            # 1. Growth Metrics (requires comparing T and T-1 periods)
            if idx > 0:
                prev_inc = incomes[idx - 1]
                # Revenue Growth YoY
                if prev_inc.revenue and inc.revenue and prev_inc.revenue > 0:
                    metrics_to_create.append(self._make_metric(company, "revenue_growth_yoy", period, (inc.revenue - prev_inc.revenue) / prev_inc.revenue))
                # EBITDA Growth YoY
                if prev_inc.ebitda and inc.ebitda and prev_inc.ebitda > 0:
                    metrics_to_create.append(self._make_metric(company, "ebitda_growth_yoy", period, (inc.ebitda - prev_inc.ebitda) / prev_inc.ebitda))
                # PAT Growth YoY
                if prev_inc.pat and inc.pat and prev_inc.pat > 0:
                    metrics_to_create.append(self._make_metric(company, "pat_growth_yoy", period, (inc.pat - prev_inc.pat) / prev_inc.pat))
                # EPS Growth YoY
                if prev_inc.eps and inc.eps and prev_inc.eps > 0:
                    metrics_to_create.append(self._make_metric(company, "eps_growth_yoy", period, (inc.eps - prev_inc.eps) / prev_inc.eps))

            # 2. Margins
            if inc.revenue and inc.revenue > 0:
                if inc.ebitda is not None:
                    metrics_to_create.append(self._make_metric(company, "ebitda_margin", period, inc.ebitda / inc.revenue))
                if inc.ebit is not None:
                    metrics_to_create.append(self._make_metric(company, "ebit_margin", period, inc.ebit / inc.revenue))
                if inc.pat is not None:
                    metrics_to_create.append(self._make_metric(company, "net_margin", period, inc.pat / inc.revenue))

            # 3. Return Metrics & Leverage (ROE, ROCE, Debt/Equity)
            if bal:
                equity = None
                if bal.equity_capital is not None and bal.reserves is not None:
                    equity = bal.equity_capital + bal.reserves

                # ROE = PAT / Equity (only when equity > 0)
                if equity and equity > 0 and inc.pat is not None:
                    metrics_to_create.append(self._make_metric(company, "return_on_equity", period, inc.pat / equity))

                # ROCE = EBIT / Capital Employed
                if equity and bal.borrowings is not None:
                    capital_employed = equity + bal.borrowings
                    if capital_employed > 0 and inc.ebit is not None:
                        metrics_to_create.append(self._make_metric(company, "return_on_capital_employed", period, inc.ebit / capital_employed))
                    if equity > 0:
                        metrics_to_create.append(self._make_metric(company, "debt_equity", period, bal.borrowings / equity))

            # 4. Cash Flow metrics
            if cf and inc.pat and inc.pat > 0:
                if cf.operating_cash_flow is not None:
                    metrics_to_create.append(self._make_metric(company, "cfo_pat", period, cf.operating_cash_flow / inc.pat))
                if cf.free_cash_flow is not None and inc.revenue and inc.revenue > 0:
                    metrics_to_create.append(self._make_metric(company, "fcf_margin", period, cf.free_cash_flow / inc.revenue))

            # 5. Point-in-Time Valuation Metrics (P/E)
            # Use market close price on the filing_date (or latest prior bar)
            instrument = Instrument.objects.filter(company=company, is_active=True).first()
            if instrument and inc.eps and inc.eps > 0:
                target_date = inc.filing_date or inc.period_end
                bar = OHLCVBar.objects.filter(
                    instrument=instrument,
                    timeframe="1d",
                    timestamp__date__lte=target_date
                ).order_by("-timestamp").first()

                price = bar.close if bar else None
                if not price:
                    snapshot = MarketSnapshot.objects.filter(instrument=instrument).order_by("-timestamp").first()
                    price = snapshot.close if snapshot else None

                if price and price > 0:
                    metrics_to_create.append(self._make_metric(company, "pe_ratio", period, price / inc.eps))

        # Save metrics in bulk
        with transaction.atomic():
            DerivedFundamentalMetric.objects.filter(company=company, period_type="ANNUAL").delete()
            if metrics_to_create:
                DerivedFundamentalMetric.objects.bulk_create(metrics_to_create, batch_size=1000)

    def _make_metric(self, company: Company, name: str, period_string: str, value: Any) -> DerivedFundamentalMetric:
        """Helper to create metric model object."""
        dec_val = None
        if value is not None:
            try:
                dec_val = Decimal(f"{float(value):.6f}")
            except (ValueError, InvalidOperation):
                dec_val = None
        return DerivedFundamentalMetric(
            company=company,
            period_type="ANNUAL",
            period_string=period_string,
            name=name,
            value=dec_val
        )
