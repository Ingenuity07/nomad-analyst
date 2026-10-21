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
        parser.add_argument(
            "--enable-fno",
            action="store_true",
            default=False,
            help="Enable real-time F&O option ingestion alongside equity streaming.",
        )

    def handle(self, *args, **options):
        # Explicit unbuffered / line-buffered execution for reliable real-time log timestamps
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(line_buffering=True)
            except Exception:
                pass

        custom_stocks = options["stocks"]
        duration = options["duration"]
        snapshot_interval = options["snapshot_interval"]
        enable_fno = options.get("enable_fno", False)

        self.stdout.write("=" * 80)
        self.stdout.write("NOMAD ANALYST — LIVE INTRADAY TICKER & STATE DAEMON")
        self.stdout.write("=" * 80)
        self.stdout.flush()

        # 0. Acquire Process-level advisory lock to prevent duplicate ticker daemons
        import fcntl
        import os

        lock_file_path = "/tmp/nomad_intraday_ticker.pid"
        try:
            # Open without truncation so existing lock PID is preserved if another daemon holds it
            lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)
            lock_file = open(lock_fd, "r+", closefd=True)
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Only truncate and write PID AFTER exclusive lock is safely acquired
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except (BlockingIOError, IOError):
            try:
                if "lock_file" in locals() and not lock_file.closed:
                    lock_file.close()
            except Exception:
                pass
            self.stderr.write(
                self.style.ERROR(
                    f"Error: Another run_intraday_ticker daemon is already running (locked via {lock_file_path}). "
                    "Aborting startup to prevent duplicate WebSocket connections and duplicate ticker processes."
                )
            )
            return

        try:
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

            fno_consumer = None
            if enable_fno:
                from fno.services.fno_ticker_consumer import FnoTickerConsumer
                try:
                    fno_consumer = FnoTickerConsumer()
                    self.stdout.write(
                        self.style.SUCCESS(
                            "F&O option ingestion enabled (--enable-fno). Initialized FnoTickerConsumer."
                        )
                    )
                except Exception as ex:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Failed to initialize FnoTickerConsumer: {ex}. Proceeding equity-only."
                        )
                    )

            def on_tick(tick: NomadMarketTick):
                nonlocal tick_count
                tick_count += 1

            manager = KiteTickerManager(
                api_key=api_key,
                access_token=access_token,
                on_tick_callback=on_tick,
                update_db_snapshot=True,
                fno_consumer=fno_consumer,
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

            # 5. Coordination Loop with Outer Reconnection Watchdog
            last_status_time = time.time()
            last_reconnect_attempt = time.time()
            reconnect_attempts = 0
            initial_backoff = 2.0
            max_backoff = 60.0
            current_backoff = initial_backoff

            try:
                while running:
                    now = time.time()

                    # Watchdog: Safe, bounded exponential backoff reconnection if disconnected
                    if not manager.is_connected and not manager._stop_requested:
                        if (now - last_reconnect_attempt) >= current_backoff:
                            last_reconnect_attempt = now
                            reconnect_attempts += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  [WATCHDOG] Connection inactive. Attempting reconnect #{reconnect_attempts} "
                                    f"(backoff: {current_backoff:.1f}s)..."
                                )
                            )
                            self.stdout.flush()
                            manager.reconnect()
                            # Allow brief grace period for connection callback
                            for _ in range(10):
                                if manager.is_connected:
                                    break
                                time.sleep(0.2)

                            if manager.is_connected:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"  [WATCHDOG] Reconnected successfully on attempt #{reconnect_attempts}. "
                                        f"Restored {len(manager.subscribed_tokens)} instrument subscriptions."
                                    )
                                )
                                self.stdout.flush()
                                reconnect_attempts = 0
                                current_backoff = initial_backoff
                            else:
                                current_backoff = min(current_backoff * 2.0, max_backoff)
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"  [WATCHDOG] Reconnection #{reconnect_attempts} pending. "
                                        f"Next attempt in {current_backoff:.1f}s."
                                    )
                                )
                                self.stdout.flush()

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
                                self.stdout.flush()
                        except Exception as ex:
                            logger.error(f"Error persisting snapshot: {ex}")

                        if fno_consumer:
                            try:
                                flushed = fno_consumer.flush_completed_bars()
                                if flushed > 0:
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"  [FNO] Flushed {flushed} completed option bar(s) to DB."
                                        )
                                    )
                                    self.stdout.flush()
                            except Exception as ex:
                                logger.error(f"Error flushing F&O completed bars: {ex}")

                    # Status update every 10 seconds
                    if (now - last_status_time) >= 10.0:
                        last_status_time = now
                        freshness = state_mgr.get_freshness_status()
                        fno_info = ""
                        if fno_consumer:
                            fno_ticks = fno_consumer.stats.get("ticks_received", 0)
                            fno_active = len(fno_consumer.active_tokens)
                            fno_bars = fno_consumer.stats.get("bars_created", 0)
                            fno_evals = fno_consumer.stats.get("strategy_evaluations", 0)
                            fno_trades = fno_consumer.stats.get("paper_trades_executed", 0)
                            fno_info = f" | F&O Ticks: {fno_ticks:<5} | F&O Active: {fno_active} | F&O Bars: {fno_bars} | Evals: {fno_evals} | Trades: {fno_trades}"
                        self.stdout.write(
                            f"  [HEARTBEAT] Ticks Received: {tick_count:<6} | "
                            f"Feed: {freshness['freshness']} ({freshness['age_seconds']}s ago) | "
                            f"Snapshots: {manager.stats['snapshots_updated']}{fno_info}"
                        )
                        self.stdout.flush()

                    time.sleep(1.0)

            finally:
                self.stdout.write("Shutting down KiteTickerManager...")
                manager.stop()
                if fno_consumer:
                    try:
                        if hasattr(fno_consumer, "force_close_and_flush_all"):
                            flushed = fno_consumer.force_close_and_flush_all()
                        else:
                            flushed = fno_consumer.flush_completed_bars()
                        if flushed > 0:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Flushed {flushed} remaining F&O option bars on shutdown."
                                )
                            )
                    except Exception as ex:
                        logger.error(f"Error flushing F&O bars on shutdown: {ex}")
                elapsed = time.time() - start_time
                fno_summary = ""
                if fno_consumer:
                    fno_summary = (
                        f" | F&O Ticks: {fno_consumer.stats.get('ticks_received', 0)}"
                        f" | F&O Bars: {fno_consumer.stats.get('bars_created', 0)}"
                        f" | F&O Quotes: {fno_consumer.stats.get('quotes_recorded', 0)}"
                        f" | F&O Evals: {fno_consumer.stats.get('strategy_evaluations', 0)}"
                        f" | Paper Trades: {fno_consumer.stats.get('paper_trades_executed', 0)}"
                    )
                self.stdout.write("=" * 80)
                self.stdout.write(
                    f"SESSION SUMMARY: Elapsed: {elapsed:.1f}s | Equity Ticks: {tick_count}{fno_summary}"
                )
                self.stdout.write("=" * 80)

        finally:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
                if os.path.exists(lock_file_path):
                    os.remove(lock_file_path)
            except Exception:
                pass
