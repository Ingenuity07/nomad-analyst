from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
import re
from market.normalizers.base import BaseNormalizer
from market.providers.base import MarketQuote

class YFinanceNormalizer(BaseNormalizer):
    """
    Normalizes raw JSON responses from Yahoo Finance chart API into canonical MarketQuote models.
    Enforces deterministic data validation for cleanliness and safety.
    """
    
    def normalize(self, raw_data: Dict[str, Any]) -> MarketQuote:
        try:
            if not raw_data or "chart" not in raw_data or not raw_data["chart"].get("result"):
                raise ValueError("Malformed provider payload: missing chart result.")
                
            result = raw_data["chart"]["result"][0]
            meta = result.get("meta")
            if not meta:
                raise ValueError("Malformed provider payload: missing metadata (meta).")
                
            # 1. Validate Symbol
            raw_symbol = meta.get("symbol")
            if not raw_symbol or not isinstance(raw_symbol, str):
                raise ValueError("Invalid symbol parameter: empty or not string.")
            
            # Strip suffix (.NS or .BO)
            clean_symbol = raw_symbol.split('.')[0].strip()
            # Map provider symbol aliases back to canonical NIFTY 50 identity
            if clean_symbol == "TMPV":
                clean_symbol = "TATAMOTORS"
            if not clean_symbol or not re.match(r"^[A-Za-z0-9_\-\^=&]+$", clean_symbol):
                raise ValueError(f"Invalid symbol characters: '{clean_symbol}'")
                
            # 2. Validate Exchange
            raw_exchange = meta.get("fullExchangeName", "NSE")
            if "NSE" in raw_exchange or "NSI" in raw_exchange:
                exchange = "NSE"
            elif "BSE" in raw_exchange or "BOM" in raw_exchange:
                exchange = "BSE"
            else:
                # Default fallback or raise error
                exchange = "NSE"
                
            # 3. Validate Price
            if "regularMarketPrice" not in meta or meta["regularMarketPrice"] is None:
                raise ValueError("Missing regularMarketPrice.")
            price = Decimal(str(meta["regularMarketPrice"]))
            if price <= 0:
                raise ValueError(f"Negative or zero price detected: {price}")
                
            # Indicators parsing
            indicators = result.get("indicators", {})
            quote_lists = indicators.get("quote", [{}])[0]
            
            # 4. Extract and validate OHLC relationships
            open_val = None
            if quote_lists.get("open") and quote_lists["open"][0] is not None:
                open_val = Decimal(str(quote_lists["open"][0]))
            elif "regularMarketPrice" in meta:
                open_val = price
                
            high_val = None
            if quote_lists.get("high") and quote_lists["high"][0] is not None:
                high_val = Decimal(str(quote_lists["high"][0]))
            elif "regularMarketDayHigh" in meta:
                high_val = Decimal(str(meta["regularMarketDayHigh"]))
                
            low_val = None
            if quote_lists.get("low") and quote_lists["low"][0] is not None:
                low_val = Decimal(str(quote_lists["low"][0]))
            elif "regularMarketDayLow" in meta:
                low_val = Decimal(str(meta["regularMarketDayLow"]))
                
            close_val = price
            if quote_lists.get("close") and quote_lists["close"][0] is not None:
                close_val = Decimal(str(quote_lists["close"][0]))
                
            volume = None
            if quote_lists.get("volume") and quote_lists["volume"][0] is not None:
                volume = int(quote_lists["volume"][0])
            elif "regularMarketVolume" in meta:
                volume = int(meta["regularMarketVolume"])
                
            # Numeric value checks
            if open_val is not None and open_val <= 0:
                raise ValueError(f"Invalid open price: {open_val}")
            if high_val is not None and high_val <= 0:
                raise ValueError(f"Invalid high price: {high_val}")
            if low_val is not None and low_val <= 0:
                raise ValueError(f"Invalid low price: {low_val}")
            if close_val is not None and close_val <= 0:
                raise ValueError(f"Invalid close price: {close_val}")
            if volume is not None and volume < 0:
                raise ValueError(f"Negative volume detected: {volume}")
                
            # OHLC consistency validation
            if low_val is not None and high_val is not None:
                if low_val > high_val:
                    raise ValueError(f"Consistency failure: low price ({low_val}) is higher than high price ({high_val}).")
                    
            if high_val is not None:
                if open_val is not None and open_val > high_val:
                    raise ValueError(f"Consistency failure: open price ({open_val}) exceeds high price ({high_val}).")
                if close_val is not None and close_val > high_val:
                    raise ValueError(f"Consistency failure: close price ({close_val}) exceeds high price ({high_val}).")
                    
            if low_val is not None:
                if open_val is not None and open_val < low_val:
                    raise ValueError(f"Consistency failure: open price ({open_val}) is lower than low price ({low_val}).")
                if close_val is not None and close_val < low_val:
                    raise ValueError(f"Consistency failure: close price ({close_val}) is lower than low price ({low_val}).")
            
            # Previous close & change calculation
            previous_close = None
            if "chartPreviousClose" in meta and meta["chartPreviousClose"] is not None:
                previous_close = Decimal(str(meta["chartPreviousClose"]))
                if previous_close <= 0:
                    raise ValueError(f"Invalid previous close price: {previous_close}")
                    
            change = None
            change_percent = None
            if previous_close is not None:
                change = Decimal(str(round(price - previous_close, 2)))
                change_percent = Decimal(str(round((change / previous_close) * 100, 2)))
                
            # 5. Timestamp validation
            market_time = meta.get("regularMarketTime")
            if not market_time:
                raise ValueError("Missing quote observation timestamp.")
                
            timestamp = datetime.fromtimestamp(market_time, tz=timezone.utc)
            
            # Future timestamp check (with 5 min clock skew tolerance)
            now_utc = datetime.now(timezone.utc)
            if timestamp > now_utc + timedelta(minutes=5):
                raise ValueError(f"Invalid future timestamp: {timestamp} (current system time: {now_utc})")
                
            # Stale data check (observations older than 7 days are considered stale/invalid)
            if timestamp < now_utc - timedelta(days=7):
                raise ValueError(f"Stale quote observation: timestamp {timestamp} is older than 7 days.")
                
            return MarketQuote(
                symbol=clean_symbol,
                exchange=exchange,
                price=price,
                open=open_val,
                high=high_val,
                low=low_val,
                close=close_val,
                volume=volume,
                previous_close=previous_close,
                change=change,
                change_percent=change_percent,
                timestamp=timestamp
            )
        except ValueError as ve:
            # Re-raise explicit validation errors
            raise ve
        except Exception as e:
            raise ValueError(f"Parsing/Normalization exception: {str(e)}")
