"""
run_intraday_ticker.py — Continuous Live Ticker & Market State Ingestion Daemon.

Streams real-time market data from Zerodha Kite WebSocket for all NIFTY 50 equities
and major indices into Redis and PostgreSQL:
  Kite WebSocket -> KiteTickerManager -> IntradayStateManager -> Redis / PostgreSQL

Usage:
  python manage.py run_intraday_ticker
  python manage.py run_intraday_ticker --duration 30
  python manage.py run_intraday_ticker --stocks INFY,TCS,RELIANCE
"""

import logging
import signal
import sys
import time
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.core.cache import cache

from market.models import Instrument
from market.services.kite_ticker import KiteTickerManager
from market.services.kite_registry import KiteInstrumentRegistry
from market.services.kite_auth import KiteCredentialService
from market.services.intraday_state_manager import IntradayStateManager
from market.normalizers.kite import NomadMarketTick

logger = logging.getLogger("nomad.intraday_ticker")


class Command(BaseCommand):
    help = "Run the continuous live market data ticker daemon for NIFTY 50."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stocks",
            type=str,
            default="",
            help="Comma-separated symbols to subscribe (defaults to all active NIFTY 50 + indices).",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=0,
            help="Duration in seconds to run (0 = run indefinitely until Ctrl+C).",
        )
        parser.add_argument(
            "--snapshot-interval",
            type=int,
            default=60,
            help="Interval in seconds to persist durable MarketContextSnapshot to DB (default: 60s).",
        )

    def handle(self, *args, **options):
        custom_stocks = options["stocks"]
        duration = options["duration"]
        snapshot_interval = options["snapshot_interval"]

        self.stdout.write("=" * 80)
        self.stdout.write("NOMAD ANALYST — LIVE INTRADAY TICKER & STATE DAEMON")
        self.stdout.write("=" * 80)

        # 1. Resolve Instrument Universe
        if custom_stocks:
            symbols = [s.strip().upper() for s in custom_stocks.split(",") if s.strip()]
        else:
            instruments = Instrument.objects.filter(
                universe_memberships__universe__name="NIFTY50",
                universe_memberships__is_active=True,
                is_active=True,
            )
            symbols = [inst.symbol for inst in instruments]
            # Add indices
            for idx_sym in ["^NSEI", "^NSEBANK", "^BSESN", "^CNXIT"]:
                if idx_sym not in symbols:
                    symbols.append(idx_sym)

        self.stdout.write(f"Universe resolved: {len(symbols)} instruments")

        token_map = {}
        for sym in symbols:
            token = KiteInstrumentRegistry.get_token(sym)
            if token:
                token_map[token] = sym
            else:
                self.stdout.write(self.style.WARNING(f"  Warning: No token found for {sym}"))

        if not token_map:
            self.stderr.write(self.style.ERROR("Error: No instrument tokens resolved. Aborting."))
            return

        tokens = list(token_map.keys())
        self.stdout.write(f"Subscribing to {len(tokens)} tokens on Zerodha Kite WebSocket.")

        # 2. Check Credentials
        api_key = KiteCredentialService.get_api_key()
        access_token = KiteCredentialService.get_valid_access_token()
        if not api_key or not access_token:
            self.stderr.write(
                self.style.ERROR(
                    "Error: Missing or expired Zerodha Kite session. Please authenticate via /api/v1/kite/login/."
                )
            )
            return

        # 3. Initialize State Manager & Ticker
        state_mgr = IntradayStateManager()
        tick_count = 0
        last_snapshot_time = time.time()
        start_time = time.time()
        running = True

        def on_tick(tick: NomadMarketTick):
            nonlocal tick_count
            tick_count += 1

        manager = KiteTickerManager(
            api_key=api_key,
            access_token=access_token,
            on_tick_callback=on_tick,
            update_db_snapshot=True,
        )

        # Graceful shutdown handler
        def shutdown_handler(signum, frame):
            nonlocal running
            self.stdout.write(self.style.WARNING("\nShutdown signal received. Stopping live ticker..."))
            running = False

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # 4. Start Ticker
        self.stdout.write(self.style.SUCCESS("Connecting to Kite WebSocket (wss://ws.kite.trade)..."))
        manager.start(tokens=tokens, threaded=True)

        self.stdout.write(self.style.SUCCESS("Live ticker streaming active. Press Ctrl+C to stop.\n"))

        # 5. Coordination Loop
        last_status_time = time.time()
        try:
            while running:
                now = time.time()
                # Check duration limit if set
                if duration > 0 and (now - start_time) >= duration:
                    self.stdout.write(self.style.SUCCESS(f"\nDuration limit ({duration}s) reached."))
                    break

                # Periodic DB snapshot
                if (now - last_snapshot_time) >= snapshot_interval:
                    last_snapshot_time = now
                    try:
                        snapshot = state_mgr.persist_snapshots()
                        if snapshot:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  [SNAPSHOT] Persisted MarketContextSnapshot @ {snapshot.as_of.strftime('%H:%M:%S')} "
                                    f"| Direction: {snapshot.market_direction} | Regime: {snapshot.market_regime}"
                                )
                            )
                    except Exception as ex:
                        logger.error(f"Error persisting snapshot: {ex}")

                # Status update every 10 seconds
                if (now - last_status_time) >= 10.0:
                    last_status_time = now
                    freshness = state_mgr.get_freshness_status()
                    self.stdout.write(
                        f"  [HEARTBEAT] Ticks Received: {tick_count:<6} | "
                        f"Feed: {freshness['freshness']} ({freshness['age_seconds']}s ago) | "
                        f"Snapshots: {manager.stats['snapshots_updated']}"
                    )

                time.sleep(1.0)

        finally:
            self.stdout.write("Shutting down KiteTickerManager...")
            manager.stop()
            elapsed = time.time() - start_time
            self.stdout.write("=" * 80)
            self.stdout.write(f"SESSION SUMMARY: Elapsed: {elapsed:.1f}s | Total Ticks: {tick_count}")
            self.stdout.write("=" * 80)
