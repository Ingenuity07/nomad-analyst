from typing import Protocol, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class MarketQuote(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g. RELIANCE, HDFCBANK)")
    exchange: str = Field(..., description="Stock exchange (e.g. NSE, BSE)")
    price: Decimal = Field(..., description="Current price")
    open_price: Optional[Decimal] = Field(None, alias="open", description="Opening price of the day")
    high: Optional[Decimal] = Field(None, alias="high", description="Highest price of the day")
    low: Optional[Decimal] = Field(None, alias="low", description="Lowest price of the day")
    close: Optional[Decimal] = Field(None, alias="close", description="Closing price of the day")
    volume: Optional[int] = Field(None, description="Volume traded")
    previous_close: Optional[Decimal] = Field(None, description="Previous day closing price")
    change: Optional[Decimal] = Field(None, description="Absolute change in price")
    change_percent: Optional[Decimal] = Field(None, description="Percentage change in price")
    timestamp: datetime = Field(..., description="Timestamp of the quote")

    class Config:
        populate_by_name = True


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> dict:
        """
        Fetches the raw quote data for the symbol from the provider.
        Returns a raw dictionary response.
        """
        ...

    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", start_date: datetime = None, end_date: datetime = None) -> dict:
        """
        Fetches historical OHLCV data for the symbol from the provider.
        Returns a raw dictionary response.
        """
        ...
