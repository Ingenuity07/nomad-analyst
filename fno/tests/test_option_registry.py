"""
Unit Tests for AC-1-U01: OptionInstrumentRegistry.
Verifies authoritative master parsing, expiry resolution, and stale file detection.
"""

import os
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from fno.services.option_registry import (
    OptionInstrumentRegistry,
    OptionContractMeta,
    StaleMasterFileError,
    CONFIG_NIFTY,
)

SAMPLE_CSV_HEADER = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"

SAMPLE_CSV_ROWS = (
    '12067586,47139,NIFTY26O1922600CE,"NIFTY",0,2026-10-19,22600,0.05,25,CE,NFO-OPT,NFO\n'
    '12067842,47140,NIFTY26O1922600PE,"NIFTY",0,2026-10-19,22600,0.05,25,PE,NFO-OPT,NFO\n'
    '12068098,47141,NIFTY26O1922650CE,"NIFTY",0,2026-10-19,22650,0.05,25,CE,NFO-OPT,NFO\n'
    '12068354,47142,NIFTY26O1922650PE,"NIFTY",0,2026-10-19,22650,0.05,25,PE,NFO-OPT,NFO\n'
    '12067074,47137,NIFTY26O2722600CE,"NIFTY",0,2026-10-27,22600,0.05,25,CE,NFO-OPT,NFO\n'
    '12067075,47138,NIFTY26O2722600PE,"NIFTY",0,2026-10-27,22600,0.05,25,PE,NFO-OPT,NFO\n'
    '99999999,99999,RELIANCE26OCTFUT,"RELIANCE",0,2026-10-29,0,0.05,250,FUT,NFO-FUT,NFO\n' # Should be skipped (FUT)
    '88888888,88888,RELIANCE,"RELIANCE",0,,0,0.05,1,EQ,NSE,NSE\n' # Should be skipped (NSE)
)


class TestOptionInstrumentRegistry(SimpleTestCase):
    """Test suite for OptionInstrumentRegistry meeting AC-1-U01."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_file = Path(self.temp_dir.name) / "test_instruments.csv"
        self.csv_file.write_text(SAMPLE_CSV_HEADER + SAMPLE_CSV_ROWS, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_csv_filters_strictly_for_nfo_options(self):
        """Registry must parse only NFO-OPT contracts and ignore futures and equities."""
        registry = OptionInstrumentRegistry(master_path=self.csv_file)
        count = registry.load_master(max_age_hours=24)
        
        # 6 NFO options in sample, futures and equities must be excluded
        self.assertEqual(count, 6)
        
        meta = registry.get_by_token(12067586)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.tradingsymbol, "NIFTY26O1922600CE")
        self.assertEqual(meta.strike, Decimal("22600"))
        self.assertEqual(meta.instrument_type, "CE")
        self.assertEqual(meta.segment, "NFO-OPT")
        self.assertEqual(meta.exchange, "NFO")
        self.assertEqual(meta.expiry, date(2026, 10, 19))

        # Check that FUT is excluded
        self.assertIsNone(registry.get_by_token(99999999))

    def test_master_expiry_date_is_authoritative(self):
        """The CSV's expiry column is the single source of truth, including holiday shifts."""
        registry = OptionInstrumentRegistry(master_path=self.csv_file)
        registry.load_master()

        active_expiries = registry.get_active_expiries(underlying="NIFTY", as_of_date=date(2026, 10, 15))
        self.assertEqual(active_expiries, [date(2026, 10, 19), date(2026, 10, 27)])

        nearest = registry.get_nearest_weekly_expiry(underlying="NIFTY", as_of_date=date(2026, 10, 15))
        self.assertEqual(nearest, date(2026, 10, 19))

        next_weekly = registry.get_next_weekly_expiry(underlying="NIFTY", as_of_date=date(2026, 10, 15))
        self.assertEqual(next_weekly, date(2026, 10, 27))

    def test_contract_lookup_by_strike_and_type(self):
        """Lookup by underlying, expiry, strike, and type must return exact contract."""
        registry = OptionInstrumentRegistry(master_path=self.csv_file)
        registry.load_master()

        contract = registry.get_contract(
            underlying="NIFTY",
            expiry=date(2026, 10, 19),
            strike=Decimal("22650"),
            option_type="PE"
        )
        self.assertIsNotNone(contract)
        self.assertEqual(contract.instrument_token, 12068354)
        self.assertEqual(contract.tradingsymbol, "NIFTY26O1922650PE")

    def test_stale_master_file_detection(self):
        """Registry must detect when the master CSV file exceeds the staleness threshold."""
        # Set file modification time to 30 hours ago
        stale_mtime = time.time() - (30 * 3600)
        os.utime(self.csv_file, (stale_mtime, stale_mtime))

        registry = OptionInstrumentRegistry(master_path=self.csv_file)
        
        # Check staleness boolean
        self.assertTrue(registry.is_master_stale(max_age_hours=24))

        # Loading with raise_if_stale=True must raise StaleMasterFileError
        with self.assertRaises(StaleMasterFileError):
            registry.load_master(max_age_hours=24, raise_if_stale=True)

        # Loading with raise_if_stale=False must succeed but flag is_stale
        count = registry.load_master(max_age_hours=24, raise_if_stale=False)
        self.assertEqual(count, 6)
        self.assertTrue(registry.is_stale)
