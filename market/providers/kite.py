"""
Zerodha Kite Connect Market Data Provider.

Implements the MarketDataProvider protocol:
- get_quote(symbol) -> dict
- get_historical_ohlcv(symbol, timeframe, start_date, end_date) -> dict

Translates Kite exceptions into canonical Nomad MarketDataError hierarchy.
Supports offline mock fixture injection for deterministic testing without credentials.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from django.conf import settings

from market.providers.base import MarketDataProvider
from market.services.kite_registry import KiteInstrumentRegistry
from market.services.trading_session import TradingSessionService
from market.exceptions import (
    ProviderConnectionError,
    RateLimitExceededError,
    SymbolNotFoundError,
    InvalidPayloadError,
    AuthenticationError,
)

logger = logging.getLogger(__name__)

# Kite Connect interval mapping
TIMEFRAME_MAP = {
    "1m": "minute",
    "minute": "minute",
    "3m": "3minute",
    "5m": "5minute",
    "5minute": "5minute",
    "10m": "10minute",
    "15m": "15minute",
    "15minute": "15minute",
    "30m": "30minute",
    "30minute": "30minute",
    "60m": "60minute",
    "1h": "60minute",
    "60minute": "60minute",
    "1d": "day",
    "day": "day",
}


class KiteMarketDataProvider(MarketDataProvider):
    """
    Market data provider backed by Zerodha Kite Connect.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        kite_client: Optional[Any] = None,
    ):
        self.api_key = api_key
        self.access_token = access_token
        self._client = kite_client

    def _get_client(self):
        """
        Initializes or returns KiteConnect client instance.
        Automatically resolves credentials via KiteCredentialService if not injected.
        """
        if self._client is not None:
            return self._client

        from market.services.kite_auth import KiteCredentialService

        api_key = self.api_key if self.api_key is not None else KiteCredentialService.get_api_key()
        access_token = self.access_token if self.access_token is not None else KiteCredentialService.get_valid_access_token()

        if not api_key or not access_token:
            raise AuthenticationError(
                "Kite credentials missing or session expired. Complete daily 2FA authentication."
            )

        try:
            from kiteconnect import KiteConnect
            client = KiteConnect(api_key=api_key)
            client.set_access_token(access_token)
            self._client = client
            return self._client
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect client: {e}")
            raise AuthenticationError(f"Failed to initialize KiteConnect client: {e}")

    def _resolve_kite_symbol(self, symbol: str) -> str:
        """
        Converts Nomad symbol to Kite exchange:tradingsymbol query format.
        e.g. 'RELIANCE' -> 'NSE:RELIANCE', '^NSEI' -> 'NSE:NIFTY 50'
        """
        upper_sym = symbol.strip().upper()
        if upper_sym in ("^NSEI", "NIFTY", "NIFTY50", "NIFTY 50"):
            return "NSE:NIFTY 50"
        if upper_sym in ("^NSEBANK", "BANKNIFTY", "NIFTY BANK"):
            return "NSE:NIFTY BANK"
        if upper_sym == "TATAMOTORS":
            return "NSE:TMPV"

        if ":" in upper_sym:
            return upper_sym
        return f"NSE:{upper_sym}"

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches the raw quote data for the symbol from Kite Connect.
        Returns a raw dictionary response.
        """
        kite_symbol = self._resolve_kite_symbol(symbol)
        client = self._get_client()

        logger.info(f"KiteProvider: requesting quote for symbol '{kite_symbol}'")
        try:
            raw_response = client.quote([kite_symbol])
            if not raw_response or kite_symbol not in raw_response:
                raise SymbolNotFoundError(f"Symbol '{symbol}' ({kite_symbol}) not found on Kite.")
            return raw_response
        except SymbolNotFoundError:
            raise
        except Exception as err:
            self._translate_exception(err, context=f"get_quote for {symbol}")

    def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetches historical OHLCV data for the symbol from Kite Connect.
        Returns a raw dictionary response containing candles and metadata.
        """
        token = KiteInstrumentRegistry.get_token(symbol)
        if not token:
            raise SymbolNotFoundError(f"Could not resolve Kite instrument token for symbol '{symbol}'.")

        interval = TIMEFRAME_MAP.get(timeframe)
        if not interval:
            raise InvalidPayloadError(f"Unsupported timeframe '{timeframe}'. Supported: {list(TIMEFRAME_MAP.keys())}")

        now_ist = TradingSessionService.to_ist()
        if end_date is None:
            end_date = now_ist
        else:
            end_date = TradingSessionService.to_ist(end_date)

        if start_date is None:
            if interval == "day":
                start_date = end_date - timedelta(days=365)
            elif "minute" in interval:
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=60)
        else:
            start_date = TradingSessionService.to_ist(start_date)

        client = self._get_client()
        logger.info(
            f"KiteProvider: fetching historical data for token {token} ({symbol}) "
            f"interval={interval}, from={start_date.date()}, to={end_date.date()}"
        )

        try:
            # Kite API expects instrument_token, from_date, to_date, interval
            candles = client.historical_data(
                instrument_token=token,
                from_date=start_date,
                to_date=end_date,
                interval=interval,
                continuous=False,
                oi=False,
            )
            return {
                "symbol": symbol,
                "instrument_token": token,
                "timeframe": timeframe,
                "interval": interval,
                "candles": candles,
                "source": "Kite",
            }
        except Exception as err:
            self._translate_exception(err, context=f"historical_data for {symbol} ({token})")

    def _translate_exception(self, err: Exception, context: str = ""):
        """
        Translates Kite exceptions into Nomad's standard MarketDataError hierarchy.
        """
        err_msg = str(err).lower()
        err_type = type(err).__name__

        logger.error(f"KiteProvider error ({err_type}) during {context}: {err}")

        # kiteconnect exception classes or text matching
        if "token" in err_msg or "unauthorized" in err_msg or "permission" in err_msg or "403" in err_msg or "401" in err_msg:
            raise AuthenticationError(f"Kite authentication failed: {err}")
        elif "rate" in err_msg or "429" in err_msg or "too many requests" in err_msg:
            raise RateLimitExceededError(f"Kite rate limit exceeded: {err}")
        elif "not found" in err_msg or "404" in err_msg or "invalid instrument" in err_msg:
            raise SymbolNotFoundError(f"Symbol/Instrument not found on Kite: {err}")
        elif "network" in err_msg or "timeout" in err_msg or "connection" in err_msg:
            raise ProviderConnectionError(f"Kite connection error: {err}")
        else:
            raise InvalidPayloadError(f"Kite provider error: {err}")
