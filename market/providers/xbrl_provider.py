import logging
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
import requests

from market.exceptions import (
    ProviderConnectionError,
    SymbolNotFoundError,
    InvalidPayloadError
)

logger = logging.getLogger(__name__)

CRORE_FACTOR = Decimal("10000000.00")  # 1 Cr = 10,000,000 INR

# Symbol alias mapping for corporate restructurings
SYMBOL_ALIASES = {
    "TATAMOTORS": "TMPV",  # Post-demerger passenger vehicles & group holding
}

REVERSE_SYMBOL_ALIASES = {
    "TMPV": "TATAMOTORS",
}


class BaseXBRLMapper:
    """Base mapper for extracting financial statement facts from parsed XBRL elements."""

    @staticmethod
    def _to_cr(val: Optional[Decimal]) -> Optional[Decimal]:
        if val is None:
            return None
        return (val / CRORE_FACTOR).quantize(Decimal("0.01"))

    @staticmethod
    def _to_decimal(val_str: Optional[str]) -> Optional[Decimal]:
        if not val_str or val_str.strip() in ("", "-", "—", "nil", "NA"):
            return None
        try:
            cleaned = val_str.strip().replace(",", "")
            return Decimal(cleaned)
        except InvalidOperation:
            return None


class INDASMapper(BaseXBRLMapper):
    """Mapper for standard corporate Ind AS financial filings (RELIANCE, TCS, COALINDIA, TMPV, etc.)."""

    @classmethod
    def map_income_statement(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        rev_raw = facts.get("RevenueFromOperations") or facts.get("Income")
        rev = cls._to_cr(rev_raw)
        
        exp_raw = facts.get("Expenses")
        exp = cls._to_cr(exp_raw)
        
        dep_raw = (
            facts.get("DepreciationDepletionAndAmortisationExpense") or
            facts.get("DepreciationAndAmortisationExpense") or
            Decimal("0.00")
        )
        dep = cls._to_cr(dep_raw)
        
        interest_raw = facts.get("FinanceCosts") or Decimal("0.00")
        interest = cls._to_cr(interest_raw)
        
        pbt_raw = facts.get("ProfitBeforeTax")
        pbt = cls._to_cr(pbt_raw)
        
        tax_raw = facts.get("TaxExpense") or Decimal("0.00")
        tax = cls._to_cr(tax_raw)
        
        pat_raw = facts.get("ProfitLossForPeriod") or facts.get("ProfitLossForPeriodFromContinuingOperations")
        pat = cls._to_cr(pat_raw)
        
        # EPS is per share (NOT divided by Crore)
        eps = facts.get("BasicEarningsLossPerShareFromContinuingOperations") or facts.get("BasicEarningsLossPerShare")
        if eps is not None:
            eps = eps.quantize(Decimal("0.01"))

        # Operating EBITDA formula:
        # Operating Expenses (ex finance costs & depreciation) = Expenses - FinanceCosts - Depreciation
        # Operating EBITDA = RevenueFromOperations - Operating Expenses
        ebitda = None
        if rev is not None and exp is not None:
            finance_costs_cr = interest or Decimal("0.00")
            depreciation_cr = dep or Decimal("0.00")
            operating_expenses = exp - finance_costs_cr - depreciation_cr
            ebitda = rev - operating_expenses

        # Operating EBIT formula: Operating EBITDA - Depreciation
        ebit = None
        if ebitda is not None and dep is not None:
            ebit = ebitda - dep
        elif pbt is not None and interest is not None:
            ebit = pbt + interest

        return {
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

    @classmethod
    def map_balance_sheet(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        eq_cap = cls._to_cr(facts.get("PaidUpValueOfEquityShareCapital") or facts.get("EquityShareCapital"))
        reserves = cls._to_cr(facts.get("OtherEquity") or facts.get("Reserves"))
        
        # Borrowings: Non-current borrowings + Current borrowings if separate, or total borrowings
        borrowings_raw = facts.get("Borrowings")
        if borrowings_raw is None:
            nc_b = facts.get("NonCurrentBorrowings") or facts.get("BorrowingsNonCurrent") or Decimal("0.00")
            c_b = facts.get("CurrentBorrowings") or facts.get("BorrowingsCurrent") or Decimal("0.00")
            if nc_b or c_b:
                borrowings_raw = nc_b + c_b
        borrowings = cls._to_cr(borrowings_raw)

        total_assets = cls._to_cr(facts.get("TotalAssets"))
        total_liab = cls._to_cr(facts.get("TotalLiabilities") or facts.get("TotalEquityAndLiabilities"))
        fixed_assets = cls._to_cr(facts.get("PropertyPlantAndEquipment") or facts.get("FixedAssets"))
        cwip = cls._to_cr(facts.get("CapitalWorkInProgress") or facts.get("CWIP"))
        investments = cls._to_cr(facts.get("NonCurrentInvestments") or facts.get("Investments"))
        other_assets = cls._to_cr(facts.get("OtherNonCurrentAssets") or facts.get("OtherAssets"))
        other_liab = cls._to_cr(facts.get("OtherNonCurrentLiabilities") or facts.get("OtherLiabilities"))

        return {
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

    @classmethod
    def map_cash_flow(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        cfo = cls._to_cr(facts.get("CashFlowsFromUsedInOperatingActivities"))
        cfi = cls._to_cr(facts.get("CashFlowsFromUsedInInvestingActivities"))
        cff = cls._to_cr(facts.get("CashFlowsFromUsedInFinancingActivities"))
        
        # FCF = CFO - Purchase of Property, Plant & Equipment (Capex)
        fcf = cfo
        capex = facts.get("PurchaseOfPropertyPlantAndEquipment") or facts.get("CapitalExpenditure")
        if cfo is not None and capex is not None:
            fcf = cfo - cls._to_cr(abs(capex))

        return {
            "operating_cash_flow": cfo,
            "investing_cash_flow": cfi,
            "financing_cash_flow": cff,
            "free_cash_flow": fcf
        }


class BankingMapper(BaseXBRLMapper):
    """Mapper for commercial banking financial filings (HDFCBANK, ICICIBANK, SBIN, etc.)."""

    @classmethod
    def map_income_statement(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        interest_earned = facts.get("InterestEarned") or Decimal("0.00")
        other_income = facts.get("OtherIncome") or Decimal("0.00")
        total_income = interest_earned + other_income
        rev = cls._to_cr(total_income)

        interest_expended = facts.get("InterestExpended") or Decimal("0.00")
        interest = cls._to_cr(interest_expended)

        op_exp = facts.get("OperatingExpenses") or Decimal("0.00")
        provisions = facts.get("ProvisionsOtherThanTaxAndContingencies") or Decimal("0.00")
        tax_exp = facts.get("TaxExpense") or Decimal("0.00")
        tax = cls._to_cr(tax_exp)

        total_expenses = interest_expended + op_exp + provisions
        exp = cls._to_cr(total_expenses)

        # Bank Operating Profit (Before Provisions & Contingencies)
        op_profit = facts.get("OperatingProfitBeforeProvisionAndContingencies")
        ebitda = cls._to_cr(op_profit) if op_profit is not None else None
        ebit = ebitda

        dep_raw = facts.get("DepreciationOnBanksProperty") or Decimal("0.00")
        dep = cls._to_cr(dep_raw)

        pbt_raw = (
            facts.get("ProfitLossBeforeTax") or
            facts.get("ProfitLossFromOrdinaryActivitiesBeforeTax") or
            (op_profit - provisions if op_profit is not None else None)
        )
        pbt = cls._to_cr(pbt_raw)

        pat_raw = (
            facts.get("ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates") or
            facts.get("ProfitLossForThePeriod") or
            facts.get("ProfitLossFromOrdinaryActivitiesAfterTax") or
            facts.get("ProfitLossForPeriod")
        )
        pat = cls._to_cr(pat_raw)

        eps = (
            facts.get("BasicEarningsPerShareAfterExtraordinaryItems") or
            facts.get("BasicEarningsPerShareBeforeExtraordinaryItems") or
            facts.get("BasicEarningsLossPerShare")
        )
        if eps is not None:
            eps = eps.quantize(Decimal("0.01"))

        return {
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

    @classmethod
    def map_balance_sheet(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        eq_cap = cls._to_cr(facts.get("Capital") or facts.get("PaidUpCapital") or facts.get("EquityShareCapital"))
        reserves = cls._to_cr(facts.get("ReservesAndSurplus") or facts.get("Reserves"))
        borrowings = cls._to_cr(facts.get("Borrowings") or facts.get("Deposits"))
        total_assets = cls._to_cr(facts.get("TotalAssets"))
        total_liab = cls._to_cr(facts.get("TotalLiabilities"))
        fixed_assets = cls._to_cr(facts.get("FixedAssets") or facts.get("PropertyPlantAndEquipment"))
        investments = cls._to_cr(facts.get("Investments"))
        other_assets = cls._to_cr(facts.get("Advances") or facts.get("OtherAssets"))
        other_liab = cls._to_cr(facts.get("OtherLiabilitiesAndProvisions"))

        return {
            "equity_capital": eq_cap,
            "reserves": reserves,
            "borrowings": borrowings,
            "other_liabilities": other_liab,
            "total_liabilities": total_liab,
            "fixed_assets": fixed_assets,
            "cwip": None,
            "investments": investments,
            "other_assets": other_assets,
            "total_assets": total_assets
        }

    @classmethod
    def map_cash_flow(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        cfo = cls._to_cr(facts.get("CashFlowFromOperatingActivities") or facts.get("CashFlowsFromUsedInOperatingActivities"))
        cfi = cls._to_cr(facts.get("CashFlowFromInvestingActivities") or facts.get("CashFlowsFromUsedInInvestingActivities"))
        cff = cls._to_cr(facts.get("CashFlowFromFinancingActivities") or facts.get("CashFlowsFromUsedInFinancingActivities"))
        return {
            "operating_cash_flow": cfo,
            "investing_cash_flow": cfi,
            "financing_cash_flow": cff,
            "free_cash_flow": cfo
        }


class NBFCIndASMapper(BaseXBRLMapper):
    """Mapper for Non-Banking Financial Companies (BAJFINANCE, BAJAJFINSV, etc.)."""

    @classmethod
    def map_income_statement(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        rev_raw = facts.get("RevenueFromOperations") or facts.get("Income")
        rev = cls._to_cr(rev_raw)

        exp_raw = facts.get("Expenses")
        exp = cls._to_cr(exp_raw)

        interest_raw = facts.get("FinanceCosts") or Decimal("0.00")
        interest = cls._to_cr(interest_raw)

        dep_raw = facts.get("DepreciationDepletionAndAmortisationExpense") or Decimal("0.00")
        dep = cls._to_cr(dep_raw)

        pbt_raw = facts.get("ProfitBeforeTax")
        pbt = cls._to_cr(pbt_raw)

        tax_raw = facts.get("TaxExpense") or Decimal("0.00")
        tax = cls._to_cr(tax_raw)

        pat_raw = facts.get("ProfitLossForPeriod")
        pat = cls._to_cr(pat_raw)

        eps = facts.get("BasicEarningsLossPerShare") or facts.get("BasicEarningsLossPerShareFromContinuingOperations")
        if eps is not None:
            eps = eps.quantize(Decimal("0.01"))

        # NBFC Operating EBITDA: Revenue - Operating Expenses (ex finance costs & depreciation)
        ebitda = None
        if rev is not None and exp is not None:
            op_expenses = exp - (interest or Decimal("0.00")) - (dep or Decimal("0.00"))
            ebitda = rev - op_expenses

        ebit = None
        if ebitda is not None and dep is not None:
            ebit = ebitda - dep
        elif pbt is not None and interest is not None:
            ebit = pbt + interest

        return {
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

    @classmethod
    def map_balance_sheet(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        eq_cap = cls._to_cr(facts.get("EquityShareCapital") or facts.get("PaidUpValueOfEquityShareCapital"))
        reserves = cls._to_cr(facts.get("OtherEquity") or facts.get("Reserves"))
        
        # NBFC Debt: DebtSecurities + BorrowingsOtherThanDebtSecurities + SubordinatedLiabilities
        debt_sec = facts.get("DebtSecurities") or Decimal("0.00")
        other_borr = facts.get("BorrowingsOtherThanDebtSecurities") or facts.get("Borrowings") or Decimal("0.00")
        sub_liab = facts.get("SubordinatedLiabilities") or Decimal("0.00")
        total_debt = debt_sec + other_borr + sub_liab if (debt_sec or other_borr or sub_liab) else None
        borrowings = cls._to_cr(total_debt)

        total_assets = cls._to_cr(facts.get("TotalAssets"))
        total_liab = cls._to_cr(facts.get("TotalLiabilities") or facts.get("TotalFinancialLiabilities"))
        fixed_assets = cls._to_cr(facts.get("PropertyPlantAndEquipment"))
        cwip = cls._to_cr(facts.get("CapitalWorkInProgress"))
        investments = cls._to_cr(facts.get("Investments"))
        other_assets = cls._to_cr(facts.get("Loans") or facts.get("OtherAssets"))
        other_liab = cls._to_cr(facts.get("OtherFinancialLiabilities") or facts.get("OtherLiabilities"))

        return {
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

    @classmethod
    def map_cash_flow(cls, facts: Dict[str, Decimal]) -> Dict[str, Optional[Decimal]]:
        cfo = cls._to_cr(facts.get("CashFlowsFromUsedInOperatingActivities"))
        cfi = cls._to_cr(facts.get("CashFlowsFromUsedInInvestingActivities"))
        cff = cls._to_cr(facts.get("CashFlowsFromUsedInFinancingActivities"))
        return {
            "operating_cash_flow": cfo,
            "investing_cash_flow": cfi,
            "financing_cash_flow": cff,
            "free_cash_flow": cfo
        }


class XBRLFundamentalProvider:
    """
    Official regulatory XBRL fundamental provider.
    Parses statutory XML documents from NSE/BSE archives into normalized statement dicts.
    """

    MAPPERS = {
        "INDAS": INDASMapper,
        "BANKING": BankingMapper,
        "NBFC_INDAS": NBFCIndASMapper,
    }

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com/"
        })

    def fetch_xbrl_file(self, xbrl_url: str) -> str:
        """Downloads raw XBRL file content via HTTP GET."""
        try:
            r = self.session.get(xbrl_url, timeout=20)
            if r.status_code != 200:
                raise ProviderConnectionError(f"Failed to fetch XBRL from {xbrl_url}: HTTP {r.status_code}")
            return r.text
        except requests.exceptions.RequestException as e:
            raise ProviderConnectionError(f"Network error fetching XBRL from {xbrl_url}: {e}")

    def extract_facts(self, xml_content: str) -> Dict[str, Decimal]:
        """Parses XML and extracts numeric facts indexed by local element name."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise InvalidPayloadError(f"Failed to parse XBRL XML: {e}")

        facts: Dict[str, Decimal] = {}
        for elem in root.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            text = elem.text
            if text and text.strip():
                val = BaseXBRLMapper._to_decimal(text)
                if val is not None:
                    # Keep first or non-zero value for fact
                    if tag_name not in facts or (facts[tag_name] == Decimal("0.00") and val != Decimal("0.00")):
                        facts[tag_name] = val
        return facts

    def parse_filing(
        self,
        xml_content: str,
        taxonomy: str = "INDAS",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parses raw XBRL XML content and maps it to normalized statement fields
        using the appropriate taxonomy mapper.
        """
        facts = self.extract_facts(xml_content)
        mapper = self.MAPPERS.get(taxonomy.upper(), INDASMapper)

        income = mapper.map_income_statement(facts)
        balance = mapper.map_balance_sheet(facts)
        cash_flow = mapper.map_cash_flow(facts)

        meta = metadata or {}
        return {
            "source": meta.get("source", "NSE_XBRL"),
            "source_url": meta.get("source_url"),
            "symbol": meta.get("symbol"),
            "isin": meta.get("isin"),
            "taxonomy": taxonomy,
            "period_type": meta.get("period_type", "QUARTERLY"),
            "period_string": meta.get("period_string"),
            "fiscal_year": meta.get("fiscal_year"),
            "period_start": meta.get("period_start"),
            "period_end": meta.get("period_end"),
            "filing_date": meta.get("filing_date"),
            "broad_cast_date": meta.get("broad_cast_date"),
            "consolidated": meta.get("consolidated", "Consolidated"),
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cash_flow,
            "raw_facts_count": len(facts),
        }
