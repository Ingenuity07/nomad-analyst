import random
from datetime import datetime, timezone
from typing import Dict, Any

class DummyMarketProvider:
    """
    Simulated market data provider returning raw stock data in a provider-specific format.
    """
    
    def __init__(self):
        # Base prices for mock Indian stocks
        self._base_prices = {
            "RELIANCE": 2450.00,
            "TCS": 3400.00,
            "INFY": 1450.00,
            "HDFCBANK": 1600.00,
            "ICICIBANK": 950.00,
            "SBIN": 580.00,
            "BHARTIENTL": 850.00
        }

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        upper_symbol = symbol.strip().upper()
        # Strip .NS or .BO suffix if present
        clean_symbol = upper_symbol.split('.')[0]
        
        base_price = self._base_prices.get(clean_symbol, 100.00)
        
        # Simulate slight price movement (-1.5% to +2.0%)
        pct_change = random.uniform(-0.015, 0.02)
        ltp = round(base_price * (1 + pct_change), 2)
        prev_close = base_price
        change = round(ltp - prev_close, 2)
        change_percent = round((change / prev_close) * 100, 2)
        
        opening = round(base_price * (1 + random.uniform(-0.005, 0.005)), 2)
        high = max(opening, ltp, round(base_price * (1 + random.uniform(0.001, 0.025)), 2))
        low = min(opening, ltp, round(base_price * (1 - random.uniform(0.001, 0.025)), 2))
        volume = random.randint(10000, 5000000)
        
        return {
            "ticker": clean_symbol,
            "mkt": "NSE" if ".BO" not in upper_symbol else "BSE",
            "ltp": ltp,
            "opening": opening,
            "day_high": high,
            "day_low": low,
            "prev_close": prev_close,
            "vol_traded": volume,
            "last_trade_time": datetime.now(timezone.utc).isoformat()
        }
