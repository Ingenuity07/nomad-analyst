"""
fno/tests/test_fno_ticker_integration.py — Integration Tests for Isolated NFO Ticker Ingestion and Celery Retention.

Verifies:
1. KiteTickerManager routes NFO tokens strictly to FnoTickerConsumer (zero pollution of IntradayStateManager).
2. Underlying NIFTY spot updates dynamically rebalance the F&O active contract set.
3. FnoTickerConsumer normalizes ticks, updates bar aggregator, and records quote snapshots.
4. Celery retention task purge_expired_option_quotes executes idempotently.
"""

import tempfile
from datetime import datetime, time, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase

from fno.models import OptionOHLCVBar, OptionQuoteSnapshot
from fno.services.desired_universe import DesiredUniverseManager, UnderlyingAssetConfig
from fno.services.fno_ticker_consumer import FnoTickerConsumer
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionNormalizer
from fno.services.option_quote_manager import OptionQuoteManager
from fno.services.option_registry import OptionInstrumentRegistry
from fno.tasks import purge_expired_option_quotes
from market.services.kite_ticker import KiteTickerManager


CSV_HEADER = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"


def generate_test_csv() -> str:
    rows = []
    token = 2000000
    for exp_str in ("2026-10-15", "2026-10-22"):
        for strike in range(24000, 25050, 50):
            for opt_type in ("CE", "PE"):
                sym = f"NIFTY26O{strike}{opt_type}_{exp_str}"
                rows.append(
                    f"{token},{token},{sym},\"NIFTY\",0,{exp_str},{strike},0.05,25,{opt_type},NFO-OPT,NFO\n"
                )
                token += 1
    return CSV_HEADER + "".join(rows)


class TestFnoTickerIntegration(TestCase):
    """Integration suite verifying isolated NFO streaming and retention."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_file = Path(self.temp_dir.name) / "instruments.csv"
        self.csv_file.write_text(generate_test_csv(), encoding="utf-8")

        self.registry = OptionInstrumentRegistry(master_path=self.csv_file)
        self.registry.load_master()

        self.config = UnderlyingAssetConfig(
            underlying_symbol="^NSEI",
            underlying_name="NIFTY 50",
            master_name="NIFTY",
            strike_step=Decimal("50.0"),
            strike_window_k=5,
            rebalance_threshold_pts=Decimal("50.0"),
            next_weekly_staging_policy_time=time(13, 0),
        )

        self.universe_mgr = DesiredUniverseManager(self.registry, self.config)
        self.normalizer = OptionNormalizer()
        self.bar_aggregator = OptionBarAggregator()
        self.quote_mgr = OptionQuoteManager()

        self.fno_consumer = FnoTickerConsumer(
            registry=self.registry,
            universe_manager=self.universe_mgr,
            normalizer=self.normalizer,
            bar_aggregator=self.bar_aggregator,
            quote_manager=self.quote_mgr,
            config=self.config,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_on_connect_subscribes_desired_tokens(self):
        """on_connect must subscribe the initial 22 desired tokens in MODE_FULL."""
        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"

        # Initial spot at 24500
        self.fno_consumer.latest_underlying_spot = Decimal("24500.00")
        subscribed = self.fno_consumer.on_connect(mock_ws)

        self.assertEqual(len(subscribed), 22)
        mock_ws.subscribe.assert_called_once()
        mock_ws.set_mode.assert_called_once_with("full", list(subscribed))
        self.assertEqual(len(self.fno_consumer.active_tokens), 22)

    def test_spot_update_triggers_dynamic_rebalance(self):
        """Spot update crossing ATM boundary must rebalance and issue ws subscribe/unsubscribe calls."""
        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"

        # Initialize at 24524 (ATM = 24500)
        spot_1 = Decimal("24524.00")
        self.fno_consumer.latest_underlying_spot = spot_1
        self.fno_consumer.on_connect(mock_ws)
        mock_ws.reset_mock()

        # Spot crosses boundary to 24526 (ATM = 24550)
        spot_2 = Decimal("24526.00")
        to_sub, to_unsub = self.fno_consumer.on_underlying_spot_update(spot_2, ws=mock_ws)

        self.assertEqual(len(to_sub), 2)
        self.assertEqual(len(to_unsub), 2)
        mock_ws.subscribe.assert_called_once_with(list(to_sub))
        mock_ws.set_mode.assert_called_once_with("full", list(to_sub))
        mock_ws.unsubscribe.assert_called_once_with(list(to_unsub))

    def test_fno_tick_isolation_in_kite_ticker_manager(self):
        """KiteTickerManager must route NFO ticks to fno_consumer and NOT to IntradayStateManager."""
        ticker_mgr = KiteTickerManager(
            api_key="mock_key",
            access_token="mock_token",
            update_db_snapshot=False,
            fno_consumer=self.fno_consumer,
        )

        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"
        self.fno_consumer.latest_underlying_spot = Decimal("24500.00")
        self.fno_consumer.on_connect(mock_ws)

        active_fno_token = list(self.fno_consumer.active_tokens)[0]

        now = datetime.now(timezone.utc)
        fno_raw_tick = {
            "instrument_token": active_fno_token,
            "last_price": 142.50,
            "volume_traded": 1000,
            "oi": 50000,
            "timestamp": now,
            "depth": {
                "buy": [{"quantity": 100, "price": 142.0, "orders": 1}],
                "sell": [{"quantity": 100, "price": 143.0, "orders": 1}],
            }
        }

        with patch("market.services.intraday_state_manager.IntradayStateManager.on_tick") as mock_equity_on_tick:
            ticker_mgr._on_ticks(mock_ws, [fno_raw_tick])

            # IntradayStateManager MUST NOT receive the F&O tick!
            mock_equity_on_tick.assert_not_called()

        # FnoTickerConsumer must have processed the tick
        self.assertEqual(self.fno_consumer.stats["ticks_received"], 1)
        self.assertEqual(self.fno_consumer.stats["quotes_recorded"], 1)

        # Quote snapshot must be persisted in fno_optionquotesnapshot table
        snapshots = OptionQuoteSnapshot.objects.filter(instrument_token=active_fno_token)
        self.assertEqual(snapshots.count(), 1)
        snap = snapshots.first()
        self.assertEqual(snap.best_bid, Decimal("142.00"))
        self.assertEqual(snap.best_ask, Decimal("143.00"))
        self.assertEqual(snap.quote_status, "VALID")
        self.assertTrue(snap.is_execution_eligible)

    def test_celery_purge_expired_option_quotes_task(self):
        """purge_expired_option_quotes Celery task purges old records idempotently."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=10)

        # Create an expired quote snapshot
        OptionQuoteSnapshot.objects.create(
            instrument_token=2000001,
            tradingsymbol="NIFTY26O24500CE",
            received_wall_clock_utc=old_time,
            exchange_timestamp_utc=old_time,
            exchange_time_status="VALID",
            best_bid=Decimal("100.0"),
            best_ask=Decimal("101.0"),
            quote_status="VALID",
            is_execution_eligible=True,
        )
        # Create a fresh quote snapshot
        OptionQuoteSnapshot.objects.create(
            instrument_token=2000001,
            tradingsymbol="NIFTY26O24500CE",
            received_wall_clock_utc=now,
            exchange_timestamp_utc=now,
            exchange_time_status="VALID",
            best_bid=Decimal("105.0"),
            best_ask=Decimal("106.0"),
            quote_status="VALID",
            is_execution_eligible=True,
        )

        self.assertEqual(OptionQuoteSnapshot.objects.count(), 2)

        # Run task directly
        res = purge_expired_option_quotes.apply(kwargs={"days": 5})
        self.assertEqual(res.result["status"], "SUCCESS")
        self.assertEqual(res.result["deleted_count"], 1)

        # Only fresh snapshot remains
        self.assertEqual(OptionQuoteSnapshot.objects.count(), 1)
        self.assertEqual(OptionQuoteSnapshot.objects.first().best_bid, Decimal("105.0"))

    def test_fno_def_01_cli_arguments_and_wiring(self):
        """FNO-DEF-01: --enable-fno CLI flag must be parsed and wire FnoTickerConsumer."""
        from market.management.commands.run_intraday_ticker import Command as TickerCommand

        cmd = TickerCommand()
        parser = cmd.create_parser("manage.py", "run_intraday_ticker")

        # 1. Default without flag: enable_fno is False
        opts_default = parser.parse_args([])
        self.assertFalse(opts_default.enable_fno)

        # 2. Explicit opt-in: enable_fno is True
        opts_fno = parser.parse_args(["--enable-fno"])
        self.assertTrue(opts_fno.enable_fno)

        # 3. Verify handle() wiring with --enable-fno
        with patch("fcntl.flock"), patch("os.open", return_value=999), patch("builtins.open"), \
             patch("os.path.exists", return_value=False), \
             patch("market.services.kite_auth.KiteCredentialService.get_api_key", return_value="test_key"), \
             patch("market.services.kite_auth.KiteCredentialService.get_valid_access_token", return_value="test_token"), \
             patch("market.services.kite_registry.KiteInstrumentRegistry.get_token", return_value=256265), \
             patch("market.models.Instrument.objects.filter") as mock_inst_filter, \
             patch("market.management.commands.run_intraday_ticker.KiteTickerManager") as mock_mgr_cls, \
             patch("fno.services.fno_ticker_consumer.FnoTickerConsumer") as mock_consumer_cls:

            mock_inst = MagicMock(symbol="^NSEI")
            mock_inst_filter.return_value = [mock_inst]
            mock_mgr = MagicMock()
            mock_mgr.is_connected = True
            mock_mgr.stats = {"snapshots_updated": 0}
            mock_mgr_cls.return_value = mock_mgr

            # Run with --enable-fno and duration=1
            cmd.handle(stocks="^NSEI", duration=1, snapshot_interval=60, enable_fno=True)
            mock_consumer_cls.assert_called_once()
            mock_mgr_cls.assert_called_once()
            _, kwargs = mock_mgr_cls.call_args
            self.assertEqual(kwargs.get("fno_consumer"), mock_consumer_cls.return_value)

            # Reset and run without --enable-fno
            mock_consumer_cls.reset_mock()
            mock_mgr_cls.reset_mock()
            cmd.handle(stocks="^NSEI", duration=1, snapshot_interval=60, enable_fno=False)
            mock_consumer_cls.assert_not_called()
            mock_mgr_cls.assert_called_once()
            _, kwargs = mock_mgr_cls.call_args
            self.assertIsNone(kwargs.get("fno_consumer"))

    def test_fno_def_02_consumer_flush_completed_bars_signatures(self):
        """FNO-DEF-02: flush_completed_bars() must accept optional as_of_datetime without TypeError."""
        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"
        self.fno_consumer.latest_underlying_spot = Decimal("24500.00")
        self.fno_consumer.on_connect(mock_ws)
        active_fno_token = list(self.fno_consumer.active_tokens)[0]

        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # Ingest tick 1 for minute base_time
        t1_time = base_time + timedelta(seconds=10)
        raw_tick_1 = {
            "instrument_token": active_fno_token,
            "last_price": 150.0,
            "volume_traded": 100,
            "oi": 10000,
            "timestamp": t1_time,
            "depth": {"buy": [], "sell": []},
        }
        self.fno_consumer.on_tick(raw_tick_1, ws=mock_ws, received_wall_clock_utc=t1_time)

        # Ingest tick 1b in same minute with increased volume
        t1b_time = base_time + timedelta(seconds=30)
        raw_tick_1b = {
            "instrument_token": active_fno_token,
            "last_price": 152.0,
            "volume_traded": 200,
            "oi": 10200,
            "timestamp": t1b_time,
            "depth": {"buy": [], "sell": []},
        }
        self.fno_consumer.on_tick(raw_tick_1b, ws=mock_ws, received_wall_clock_utc=t1b_time)

        # Ingest tick for next minute (closes base_time bar)
        t2_time = base_time + timedelta(minutes=1, seconds=15)
        raw_tick_2 = {
            "instrument_token": active_fno_token,
            "last_price": 155.0,
            "volume_traded": 250,
            "oi": 10500,
            "timestamp": t2_time,
            "depth": {"buy": [], "sell": []},
        }
        self.fno_consumer.on_tick(raw_tick_2, ws=mock_ws, received_wall_clock_utc=t2_time)

        # Ingest tick 2b in same minute with increased volume
        t2b_time = base_time + timedelta(minutes=1, seconds=45)
        raw_tick_2b = {
            "instrument_token": active_fno_token,
            "last_price": 156.0,
            "volume_traded": 400,
            "oi": 10600,
            "timestamp": t2b_time,
            "depth": {"buy": [], "sell": []},
        }
        self.fno_consumer.on_tick(raw_tick_2b, ws=mock_ws, received_wall_clock_utc=t2b_time)

        # 1. Call flush_completed_bars() with no arguments (standard periodic flush)
        written_count = self.fno_consumer.flush_completed_bars()
        self.assertEqual(written_count, 1)
        self.assertEqual(self.fno_consumer.stats["bars_created"], 1)

        persisted_bar = OptionOHLCVBar.objects.get(
            instrument_token=active_fno_token,
            timestamp=base_time,
        )
        self.assertEqual(persisted_bar.open, Decimal("150.0"))
        self.assertEqual(persisted_bar.high, Decimal("152.0"))
        self.assertEqual(persisted_bar.volume, 100)  # 200 - 100

        # 2. Call flush_completed_bars() with as_of_datetime parameter
        cutoff_dt = base_time + timedelta(minutes=2)
        # In-flight (base_time + 1 min) bar has timestamp < cutoff_dt, so it rolls over and flushes
        written_count_2 = self.fno_consumer.flush_completed_bars(as_of_datetime=cutoff_dt)
        self.assertEqual(written_count_2, 1)
        self.assertEqual(self.fno_consumer.stats["bars_created"], 2)

        persisted_bar_2 = OptionOHLCVBar.objects.get(
            instrument_token=active_fno_token,
            timestamp=base_time + timedelta(minutes=1),
        )
        self.assertEqual(persisted_bar_2.open, Decimal("155.0"))
        self.assertEqual(persisted_bar_2.high, Decimal("156.0"))
        self.assertEqual(persisted_bar_2.volume, 150)  # 400 - 250

    def test_fno_def_03_disconnect_reconnect_marks_partial_bars(self):
        """FNO-DEF-03: Active option bars spanning disconnect/reconnect must be marked partial."""
        mock_ws = MagicMock()
        mock_ws.MODE_FULL = "full"

        ticker_mgr = KiteTickerManager(
            api_key="mock_key",
            access_token="mock_token",
            update_db_snapshot=False,
            fno_consumer=self.fno_consumer,
        )
        self.fno_consumer.latest_underlying_spot = Decimal("24500.00")
        self.fno_consumer.on_connect(mock_ws)
        active_fno_token = list(self.fno_consumer.active_tokens)[0]

        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # 1. Ingest tick into bar at base_time + 10s
        t1_time = base_time + timedelta(seconds=10)
        t1 = {
            "instrument_token": active_fno_token,
            "last_price": 100.0,
            "volume_traded": 100,
            "oi": 5000,
            "timestamp": t1_time,
            "depth": {"buy": [], "sell": []},
        }
        with patch("market.services.kite_ticker.datetime") as mock_dt:
            mock_dt.now.return_value = t1_time
            mock_dt.fromtimestamp = datetime.fromtimestamp
            ticker_mgr._on_ticks(mock_ws, [t1])

        active_bar = self.fno_consumer.bar_aggregator._active_bars[active_fno_token]
        self.assertFalse(active_bar.is_partial_bar)

        # 2. Simulate WebSocket disconnect event
        ticker_mgr._on_close(mock_ws, code=1006, reason="Connection abruptly closed")

        # Active bar must now be flagged as partial
        self.assertTrue(active_bar.is_partial_bar)

        # 3. Simulate reconnect attempt and successful reconnect
        ticker_mgr._on_reconnect(mock_ws, attempts_count=1)
        self.assertTrue(active_bar.is_partial_bar)

        ticker_mgr._on_connect(mock_ws, response=None)
        self.assertTrue(active_bar.is_partial_bar)

        # 4. Ingest next minute tick (closes the base_time bar)
        t2_time = base_time + timedelta(minutes=1, seconds=10)
        t2 = {
            "instrument_token": active_fno_token,
            "last_price": 102.0,
            "volume_traded": 200,
            "oi": 5100,
            "timestamp": t2_time,
            "depth": {"buy": [], "sell": []},
        }
        with patch("market.services.kite_ticker.datetime") as mock_dt:
            mock_dt.now.return_value = t2_time
            mock_dt.fromtimestamp = datetime.fromtimestamp
            ticker_mgr._on_ticks(mock_ws, [t2])

        # 5. Flush completed bars and verify database row
        self.fno_consumer.flush_completed_bars()

        db_bar_1 = OptionOHLCVBar.objects.get(
            instrument_token=active_fno_token,
            timestamp=base_time,
        )
        self.assertTrue(db_bar_1.is_partial_bar, "Bar affected by connection gap must have is_partial_bar=True")

        # 6. Verify that the subsequent bar (not affected by disconnect) completes as complete
        t3_time = base_time + timedelta(minutes=2, seconds=10)
        t3 = {
            "instrument_token": active_fno_token,
            "last_price": 104.0,
            "volume_traded": 300,
            "oi": 5200,
            "timestamp": t3_time,
            "depth": {"buy": [], "sell": []},
        }
        with patch("market.services.kite_ticker.datetime") as mock_dt:
            mock_dt.now.return_value = t3_time
            mock_dt.fromtimestamp = datetime.fromtimestamp
            ticker_mgr._on_ticks(mock_ws, [t3])
        self.fno_consumer.flush_completed_bars()

        db_bar_2 = OptionOHLCVBar.objects.get(
            instrument_token=active_fno_token,
            timestamp=base_time + timedelta(minutes=1),
        )
        self.assertFalse(db_bar_2.is_partial_bar, "Bar unaffected by disconnect must have is_partial_bar=False")
