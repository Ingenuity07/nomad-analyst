from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
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
            # Convert Decimal fields to floats for standard JSON serialization
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
