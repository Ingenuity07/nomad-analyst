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


class GetMarketContextInput(BaseModel):
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")
    universe: str = Field("NIFTY50", description="The stock universe to evaluate breadth for (e.g. NIFTY50).")

class GetMarketContextTool(BaseTool):
    """Tool to retrieve structured market context (regimes, breadth, global cues, correlations)."""

    @property
    def name(self) -> str:
        return "get_market_context"

    @property
    def description(self) -> str:
        return "Retrieve the structured market context snapshot (index regimes, market breadth, sector leaderboard, global cues, cross-market correlations, macro events, and data quality) for a given point-in-time."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetMarketContextInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetMarketContextInput

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
        return "Aggregated market context snapshot."

    def execute(self, as_of: Optional[str] = None, universe: str = "NIFTY50", **kwargs) -> ToolResult:
        try:
            from market.services.context_service import MarketContextService
            service = MarketContextService()
            context = service.get_market_context(as_of=as_of, universe=universe)
            return ToolResult(
                success=True,
                data=context,
                provider="MarketContextService",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetStockOpportunitiesInput(BaseModel):
    universe: str = Field("NIFTY50", description="The stock universe to scan (e.g. NIFTY50).")
    horizon: str = Field("DELIVERY_SWING", description="Investment horizon: 'DELIVERY_SWING', 'LONG_TERM', 'INTRADAY'.")
    opportunity_type: Optional[str] = Field(None, description="Optional opportunity type filter (e.g. TRENDING, MOMENTUM).")
    sector: Optional[str] = Field(None, description="Optional sector name filter.")
    limit: int = Field(10, description="Max candidates to return.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp (e.g. '2026-08-22T00:00:00Z').")

class GetStockOpportunitiesTool(BaseTool):
    """Tool to retrieve a ranked list of candidates matching discovery opportunity filters."""

    @property
    def name(self) -> str:
        return "get_stock_opportunities"

    @property
    def description(self) -> str:
        return "Retrieve ranked list of stock candidates with final scores, classifications, pros, and risks matching the given filters."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetStockOpportunitiesInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetStockOpportunitiesInput

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
        return "List of discovery stock opportunities."

    def execute(self, universe: str = "NIFTY50", horizon: str = "DELIVERY_SWING", opportunity_type: Optional[str] = None, sector: Optional[str] = None, limit: int = 10, as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            from django.utils import timezone as django_timezone
            from market.services.discovery_service import OpportunityDiscoveryService
            from market.models import StockOpportunitySnapshot
            
            if horizon == "INTRADAY":
                return ToolResult(
                    success=True,
                    data={"status": "NOT READY", "message": "Intraday investment horizon capability is not ready."},
                    provider="OpportunityDiscoveryService",
                    tool_name=self.name
                )
                
            service = OpportunityDiscoveryService()
            dt_as_of = service._parse_as_of(as_of)
            
            # Check if snapshots already exist in DB for this PIT
            snapshots = list(StockOpportunitySnapshot.objects.filter(
                as_of=dt_as_of,
                universe=universe,
                horizon=horizon
            ))
            
            # If not, scan dynamically
            if not snapshots:
                snapshots = service.scan_universe(universe, horizon, dt_as_of)
                
            # Filter
            if opportunity_type:
                snapshots = [s for s in snapshots if s.opportunity_type == opportunity_type.upper()]
            if sector:
                snapshots = [s for s in snapshots if s.instrument.company.sector and s.instrument.company.sector.lower() == sector.lower()]
                
            # Sort by final score descending
            snapshots.sort(key=lambda s: s.final_opportunity_score, reverse=True)
            
            data = []
            for s in snapshots[:limit]:
                data.append({
                    "symbol": s.instrument.symbol,
                    "company_name": s.instrument.company.name,
                    "sector": s.instrument.company.sector,
                    "opportunity_type": s.opportunity_type,
                    "final_score": float(s.final_opportunity_score),
                    "component_scores": s.component_scores,
                    "data_quality": s.data_quality["status"],
                    "reasons": s.supporting_features.get("pros", []),
                    "risks": s.risks
                })
                
            return ToolResult(
                success=True,
                data=data,
                provider="OpportunityDiscoveryService",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetStockOpportunityInput(BaseModel):
    symbol: str = Field(..., description="Stock symbol to retrieve detailed snapshot for (e.g. RELIANCE).")
    horizon: str = Field("DELIVERY_SWING", description="Investment horizon: 'DELIVERY_SWING', 'LONG_TERM', 'INTRADAY'.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp.")

class GetStockOpportunityTool(BaseTool):
    """Tool to retrieve full opportunity details for a single specific stock."""

    @property
    def name(self) -> str:
        return "get_stock_opportunity"

    @property
    def description(self) -> str:
        return "Retrieve the full point-in-time scores, features, pros, and risks for a single stock opportunity."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetStockOpportunityInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetStockOpportunityInput

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
        return "Detailed stock opportunity snapshot."

    def execute(self, symbol: str, horizon: str = "DELIVERY_SWING", as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            from market.services.discovery_service import OpportunityDiscoveryService
            from market.models import StockOpportunitySnapshot, Instrument
            
            if horizon == "INTRADAY":
                return ToolResult(
                    success=True,
                    data={"status": "NOT READY", "message": "Intraday investment horizon capability is not ready."},
                    provider="OpportunityDiscoveryService",
                    tool_name=self.name
                )
                
            service = OpportunityDiscoveryService()
            dt_as_of = service._parse_as_of(as_of)
            clean_symbol = symbol.strip().upper().split('.')[0]
            
            snapshot = StockOpportunitySnapshot.objects.filter(
                instrument__symbol=clean_symbol,
                as_of=dt_as_of,
                horizon=horizon
            ).first()
            
            if not snapshot:
                # Run dynamic scan for the target stock's universe to find it
                inst = Instrument.objects.filter(symbol=clean_symbol, is_active=True).first()
                if inst:
                    service.scan_universe("NIFTY50", horizon, dt_as_of)
                    snapshot = StockOpportunitySnapshot.objects.filter(
                        instrument__symbol=clean_symbol,
                        as_of=dt_as_of,
                        horizon=horizon
                    ).first()
                    
            if not snapshot:
                return ToolResult(
                    success=False,
                    data=None,
                    error=ToolError(code="NOT_FOUND", message=f"No opportunity snapshot found for symbol '{clean_symbol}' at {dt_as_of.isoformat()}.", retryable=False),
                    tool_name=self.name
                )
                
            data = {
                "symbol": snapshot.instrument.symbol,
                "company_name": snapshot.instrument.company.name,
                "sector": snapshot.instrument.company.sector,
                "horizon": snapshot.horizon,
                "opportunity_type": snapshot.opportunity_type,
                "final_score": float(snapshot.final_opportunity_score),
                "component_scores": snapshot.component_scores,
                "supporting_features": snapshot.supporting_features,
                "reasons": snapshot.supporting_features.get("pros", []),
                "risks": snapshot.risks,
                "data_quality": snapshot.data_quality
            }
            
            return ToolResult(
                success=True,
                data=data,
                provider="OpportunityDiscoveryService",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetSectorOpportunitiesInput(BaseModel):
    sector: Optional[str] = Field(None, description="Optional sector name to filter. If not provided, returns a summary of all sectors.")
    horizon: str = Field("DELIVERY_SWING", description="Investment horizon: 'DELIVERY_SWING', 'LONG_TERM', 'INTRADAY'.")
    as_of: Optional[str] = Field(None, description="ISO point-in-time timestamp.")

class GetSectorOpportunitiesTool(BaseTool):
    """Tool to summarize or retrieve opportunities grouped at the sector level."""

    @property
    def name(self) -> str:
        return "get_sector_opportunities"

    @property
    def description(self) -> str:
        return "Retrieve sector performance rankings or lists of candidates grouped by sector."

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetSectorOpportunitiesInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetSectorOpportunitiesInput

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
        return "Sector level opportunity discovery information."

    def execute(self, sector: Optional[str] = None, horizon: str = "DELIVERY_SWING", as_of: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            from market.services.discovery_service import OpportunityDiscoveryService
            from market.models import StockOpportunitySnapshot
            from django.db.models import Avg, Count
            
            if horizon == "INTRADAY":
                return ToolResult(
                    success=True,
                    data={"status": "NOT READY", "message": "Intraday investment horizon capability is not ready."},
                    provider="OpportunityDiscoveryService",
                    tool_name=self.name
                )
                
            service = OpportunityDiscoveryService()
            dt_as_of = service._parse_as_of(as_of)
            
            # Retrieve snapshots
            snapshots = list(StockOpportunitySnapshot.objects.filter(
                as_of=dt_as_of,
                horizon=horizon
            ))
            
            if not snapshots:
                # Trigger dynamic NIFTY50 scan
                snapshots = service.scan_universe("NIFTY50", horizon, dt_as_of)
                
            if sector and sector.upper() != "ALL":
                # Filter to sector
                snapshots = [s for s in snapshots if s.instrument.company.sector and s.instrument.company.sector.lower() == sector.lower()]
                data = []
                for s in snapshots:
                    data.append({
                        "symbol": s.instrument.symbol,
                        "company_name": s.instrument.company.name,
                        "opportunity_type": s.opportunity_type,
                        "final_score": float(s.final_opportunity_score),
                        "component_scores": s.component_scores
                    })
                return ToolResult(
                    success=True,
                    data={"sector": sector, "opportunities": data},
                    provider="OpportunityDiscoveryService",
                    tool_name=self.name
                )
            else:
                # Group by sector and return averages
                sector_stats = {}
                for s in snapshots:
                    sec = s.instrument.company.sector or "Unknown"
                    stats = sector_stats.setdefault(sec, {"count": 0, "sum_score": 0.0, "opportunities": []})
                    stats["count"] += 1
                    stats["sum_score"] += float(s.final_opportunity_score)
                    stats["opportunities"].append({
                        "symbol": s.instrument.symbol,
                        "opportunity_type": s.opportunity_type,
                        "final_score": float(s.final_opportunity_score)
                    })
                    
                data = []
                for sec, stats in sector_stats.items():
                    data.append({
                        "sector": sec,
                        "average_score": round(stats["sum_score"] / stats["count"], 2),
                        "candidate_count": stats["count"],
                        "candidates": sorted(stats["opportunities"], key=lambda c: c["final_score"], reverse=True)[:5]
                    })
                    
                data.sort(key=lambda d: d["average_score"], reverse=True)
                return ToolResult(
                    success=True,
                    data=data,
                    provider="OpportunityDiscoveryService",
                    tool_name=self.name
                )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


# ─────────────────────────────────────────────────────────────────────────────
# Module 8 — Recommendation Tools
# ─────────────────────────────────────────────────────────────────────────────

class GetRecommendationsInput(BaseModel):
    horizon: Optional[str] = Field(
        None,
        description="Filter by investment horizon: DELIVERY_SWING or LONG_TERM. Leave blank for all."
    )
    signal: Optional[str] = Field(
        None,
        description="Filter by signal direction: BUY, SELL, NO_ACTION. Leave blank for all."
    )
    confidence: Optional[str] = Field(
        None,
        description="Filter by confidence level: LOW, MEDIUM, HIGH. Leave blank for all."
    )
    symbol: Optional[str] = Field(
        None,
        description="Filter to recommendations for a specific ticker symbol."
    )
    status: Optional[str] = Field(
        "ACTIVE",
        description="Lifecycle status filter: ACTIVE, TRIGGERED, TARGET_HIT, STOPPED, EXPIRED, INVALIDATED, CANCELLED. Defaults to ACTIVE."
    )
    limit: int = Field(
        20,
        description="Maximum number of recommendations to return. Default 20."
    )


class GetRecommendationsTool(BaseTool):
    """
    Query stored StockRecommendation records with optional filters.

    IMPORTANT RULE: The LLM MUST use this tool to retrieve existing recommendations.
    The LLM must NEVER invent, modify, or override any recommendation fields
    (entry_price, stop_price, target_price, signal). It may only use the
    data returned by this tool.
    """

    @property
    def name(self) -> str:
        return "get_recommendations"

    @property
    def description(self) -> str:
        return (
            "Retrieve stored stock recommendations filtered by horizon, signal direction, "
            "confidence, status, or ticker. Use this to answer questions about actionable "
            "opportunities. DO NOT fabricate entry/stop/target values — always use the values "
            "returned by this tool."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetRecommendationsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetRecommendationsInput

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
        return "List of StockRecommendation records matching the filters."

    def execute(
        self,
        horizon: Optional[str] = None,
        signal: Optional[str] = None,
        confidence: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = "ACTIVE",
        limit: int = 20,
        **kwargs
    ) -> ToolResult:
        try:
            from market.models import StockRecommendation
            qs = StockRecommendation.objects.select_related(
                'instrument__company'
            ).order_by('-generated_at')

            if status:
                qs = qs.filter(status=status)
            if horizon:
                qs = qs.filter(horizon=horizon)
            if signal:
                qs = qs.filter(signal=signal)
            if confidence:
                qs = qs.filter(confidence=confidence)
            if symbol:
                qs = qs.filter(instrument__symbol=symbol.upper())

            records = list(qs[:limit])

            data = []
            for rec in records:
                data.append({
                    "id": str(rec.id),
                    "symbol": rec.instrument.symbol,
                    "company_name": rec.instrument.company.name if rec.instrument.company else None,
                    "sector": rec.instrument.company.sector if rec.instrument.company else None,
                    "horizon": rec.horizon,
                    "signal": rec.signal,
                    "setup_type": rec.setup_type,
                    "confidence": rec.confidence,
                    "status": rec.status,
                    "as_of": rec.as_of.isoformat(),
                    "generated_at": rec.generated_at.isoformat(),
                    "entry_type": rec.entry_type,
                    "entry_price": float(rec.entry_price) if rec.entry_price else None,
                    "entry_condition": rec.entry_condition,
                    "stop_price": float(rec.stop_price) if rec.stop_price else None,
                    "stop_method": rec.stop_method,
                    "target_price": float(rec.target_price) if rec.target_price else None,
                    "target_method": rec.target_method,
                    "risk_reward_ratio": float(rec.risk_reward_ratio) if rec.risk_reward_ratio else None,
                    "supporting_factors_count": len(rec.supporting_factors or []),
                    "risk_factors_count": len(rec.risk_factors or []),
                })

            return ToolResult(
                success=True,
                data={"count": len(data), "recommendations": data},
                provider="RecommendationService",
                tool_name=self.name
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetRecommendationInput(BaseModel):
    recommendation_id: Optional[str] = Field(
        None,
        description="UUID of a specific StockRecommendation record to retrieve in full detail."
    )
    symbol: Optional[str] = Field(
        None,
        description="Ticker symbol to get the most recent recommendation for."
    )
    horizon: Optional[str] = Field(
        None,
        description="Horizon filter when using symbol lookup: DELIVERY_SWING or LONG_TERM."
    )


class GetRecommendationTool(BaseTool):
    """
    Retrieve the full detail of a single StockRecommendation record.

    Use this when the user asks for a deep-dive on a specific recommendation,
    including all confidence components, supporting factors, market context, and
    setup conditions. The LLM must NEVER alter or restate the numeric fields.
    """

    @property
    def name(self) -> str:
        return "get_recommendation"

    @property
    def description(self) -> str:
        return (
            "Retrieve full detail of a single recommendation by its UUID or by ticker symbol. "
            "Returns all confidence dimensions, supporting factors, risk factors, "
            "setup conditions, and market context used at generation time."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetRecommendationInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetRecommendationInput

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
        return "Full detail of a single StockRecommendation record."

    def execute(
        self,
        recommendation_id: Optional[str] = None,
        symbol: Optional[str] = None,
        horizon: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        try:
            from market.models import StockRecommendation
            rec = None

            if recommendation_id:
                rec = StockRecommendation.objects.select_related(
                    'instrument__company'
                ).filter(id=recommendation_id).first()
            elif symbol:
                qs = StockRecommendation.objects.filter(
                    instrument__symbol=symbol.upper()
                ).select_related('instrument__company').order_by('-generated_at')
                if horizon:
                    qs = qs.filter(horizon=horizon)
                rec = qs.first()

            if not rec:
                return ToolResult(
                    success=False,
                    data=None,
                    error=ToolError(
                        code="NOT_FOUND",
                        message="No recommendation found with the given filters.",
                        retryable=False
                    ),
                    tool_name=self.name
                )

            data = {
                "id": str(rec.id),
                "symbol": rec.instrument.symbol,
                "company_name": rec.instrument.company.name if rec.instrument.company else None,
                "sector": rec.instrument.company.sector if rec.instrument.company else None,
                "horizon": rec.horizon,
                "signal": rec.signal,
                "setup_type": rec.setup_type,
                "confidence": rec.confidence,
                "status": rec.status,
                "status_updated_at": rec.status_updated_at.isoformat() if rec.status_updated_at else None,
                "as_of": rec.as_of.isoformat(),
                "generated_at": rec.generated_at.isoformat(),
                # Entry
                "entry_type": rec.entry_type,
                "entry_price": float(rec.entry_price) if rec.entry_price else None,
                "entry_condition": rec.entry_condition,
                # Stop
                "stop_price": float(rec.stop_price) if rec.stop_price else None,
                "stop_method": rec.stop_method,
                "invalidation_reason": rec.invalidation_reason,
                # Target
                "target_price": float(rec.target_price) if rec.target_price else None,
                "target_method": rec.target_method,
                # R:R
                "risk": float(rec.risk) if rec.risk else None,
                "reward": float(rec.reward) if rec.reward else None,
                "risk_reward_ratio": float(rec.risk_reward_ratio) if rec.risk_reward_ratio else None,
                # Confidence detail
                "confidence_components": rec.confidence_components,
                # Evidence
                "supporting_factors": rec.supporting_factors,
                "risk_factors": rec.risk_factors,
                # Setup detail
                "setup_details": rec.setup_details,
                # Context
                "market_context": rec.market_context,
                "sector_context": rec.sector_context,
                # Quality
                "data_quality": rec.data_quality,
                # LLM explanation (may be null if not yet generated)
                "llm_explanation": rec.llm_explanation,
            }

            return ToolResult(
                success=True,
                data=data,
                provider="RecommendationService",
                tool_name=self.name
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )


class GetActiveRecommendationsInput(BaseModel):
    horizon: Optional[str] = Field(
        None,
        description="Filter by horizon: DELIVERY_SWING or LONG_TERM. Leave blank for all."
    )
    signal: Optional[str] = Field(
        None,
        description="Filter by signal: BUY, SELL. Leave blank for all."
    )
    limit: int = Field(30, description="Maximum records to return. Default 30.")


class GetActiveRecommendationsTool(BaseTool):
    """
    Retrieve all ACTIVE StockRecommendation records, ranked by recency.

    Use this to get a comprehensive view of open recommendations across the
    portfolio universe. The LLM must use the returned data verbatim when
    discussing entry/stop/target levels.
    """

    @property
    def name(self) -> str:
        return "get_active_recommendations"

    @property
    def description(self) -> str:
        return (
            "Get all currently ACTIVE StockRecommendations with optional filters on "
            "horizon and signal direction. Returns a ranked list of open opportunities "
            "with entry, stop, target and confidence."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetActiveRecommendationsInput.model_json_schema()

    @property
    def input_schema(self) -> type[BaseModel]:
        return GetActiveRecommendationsInput

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
        return "All ACTIVE recommendations matching the optional horizon/signal filters."

    def execute(
        self,
        horizon: Optional[str] = None,
        signal: Optional[str] = None,
        limit: int = 30,
        **kwargs
    ) -> ToolResult:
        try:
            from market.services.recommendation_service import RecommendationService
            svc = RecommendationService()
            records = svc.get_active_recommendations(
                horizon=horizon, signal=signal, limit=limit
            )

            data = []
            for rec in records:
                data.append({
                    "id": str(rec.id),
                    "symbol": rec.instrument.symbol,
                    "company_name": rec.instrument.company.name if rec.instrument.company else None,
                    "sector": rec.instrument.company.sector if rec.instrument.company else None,
                    "horizon": rec.horizon,
                    "signal": rec.signal,
                    "setup_type": rec.setup_type,
                    "confidence": rec.confidence,
                    "as_of": rec.as_of.isoformat(),
                    "entry_price": float(rec.entry_price) if rec.entry_price else None,
                    "stop_price": float(rec.stop_price) if rec.stop_price else None,
                    "target_price": float(rec.target_price) if rec.target_price else None,
                    "risk_reward_ratio": float(rec.risk_reward_ratio) if rec.risk_reward_ratio else None,
                    "supporting_factors": rec.supporting_factors,
                    "risk_factors": rec.risk_factors,
                })

            return ToolResult(
                success=True,
                data={"count": len(data), "active_recommendations": data},
                provider="RecommendationService",
                tool_name=self.name
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=ToolError(code="EXECUTION_ERROR", message=str(e), retryable=False),
                tool_name=self.name
            )




# ── Module 9: Intraday Data Tools ────────────────────────────────────────────


class GetIntradayOHLCVInput(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (e.g. RELIANCE, TCS).")
    timeframe: str = Field(default="5m", description="Intraday timeframe: '5m', '15m', or '1h'.")
    limit: int = Field(default=50, description="Maximum number of bars to return (max 200).")
    as_of: Optional[str] = Field(default=None, description="ISO 8601 UTC datetime for PIT query.")


class GetIntradayOHLCVTool(BaseTool):
    """Retrieve stored intraday OHLCV bars for a symbol at a given timeframe."""

    @property
    def name(self) -> str:
        return "get_intraday_ohlcv"

    @property
    def description(self) -> str:
        return (
            "Retrieve stored intraday OHLCV bars (open, high, low, close, volume) "
            "for a stock symbol at a given timeframe (5m, 15m, 1h). "
            "Returns only bars already in the database — does NOT fetch live data."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetIntradayOHLCVInput.model_json_schema()

    @property
    def input_schema(self):
        return GetIntradayOHLCVInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    def execute(self, symbol: str, timeframe: str = "5m", limit: int = 50,
                as_of: Optional[str] = None, **kwargs) -> ToolResult:
        from market.models import Instrument, OHLCVBar
        limit = min(limit, 200)
        symbol_upper = symbol.strip().upper()
        try:
            instrument = Instrument.objects.get(symbol=symbol_upper)
        except Instrument.DoesNotExist:
            return ToolResult(
                success=False, data=None,
                error=ToolError(code="SYMBOL_NOT_FOUND",
                                message=f"Instrument '{symbol_upper}' not found.", retryable=False),
                tool_name=self.name
            )
        as_of_dt = None
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError:
                pass
        qs = OHLCVBar.objects.filter(instrument=instrument, timeframe=timeframe)
        if as_of_dt:
            qs = qs.filter(timestamp__lte=as_of_dt)
        bars = list(qs.order_by("-timestamp")[:limit])
        bars.reverse()
        return ToolResult(
            success=True,
            data={
                "symbol": symbol_upper, "timeframe": timeframe, "bar_count": len(bars),
                "bars": [{"timestamp": b.timestamp.isoformat(), "open": float(b.open),
                          "high": float(b.high), "low": float(b.low), "close": float(b.close),
                          "volume": b.volume} for b in bars]
            },
            tool_name=self.name
        )


class GetIntradayDataQualityInput(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (e.g. RELIANCE, TCS).")
    timeframe: str = Field(default="5m", description="Intraday timeframe: '5m', '15m', or '1h'.")
    as_of: Optional[str] = Field(default=None, description="ISO 8601 UTC datetime for PIT assessment.")


class GetIntradayDataQualityTool(BaseTool):
    """Check intraday data quality (HEALTHY/STALE/INCOMPLETE/UNAVAILABLE) for a symbol."""

    @property
    def name(self) -> str:
        return "get_intraday_data_quality"

    @property
    def description(self) -> str:
        return (
            "Check the intraday data quality and freshness for a stock symbol at "
            "a given timeframe. Returns status, lag in seconds, completeness %, and data gap count."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetIntradayDataQualityInput.model_json_schema()

    @property
    def input_schema(self):
        return GetIntradayDataQualityInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    def execute(self, symbol: str, timeframe: str = "5m", as_of: Optional[str] = None, **kwargs) -> ToolResult:
        from market.models import Instrument
        from market.services.intraday_quality import get_data_quality
        symbol_upper = symbol.strip().upper()
        try:
            instrument = Instrument.objects.get(symbol=symbol_upper)
        except Instrument.DoesNotExist:
            return ToolResult(success=False, data=None,
                              error=ToolError(code="SYMBOL_NOT_FOUND",
                                             message=f"Instrument '{symbol_upper}' not found.", retryable=False),
                              tool_name=self.name)
        as_of_dt = None
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError:
                pass
        quality = get_data_quality(instrument, timeframe, as_of_dt)
        return ToolResult(success=True,
                          data={"symbol": symbol_upper, "timeframe": timeframe, **quality.as_dict()},
                          tool_name=self.name)


class GetIntradayFeaturesInput(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (e.g. RELIANCE, TCS).")
    timeframe: str = Field(default="5m", description="Intraday timeframe: '5m', '15m', or '1h'.")
    as_of: Optional[str] = Field(default=None, description="ISO 8601 UTC datetime for PIT feature query.")


class GetIntradayFeaturesTool(BaseTool):
    """Retrieve latest technical features (RSI, SMA, MACD, ATR etc.) for an intraday timeframe."""

    @property
    def name(self) -> str:
        return "get_intraday_features"

    @property
    def description(self) -> str:
        return (
            "Retrieve the latest calculated technical features (RSI, SMA, MACD, ATR, etc.) "
            "for a stock symbol at an intraday timeframe (5m, 15m, 1h). "
            "Returns the most recent feature snapshot from the database."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return GetIntradayFeaturesInput.model_json_schema()

    @property
    def input_schema(self):
        return GetIntradayFeaturesInput

    @property
    def category(self) -> str:
        return "market"

    @property
    def read_only(self) -> bool:
        return True

    def execute(self, symbol: str, timeframe: str = "5m", as_of: Optional[str] = None, **kwargs) -> ToolResult:
        from market.models import Instrument, TechnicalFeature
        from django.db.models import Max
        symbol_upper = symbol.strip().upper()
        try:
            instrument = Instrument.objects.get(symbol=symbol_upper)
        except Instrument.DoesNotExist:
            return ToolResult(success=False, data=None,
                              error=ToolError(code="SYMBOL_NOT_FOUND",
                                             message=f"Instrument '{symbol_upper}' not found.", retryable=False),
                              tool_name=self.name)
        as_of_dt = None
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError:
                pass
        qs = TechnicalFeature.objects.filter(instrument=instrument, timeframe=timeframe)
        if as_of_dt:
            qs = qs.filter(timestamp__lte=as_of_dt)
        latest_row = qs.order_by("instrument").values("instrument").annotate(max_ts=Max("timestamp")).first()
        if not latest_row:
            return ToolResult(success=True,
                              data={"symbol": symbol_upper, "timeframe": timeframe,
                                    "features": {}, "timestamp": None,
                                    "note": "No intraday features found. Run feature calculation first."},
                              tool_name=self.name)
        features_qs = TechnicalFeature.objects.filter(
            instrument=instrument, timeframe=timeframe, timestamp=latest_row["max_ts"]
        )
        feature_map = {f.name: float(f.value) if f.value is not None else None for f in features_qs}
        return ToolResult(success=True,
                          data={"symbol": symbol_upper, "timeframe": timeframe,
                                "timestamp": latest_row["max_ts"].isoformat(), "features": feature_map},
                          tool_name=self.name)
