"""
Zerodha Kite Ticker Client and Live Market Data Stream Manager.

Manages Kite WebSocket connection lifecycle:
- Outbound connection to Zerodha wss://ws.kite.trade
- Authentication and session handling
- Dynamic token subscriptions (Full, Quote, LTP modes)
- Automatic reconnection and exponential backoff
- Tick normalization (raw tick -> NomadMarketTick)
- Live MarketSnapshot updates in database/cache
- Resilient disconnect and graceful shutdown
"""

import logging
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Callable, Optional, Dict, Any
from django.conf import settings
from django.db import transaction

from market.models import Instrument, MarketSnapshot
from market.normalizers.kite import KiteNormalizer, NomadMarketTick
from market.services.kite_registry import KiteInstrumentRegistry
from market.services.trading_session import TradingSessionService
from market.exceptions import AuthenticationError, ProviderConnectionError

logger = logging.getLogger(__name__)


class KiteTickerManager:
    """
    Manages the KiteTicker WebSocket client for streaming market data.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        on_tick_callback: Optional[Callable[[NomadMarketTick], None]] = None,
        update_db_snapshot: bool = True,
        ticker_client: Optional[Any] = None,
        fno_consumer: Optional[Any] = None,
    ):
        from market.services.kite_auth import KiteCredentialService
        self.api_key = api_key or KiteCredentialService.get_api_key()
        self.access_token = access_token or KiteCredentialService.get_valid_access_token()
        self.on_tick_callback = on_tick_callback
        self.update_db_snapshot = update_db_snapshot
        self.fno_consumer = fno_consumer

        self.kws = ticker_client
        self.is_connected = False
        self.reconnect_count = 0
        self.subscribed_tokens: List[int] = []
        self._stop_requested = False
        self._worker_thread: Optional[threading.Thread] = None
        self._connect_lock = threading.Lock()

        # Statistics
        self.stats = {
            "ticks_received": 0,
            "snapshots_updated": 0,
            "errors": 0,
            "reconnects": 0,
            "start_time": None,
        }

    def _init_kws(self):
        if self.kws is None:
            from market.services.kite_auth import KiteCredentialService
            api_key = self.api_key or KiteCredentialService.get_api_key()
            access_token = self.access_token or KiteCredentialService.get_valid_access_token()

            if not api_key or not access_token:
                raise AuthenticationError("Kite credentials missing or session expired for WebSocket ticker.")

            from kiteconnect import KiteTicker
            self.kws = KiteTicker(api_key, access_token)

        # Wire callbacks
        self.kws.on_ticks = self._on_ticks
        self.kws.on_connect = self._on_connect
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error
        self.kws.on_reconnect = self._on_reconnect
        self.kws.on_noreconnect = self._on_noreconnect

    def _on_connect(self, ws, response):
        logger.info("KiteTicker: WebSocket connected successfully.")
        self.is_connected = True
        if self.subscribed_tokens:
            logger.info(f"KiteTicker: Resubscribing to {len(self.subscribed_tokens)} tokens...")
            ws.subscribe(self.subscribed_tokens)
            ws.set_mode(ws.MODE_FULL, self.subscribed_tokens)
        if self.fno_consumer:
            try:
                self.fno_consumer.on_connect(ws)
            except Exception as e:
                logger.error(f"KiteTicker: Error in fno_consumer.on_connect: {e}", exc_info=True)

    def _on_ticks(self, ws, ticks: List[Dict[str, Any]]):
        received_at = datetime.now(timezone.utc)
        from django.core.cache import cache

        for raw_tick in ticks:
            # 0. Route F&O derivative contracts strictly to isolated FnoTickerConsumer
            token = raw_tick.get("instrument_token") if isinstance(raw_tick, dict) else None
            if self.fno_consumer and token and self.fno_consumer.is_fno_token(token):
                try:
                    self.fno_consumer.on_tick(raw_tick, ws=ws, received_wall_clock_utc=received_at)
                except Exception as ex:
                    logger.error(f"KiteTicker: Error in fno_consumer.on_tick for token {token}: {ex}", exc_info=True)
                continue

            try:
                self.stats["ticks_received"] += 1
                norm_tick = KiteNormalizer.normalize_tick(raw_tick, received_at=received_at)

                # Update F&O consumer underlying spot price if benchmark index ticks
                if self.fno_consumer and norm_tick.symbol in ("^NSEI", "NIFTY 50", "NIFTY"):
                    try:
                        self.fno_consumer.on_underlying_spot_update(
                            norm_tick.last_price,
                            ws=ws,
                            as_of_datetime=norm_tick.exchange_timestamp or received_at
                        )
                    except Exception as ex:
                        logger.debug(f"KiteTicker: Updating FNO underlying spot failed: {ex}")

                # 1. Update in-memory / Redis cache live state
                cache_payload = {
                    "symbol": norm_tick.symbol,
                    "last_price": float(norm_tick.last_price),
                    "volume": norm_tick.volume,
                    "open": float(norm_tick.open) if norm_tick.open else None,
                    "high": float(norm_tick.high) if norm_tick.high else None,
                    "low": float(norm_tick.low) if norm_tick.low else None,
                    "close": float(norm_tick.close) if norm_tick.close else None,
                    "change": float(norm_tick.change) if norm_tick.change else None,
                    "change_percent": float(norm_tick.change_percent) if norm_tick.change_percent else None,
                    "exchange_timestamp": norm_tick.exchange_timestamp.isoformat() if norm_tick.exchange_timestamp else None,
                    "received_timestamp": norm_tick.received_timestamp.isoformat(),
                    "is_suspicious": norm_tick.is_suspicious_timestamp,
                }
                cache.set(f"live_tick:{norm_tick.symbol}", cache_payload, timeout=3600)
                cache.set("kite_last_tick", cache_payload, timeout=3600)

                # 2. Update durable database snapshot if enabled
                if self.update_db_snapshot:
                    self.update_market_snapshot(norm_tick)

                # 3. Process via IntradayStateManager (bar aggregation, breadth, regime, channels)
                try:
                    from market.services.intraday_state_manager import IntradayStateManager
                    IntradayStateManager().on_tick(norm_tick)
                except Exception as ex:
                    logger.debug(f"IntradayStateManager processing tick failed: {ex}")

                if self.on_tick_callback:
                    self.on_tick_callback(norm_tick)

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error processing Kite tick: {e}", exc_info=True)

    def _on_close(self, ws, code, reason):
        logger.warning(f"KiteTicker: Connection closed (code: {code}, reason: {reason})")
        self.is_connected = False
        if self.fno_consumer:
            if hasattr(self.fno_consumer, "on_disconnect"):
                try:
                    self.fno_consumer.on_disconnect(code=code, reason=reason)
                except Exception as ex:
                    logger.debug(f"KiteTicker: notifying fno_consumer of disconnect failed: {ex}")
            elif hasattr(self.fno_consumer, "bar_aggregator") and hasattr(self.fno_consumer.bar_aggregator, "mark_partial_bars"):
                try:
                    self.fno_consumer.bar_aggregator.mark_partial_bars()
                except Exception as ex:
                    logger.debug(f"KiteTicker: marking partial bars on disconnect failed: {ex}")

    def _on_error(self, ws, code, reason):
        if self._stop_requested:
            logger.debug(f"KiteTicker: Connection closing during shutdown (code: {code})")
            return
        logger.error(f"KiteTicker: Error encountered (code: {code}, reason: {reason})")
        self.stats["errors"] += 1

    def _on_reconnect(self, ws, attempts_count):
        logger.info(f"KiteTicker: Reconnecting attempt {attempts_count}...")
        self.reconnect_count += 1
        self.stats["reconnects"] += 1
        if self.fno_consumer:
            if hasattr(self.fno_consumer, "on_reconnect"):
                try:
                    self.fno_consumer.on_reconnect(attempts_count=attempts_count)
                except Exception as ex:
                    logger.debug(f"KiteTicker: notifying fno_consumer of reconnect failed: {ex}")
            elif hasattr(self.fno_consumer, "on_disconnect"):
                try:
                    self.fno_consumer.on_disconnect(code=None, reason=f"Reconnecting attempt {attempts_count}")
                except Exception as ex:
                    logger.debug(f"KiteTicker: notifying fno_consumer of reconnect failed: {ex}")
            elif hasattr(self.fno_consumer, "bar_aggregator") and hasattr(self.fno_consumer.bar_aggregator, "mark_partial_bars"):
                try:
                    self.fno_consumer.bar_aggregator.mark_partial_bars()
                except Exception as ex:
                    logger.debug(f"KiteTicker: marking partial bars on reconnect failed: {ex}")

    def _on_noreconnect(self, ws):
        logger.error("KiteTicker: Maximum reconnection attempts exhausted.")
        self.is_connected = False
        if self.fno_consumer:
            if hasattr(self.fno_consumer, "on_disconnect"):
                try:
                    self.fno_consumer.on_disconnect(code=None, reason="Max reconnection attempts exhausted")
                except Exception as ex:
                    logger.debug(f"KiteTicker: notifying fno_consumer of disconnect failed: {ex}")
            elif hasattr(self.fno_consumer, "bar_aggregator") and hasattr(self.fno_consumer.bar_aggregator, "mark_partial_bars"):
                try:
                    self.fno_consumer.bar_aggregator.mark_partial_bars()
                except Exception as ex:
                    logger.debug(f"KiteTicker: marking partial bars failed: {ex}")

    def subscribe(self, tokens: List[int], mode: str = "full"):
        """
        Subscribes to list of instrument tokens.
        """
        for t in tokens:
            if t not in self.subscribed_tokens:
                self.subscribed_tokens.append(t)

        if self.is_connected and self.kws:
            self.kws.subscribe(tokens)
            if hasattr(self.kws, f"MODE_{mode.upper()}"):
                mode_val = getattr(self.kws, f"MODE_{mode.upper()}")
                self.kws.set_mode(mode_val, tokens)
            logger.info(f"KiteTicker: Subscribed to {len(tokens)} tokens in {mode} mode.")

    def start(self, tokens: Optional[List[int]] = None, threaded: bool = True):
        """
        Starts the KiteTicker connection.
        """
        self._stop_requested = False
        self.stats["start_time"] = datetime.now(timezone.utc)
        if tokens:
            self.subscribe(tokens)

        self._init_kws()

        if threaded:
            if hasattr(self.kws, "connect"):
                # KiteTicker.connect(threaded=True) suppresses Twisted signal handlers
                # and runs reactor on its own daemon background thread safely on Python 3.14.
                self.kws.connect(threaded=True)
                logger.info("KiteTicker connected in background threaded mode.")
            else:
                self._worker_thread = threading.Thread(target=self._run, daemon=True)
                self._worker_thread.start()
                logger.info("KiteTicker worker thread started.")
        else:
            self._run()

    def _run(self):
        try:
            self.kws.connect(threaded=False)
        except Exception as e:
            logger.error(f"KiteTicker connect failed: {e}")
            self.is_connected = False

    def reconnect(self) -> bool:
        """
        Safely reconnects the WebSocket client.
        Guards against duplicate connections. Preserves subscribed tokens.
        """
        with self._connect_lock:
            if self.is_connected:
                logger.info("KiteTickerManager: Already connected. Reconnect skipped.")
                return True

            logger.info("KiteTickerManager: Initiating safe reconnection...")
            if self.fno_consumer:
                if hasattr(self.fno_consumer, "on_disconnect"):
                    try:
                        self.fno_consumer.on_disconnect(code=None, reason="Reconnection initiated by manager")
                    except Exception as ex:
                        logger.debug(f"KiteTicker: notifying fno_consumer of reconnect failed: {ex}")
                elif hasattr(self.fno_consumer, "bar_aggregator") and hasattr(self.fno_consumer.bar_aggregator, "mark_partial_bars"):
                    try:
                        self.fno_consumer.bar_aggregator.mark_partial_bars()
                    except Exception as ex:
                        logger.debug(f"KiteTicker: marking partial bars on reconnect failed: {ex}")

            if self.kws:
                try:
                    self.kws.close()
                except Exception as ex:
                    logger.debug(f"Error closing existing kws: {ex}")
                self.kws = None

            try:
                tokens_to_restore = list(self.subscribed_tokens)
                self._init_kws()
                if hasattr(self.kws, "connect"):
                    self.kws.connect(threaded=True)
                elif self._worker_thread is None or not self._worker_thread.is_alive():
                    self._worker_thread = threading.Thread(target=self._run, daemon=True)
                    self._worker_thread.start()

                logger.info(
                    f"KiteTickerManager: Reconnect initiated with {len(tokens_to_restore)} tokens preserved."
                )
                return True
            except Exception as e:
                logger.error(f"KiteTickerManager: Reconnection attempt failed: {e}")
                self.is_connected = False
                return False

    def stop(self):
        """
        Gracefully closes the WebSocket connection and terminates worker thread.
        """
        logger.info("KiteTicker: Graceful shutdown initiated.")
        self._stop_requested = True
        with self._connect_lock:
            if self.kws and hasattr(self.kws, "close"):
                try:
                    self.kws.close()
                except Exception as e:
                    logger.warning(f"Error during KiteTicker close: {e}")

            self.is_connected = False
            if hasattr(self.kws, "websocket_thread") and self.kws.websocket_thread and self.kws.websocket_thread.is_alive():
                self.kws.websocket_thread.join(timeout=3.0)
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=3.0)
            logger.info("KiteTicker: Shutdown complete.")

    def update_market_snapshot(self, tick: NomadMarketTick):
        """
        Updates or creates a MarketSnapshot in the database from a normalized tick.
        """
        # Resolve instrument in DB
        inst = Instrument.objects.filter(symbol=tick.symbol).first()
        if not inst:
            # Check if index
            inst = Instrument.objects.filter(symbol=tick.symbol).first()
            if not inst:
                return

        # Record snapshot
        ts = tick.exchange_timestamp or tick.received_timestamp

        MarketSnapshot.objects.create(
            instrument=inst,
            timestamp=ts,
            open=tick.open,
            high=tick.high,
            low=tick.low,
            close=tick.last_price,
            volume=tick.volume,
            previous_close=tick.close,
            change=tick.change,
            change_percent=tick.change_percent,
            source="KiteTicker",
            source_timestamp=tick.exchange_timestamp,
        )
        self.stats["snapshots_updated"] += 1
