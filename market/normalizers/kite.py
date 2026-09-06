"""
Kite Market Data Normalizer.

Transforms Zerodha Kite Connect responses (REST quotes, historical candles, and live WebSocket ticks)
into canonical Nomad internal representations (MarketQuote, NomadMarketTick, OHLCVBar dicts).

All timestamps are converted to timezone-aware Asia/Kolkata (IST).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from market.normalizers.base import BaseNormalizer
from market.providers.base import MarketQuote
from market.services.kite_registry import KiteInstrumentRegistry
from market.services.trading_session import TradingSessionService, IST_TIMEZONE
from market.exceptions import InvalidPayloadError

logger = logging.getLogger(__name__)


class NomadMarketTick(BaseModel):
    """
    Provider-agnostic live market tick representation for Nomad.
    """
    instrument_token: int = Field(..., description="Unique provider instrument identifier")
    symbol: str = Field(..., description="Nomad ticker symbol (e.g. RELIANCE, ^NSEI)")
    exchange: str = Field(default="NSE", description="Exchange (e.g. NSE, BSE)")
    last_price: Decimal = Field(..., description="Last traded price")
    last_traded_quantity: Optional[int] = Field(default=None, description="Quantity of the last trade")
    volume: Optional[int] = Field(default=None, description="Cumulative day volume")
    open: Optional[Decimal] = Field(default=None, description="Day open price")
    high: Optional[Decimal] = Field(default=None, description="Day high price")
    low: Optional[Decimal] = Field(default=None, description="Day low price")
    close: Optional[Decimal] = Field(default=None, description="Previous day closing price")
    change: Optional[Decimal] = Field(default=None, description="Absolute change from previous close")
    change_percent: Optional[Decimal] = Field(default=None, description="Percentage change")
    average_price: Optional[Decimal] = Field(default=None, description="Average traded price (session VWAP) from exchange")
    exchange_timestamp: Optional[datetime] = Field(default=None, description="Timestamp from the exchange in IST")
    received_timestamp: datetime = Field(..., description="Timestamp when tick was received by Nomad")
    is_suspicious_timestamp: bool = Field(default=False, description="Flagged True if exchange timestamp is outside regular market trading hours")
    depth: Optional[Dict[str, Any]] = Field(default=None, description="Bid/Ask order book ladder if available")

    class Config:
        populate_by_name = True


class KiteNormalizer(BaseNormalizer):
    """
    Normalizes Zerodha Kite Connect payloads into Nomad models.
    """

    def normalize(self, raw_data: Dict[str, Any]) -> MarketQuote:
        """
        Normalizes a Kite REST quote payload into a MarketQuote.
        Expected format from KiteConnect:
        {
            "NSE:RELIANCE": {
                "instrument_token": 738561,
                "timestamp": "2026-09-04 15:30:00",
                "last_price": 2950.5,
                "volume": 2500000,
                "ohlc": {"open": 2940.0, "high": 2965.0, "low": 2930.0, "close": 2935.0},
                ...
            }
        }
        """
        if not raw_data:
            raise InvalidPayloadError("Empty Kite quote payload received.")

        # If keyed by instrument (e.g. 'NSE:RELIANCE'), extract inner quote
        if len(raw_data) == 1 and any(":" in k for k in raw_data.keys()):
            key = list(raw_data.keys())[0]
            quote = raw_data[key]
            symbol = key.split(":")[-1]
            exchange = key.split(":")[0]
        else:
            quote = raw_data
            symbol = quote.get("tradingsymbol", "UNKNOWN")
            exchange = quote.get("exchange", "NSE")

        last_price = quote.get("last_price")
        if last_price is None or float(last_price) <= 0:
            raise InvalidPayloadError(f"Invalid last_price for {symbol}: {last_price}")

        price = Decimal(str(last_price))
        ohlc = quote.get("ohlc", {})

        open_price = Decimal(str(ohlc["open"])) if ohlc.get("open") is not None else None
        high = Decimal(str(ohlc["high"])) if ohlc.get("high") is not None else None
        low = Decimal(str(ohlc["low"])) if ohlc.get("low") is not None else None
        prev_close = Decimal(str(ohlc["close"])) if ohlc.get("close") is not None else None

        volume = quote.get("volume")
        if volume is not None:
            volume = int(volume)

        # Compute change and change_percent if prev_close available
        change = None
        change_pct = None
        if prev_close and prev_close > 0:
            change = price - prev_close
            change_pct = (change / prev_close) * Decimal("100.0")

        # Timestamp conversion to IST
        raw_ts = quote.get("timestamp")
        if isinstance(raw_ts, datetime):
            ts = TradingSessionService.to_ist(raw_ts)
        elif isinstance(raw_ts, str):
            try:
                parsed_dt = datetime.fromisoformat(raw_ts)
                ts = TradingSessionService.to_ist(parsed_dt)
            except Exception:
                ts = TradingSessionService.to_ist()
        else:
            ts = TradingSessionService.to_ist()

        return MarketQuote(
            symbol=symbol,
            exchange=exchange,
            price=price,
            open=open_price,
            high=high,
            low=low,
            close=price,
            volume=volume,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            timestamp=ts,
        )

    @staticmethod
    def normalize_candle(raw_candle: List[Any], symbol: str, timeframe: str = "1d") -> Dict[str, Any]:
        """
        Normalizes a Kite historical candle item:
        Format: [timestamp, open, high, low, close, volume, (oi)]
        
        Validates OHLC constraints:
        - high >= max(open, close)
        - low <= min(open, close)
        - volume >= 0
        """
        if len(raw_candle) < 6:
            raise InvalidPayloadError(f"Malformed candle for {symbol}: length {len(raw_candle)} < 6")

        raw_ts, open_val, high_val, low_val, close_val, vol = raw_candle[:6]

        # Timestamp normalization to IST
        if isinstance(raw_ts, datetime):
            ts = TradingSessionService.to_ist(raw_ts)
        elif isinstance(raw_ts, str):
            try:
                # Kite returns formats like '2026-09-04T09:15:00+0530' or '2026-09-04 09:15:00'
                ts = TradingSessionService.to_ist(datetime.fromisoformat(raw_ts))
            except Exception:
                ts = TradingSessionService.to_ist(datetime.strptime(raw_ts[:19], "%Y-%m-%d %H:%M:%S"))
        else:
            raise InvalidPayloadError(f"Invalid candle timestamp type: {type(raw_ts)}")

        open_dec = Decimal(str(open_val))
        high_dec = Decimal(str(high_val))
        low_dec = Decimal(str(low_val))
        close_dec = Decimal(str(close_val))
        vol_int = int(vol)

        # Integrity validations
        if open_dec <= 0 or high_dec <= 0 or low_dec <= 0 or close_dec <= 0:
            raise InvalidPayloadError(f"Non-positive price in candle for {symbol} at {ts}")

        if high_dec < max(open_dec, close_dec):
            raise InvalidPayloadError(
                f"Candle integrity failure for {symbol} at {ts}: high ({high_dec}) < max(open, close) ({max(open_dec, close_dec)})"
            )

        if low_dec > min(open_dec, close_dec):
            raise InvalidPayloadError(
                f"Candle integrity failure for {symbol} at {ts}: low ({low_dec}) > min(open, close) ({min(open_dec, close_dec)})"
            )

        if vol_int < 0:
            raise InvalidPayloadError(f"Negative volume ({vol_int}) in candle for {symbol} at {ts}")

        return {
            "timestamp": ts,
            "open": open_dec,
            "high": high_dec,
            "low": low_dec,
            "close": close_dec,
            "volume": vol_int,
            "timeframe": timeframe,
            "source": "Kite",
        }

    @classmethod
    def normalize_tick(cls, raw_tick: Dict[str, Any], received_at: Optional[datetime] = None) -> NomadMarketTick:
        """
        Normalizes a raw WebSocket tick dict from KiteTicker into a NomadMarketTick.
        Handles both LTP, Quote, and Full packet modes.
        """
        if not raw_tick or "instrument_token" not in raw_tick:
            raise InvalidPayloadError("Malformed WebSocket tick: missing instrument_token.")

        token = int(raw_tick["instrument_token"])
        symbol = KiteInstrumentRegistry.get_symbol(token) or f"TOKEN_{token}"

        last_price_val = raw_tick.get("last_price")
        if last_price_val is None or float(last_price_val) <= 0:
            raise InvalidPayloadError(f"Non-positive or missing last_price in tick for token {token}: {last_price_val}")

        last_price = Decimal(str(last_price_val))
        volume = int(raw_tick.get("volume_traded", raw_tick.get("volume", 0)) or 0)
        last_traded_qty = raw_tick.get("last_traded_quantity")
        if last_traded_qty is not None:
            last_traded_qty = int(last_traded_qty)

        # OHLC sub-dict
        ohlc = raw_tick.get("ohlc", {})
        open_val = Decimal(str(ohlc["open"])) if ohlc.get("open") is not None else None
        high_val = Decimal(str(ohlc["high"])) if ohlc.get("high") is not None else None
        low_val = Decimal(str(ohlc["low"])) if ohlc.get("low") is not None else None
        prev_close = Decimal(str(ohlc["close"])) if ohlc.get("close") is not None else None

        change = None
        change_pct = None
        if raw_tick.get("change") is not None:
            change_pct = Decimal(str(raw_tick["change"]))
            if prev_close:
                change = (change_pct * prev_close) / Decimal("100.0")
        elif prev_close and prev_close > 0:
            change = last_price - prev_close
            change_pct = (change / prev_close) * Decimal("100.0")

        # Exchange timestamp
        ex_ts = raw_tick.get("exchange_timestamp") or raw_tick.get("timestamp")
        exchange_timestamp = None
        if isinstance(ex_ts, datetime):
            exchange_timestamp = TradingSessionService.to_ist(ex_ts)
        elif isinstance(ex_ts, str):
            try:
                exchange_timestamp = TradingSessionService.to_ist(datetime.fromisoformat(ex_ts))
            except Exception:
                exchange_timestamp = None

        received_timestamp = TradingSessionService.to_ist(received_at)

        # Check timestamp plausibility (NSE equity market hours 09:00 - 16:05 IST)
        is_suspicious = False
        if exchange_timestamp is not None:
            if not TradingSessionService.is_plausible_exchange_timestamp(exchange_timestamp):
                is_suspicious = True
                logger.warning(
                    f"Suspicious exchange timestamp detected for {symbol} ({token}): {exchange_timestamp} IST (outside market hours)."
                )

        # Average price / ATP / Session VWAP from exchange
        atp_val = raw_tick.get("average_price") or raw_tick.get("average_traded_price") or raw_tick.get("atp")
        average_price = None
        if atp_val is not None and float(atp_val) > 0:
            average_price = Decimal(str(atp_val))

        # Order depth if present
        depth = raw_tick.get("depth")

        return NomadMarketTick(
            instrument_token=token,
            symbol=symbol,
            exchange="NSE",
            last_price=last_price,
            last_traded_quantity=last_traded_qty,
            volume=volume,
            open=open_val,
            high=high_val,
            low=low_val,
            close=prev_close,
            change=change,
            change_percent=change_pct,
            average_price=average_price,
            exchange_timestamp=exchange_timestamp,
            received_timestamp=received_timestamp,
            is_suspicious_timestamp=is_suspicious,
            depth=depth,
        )
