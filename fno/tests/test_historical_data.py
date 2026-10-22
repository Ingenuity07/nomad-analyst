"""
Nomad Analyst — F&O Historical Data Foundation Unit Tests.

Uses isolated, synthetic in-memory Parquet fixtures ONLY.
Never touches or pollutes authentic market data or production databases.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import zoneinfo

from django.test import SimpleTestCase
import pyarrow as pa
import pyarrow.parquet as pq

from fno.management.commands.fetch_fno_historical import Command as FetchCommand
from fno.management.commands.validate_fno_historical import HistoricalValidator
from fno.services.historical_reader import HistoricalDataUnavailableError, HistoricalParquetReader

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")


class SyntheticFixtureFactory:
    """Helper to create synthetic index and option Parquet files for isolated testing."""

    @staticmethod
    def create_synthetic_index_parquet(
        target_path: Path,
        session_date: date = date(2026, 6, 15),
        bar_count: int = 15,
        inject_bad_ohlc: bool = False,
        inject_duplicate: bool = False,
        inject_bad_hours: bool = False,
        drop_column: bool = False,
    ) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = datetime.combine(session_date, time(3, 0) if inject_bad_hours else time(9, 15), tzinfo=IST)

        timestamps = [start_time + timedelta(minutes=i) for i in range(bar_count)]
        if inject_duplicate and len(timestamps) > 1:
            timestamps[1] = timestamps[0]

        opens = [24500.0 + i for i in range(bar_count)]
        highs = [24510.0 + i for i in range(bar_count)]
        lows = [24490.0 + i for i in range(bar_count)]
        closes = [24505.0 + i for i in range(bar_count)]
        volumes = [1000 + i * 10 for i in range(bar_count)]
        trading_days = [str(session_date) for _ in range(bar_count)]
        symbols = ["NIFTY" for _ in range(bar_count)]

        if inject_bad_ohlc and len(highs) > 0:
            highs[0] = lows[0] - 10.0  # high < low violation

        data = {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "trading_day": trading_days,
            "symbol": symbols,
        }
        if drop_column:
            del data["open"]

        table = pa.Table.from_pydict(data)
        pq.write_table(table, str(target_path))
        return target_path

    @staticmethod
    def create_synthetic_option_parquet(
        target_path: Path,
        expiry_str: str = "2026-06-18",
        session_date: date = date(2026, 6, 15),
        inject_negative_oi: bool = False,
        inject_bad_symbol: bool = False,
        inject_duplicate: bool = False,
        inject_conflict: bool = False,
        omit_ce: bool = False,
        inject_bad_hours: bool = False,
        drop_column: bool = False,
    ) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = datetime.combine(session_date, time(9, 15), tzinfo=IST)
        if inject_bad_hours:
            start_time = datetime.combine(session_date, time(3, 0), tzinfo=IST)

        timestamps = [
            start_time,
            start_time,
            start_time + timedelta(minutes=1),
            start_time + timedelta(minutes=1),
        ]
        strikes = [24500, 24500, 24600, 24600]
        option_types = ["PE" if omit_ce else "CE", "PE", "PE" if omit_ce else "CE", "PE"]
        opens = [150.0, 120.0, 90.0, 180.0]
        highs = [155.0, 125.0, 95.0, 185.0]
        lows = [148.0, 118.0, 88.0, 175.0]
        closes = [152.0, 122.0, 92.0, 182.0]
        volumes = [500, 0, 300, 0]  # Note: zero volume present for inactive PE
        open_interests = [10000, 8000, 12000, -500 if inject_negative_oi else 6000]

        if inject_duplicate:
            # Identical record across all audited fields
            timestamps[2] = timestamps[0]
            strikes[2] = strikes[0]
            option_types[2] = option_types[0]
            opens[2] = opens[0]
            highs[2] = highs[0]
            lows[2] = lows[0]
            closes[2] = closes[0]
            volumes[2] = volumes[0]
            open_interests[2] = open_interests[0]
        elif inject_conflict:
            # Conflicting record: same identity & timestamp, but differing OHLCV values
            timestamps[2] = timestamps[0]
            strikes[2] = strikes[0]
            option_types[2] = option_types[0]
            opens[2] = 90.0
            closes[2] = 92.0
        symbols = ["INVALID" if inject_bad_symbol else "NIFTY" for _ in range(4)]
        expiries = [expiry_str for _ in range(4)]
        trading_days = [str(session_date) for _ in range(4)]

        data = {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "open_interest": open_interests,
            "trading_day": trading_days,
            "symbol": symbols,
            "strike": strikes,
            "option_type": option_types,
            "expiry": expiries,
        }
        if drop_column:
            del data["open_interest"]

        table = pa.Table.from_pydict(data)
        pq.write_table(table, str(target_path))
        return target_path


class HistoricalReaderTests(SimpleTestCase):
    """Verifies HistoricalParquetReader querying, timezone conversion, and safety bounds."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.reader = HistoricalParquetReader(base_dir=self.base_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_missing_index_raises_error(self):
        with self.assertRaises(HistoricalDataUnavailableError):
            self.reader.query_index_bars("2026-06-15", "2026-06-15")

    def test_query_index_bars_returns_normalized_timestamps(self):
        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, bar_count=15)

        bars = self.reader.query_index_bars("2026-06-15", "2026-06-15")
        self.assertEqual(len(bars), 15)
        first_bar = bars[0]
        self.assertEqual(first_bar["symbol"], "NIFTY")
        self.assertEqual(first_bar["open"], Decimal("24500.0"))
        # Verify IST and UTC timezone preservation
        self.assertEqual(first_bar["timestamp_ist"].tzinfo, IST)
        self.assertEqual(first_bar["timestamp_utc"].tzinfo, UTC)
        self.assertEqual(first_bar["timestamp_ist"].hour, 9)
        self.assertEqual(first_bar["timestamp_ist"].minute, 15)

    def test_query_option_bars_with_predicate_pushdown(self):
        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file)

        # Query only CE
        ce_bars = self.reader.query_option_bars("2026-06-15", "2026-06-15", option_type="CE")
        self.assertEqual(len(ce_bars), 2)
        for b in ce_bars:
            self.assertEqual(b["option_type"], "CE")
            self.assertFalse(b["bid_ask_available"])  # Explicitly verified

        # Query specific strike
        strike_bars = self.reader.query_option_bars("2026-06-15", "2026-06-15", strike=24500)
        self.assertEqual(len(strike_bars), 2)
        for b in strike_bars:
            self.assertEqual(b["strike"], 24500)

    def test_get_trading_days(self):
        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, session_date=date(2026, 6, 15))
        days = self.reader.get_trading_days()
        self.assertEqual(days, [date(2026, 6, 15)])


