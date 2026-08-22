from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from llm.tools.base import BaseTool
from llm.tools.result import ToolResult, ToolError
from market.services.market_service import MarketService
from market.services.fundamental_service import FundamentalDataService, FundamentalMetricService
from market.services.news_service import NewsIntelligenceService
from market.models import (
    IncomeStatement,
    BalanceSheetStatement,
    CashFlowStatement,
    DerivedFundamentalMetric,
    Company
)

class GetStockSnapshotInput(BaseModel):
    symbol: str = Field(..., description="The stock ticker symbol to look up (e.g. RELIANCE, TCS).")

class GetStockSnapshotTool(BaseTool):
    """Tool to fetch the latest price and trade metrics for a given stock symbol."""

    @property
    def name(self) -> str:
        return "get_stock_snapshot"

    @property
    def description(self) -> str:
        return "Retrieve the latest price, daily high/low, change, and volume metrics for a stock ticker symbol."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetStockSnapshotInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetStockSnapshotInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "Latest stock trade price and daily metrics."

    def execute(self, symbol: str, **kwargs) -> ToolResult:
        try:
            service = MarketService()
            quote = service.fetch_and_save_quote(symbol)
            data = {
                "symbol": quote.symbol,
                "exchange": quote.exchange,
                "price": float(quote.price),
                "open": float(quote.open_price) if quote.open_price is not None else None,
                "high": float(quote.high) if quote.high is not None else None,
                "low": float(quote.low) if quote.low is not None else None,
                "close": float(quote.close) if quote.close is not None else None,
                "volume": quote.volume,
                "previous_close": float(quote.previous_close) if quote.previous_close is not None else None,
                "change": float(quote.change) if quote.change is not None else None,
                "change_percent": float(quote.change_percent) if quote.change_percent is not None else None,
                "timestamp": quote.timestamp.isoformat()
            }
            return ToolResult(
                success=True,
                data=data,
                provider="YFinanceMarketProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetHistoricalOHLCVInput(BaseModel):
    symbol: str = Field(..., description="The stock ticker symbol (e.g. RELIANCE, TCS).")
    timeframe: str = Field("1d", description="Bar timeframe: '1d', '1h', '5m', etc.")
    limit: int = Field(100, description="Maximum number of historical bars to retrieve.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetHistoricalOHLCVTool(BaseTool):
    """Tool to fetch historical price and volume bars for a stock."""

    @property
    def name(self) -> str:
        return "get_historical_ohlcv"

    @property
    def description(self) -> str:
        return "Retrieve historical OHLCV bars (open, high, low, close, volume) for a given symbol and timeframe."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetHistoricalOHLCVInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetHistoricalOHLCVInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of historical price bars sorted chronologically."

    def execute(self, symbol: str, timeframe: str = "1d", limit: int = 100, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            service = MarketService()
            as_of_dt = None
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                
            bars = service.get_historical_ohlcv(symbol, timeframe, limit, as_of=as_of_dt)
            if not bars and not as_of_dt:
                bars = service.fetch_and_save_historical_ohlcv(symbol, timeframe)
                bars = bars[-limit:] if len(bars) > limit else bars
                
            data = []
            for b in bars:
                data.append({
                    "timestamp": b.timestamp.isoformat(),
                    "open": float(b.open),
                    "high": float(b.high),
                    "low": float(b.low),
                    "close": float(b.close),
                    "volume": b.volume,
                    "source": b.source
                })
            return ToolResult(
                success=True,
                data=data,
                provider="YFinanceMarketProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetTechnicalFeaturesInput(BaseModel):
    symbol: str = Field(..., description="The stock ticker symbol (e.g. RELIANCE, TCS).")
    timeframe: str = Field("1d", description="Bar timeframe: '1d', '1h', etc.")
    name: Optional[str] = Field(None, description="Filter for specific indicator name (e.g. 'RSI_14', 'SMA_20').")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetTechnicalFeaturesTool(BaseTool):
    """Tool to fetch stored calculated technical features for a stock."""

    @property
    def name(self) -> str:
        return "get_technical_features"

    @property
    def description(self) -> str:
        return "Retrieve pre-calculated derived technical features (RSI, SMA, EMA, MACD, ATR, volatility) for a stock ticker."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetTechnicalFeaturesInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetTechnicalFeaturesInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of technical indicators with timestamp mapping."

    def execute(self, symbol: str, timeframe: str = "1d", name: Optional[str] = None, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            service = MarketService()
            as_of_dt = None
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                
            features = service.get_stored_features(symbol, timeframe, name, as_of=as_of_dt)
            if not features and not as_of_dt:
                service.refresh_features(symbol, timeframe)
                features = service.get_stored_features(symbol, timeframe, name)
                
            data = []
            for f in features:
                data.append({
                    "timestamp": f.timestamp.isoformat(),
                    "name": f.name,
                    "param_key": f.param_key,
                    "value": float(f.value) if f.value is not None else None
                })
            return ToolResult(
                success=True,
                data=data,
                provider="YFinanceMarketProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetCompanyFinancialsInput(BaseModel):
    symbol: str = Field(..., description="The company short ticker symbol (e.g. RELIANCE, TCS).")
    period_type: str = Field("ANNUAL", description="Statement period filter: 'ANNUAL' or 'QUARTERLY'.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetCompanyFinancialsTool(BaseTool):
    """Tool to fetch normalized income, balance sheet, and cash flow statements for a company."""

    @property
    def name(self) -> str:
        return "get_company_financials"

    @property
    def description(self) -> str:
        return "Retrieve normalized historical financial statements (income, balance sheet, cash flows) for a company."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetCompanyFinancialsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetCompanyFinancialsInput

    @property
    def category(self) -> str:
        return "fundamental"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "Structured income, balance sheet, and cash flow statement arrays."

    def execute(self, symbol: str, period_type: str = "ANNUAL", as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            clean_symbol = symbol.strip().upper().split('.')[0]
            company = Company.objects.get(short_name=clean_symbol)
            incomes = IncomeStatement.objects.filter(company=company, period_type=period_type)
            balances = BalanceSheetStatement.objects.filter(company=company, period_type=period_type)
            cash_flows = CashFlowStatement.objects.filter(company=company, period_type=period_type)
            
            # Trigger backfill first if database is empty and no as_of is restricting it
            if not incomes.exists() and not as_of:
                service = FundamentalDataService()
                service.ingest_company_financials(clean_symbol)
                incomes = IncomeStatement.objects.filter(company=company, period_type=period_type)
                balances = BalanceSheetStatement.objects.filter(company=company, period_type=period_type)
                cash_flows = CashFlowStatement.objects.filter(company=company, period_type=period_type)
                
            # Apply point-in-time constraints
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                as_of_date = as_of_dt.date()
                incomes = incomes.filter(period_end__lte=as_of_date)
                balances = balances.filter(period_end__lte=as_of_date)
                cash_flows = cash_flows.filter(period_end__lte=as_of_date)
                
            data = {
                "income_statement": [],
                "balance_sheet": [],
                "cash_flow": []
            }
            
            for inc in incomes.order_by('fiscal_year'):
                data["income_statement"].append({
                    "period": inc.period_string,
                    "fiscal_year": inc.fiscal_year,
                    "revenue": float(inc.revenue) if inc.revenue is not None else None,
                    "expenses": float(inc.expenses) if inc.expenses is not None else None,
                    "ebitda": float(inc.ebitda) if inc.ebitda is not None else None,
                    "ebit": float(inc.ebit) if inc.ebit is not None else None,
                    "depreciation": float(inc.depreciation) if inc.depreciation is not None else None,
                    "interest": float(inc.interest) if inc.interest is not None else None,
                    "pbt": float(inc.pbt) if inc.pbt is not None else None,
                    "tax": float(inc.tax) if inc.tax is not None else None,
                    "pat": float(inc.pat) if inc.pat is not None else None,
                    "eps": float(inc.eps) if inc.eps is not None else None,
                })
                
            for bal in balances.order_by('fiscal_year'):
                data["balance_sheet"].append({
                    "period": bal.period_string,
                    "fiscal_year": bal.fiscal_year,
                    "equity_capital": float(bal.equity_capital) if bal.equity_capital is not None else None,
                    "reserves": float(bal.reserves) if bal.reserves is not None else None,
                    "borrowings": float(bal.borrowings) if bal.borrowings is not None else None,
                    "other_liabilities": float(bal.other_liabilities) if bal.other_liabilities is not None else None,
                    "total_liabilities": float(bal.total_liabilities) if bal.total_liabilities is not None else None,
                    "fixed_assets": float(bal.fixed_assets) if bal.fixed_assets is not None else None,
                    "cwip": float(bal.cwip) if bal.cwip is not None else None,
                    "investments": float(bal.investments) if bal.investments is not None else None,
                    "other_assets": float(bal.other_assets) if bal.other_assets is not None else None,
                    "total_assets": float(bal.total_assets) if bal.total_assets is not None else None,
                })
                
            for cf in cash_flows.order_by('fiscal_year'):
                data["cash_flow"].append({
                    "period": cf.period_string,
                    "fiscal_year": cf.fiscal_year,
                    "operating_cash_flow": float(cf.operating_cash_flow) if cf.operating_cash_flow is not None else None,
                    "investing_cash_flow": float(cf.investing_cash_flow) if cf.investing_cash_flow is not None else None,
                    "financing_cash_flow": float(cf.financing_cash_flow) if cf.financing_cash_flow is not None else None,
                    "free_cash_flow": float(cf.free_cash_flow) if cf.free_cash_flow is not None else None,
                })
                
            return ToolResult(
                success=True,
                data=data,
                provider="ScreenerFundamentalProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetFinancialMetricsInput(BaseModel):
    symbol: str = Field(..., description="The company short ticker symbol (e.g. RELIANCE, TCS).")
    name: Optional[str] = Field(None, description="Optional name of specific derived metric (e.g. 'return_on_equity', 'debt_equity').")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetFinancialMetricsTool(BaseTool):
    """Tool to fetch pre-calculated derived fundamental metrics for a company."""

    @property
    def name(self) -> str:
        return "get_financial_metrics"

    @property
    def description(self) -> str:
        return "Retrieve derived historical profitability, growth, leverage, and valuation ratios for a company."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetFinancialMetricsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetFinancialMetricsInput

    @property
    def category(self) -> str:
        return "fundamental"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of fundamental ratios and growth rates grouped by reporting period."

    def execute(self, symbol: str, name: Optional[str] = None, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            clean_symbol = symbol.strip().upper().split('.')[0]
            company = Company.objects.get(short_name=clean_symbol)
            metrics = DerivedFundamentalMetric.objects.filter(company=company)
            
            if not metrics.exists() and not as_of:
                service = FundamentalDataService()
                service.ingest_company_financials(clean_symbol)
                metrics = DerivedFundamentalMetric.objects.filter(company=company)
                
            if name:
                metrics = metrics.filter(name=name)
                
            # Filter in Python using the parsed period end date helper
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                as_of_date = as_of_dt.date()
                
                filtered_metrics = []
                helper_service = FundamentalDataService()
                for m in metrics:
                    p_end = helper_service._parse_period_end(m.period_string)
                    if p_end and p_end > as_of_date:
                        continue
                    filtered_metrics.append(m)
                metrics = filtered_metrics
            else:
                metrics = list(metrics)
                
            data = []
            for m in sorted(metrics, key=lambda x: (x.period_string, x.name)):
                data.append({
                    "period": m.period_string,
                    "name": m.name,
                    "value": float(m.value) if m.value is not None else None
                })
            return ToolResult(
                success=True,
                data=data,
                provider="ScreenerFundamentalProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetCompanyNewsInput(BaseModel):
    symbol: str = Field(..., description="The stock ticker symbol (e.g. RELIANCE, TCS).")
    limit: int = Field(10, description="Max number of news articles to retrieve.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetCompanyNewsTool(BaseTool):
    """Tool to fetch recent company news headlines and summaries."""

    @property
    def name(self) -> str:
        return "get_company_news"

    @property
    def description(self) -> str:
        return "Retrieve recent structured news headlines, summaries, and source details for a stock ticker symbol."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetCompanyNewsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetCompanyNewsInput

    @property
    def category(self) -> str:
        return "news"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of news articles sorted by publication date."

    def execute(self, symbol: str, limit: int = 10, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            clean_symbol = symbol.strip().upper().split('.')[0]
            company = Company.objects.get(short_name=clean_symbol)
            service = NewsIntelligenceService()
            
            as_of_dt = None
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                
            # Fetch latest news first
            news_items = service.get_company_news(company.id, as_of=as_of_dt)
            if not news_items and not as_of_dt:
                service.fetch_and_save_company_news(clean_symbol)
                news_items = service.get_company_news(company.id)
                
            news_items = news_items[:limit]
            
            data = []
            for item in news_items:
                data.append({
                    "headline": item.headline,
                    "summary": item.summary,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at.isoformat(),
                    "event_type": item.event_type
                })
            return ToolResult(
                success=True,
                data=data,
                provider="YahooRSSNewsProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetCompanyEventsInput(BaseModel):
    symbol: str = Field(..., description="The stock ticker symbol (e.g. RELIANCE, TCS).")
    event_type: str = Field(..., description="Deterministic category filter (e.g. 'earnings/results', 'dividend').")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetCompanyEventsTool(BaseTool):
    """Tool to fetch company news filtered by categorized event type."""

    @property
    def name(self) -> str:
        return "get_company_events"

    @property
    def description(self) -> str:
        return "Retrieve categorized corporate material events (dividend, earnings, split, management change) for a stock symbol."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetCompanyEventsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetCompanyEventsInput

    @property
    def category(self) -> str:
        return "news"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of categorized events sorted by date."

    def execute(self, symbol: str, event_type: str, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            clean_symbol = symbol.strip().upper().split('.')[0]
            company = Company.objects.get(short_name=clean_symbol)
            service = NewsIntelligenceService()
            
            as_of_dt = None
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                
            # Fetch latest news first
            news_items = service.get_company_news(company.id, as_of=as_of_dt)
            if not news_items and not as_of_dt:
                service.fetch_and_save_company_news(clean_symbol)
                
            events = service.get_company_events(company.id, event_type, as_of=as_of_dt)
            
            data = []
            for item in events:
                data.append({
                    "headline": item.headline,
                    "summary": item.summary,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at.isoformat(),
                    "event_type": item.event_type
                })
            return ToolResult(
                success=True,
                data=data,
                provider="YahooRSSNewsProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetMarketNewsInput(BaseModel):
    limit: int = Field(10, description="Max number of market news to retrieve.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetMarketNewsTool(BaseTool):
    """Tool to fetch recent market-wide news feed."""

    @property
    def name(self) -> str:
        return "get_market_news"

    @property
    def description(self) -> str:
        return "Retrieve general market-wide financial news feed."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetMarketNewsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetMarketNewsInput

    @property
    def category(self) -> str:
        return "news"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def output_description(self) -> str:
        return "A list of general market-wide news articles."

    def execute(self, limit: int = 10, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            service = NewsIntelligenceService()
            as_of_dt = None
            if as_of:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                
            news_items = service.get_market_news(as_of=as_of_dt)[:limit]
            
            data = []
            for item in news_items:
                data.append({
                    "company": item.company.short_name if item.company else None,
                    "headline": item.headline,
                    "summary": item.summary,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at.isoformat(),
                    "event_type": item.event_type
                })
            return ToolResult(
                success=True,
                data=data,
                provider="YahooRSSNewsProvider",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )
