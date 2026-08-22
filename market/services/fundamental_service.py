import logging
from datetime import datetime, timezone, date
from decimal import Decimal
import re
from typing import Dict, Any, List, Optional
from django.db import transaction

from market.models import (
    Company,
    Instrument,
    MarketSnapshot,
    RawFundamentalData,
    IncomeStatement,
    BalanceSheetStatement,
    CashFlowStatement,
    DerivedFundamentalMetric
)
from market.providers.screener import ScreenerFundamentalProvider

logger = logging.getLogger(__name__)

class FundamentalDataService:
    """
    Handles ingestion of raw fundamental data, raw payload logging (provenance),
    normalization mapping, and database persistence.
    """
    
    def __init__(self, provider=None):
        self.provider = provider or ScreenerFundamentalProvider()

    def _parse_period_end(self, period_str: str) -> Optional[date]:
        """
        Parses Screener period labels (e.g. 'Mar 2025') into standard dates (e.g. 2025-03-31).
        """
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
        """
        Queries Screener for the company financials, saves raw payload to RawFundamentalData
        for audit logs, normalizes, and upserts Income, Balance Sheet, and Cash Flow statements.
        """
        logger.info(f"Ingesting fundamentals for symbol: {symbol}")
        
        # 1. Fetch raw HTML parsed dictionary
        raw_data = self.provider.get_fundamental_data(symbol)
        
        clean_symbol = raw_data["symbol"]
        company = Company.objects.get(short_name=clean_symbol)
        
        # 2. Save raw provenance record
        raw_record = RawFundamentalData.objects.create(
            company=company,
            source=raw_data["source"],
            source_url=raw_data["source_url"],
            fiscal_period=raw_data["profit_loss"].get("periods", ["Latest"])[-1] if raw_data["profit_loss"] else "Latest",
            reporting_type="ANNUAL",
            raw_payload=raw_data,
            status="RAW"
        )
        
        # 3. Parse & Normalize Annual statements (from profit_loss, balance_sheet, cash_flow)
        self._normalize_and_save_annual_statements(company, raw_data)
        
        # 4. Parse & Normalize Quarterly statements
        self._normalize_and_save_quarterly_statements(company, raw_data)
        
        # Mark raw log as normalized
        raw_record.status = "NORMALIZED"
        raw_record.save()
        
        # Calculate derived metrics
        metric_service = FundamentalMetricService()
        metric_service.calculate_and_save_metrics(company)
        
        logger.info(f"Successfully ingested and normalized fundamental statements for {company.name}.")
        return raw_data

    def _normalize_and_save_annual_statements(self, company: Company, raw_data: Dict[str, Any]):
        """Parses and normalizes annual columns."""
        pl_data = raw_data.get("profit_loss", {})
        bs_data = raw_data.get("balance_sheet", {})
        cf_data = raw_data.get("cash_flow", {})
        
        periods = pl_data.get("periods", [])
        
        # Helper to retrieve value safely
        def get_val(dataset, row_name, period_str):
            if not dataset or "rows" not in dataset:
                return None
            row = dataset["rows"].get(row_name, [])
            for item in row:
                if item["period"] == period_str:
                    return Decimal(str(item["value"])) if item["value"] is not None else None
            return None

        with transaction.atomic():
            for period in periods:
                if period == "TTM":
                    # TTM is trailing, handled separately or skipped for standard annuals
                    continue
                    
                # Parse fiscal year, e.g. "Mar 2025" -> 2025
                year_match = re.search(r'\d{4}', period)
                fiscal_year = int(year_match.group()) if year_match else datetime.now().year
                period_end_date = self._parse_period_end(period)
                
                # 1. Income Statement Ingestion
                # Screener names: Sales, Expenses, Operating Profit, Depreciation, Interest, Profit before tax, Net Profit, EPS in Rs
                rev = get_val(pl_data, "Sales", period)
                exp = get_val(pl_data, "Expenses", period)
                ebitda = get_val(pl_data, "Operating Profit", period)
                dep = get_val(pl_data, "Depreciation", period)
                interest = get_val(pl_data, "Interest", period)
                pbt = get_val(pl_data, "Profit before tax", period)
                pat = get_val(pl_data, "Net Profit", period)
                eps = get_val(pl_data, "EPS in Rs", period)
                
                # Derive EBIT: EBITDA - Depreciation
                ebit = None
                if ebitda is not None and dep is not None:
                    ebit = ebitda - dep
                elif pbt is not None and interest is not None:
                    ebit = pbt + interest
                    
                # Tax calculation
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
                        "revenue": rev,
                        "expenses": exp,
                        "ebitda": ebitda,
                        "ebit": ebit,
                        "depreciation": dep,
                        "interest": interest,
                        "pbt": pbt,
                        "tax": tax,
                        "pat": pat,
                        "eps": eps
                    }
                )
                
                # 2. Balance Sheet Ingestion
                eq_cap = get_val(bs_data, "Equity Capital", period) or get_val(bs_data, "Share Capital", period)
                reserves = get_val(bs_data, "Reserves", period)
                borrowings = get_val(bs_data, "Borrowings", period)
                other_liab = get_val(bs_data, "Other Liabilities", period)
                total_liab = get_val(bs_data, "Total Liabilities", period)
                fixed_assets = get_val(bs_data, "Fixed Assets", period)
                cwip = get_val(bs_data, "CWIP", period)
                investments = get_val(bs_data, "Investments", period)
                other_assets = get_val(bs_data, "Other Assets", period)
                total_assets = get_val(bs_data, "Total Assets", period)
                
                BalanceSheetStatement.objects.update_or_create(
                    company=company,
                    period_type="ANNUAL",
                    period_string=period,
                    defaults={
                        "fiscal_year": fiscal_year,
                        "period_end": period_end_date,
                        "equity_capital": eq_cap,
                        "reserves": reserves,
                        "borrowings": borrowings,
                        "other_liabilities": other_liab,
                        "total_liabilities": total_liab,
                        "fixed_assets": fixed_assets,
                        "cwip": cwip,
                        "investments": investments,
                        "other_assets": other_assets,
                        "total_assets": total_assets
                    }
                )
                
                # 3. Cash Flow Ingestion
                cfo = get_val(cf_data, "Cash from Operating Activity", period)
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
                        "operating_cash_flow": cfo,
                        "investing_cash_flow": cfi,
                        "financing_cash_flow": cff,
                        "free_cash_flow": fcf
                    }
                )

    def _normalize_and_save_quarterly_statements(self, company: Company, raw_data: Dict[str, Any]):
        """Parses and normalizes quarterly columns (from quarters table)."""
        q_data = raw_data.get("quarters", {})
        periods = q_data.get("periods", [])
        
        def get_val(dataset, row_name, period_str):
            if not dataset or "rows" not in dataset:
                return None
            row = dataset["rows"].get(row_name, [])
            for item in row:
                if item["period"] == period_str:
                    return Decimal(str(item["value"])) if item["value"] is not None else None
            return None

        with transaction.atomic():
            for period in periods:
                year_match = re.search(r'\d{4}', period)
                fiscal_year = int(year_match.group()) if year_match else datetime.now().year
                period_end_date = self._parse_period_end(period)
                
                # Quarters names match Profit Loss table names
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
                        "revenue": rev,
                        "expenses": exp,
                        "ebitda": ebitda,
                        "ebit": ebit,
                        "depreciation": dep,
                        "interest": interest,
                        "pbt": pbt,
                        "tax": tax,
                        "pat": pat,
                        "eps": eps
                    }
                )