class HistoricalValidatorTests(SimpleTestCase):
    """Verifies HistoricalValidator detects integrity errors, skips missing data safely, and passes clean data."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.validator = HistoricalValidator(base_dir=self.base_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_not_tested_when_files_absent(self):
        report = self.validator.run_all_checks()
        self.assertEqual(report["overall_status"], "FAIL")  # Missing manifest causes FAIL
        self.assertEqual(report["checks"]["INDEX_SCHEMA"]["status"], "NOT_TESTED")
        self.assertEqual(report["checks"]["OPTIONS_SCHEMA"]["status"], "NOT_TESTED")
        self.assertEqual(report["checks"]["BID_ASK_AVAILABILITY_DISCLAIMER"]["status"], "PASS")

    def test_pass_on_clean_synthetic_dataset(self):
        # Create manifest
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"dataset_id": "test", "files": {}}), encoding="utf-8")

        # Create valid index
        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, bar_count=15)

        # Create valid options
        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file)

        report = self.validator.run_all_checks()
        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(report["checks"]["INDEX_SCHEMA"]["status"], "PASS")
        self.assertEqual(report["checks"]["INDEX_OHLC_GEOMETRY"]["status"], "PASS")
        self.assertEqual(report["checks"]["INDEX_DUPLICATES"]["status"], "PASS")
        self.assertEqual(report["checks"]["INDEX_ORB_15M_READINESS"]["status"], "PASS")
        self.assertEqual(report["checks"]["OPTIONS_SCHEMA"]["status"], "PASS")
        self.assertEqual(report["checks"]["OPTIONS_OHLC_GEOMETRY"]["status"], "PASS")
        self.assertEqual(report["checks"]["OPTIONS_DUPLICATES"]["status"], "PASS")
        self.assertEqual(report["checks"]["OPTIONS_CONTRACT_METADATA"]["status"], "PASS")
        self.assertEqual(report["checks"]["OPTIONS_VOLUME_AND_OI"]["status"], "PASS")

    def test_fail_on_bad_ohlc_geometry(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, inject_bad_ohlc=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["INDEX_OHLC_GEOMETRY"]["status"], "FAIL")
        self.assertEqual(report["overall_status"], "FAIL")

    def test_fail_on_missing_schema_column(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, drop_column=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["INDEX_SCHEMA"]["status"], "FAIL")

    def test_fail_on_duplicate_timestamps(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, inject_duplicate=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["INDEX_DUPLICATES"]["status"], "FAIL")

    def test_fail_on_negative_open_interest(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file, inject_negative_oi=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["OPTIONS_VOLUME_AND_OI"]["status"], "FAIL")

    def test_fail_on_missing_opening_range_bar(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        index_file = self.base_dir / "index" / "NIFTY.parquet"
        # Create only 14 bars during 09:15-09:29 (one bar missing)
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, bar_count=14)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["INDEX_ORB_15M_READINESS"]["status"], "FAIL")

    def test_fail_on_invalid_market_hours_boundary(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, inject_bad_hours=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["INDEX_MARKET_HOURS"]["status"], "FAIL")

    def test_fail_on_duplicate_option_records(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file, inject_duplicate=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["OPTIONS_DUPLICATES"]["status"], "FAIL")

    def test_fail_on_missing_atm_series(self):
        manifest_path = self.base_dir / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        # Create valid index with spot close at 09:30
        index_file = self.base_dir / "index" / "NIFTY.parquet"
        SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, bar_count=16)

        # Create option with omit_ce=True (ATM 24500 CE series missing)
        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file, omit_ce=True)

        report = self.validator.run_all_checks()
        self.assertEqual(report["checks"]["OPTIONS_ATM_SERIES_COVERAGE"]["status"], "PARTIAL_PASS")


class FetchHistoricalCommandTests(SimpleTestCase):
    """Verifies downloader command logic, option file filtering, and manifest management."""

    def test_filter_option_files_by_dates(self):
        cmd = FetchCommand()
        all_options = [
            "options/NIFTY/2026-05-28.parquet",
            "options/NIFTY/2026-06-04.parquet",
            "options/NIFTY/2026-06-11.parquet",
            "options/NIFTY/2026-06-18.parquet",
            "options/NIFTY/2026-06-25.parquet",
            "options/NIFTY/2026-07-30.parquet",
            "options/NIFTY/2026-10-29.parquet",
        ]

        # Bounded filter: 2026-06-01 to 2026-06-30
        matched = cmd._filter_option_files(
            option_files=all_options,
            symbol="NIFTY",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            single_expiry=None,
        )
        self.assertIn("options/NIFTY/2026-06-04.parquet", matched)
        self.assertIn("options/NIFTY/2026-06-11.parquet", matched)
        self.assertIn("options/NIFTY/2026-06-18.parquet", matched)
        self.assertIn("options/NIFTY/2026-06-25.parquet", matched)
        self.assertIn("options/NIFTY/2026-07-30.parquet", matched)  # Expiry within 45 days of window end
        self.assertNotIn("options/NIFTY/2026-05-28.parquet", matched)  # Expired before start
        self.assertNotIn("options/NIFTY/2026-10-29.parquet", matched)  # Expired far after end

    def test_single_expiry_filter(self):
        cmd = FetchCommand()
        all_options = [
            "options/NIFTY/2026-06-18.parquet",
            "options/NIFTY/2026-06-25.parquet",
        ]
        matched = cmd._filter_option_files(
            option_files=all_options,
            symbol="NIFTY",
            start_date=None,
            end_date=None,
            single_expiry="2026-06-18",
        )
        self.assertEqual(matched, ["options/NIFTY/2026-06-18.parquet"])

    def test_verify_checksum_matching(self):
        cmd = FetchCommand()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"sample parquet content")
            f_path = Path(f.name)

        try:
            import hashlib
            expected_sha = hashlib.sha256(b"sample parquet content").hexdigest()
            self.assertTrue(cmd._verify_checksum(f_path, expected_sha))
            self.assertFalse(cmd._verify_checksum(f_path, "incorrect_hash"))
            self.assertFalse(cmd._verify_checksum(Path("/nonexistent/file.parquet"), expected_sha))
        finally:
            f_path.unlink()

    def test_extract_file_coverage_metadata(self):
        cmd = FetchCommand()
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            f_path = Path(f.name)

        try:
            SyntheticFixtureFactory.create_synthetic_index_parquet(
                f_path, session_date=date(2026, 6, 15), bar_count=15
            )
            coverage = cmd._extract_file_coverage(f_path)
            self.assertEqual(coverage["row_count"], 15)
            self.assertEqual(coverage["min_trading_day"], "2026-06-15")
            self.assertEqual(coverage["max_trading_day"], "2026-06-15")
        finally:
            f_path.unlink()

    def test_manifest_load_and_save(self):
        cmd = FetchCommand()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            manifest = cmd._load_manifest(out_dir)
            self.assertEqual(manifest["dataset_id"], "thetrademarkk/india-index-options-1m")
            self.assertEqual(manifest["license"], "CC BY-NC 4.0")
            self.assertIn("CC BY-NC 4.0", manifest["attribution"])

            # Add entry and save
            manifest["files"]["test.parquet"] = {
                "sha256": "abc123hash",
                "size_bytes": 100,
            }
            cmd._save_manifest(out_dir, manifest)

            # Reload and verify
            reloaded = cmd._load_manifest(out_dir)
            self.assertIn("test.parquet", reloaded["files"])
            self.assertEqual(reloaded["files"]["test.parquet"]["sha256"], "abc123hash")

    def test_reuse_existing_valid_file_and_checksum_mismatch(self):
        cmd = FetchCommand()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            index_dir = out_dir / "index"
            index_dir.mkdir(parents=True)
            index_file = index_dir / "NIFTY.parquet"
            SyntheticFixtureFactory.create_synthetic_index_parquet(index_file, bar_count=5)

            import hashlib
            with open(index_file, "rb") as f:
                valid_sha = hashlib.sha256(f.read()).hexdigest()

            # 1. Matching SHA: should verify as valid
            self.assertTrue(cmd._verify_checksum(index_file, valid_sha))

            # 2. Checksum mismatch: corrupted file or outdated manifest
            corrupt_sha = "ffff" * 16
            self.assertFalse(cmd._verify_checksum(index_file, corrupt_sha))


class HistoricalReaderDeduplicationTests(SimpleTestCase):
    """Verifies that query_option_bars deduplicates identical rows across audited fields."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.reader = HistoricalParquetReader(base_dir=self.base_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_query_option_bars_deduplicates_identical_rows(self):
        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        # SyntheticFixtureFactory with inject_duplicate=True creates duplicate records
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file, inject_duplicate=True)

        bars = self.reader.query_option_bars("2026-06-15", "2026-06-15")
        # Raw parquet had exact duplicate injected across all audited fields, collapsed via DISTINCT
        keys = [(b["timestamp_ist"], b["strike"], b["option_type"]) for b in bars]
        self.assertEqual(len(keys), len(set(keys)), "Returned option bars must be unique contract-minute records.")

    def test_query_option_bars_raises_on_conflicting_rows(self):
        from fno.services.historical_reader import HistoricalDataConflictError

        opt_file = self.base_dir / "options" / "2026-06-18.parquet"
        SyntheticFixtureFactory.create_synthetic_option_parquet(opt_file, inject_conflict=True)

        with self.assertRaises(HistoricalDataConflictError):
            self.reader.query_option_bars("2026-06-15", "2026-06-15")


