import logging
import requests
from typing import Dict, Any
from market.providers.base import MarketDataProvider
from market.exceptions import (
    ProviderConnectionError,
    RateLimitExceededError,
    SymbolNotFoundError,
    InvalidPayloadError,
    AuthenticationError
)

logger = logging.getLogger(__name__)

class YFinanceMarketProvider(MarketDataProvider):
    """
    Yahoo Finance chart API provider implementing the MarketDataProvider Protocol.
    Fetches raw price, volume, and trade metric payloads deterministically.
    """
    
    def __init__(self):
        # Emulate standard browser headers to bypass blockages
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        upper_symbol = symbol.strip().upper()
        
        # Suffix handling: if symbol starts with ^, contains =, or has exchange suffix, use as-is
        if upper_symbol.startswith("^") or "=" in upper_symbol or upper_symbol.endswith(".NS") or upper_symbol.endswith(".BO"):
            yfinance_symbol = upper_symbol
        else:
            yfinance_symbol = f"{upper_symbol}.NS"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yfinance_symbol}?interval=1d&range=1d"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }

        logger.info(f"YFinanceProvider: requesting quote for symbol '{yfinance_symbol}' via url {url}")

        try:
            response = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.Timeout as t_err:
            logger.error(f"YFinanceProvider: connection timed out for {yfinance_symbol}: {t_err}")
            raise ProviderConnectionError(f"Connection timed out for symbol '{symbol}': {t_err}")
        except requests.exceptions.RequestException as r_err:
            logger.error(f"YFinanceProvider: HTTP request exception for {yfinance_symbol}: {r_err}")
            raise ProviderConnectionError(f"Provider connection error: {r_err}")

        # HTTP Status Checks
        if response.status_code == 401 or response.status_code == 403:
            raise AuthenticationError(f"Provider unauthorized (status {response.status_code}). Check cookie blocks.")
        elif response.status_code == 429:
            raise RateLimitExceededError("Yahoo Finance rate limits exceeded. Slow down requests.")
        elif response.status_code == 404:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found (HTTP 404).")
        elif response.status_code != 200:
            raise ProviderConnectionError(f"Provider returned HTTP status {response.status_code}.")

        # Parse JSON payload
        try:
            data = response.json()
        except ValueError as json_err:
            logger.error(f"YFinanceProvider: failed to parse JSON response for {yfinance_symbol}: {json_err}")
            raise InvalidPayloadError(f"Provider returned invalid JSON: {json_err}")

        # Check for inline Yahoo API error responses
        chart = data.get("chart", {})
        if chart.get("error") is not None:
            err = chart["error"]
            err_code = err.get("code")
            err_desc = err.get("description", "")
            
            if "unauthorized" in err_desc.lower() or "unauthorized" in err_code.lower():
                raise AuthenticationError(f"Provider API unauthorized: {err_desc}")
            elif "not found" in err_desc.lower() or "not found" in err_code.lower():
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found on Yahoo Finance.")
            else:
                raise InvalidPayloadError(f"Provider API error ({err_code}): {err_desc}")

        result_list = chart.get("result")
        if not result_list or result_list[0] is None:
            raise SymbolNotFoundError(f"Symbol '{symbol}' returned no results.")

        return data

    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        upper_symbol = symbol.strip().upper()
        
        # Suffix handling: if symbol starts with ^, contains =, or has exchange suffix, use as-is
        if upper_symbol.startswith("^") or "=" in upper_symbol or upper_symbol.endswith(".NS") or upper_symbol.endswith(".BO"):
            yfinance_symbol = upper_symbol
        else:
            yfinance_symbol = f"{upper_symbol}.NS"

        # Timeframe mapping
        timeframe_lookup = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "1d": "1d",
            "1w": "1wk",
            "1mo": "1mo"
        }
        interval = timeframe_lookup.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: '{timeframe}'")

        if start_date and end_date:
            period1 = int(start_date.timestamp())
            period2 = int(end_date.timestamp())
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yfinance_symbol}?interval={interval}&period1={period1}&period2={period2}"
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yfinance_symbol}?interval={interval}&range=1y"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }

        logger.info(f"YFinanceProvider: requesting historical chart data for symbol '{yfinance_symbol}' via url {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.Timeout as t_err:
            logger.error(f"YFinanceProvider: connection timed out for {yfinance_symbol}: {t_err}")
            raise ProviderConnectionError(f"Connection timed out for symbol '{symbol}': {t_err}")
        except requests.exceptions.RequestException as r_err:
            logger.error(f"YFinanceProvider: HTTP request exception for {yfinance_symbol}: {r_err}")
            raise ProviderConnectionError(f"Provider connection error: {r_err}")

        # HTTP Status Checks
        if response.status_code == 401 or response.status_code == 403:
            raise AuthenticationError(f"Provider unauthorized (status {response.status_code}). Check cookie blocks.")
        elif response.status_code == 429:
            raise RateLimitExceededError("Yahoo Finance rate limits exceeded. Slow down requests.")
        elif response.status_code == 404:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found (HTTP 404).")
        elif response.status_code != 200:
            raise ProviderConnectionError(f"Provider returned HTTP status {response.status_code}.")

        # Parse JSON payload
        try:
            data = response.json()
        except ValueError as json_err:
            logger.error(f"YFinanceProvider: failed to parse JSON response for {yfinance_symbol}: {json_err}")
            raise InvalidPayloadError(f"Provider returned invalid JSON: {json_err}")

        # Check inline error
        chart = data.get("chart", {})
        if chart.get("error") is not None:
            err = chart["error"]
            err_code = err.get("code")
            err_desc = err.get("description", "")
            
            if "unauthorized" in err_desc.lower() or "unauthorized" in err_code.lower():
                raise AuthenticationError(f"Provider API unauthorized: {err_desc}")
            elif "not found" in err_desc.lower() or "not found" in err_code.lower():
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found on Yahoo Finance.")
            else:
                raise InvalidPayloadError(f"Provider API error ({err_code}): {err_desc}")

        result_list = chart.get("result")
        if not result_list or result_list[0] is None:
            raise SymbolNotFoundError(f"Symbol '{symbol}' returned no results.")

        return data