class FundamentalMetricService:
    """
    Handles calculations of derived fundamental indicators: Growth, Profitability, Leverage,
    and Valuation metrics based on the persisted statements.
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
        
        # 1. Growth Metrics (requires sorting to compare T and T-1 periods)
        for idx, inc in enumerate(incomes):
            period = inc.period_string
            bal = balances.get(period)
            cf = cash_flows.get(period)
            
            # Growth calculation
            if idx > 0:
                prev_inc = incomes[idx - 1]
                # Revenue Growth YoY
                if prev_inc.revenue and inc.revenue:
                    metrics_to_create.append(self._make_metric(company, "revenue_growth_yoy", period, (inc.revenue - prev_inc.revenue) / prev_inc.revenue))
                # EBITDA Growth YoY
                if prev_inc.ebitda and inc.ebitda:
                    metrics_to_create.append(self._make_metric(company, "ebitda_growth_yoy", period, (inc.ebitda - prev_inc.ebitda) / prev_inc.ebitda))
                # PAT Growth YoY
                if prev_inc.pat and inc.pat:
                    metrics_to_create.append(self._make_metric(company, "pat_growth_yoy", period, (inc.pat - prev_inc.pat) / prev_inc.pat))
                # EPS Growth YoY
                if prev_inc.eps and inc.eps:
                    metrics_to_create.append(self._make_metric(company, "eps_growth_yoy", period, (inc.eps - prev_inc.eps) / prev_inc.eps))
            
            # 2. Margins
            if inc.revenue:
                if inc.ebitda:
                    metrics_to_create.append(self._make_metric(company, "ebitda_margin", period, inc.ebitda / inc.revenue))
                if inc.ebit:
                    metrics_to_create.append(self._make_metric(company, "ebit_margin", period, inc.ebit / inc.revenue))
                if inc.pat:
                    metrics_to_create.append(self._make_metric(company, "net_margin", period, inc.pat / inc.revenue))

            # 3. Return Metrics & Leverage (ROE, ROCE, Debt/Equity)
            if bal:
                # Equity = Equity Capital + Reserves
                equity = None
                if bal.equity_capital is not None and bal.reserves is not None:
                    equity = bal.equity_capital + bal.reserves
                
                # ROE = PAT / Equity
                if equity and inc.pat:
                    metrics_to_create.append(self._make_metric(company, "return_on_equity", period, inc.pat / equity))
                    
                # ROCE = EBIT / (Total Assets - Current Liabilities)
                # Current Liabilities = Total Liabilities - Borrowings (or other approximation if specific field doesn't exist)
                # Screener has Total Assets. Capital Employed = Equity + Borrowings
                capital_employed = None
                if equity is not None and bal.borrowings is not None:
                    capital_employed = equity + bal.borrowings
                    
                if capital_employed and inc.ebit:
                    metrics_to_create.append(self._make_metric(company, "return_on_capital_employed", period, inc.ebit / capital_employed))
                    
                # Debt/Equity
                if equity and bal.borrowings is not None:
                    metrics_to_create.append(self._make_metric(company, "debt_equity", period, bal.borrowings / equity))

            # 4. Cash Flow metrics
            if cf and inc.pat:
                if cf.operating_cash_flow:
                    metrics_to_create.append(self._make_metric(company, "cfo_pat", period, cf.operating_cash_flow / inc.pat))
                if cf.free_cash_flow and inc.revenue:
                    metrics_to_create.append(self._make_metric(company, "fcf_margin", period, cf.free_cash_flow / inc.revenue))

            # 5. Valuation Metrics (PE, PB using point-in-time close price if available)
            instrument = Instrument.objects.filter(company=company, is_active=True).first()
            if instrument:
                # Retrieve latest snapshot price at or near period end (or overall latest snapshot)
                snapshot = MarketSnapshot.objects.filter(instrument=instrument).order_by('-timestamp').first()
                if snapshot and snapshot.close:
                    price = snapshot.close
                    # PE = price / EPS
                    if inc.eps and inc.eps > 0:
                        metrics_to_create.append(self._make_metric(company, "pe_ratio", period, price / inc.eps))
                    
                    # PB = price / Book Value Per Share
                    # Book Value Per Share = Equity / Share Count
                    # Share Count = Equity Capital / Face Value (usually Rs 10 or Rs 2, but since we don't have face value,
                    # we can compute Book Value as Equity / Share Count, or check if we can approximate PB as
                    # Market Cap / Equity. Market Cap = price * Share Count. Equity = Equity.
                    # Since we don't have share count, we can approximate PB = Price / (Book Value per Share) if we have BV,
                    # or skip PB if share count is missing.
                    # Wait! Equity = Equity Capital + Reserves. If we assume face value is 10: share_count = Equity Capital / 10.
                    # Let's skip PB to keep it clean and avoid assumptions, or calculate it if Equity Capital exists.
                    # Actually, we don't need to guess face value. Let's just calculate PE ratio which is standard and robust.

        # Save metrics in bulk
        with transaction.atomic():
            DerivedFundamentalMetric.objects.filter(company=company, period_type="ANNUAL").delete()
            if metrics_to_create:
                DerivedFundamentalMetric.objects.bulk_create(metrics_to_create, batch_size=1000)

    def _make_metric(self, company: Company, name: str, period_string: str, value: float) -> DerivedFundamentalMetric:
        """Helper to create metric model object."""
        return DerivedFundamentalMetric(
            company=company,
            period_type="ANNUAL",
            period_string=period_string,
            name=name,
            value=Decimal(f"{value:.6f}") if value is not None else None
        )