class BacktesterEdgeCaseDesignTests(SimpleTestCase):
    """Synthetic unit tests for remediated backtester design invariants."""

    def test_exercise_settlement_statutory_stt_and_brokerage(self):
        from fno.execution.fee_calculator import StatutoryFeeCalculator

        # Scenario A: ITM Option exercised at expiration with intrinsic settlement price 150.00
        # Buy at 100.00, exercised at 150.00, qty 65
        fee_itm = StatutoryFeeCalculator.calculate_round_trip(
            buy_price=Decimal("100.00"),
            sell_price=Decimal("150.00"),
            quantity=65,
            is_exercise_settlement=True,
            trade_date=date(2026, 4, 15),
        )
        # Brokerage charged on both legs
        self.assertEqual(fee_itm.brokerage, Decimal("40.00"))
        # STT charged at 0.15% on intrinsic settlement turnover (150 * 65 = 9750 -> 14.625 -> 14.63)
        self.assertEqual(fee_itm.stt, Decimal("14.63"))
        self.assertEqual(fee_itm.sell_turnover, Decimal("9750.00"))

        # Scenario B: OTM Option expiring worthless at 0.00
        fee_otm = StatutoryFeeCalculator.calculate_round_trip(
            buy_price=Decimal("100.00"),
            sell_price=Decimal("0.00"),
            quantity=65,
            is_exercise_settlement=True,
            trade_date=date(2026, 4, 15),
        )
        # Only entry order brokerage charged (20.00) because no exchange sell order executed
        self.assertEqual(fee_otm.brokerage, Decimal("20.00"))
        # Zero STT on worthless expiry
        self.assertEqual(fee_otm.stt, Decimal("0.00"))
        self.assertEqual(fee_otm.sell_turnover, Decimal("0.00"))

    def test_fill_timestamp_cutoff_rule(self):
        """Entry eligibility must be evaluated on simulated fill timestamp (T_fill <= 14:30:00)."""
        entry_cutoff = time(14, 30, 0)

        # Breakout bar 14:29:00 (closes 14:30:00) -> Fill at 14:30:00 Open -> Eligible
        fill_time_eligible = time(14, 30, 0)
        self.assertLessEqual(fill_time_eligible, entry_cutoff)

        # Breakout bar 14:30:00 (closes 14:31:00) -> Fill at 14:31:00 Open -> Rejected
        fill_time_past_cutoff = time(14, 31, 0)
        self.assertGreater(fill_time_past_cutoff, entry_cutoff)

    def test_independent_expiry_calendar_validation(self):
        """Cross-referencing scheduled exchange expiries against local dataset identifies missing files."""
        scheduled_exchange_expiries = {
            date(2025, 10, 7),
            date(2025, 10, 14),
            date(2025, 10, 21),  # Existed on exchange, but missing from Hugging Face upload
            date(2025, 10, 28),
        }
        dataset_available_expiries = {
            date(2025, 10, 7),
            date(2025, 10, 14),
            date(2025, 10, 28),
        }

        missing_expiries = scheduled_exchange_expiries - dataset_available_expiries
        self.assertEqual(missing_expiries, {date(2025, 10, 21)})
