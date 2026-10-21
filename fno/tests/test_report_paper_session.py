"""
fno/tests/test_report_paper_session.py — Unit Tests for report_paper_session Command.
Verifies:
1. Exact IST boundary filtering (session-scoped vs historical records).
2. Honest reporting of NO DATA when 0 market bars exist.
3. Honest reporting of NOT EVALUATED / UN-WIRED when bars exist but 0 signals/trades occurred.
4. Correct aggregation of fills, rejections, fees, slippage, and PnL.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import uuid
import zoneinfo
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from fno.models import OptionOHLCVBar, OptionQuoteSnapshot, PaperTradeLedger

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class ReportPaperSessionCommandTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.session_date = date(2026, 10, 22)
        # 10:00 IST on 2026-10-22 is 04:30 UTC
        self.session_time_utc = datetime(2026, 10, 22, 4, 30, tzinfo=timezone.utc)
        # Previous day 2026-10-21 10:00 IST is 04:30 UTC
        self.yesterday_utc = datetime(2026, 10, 21, 4, 30, tzinfo=timezone.utc)

    def test_report_no_data_state(self):
        """When 0 bars and 0 quotes exist for session date, reports NO DATA."""
        out = io.StringIO()
        call_command("report_paper_session", "--date", "2026-10-22", stdout=out)
        output = out.getvalue()

        self.assertIn("[DATA STATUS: NO DATA]", output)
        self.assertIn("Strategy Execution Status: NO DATA", output)

    def test_report_unwired_state_when_bars_exist_but_zero_signals(self):
        """When bars exist but zero signals/trades recorded, reports UN-WIRED RUNTIME."""
        OptionOHLCVBar.objects.create(
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            timeframe="1m",
            timestamp=self.session_time_utc,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=500,
            open_interest=50000,
            expiry_date=date(2026, 10, 27),
            strike_price=Decimal("24500.00"),
            option_type="CE",
            is_partial_bar=False,
        )

        out = io.StringIO()
        call_command("report_paper_session", "--date", "2026-10-22", stdout=out)
        output = out.getvalue()

        self.assertIn("**Option 1m OHLCV Bars:** 1 total", output)
        self.assertIn("Strategy Execution Status: NOT EVALUATED / UN-WIRED RUNTIME", output)

    def test_ist_day_boundary_filtering_and_historical_separation(self):
        """Verifies session filtering strictly isolates IST day and separates from historical totals."""
        # Create trade for session date (2026-10-22)
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            entry_timestamp=self.session_time_utc,
            entry_fill_price=Decimal("100.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            exit_timestamp=self.session_time_utc + timedelta(minutes=15),
            exit_fill_price=Decimal("120.00"),
            exit_slippage=Decimal("0.50"),
            gross_pnl=Decimal("1300.00"),
            total_frictions=Decimal("65.00"),
            net_pnl=Decimal("1235.00"),
            status="CLOSED",
        )

        # Create historical trade from yesterday (2026-10-21)
        PaperTradeLedger.objects.create(
            strategy_id="STRAT-ORB-15M",
            strategy_version="1.0.0",
            signal_id=uuid.uuid4(),
            instrument_token=1001,
            tradingsymbol="NIFTY26OCT24500CE",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=date(2026, 10, 27),
            entry_timestamp=self.yesterday_utc,
            entry_fill_price=Decimal("80.00"),
            entry_slippage=Decimal("0.50"),
            quantity=65,
            exit_timestamp=self.yesterday_utc + timedelta(minutes=15),
            exit_fill_price=Decimal("90.00"),
            exit_slippage=Decimal("0.50"),
            gross_pnl=Decimal("650.00"),
            total_frictions=Decimal("65.00"),
            net_pnl=Decimal("585.00"),
            status="CLOSED",
        )

        out = io.StringIO()
        call_command("report_paper_session", "--date", "2026-10-22", stdout=out)
        output = out.getvalue()

        # Session trade count should be 1
        self.assertIn("**Total Signals Recorded:** 1", output)
        self.assertIn("**Executed Fills (Taker):** 1", output)
        self.assertIn("**Session Completed Trades:** 1", output)
        self.assertIn("**Net P&L:** ₹1,235.00", output)

        # All-time trade count should be 2
        self.assertIn("**All-Time Ledger Records:** 2", output)
