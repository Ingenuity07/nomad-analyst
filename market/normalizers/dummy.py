from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from market.normalizers.base import BaseNormalizer
from market.providers.base import MarketQuote

class DummyNormalizer(BaseNormalizer):
    """
    Normalizes raw simulated responses from DummyMarketProvider into canonical MarketQuote models.
    """
    
    def normalize(self, raw_data: Dict[str, Any]) -> MarketQuote:
        # Parse timestamp string to datetime
        timestamp_str = raw_data.get("last_trade_time")
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str)
        else:
            timestamp = datetime.now()

        # Extract values cleanly and cast to Decimals where required
        return MarketQuote(
            symbol=raw_data["ticker"],
            exchange=raw_data.get("mkt", "NSE"),
            price=Decimal(str(raw_data["ltp"])),
            open=Decimal(str(raw_data["opening"])) if "opening" in raw_data else None,
            high=Decimal(str(raw_data["day_high"])) if "day_high" in raw_data else None,
            low=Decimal(str(raw_data["day_low"])) if "day_low" in raw_data else None,
            close=Decimal(str(raw_data["ltp"])),  # For a snapshot, close is the LTP
            volume=raw_data.get("vol_traded"),
            previous_close=Decimal(str(raw_data["prev_close"])) if "prev_close" in raw_data else None,
            change=Decimal(str(round(raw_data["ltp"] - raw_data["prev_close"], 2))) if "prev_close" in raw_data else None,
            change_percent=Decimal(str(round(((raw_data["ltp"] - raw_data["prev_close"]) / raw_data["prev_close"]) * 100, 2))) if "prev_close" in raw_data else None,
            timestamp=timestamp
        )
