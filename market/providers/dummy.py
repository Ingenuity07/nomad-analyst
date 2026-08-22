import random
from datetime import datetime, timezone, timedelta
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

    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        upper_symbol = symbol.strip().upper()
        clean_symbol = upper_symbol.split('.')[0]
        
        # Determine number of days
        days = 30
        if start_date and end_date:
            days = max(1, (end_date - start_date).days)
            
        timestamps = []
        base_time = end_date or datetime.now(timezone.utc)
        for i in range(days):
            t = base_time - timedelta(days=days - i)
            timestamps.append(int(t.timestamp()))
            
        base_price = self._base_prices.get(clean_symbol, 100.00)
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        
        current_price = base_price
        for _ in range(days):
            change = current_price * random.uniform(-0.015, 0.02)
            close = round(current_price + change, 2)
            open_p = round(current_price * (1 + random.uniform(-0.005, 0.005)), 2)
            high = max(open_p, close, round(current_price * (1 + random.uniform(0.001, 0.02)), 2))
            low = min(open_p, close, round(current_price * (1 - random.uniform(0.001, 0.02)), 2))
            vol = random.randint(50000, 2000000)
            
            opens.append(open_p)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            volumes.append(vol)
            current_price = close
            
        return {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": f"{clean_symbol}.NS",
                            "currency": "INR",
                            "fullExchangeName": "NSE",
                            "regularMarketTime": timestamps[-1],
                            "regularMarketPrice": closes[-1],
                            "chartPreviousClose": base_price
                        },
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [
                                {
                                    "open": opens,
                                    "high": highs,
                                    "low": lows,
                                    "close": closes,
                                    "volume": volumes
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }

