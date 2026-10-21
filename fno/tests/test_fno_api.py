"""
Nomad Analyst — F&O API Endpoints Tests
Tests for Phase FNO-1 & FNO-1A DRF endpoints:
- GET /api/v1/fno/overview/
- GET /api/v1/fno/strategy/
- GET /api/v1/fno/trades/
- GET /api/v1/fno/diagnostics/
"""

from decimal import Decimal
from datetime import datetime, date, time
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from fno.models import OptionQuoteSnapshot, OptionOHLCVBar, PaperTradeLedger
from market.models import Company, Instrument, MarketSnapshot, MarketContextSnapshot

IST = ZoneInfo("Asia/Kolkata")


class FnoAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("fno.views.check_ticker_daemon_running", return_value=(False, None))
    def test_overview_endpoint_daemon_stopped(self, mock_ticker):
        """Test GET /api/v1/fno/overview/ returns DISCONNECTED when daemon is stopped."""
        response = self.client.get("/api/v1/fno/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("underlying", data)
        self.assertIn("feed", data)
        self.assertIn("quotes", data)
        self.assertEqual(data["feed"]["status"], "DISCONNECTED")
        self.assertFalse(data["feed"]["ticker_running"])
        self.assertEqual(len(data["quotes"]), 0)

    @patch("fno.views.check_ticker_daemon_running", return_value=(True, 41325))
    @patch("fno.views.is_nse_market_open", return_value=False)
    def test_overview_endpoint_market_closed(self, mock_market, mock_ticker):
        """Test GET /api/v1/fno/overview/ returns STANDBY_MARKET_CLOSED when market is closed."""
        response = self.client.get("/api/v1/fno/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["feed"]["status"], "STANDBY_MARKET_CLOSED")
        self.assertEqual(data["feed"]["market_session"], "CLOSED")
        self.assertTrue(data["feed"]["ticker_running"])

    @patch("fno.views.check_ticker_daemon_running", return_value=(True, 41325))
    @patch("fno.views.is_nse_market_open", return_value=True)
    def test_overview_endpoint_with_data_and_active_feed(self, mock_market, mock_ticker):
        """Test overview endpoint with spot instrument, ATM calculation, and active feed."""
        co = Company.objects.create(name="Nifty 50 Index", sector="Indices")
        inst = Instrument.objects.create(
            company=co,
            symbol="^NSEI",
            exchange="NSE",
            instrument_type="INDEX",
            lot_size=25,
        )
        now = timezone.now()
        # Test mathematical midpoint rounding: 24525.00 with step 50 rounds to 24550.00 under ROUND_HALF_UP
        MarketSnapshot.objects.create(
            instrument=inst,
            timestamp=now,
            open=Decimal("24500.00"),
            high=Decimal("24550.00"),
            low=Decimal("24480.00"),
            close=Decimal("24525.00"),
            volume=1000000,
        )

        OptionQuoteSnapshot.objects.create(
            instrument_token=123456,
            tradingsymbol="NIFTY26O2124500CE",
            exchange_timestamp_utc=now,
            received_wall_clock_utc=now,
            exchange_time_status="VALID",
            best_bid=Decimal("120.00"),
            best_ask=Decimal("120.50"),
            bid_quantity_l1=150,
            ask_quantity_l1=225,
            quote_status="VALID",
            is_stale=False,
            is_locked=False,
            is_crossed=False,
            is_execution_eligible=True,
        )

        response = self.client.get("/api/v1/fno/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["underlying"]["spot_price"], 24525.0)
        self.assertEqual(data["underlying"]["atm_strike"], 24550)
        self.assertEqual(data["feed"]["status"], "ACTIVE")
        self.assertEqual(data["feed"]["market_session"], "OPEN")
        self.assertGreater(len(data["quotes"]), 0)
        quote = data["quotes"][0]
        self.assertEqual(quote["spread_abs"], "0.50")

    def test_quote_spread_none_when_bid_or_ask_missing(self):
        """Test serializer returns null (None) rather than '0.00' when bid or ask is missing."""
        now = timezone.now()
        snap = OptionQuoteSnapshot.objects.create(
            instrument_token=987654,
            tradingsymbol="NIFTY26O2125000PE",
            exchange_timestamp_utc=now,
            received_wall_clock_utc=now,
            exchange_time_status="VALID",
            best_bid=None,
            best_ask=Decimal("15.00"),
            quote_status="ZERO_BID",
        )
        from fno.serializers import OptionQuoteSnapshotSerializer
        serialized = OptionQuoteSnapshotSerializer(snap).data
        self.assertIsNone(serialized["spread_abs"])
        self.assertIsNone(serialized["spread_pct"])

    def test_strategy_endpoint_without_runtime_telemetry(self):
        """Test GET /api/v1/fno/strategy/ when no runtime telemetry is in cache."""
        response = self.client.get("/api/v1/fno/strategy/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("strategy", data)
        self.assertEqual(data["strategy"]["strategy_id"], "STRAT-ORB-15M")
        self.assertEqual(data["strategy"]["status"], "UNAVAILABLE")
        self.assertFalse(data["strategy"]["runtime_telemetry_available"])
        self.assertEqual(data["opening_range"]["status"], "UNAVAILABLE")
        self.assertIsNone(data["opening_range"]["range_high"])
        self.assertIsNone(data["audit_trail"]["evaluations_count"])

    def test_strategy_endpoint_with_runtime_telemetry(self):
        """Test GET /api/v1/fno/strategy/ with authoritative cached runtime health."""
        now_ist = timezone.now().astimezone(IST)
        session_date = now_ist.date()
        cache_key = f"fno_strategy_health:{session_date}:STRAT-ORB-15M"
        cache.set(cache_key, {
            "strategy_id": "STRAT-ORB-15M",
            "strategy_version": "1.0.0",
            "session_date": str(session_date),
            "is_registered": True,
            "is_enabled": True,
            "opening_range_established": True,
            "opening_range_high": 24650.50,
            "opening_range_low": 24510.25,
            "evaluations_count": 350,
            "eligible_evaluations": 350,
            "signals_count": 2,
            "trades_count": 1,
            "rejections_count": 5,
            "rejection_breakdown": {"REJECTED_STALE_QUOTE": 5},
            "last_evaluation_time": now_ist.isoformat(),
        }, timeout=3600)

        response = self.client.get("/api/v1/fno/strategy/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["strategy"]["runtime_telemetry_available"])
        self.assertEqual(data["strategy"]["status"], "ACTIVE")
        self.assertEqual(data["opening_range"]["status"], "LOCKED")
        self.assertEqual(data["opening_range"]["range_high"], 24650.50)
        self.assertEqual(data["opening_range"]["range_low"], 24510.25)
        self.assertEqual(data["opening_range"]["range_width"], 140.25)
        self.assertEqual(data["audit_trail"]["evaluations_count"], 350)
        self.assertEqual(data["audit_trail"]["signals_count"], 2)
        self.assertEqual(data["audit_trail"]["rejection_summary"], {"REJECTED_STALE_QUOTE": 5})

    def test_trades_endpoint_empty_ledger(self):
        """Test GET /api/v1/fno/trades/ clearly distinguishes empty ledger."""
        response = self.client.get("/api/v1/fno/trades/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["summary"]["ledger_status"], "EMPTY")
        self.assertEqual(data["summary"]["total_trades"], 0)
        self.assertEqual(data["summary"]["open_positions_count"], 0)
        self.assertEqual(len(data["open_positions"]), 0)

    def test_trades_endpoint_populated(self):
        """Test GET /api/v1/fno/trades/ with active and closed trades."""
        now = timezone.now()
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id="11111111-1111-1111-1111-111111111111",
            instrument_token=999999,
            tradingsymbol="NIFTY26O2124500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 21),
            entry_timestamp=now,
            entry_fill_price=Decimal("150.00"),
            entry_slippage=Decimal("0.25"),
            quantity=25,
            status="OPEN",
        )
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id="22222222-2222-2222-2222-222222222222",
            instrument_token=999999,
            tradingsymbol="NIFTY26O2124500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 21),
            entry_timestamp=now,
            exit_timestamp=now,
            entry_fill_price=Decimal("150.00"),
            entry_slippage=Decimal("0.25"),
            exit_fill_price=Decimal("165.00"),
            exit_slippage=Decimal("0.25"),
            gross_pnl=Decimal("375.00"),
            total_frictions=Decimal("18.50"),
            net_pnl=Decimal("356.50"),
            quantity=25,
            status="CLOSED",
        )

        response = self.client.get("/api/v1/fno/trades/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["summary"]["ledger_status"], "POPULATED")
        self.assertEqual(data["summary"]["open_positions_count"], 1)
        self.assertEqual(data["summary"]["total_trades"], 1)
        self.assertEqual(data["summary"]["gross_pnl"], "375.00")
        self.assertEqual(data["summary"]["net_pnl"], "356.50")
        self.assertEqual(data["summary"]["total_frictions"], "18.50")

    def test_diagnostics_endpoint_filters_1m_bars(self):
        """Test GET /api/v1/fno/diagnostics/ filters strictly 1m timeframe bars."""
        now = timezone.now()
        OptionOHLCVBar.objects.create(
            instrument_token=111,
            tradingsymbol="OPT_111",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=now.date(),
            timeframe="1m",
            timestamp=now,
            open=Decimal("10"),
            high=Decimal("12"),
            low=Decimal("9"),
            close=Decimal("11"),
            is_partial_bar=False,
        )
        OptionOHLCVBar.objects.create(
            instrument_token=111,
            tradingsymbol="OPT_111",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=now.date(),
            timeframe="5m",  # Different timeframe; should NOT be included in 1m bar completeness
            timestamp=now,
            open=Decimal("10"),
            high=Decimal("12"),
            low=Decimal("9"),
            close=Decimal("11"),
            is_partial_bar=True,
        )

        response = self.client.get("/api/v1/fno/diagnostics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["bars"]["total_today"], 1)
        self.assertEqual(data["bars"]["partial_count"], 0)
        self.assertEqual(data["components"]["postgresql"], "HEALTHY")
        self.assertIn("ticker_daemon", data["components"])
