from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from llm.tools.base import BaseTool
from llm.tools.result import ToolResult, ToolError
from market.services.market_service import MarketService

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

    def execute(self, symbol: str, timeframe: str = "1d", limit: int = 100, **kwargs) -> ToolResult:
        try:
            service = MarketService()
            # If database has no bars, trigger a backfill fetch first
            bars = service.get_historical_ohlcv(symbol, timeframe, limit)
            if not bars:
                # Triggers standard 1-year backfill
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

    def execute(self, symbol: str, timeframe: str = "1d", name: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            service = MarketService()
            features = service.get_stored_features(symbol, timeframe, name)
            if not features:
                # If no features exist, calculate and save them first
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
