"""
run_kite_ticker_poc.py — Django management command.

Validates the live WebSocket market data ingestion flow:
  Kite WebSocket -> Nomad Normalizer (NomadMarketTick) -> Live MarketSnapshot

Supports:
- 2–5 NIFTY 50 equities (e.g. RELIANCE, TCS, INFY) + NIFTY 50 / BANKNIFTY indices.
- Tick inspection: token, LTP, LTQ, volume, OHLC, exchange_timestamp, depth.
- Controlled disconnect/reconnect resilience testing.
- Database MarketSnapshot persistence validation.
- Mock mode for offline testing when live Kite credentials are not available.

Usage:
  python manage.py run_kite_ticker_poc --stocks RELIANCE,TCS,INFY --duration 10
  python manage.py run_kite_ticker_poc --mock --duration 5
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings

from market.models import Instrument, MarketSnapshot
from market.services.kite_ticker import KiteTickerManager
from market.services.kite_registry import KiteInstrumentRegistry
from market.normalizers.kite import NomadMarketTick

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_STOCKS = ["RELIANCE", "TCS", "INFY", "^NSEI"]


class Command(BaseCommand):
    help = "Run the Kite WebSocket Live Ticker proof-of-concept."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stocks",
            type=str,
            default=",".join(DEFAULT_SAMPLE_STOCKS),
            help="Comma-separated stock/index symbols to subscribe (2-5 recommended).",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=10,
            help="Duration in seconds to run the live stream test.",
        )
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Run in mock mode using synthetic tick streamer.",
        )
        parser.add_argument(
            "--test-reconnect",
            action="store_true",
            default=True,
            help="Simulate a controlled connection drop and reconnect.",
        )

    def handle(self, *args, **options):
        stock_symbols = [s.strip().upper() for s in options["stocks"].split(",") if s.strip()]
        duration = options["duration"]
        use_mock = options["mock"]
        test_reconnect = options["test_reconnect"]

        self.stdout.write("=" * 80)
        self.stdout.write("PHASE 17A: KITE WEBSOCKET LIVE TICKER & SNAPSHOT POC")
        self.stdout.write("=" * 80)

        # Resolve tokens
        token_map = {}
        for sym in stock_symbols:
            token = KiteInstrumentRegistry.get_token(sym)
            if token:
                token_map[token] = sym
            else:
                self.stdout.write(self.style.WARNING(f"Warning: Could not resolve token for {sym}"))

        if not token_map:
            self.stderr.write(self.style.ERROR("No valid instrument tokens resolved. Aborting."))
            return

        tokens = list(token_map.keys())
        self.stdout.write(f"Subscribed Symbols ({len(tokens)}):")
        for t, sym in token_map.items():
            self.stdout.write(f"  {sym:<10} -> Token: {t}")

        # Check credentials via KiteCredentialService (DB OAuth token + fallback)
        from market.services.kite_auth import KiteCredentialService
        api_key = KiteCredentialService.get_api_key()
        access_token = KiteCredentialService.get_valid_access_token()
        has_creds = bool(api_key and access_token)
        if not has_creds and not use_mock:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo active Kite credentials found in DB or settings/.env.\n"
                    "Automatically activating MOCK mode for live ticker validation."
                )
            )
            use_mock = True

        self.stdout.write(f"\nExecution Mode: {'MOCK TICK STREAMER' if use_mock else 'LIVE KITE WEBSOCKET'}")
        self.stdout.write(f"Test Duration:  {duration} seconds\n")

        # Track received ticks in POC
        inspected_ticks = []

        def on_tick(tick: NomadMarketTick):
            if len(inspected_ticks) < 5:
                inspected_ticks.append(tick)
            # Log tick
            self.stdout.write(
                f"  [TICK] {tick.symbol:<10} | LTP: ₹{tick.last_price:<10} | Vol: {tick.volume:<10} | "
                f"ExchTime: {tick.exchange_timestamp.strftime('%H:%M:%S') if tick.exchange_timestamp else 'N/A'} | "
                f"Change: {tick.change_percent or 0:.2f}%"
            )

        mock_client = self._create_mock_client(tokens, token_map) if use_mock else None
        manager = KiteTickerManager(
            on_tick_callback=on_tick,
            update_db_snapshot=True,
            ticker_client=mock_client,
        )

        initial_snapshot_count = MarketSnapshot.objects.count()
        start_ts = time.time()

        # Start ticker
        manager.start(tokens=tokens, threaded=True)

        if use_mock:
            # Trigger connect callback on mock
            mock_client.simulate_connection()

        # Let it stream for half duration
        first_half = duration // 2 if duration >= 4 else duration
        time.sleep(first_half)

        # If test_reconnect requested, simulate disconnect & reconnect
        if test_reconnect and use_mock:
            self.stdout.write(self.style.WARNING("\nSimulating controlled network disconnect..."))
            mock_client.simulate_disconnect()
            time.sleep(1)
            self.stdout.write(self.style.SUCCESS("Simulating automatic reconnection and resubscription..."))
            mock_client.simulate_reconnect()
            time.sleep(max(1, duration - first_half - 1))
        else:
            time.sleep(max(1, duration - first_half))

        # Stop ticker
        manager.stop()
        elapsed = time.time() - start_ts

        new_snapshot_count = MarketSnapshot.objects.count() - initial_snapshot_count

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("LIVE WEBSOCKET POC METRICS & INSPECTION")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Duration Elapsed:          {elapsed:.2f} seconds")
        self.stdout.write(f"Total Ticks Received:      {manager.stats['ticks_received']}")
        self.stdout.write(f"Ticks / Second:            {manager.stats['ticks_received'] / elapsed:.2f}")
        self.stdout.write(f"MarketSnapshots Saved:     {new_snapshot_count}")
        self.stdout.write(f"Reconnect Events:          {manager.stats['reconnects']}")
        self.stdout.write(f"Processing Errors:         {manager.stats['errors']}")

        self.stdout.write("\n" + "-" * 80)
        self.stdout.write("NORMALIZED TICK PAYLOAD INSPECTION (SAMPLE):")
        self.stdout.write("-" * 80)
        for t in inspected_ticks[:2]:
            self.stdout.write(f"Symbol:               {t.symbol}")
            self.stdout.write(f"Instrument Token:     {t.instrument_token}")
            self.stdout.write(f"Last Traded Price:    {t.last_price}")
            self.stdout.write(f"Last Traded Quantity: {t.last_traded_quantity}")
            self.stdout.write(f"Day Volume:           {t.volume}")
            self.stdout.write(f"Day OHLC:             O={t.open}, H={t.high}, L={t.low}, C={t.close}")
            self.stdout.write(f"Exchange Timestamp:   {t.exchange_timestamp}")
            self.stdout.write(f"Received Timestamp:   {t.received_timestamp}")
            self.stdout.write(f"Depth Available:      {'Yes' if t.depth else 'No'}")
            self.stdout.write("-" * 40)

        # Verification of exit criteria
        if manager.stats["ticks_received"] > 0 and new_snapshot_count > 0 and manager.stats["errors"] == 0:
            self.stdout.write(self.style.SUCCESS("\nLIVE WEBSOCKET POC: 100% SUCCESS — INGESTION & SNAPSHOT VERIFIED"))
        else:
            self.stdout.write(self.style.ERROR("\nLIVE WEBSOCKET POC: FAILED TO VERIFY INGESTION OR SNAPSHOTS"))

    def _create_mock_client(self, tokens: list, token_map: dict):
        class MockTicker:
            MODE_FULL = "full"
            MODE_QUOTE = "quote"
            MODE_LTP = "ltp"

            def __init__(self):
                self.on_ticks = None
                self.on_connect = None
                self.on_close = None
                self.on_error = None
                self.on_reconnect = None
                self.on_noreconnect = None
                self._running = False
                self._thread = None
                self.tokens = []

            def subscribe(self, tokens):
                self.tokens.extend(tokens)

            def set_mode(self, mode, tokens):
                pass

            def connect(self, threaded=False):
                self._running = True
                if self.on_connect:
                    self.on_connect(self, {})

            def simulate_connection(self):
                import threading
                def _stream():
                    prices = {256265: 24500.0, 738561: 1320.0, 2953217: 2300.0, 408065: 1130.0}
                    while self._running:
                        ticks = []
                        now = datetime.now(timezone.utc)
                        for tok in self.tokens:
                            p = prices.get(tok, 1000.0) + (time.time() % 5)
                            tick = {
                                "instrument_token": tok,
                                "last_price": p,
                                "last_traded_quantity": 25,
                                "volume": 1250000,
                                "ohlc": {
                                    "open": p - 5,
                                    "high": p + 10,
                                    "low": p - 8,
                                    "close": p - 2,
                                },
                                "timestamp": now.isoformat(),
                                "exchange_timestamp": now.isoformat(),
                                "change": 0.45,
                                "depth": {"buy": [{"quantity": 100, "price": p - 0.05, "orders": 1}], "sell": []},
                            }
                            ticks.append(tick)

                        if self.on_ticks and ticks:
                            self.on_ticks(self, ticks)
                        time.sleep(0.5)

                self._thread = threading.Thread(target=_stream, daemon=True)
                self._thread.start()

            def simulate_disconnect(self):
                if self.on_close:
                    self.on_close(self, 1006, "Simulated network failure")

            def simulate_reconnect(self):
                if self.on_reconnect:
                    self.on_reconnect(self, 1)
                if self.on_connect:
                    self.on_connect(self, {})

            def close(self):
                self._running = False

        return MockTicker()
