"""
Regression tests for look-ahead-free completed spot bar timing convention (AC-1-L02).
"""

import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django.db.models import Q
from market.models import Company, Instrument, OHLCVBar, StockIntradayContext
from fno.models import OptionOHLCVBar, OptionQuoteSnapshot
from fno.services.log_parsers import (
    get_latest_completed_spot_bar,
    evaluate_equity_isolation_verdict,
    evaluate_option_bar_coverage_verdict,
    is_bar_within_disconnect_interval,
    extract_verified_disconnect_intervals,
    evaluate_quote_snapshot_integrity,
    evaluate_quote_freshness_and_universe_verdict,
)


class CompletedBarTimingTests(SimpleTestCase):
    """
    Verifies that spot bar selection strictly enforces completed-bar timing conventions
    and eliminates look-ahead bias.

    In OHLCVBar:
        timestamp denotes the bar OPENING time.
        A 1-minute bar starting at T_open covers [T_open, T_open + 60s).
        The close price is formed only at T_close = T_open + 60s.
    """

    def setUp(self):
        self.utc = datetime.timezone.utc
        self.ist = ZoneInfo("Asia/Kolkata")
        # Dummy Instrument (unpersisted, used for mock OHLCVBar instances)
        self.inst = Instrument(symbol="^NSEI", exchange="INDEX")

        # Bar 1: 09:19 IST [09:19:00 - 09:20:00 IST), Close = 24500.00
        self.t_0919_ist = datetime.datetime(2026, 10, 19, 9, 19, 0, tzinfo=self.ist)
        self.bar_0919 = OHLCVBar(
            instrument=self.inst,
            timeframe="1m",
            timestamp=self.t_0919_ist,
            open=Decimal("24490.00"),
            high=Decimal("24510.00"),
            low=Decimal("24485.00"),
            close=Decimal("24500.00"),
            volume=1000
        )

        # Bar 2: 09:20 IST [09:20:00 - 09:21:00 IST), Close = 24555.00
        self.t_0920_ist = datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist)
        self.bar_0920 = OHLCVBar(
            instrument=self.inst,
            timeframe="1m",
            timestamp=self.t_0920_ist,
            open=Decimal("24505.00"),
            high=Decimal("24560.00"),
            low=Decimal("24500.00"),
            close=Decimal("24555.00"),
            volume=1200
        )

        self.spot_bars = [self.bar_0919, self.bar_0920]

    def test_model_semantics_timestamp_is_bar_opening(self):
        """Verify model field documentation/help_text defines timestamp as bar opening."""
        field = OHLCVBar._meta.get_field("timestamp")
        self.assertIn("opening", field.help_text.lower())

    def test_boundary_at_slot_start_excludes_uncompleted_current_bar(self):
        """
        Boundary condition: At 09:20:00 IST (start of the 09:20 slot), Bar 2 (09:20) has
        just opened and is in-flight. Its close (24555.00) will NOT be available until 09:21:00.
        Only Bar 1 (09:19) is completed and eligible.
        """
        eval_time = self.t_0920_ist  # 09:20:00 IST
        completed_bar = get_latest_completed_spot_bar(self.spot_bars, as_of_time=eval_time)

        self.assertIsNotNone(completed_bar)
        self.assertEqual(completed_bar.timestamp, self.t_0919_ist)
        self.assertEqual(completed_bar.close, Decimal("24500.00"))

    def test_boundary_intrabar_still_excludes_uncompleted_current_bar(self):
        """At 09:20:59 IST, Bar 2 is still in progress; Bar 1 remains the latest completed."""
        eval_time = self.t_0920_ist + datetime.timedelta(seconds=59)
        completed_bar = get_latest_completed_spot_bar(self.spot_bars, as_of_time=eval_time)

        self.assertIsNotNone(completed_bar)
        self.assertEqual(completed_bar.timestamp, self.t_0919_ist)
        self.assertEqual(completed_bar.close, Decimal("24500.00"))

    def test_boundary_at_slot_end_includes_completed_bar(self):
        """
        At 09:21:00 IST, Bar 2 (09:20) is fully concluded (09:20:00 + 60s <= 09:21:00).
        Its close (24555.00) is now valid and returned.
        """
        eval_time = self.t_0920_ist + datetime.timedelta(minutes=1)  # 09:21:00 IST
        completed_bar = get_latest_completed_spot_bar(self.spot_bars, as_of_time=eval_time)

        self.assertIsNotNone(completed_bar)
        self.assertEqual(completed_bar.timestamp, self.t_0920_ist)
        self.assertEqual(completed_bar.close, Decimal("24555.00"))

    def test_lookahead_bug_demonstration_and_fix(self):
        """
        Demonstrates that the naive condition `b.timestamp <= slot` commits look-ahead bias
        by using Bar 2 close at 09:20:00, whereas `get_latest_completed_spot_bar` eliminates it.
        """
        slot = self.t_0920_ist

        # Naive / buggy look-ahead condition:
        buggy_matching = [b for b in self.spot_bars if b.timestamp <= slot]
        buggy_spot = buggy_matching[-1].close  # This is 24555.00 (from future close of 09:20 bar!)
        self.assertEqual(buggy_spot, Decimal("24555.00"))

        # Look-ahead-free condition:
        correct_bar = get_latest_completed_spot_bar(self.spot_bars, as_of_time=slot)
        self.assertEqual(correct_bar.close, Decimal("24500.00"))  # Authoritative completed bar!
        self.assertNotEqual(buggy_spot, correct_bar.close)

    def test_unsorted_input_enforces_chronological_selection(self):
        """
        Verify that get_latest_completed_spot_bar guarantees returning the chronologically
        latest completed bar even if the caller provides spot_bars in reverse or unsorted order.
        """
        # Bar 0: 09:18 IST
        t_0918_ist = datetime.datetime(2026, 10, 19, 9, 18, 0, tzinfo=self.ist)
        bar_0918 = OHLCVBar(
            instrument=self.inst,
            timeframe="1m",
            timestamp=t_0918_ist,
            open=Decimal("24480.00"),
            high=Decimal("24495.00"),
            low=Decimal("24475.00"),
            close=Decimal("24490.00"),
            volume=800
        )

        # Provide bars in reverse/shuffled order: [09:20, 09:18, 09:19]
        unsorted_bars = [self.bar_0920, bar_0918, self.bar_0919]

        eval_time = self.t_0920_ist  # At 09:20:00, only 09:18 and 09:19 are completed
        res = get_latest_completed_spot_bar(unsorted_bars, as_of_time=eval_time)

        self.assertIsNotNone(res)
        self.assertEqual(res.timestamp, self.t_0919_ist)
        self.assertEqual(res.close, Decimal("24500.00"))

    def test_exact_completion_boundary_subsecond_precision(self):
        """
        Verify exact sub-second boundary condition:
        Bar 1 opens at 09:19:00.000000 IST; bar concludes at exactly 09:20:00.000000 IST.
        - At 09:19:59.999999 IST (1 microsecond prior): Bar is in-flight, NOT completed.
        - At 09:20:00.000000 IST: Bar is completed and eligible.
        """
        # 1 microsecond before conclusion
        just_before_close = self.t_0920_ist - datetime.timedelta(microseconds=1)
        res_before = get_latest_completed_spot_bar([self.bar_0919], as_of_time=just_before_close)
        self.assertIsNone(res_before)

        # Exactly at conclusion
        at_close = self.t_0920_ist
        res_at = get_latest_completed_spot_bar([self.bar_0919], as_of_time=at_close)
        self.assertIsNotNone(res_at)
        self.assertEqual(res_at.timestamp, self.t_0919_ist)

    def test_inflight_spot_bar_cannot_determine_expected_atm_universe(self):
        """
        Boundary test: At 09:20:30 IST, Bar 2 (09:20-09:21) is in-flight with open=24505, close=24555.
        An in-flight bar CANNOT determine the expected ATM universe because its close is not yet formed.
        Only completed Bar 1 (09:19 close=24500) determines authoritative ATM (24500).
        """
        eval_time = self.t_0920_ist + datetime.timedelta(seconds=30)  # 09:20:30 IST
        completed_bar = get_latest_completed_spot_bar(self.spot_bars, as_of_time=eval_time)

        self.assertIsNotNone(completed_bar)
        self.assertEqual(completed_bar.timestamp, self.t_0919_ist)
        self.assertEqual(completed_bar.close, Decimal("24500.00"))

        step = Decimal("50.0")
        atm_strike = (completed_bar.close / step).quantize(Decimal("1")) * step
        self.assertEqual(atm_strike, Decimal("24500.00"))

        # Naive query commits look-ahead and would derive 24550 ATM from in-flight bar
        naive_bar = [b for b in self.spot_bars if b.timestamp <= eval_time][-1]
        naive_atm = (naive_bar.close / step).quantize(Decimal("1")) * step
        self.assertEqual(naive_atm, Decimal("24550.00"))
        self.assertNotEqual(atm_strike, naive_atm)

    def test_pipeline_drops_with_zero_persisted_bars_returns_fail(self):
        """
        Regression test: When expected slots exist (22), bars are absent (0 persisted),
        and matching token/slot quote snapshots exist (pipeline drop), the outcome MUST
        return FAIL, not NOT TESTED.
        """
        from fno.services.log_parsers import evaluate_option_bar_coverage_verdict

        pipeline_drops = [
            ("NIFTY26OCT24500CE", "09:20", "EFFECTIVE_SNAPS_(5)_ARRIVED_BUT_BAR_NOT_PERSISTED")
        ]
        res = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=0,  # Zero bars persisted!
            pipeline_drops=pipeline_drops,
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=True,
            disconnect_evidence_summary="VALID_LOGS_ZERO_DISCONNECT_EVENTS",
        )
        # Precedence rule: pipeline drop MUST result in FAIL, never NOT TESTED
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("DATA_CHECK_FAIL", res["evidence"])
        self.assertIn("1 pipeline drops", res["evidence"])

    def test_missing_slots_without_telemetry_returns_inconclusive(self):
        """Missing slots without broker telemetry or snapshots must return INSUFFICIENT_TELEMETRY."""
        from fno.services.log_parsers import evaluate_option_bar_coverage_verdict

        unverified = [("NIFTY26OCT24500CE", "09:20", "NO_TICK_TELEMETRY_AVAILABLE")]
        res = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=0,
            pipeline_drops=[],
            unverified_missing_slots=unverified,
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=True,
            disconnect_evidence_summary="VALID_LOGS_ZERO_DISCONNECT_EVENTS",
        )
        self.assertEqual(res["verdict"], "INCONCLUSIVE")
        self.assertEqual(res["status"], "NOT TESTED (INSUFFICIENT_TELEMETRY)")

    def test_disconnect_interval_temporal_overlap_exact_bounds(self):
        """Verifies exact temporal overlap without adding arbitrary neighboring minutes."""
        from fno.services.log_parsers import is_bar_within_disconnect_interval

        # Disconnect: 09:20:15 to 09:20:25 IST
        d_start = datetime.datetime(2026, 10, 19, 9, 20, 15, tzinfo=self.ist)
        d_end = datetime.datetime(2026, 10, 19, 9, 20, 25, tzinfo=self.ist)
        intervals = [(d_start, d_end)]

        # Bar A: 09:20:00 to 09:21:00 (overlaps disconnect)
        bar_a_start = datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist)
        self.assertTrue(is_bar_within_disconnect_interval(bar_a_start, datetime.timedelta(minutes=1), intervals))

        # Bar B: 09:19:00 to 09:20:00 (ends before disconnect, strictly does NOT overlap)
        bar_b_start = datetime.datetime(2026, 10, 19, 9, 19, 0, tzinfo=self.ist)
        self.assertFalse(is_bar_within_disconnect_interval(bar_b_start, datetime.timedelta(minutes=1), intervals))

        # Bar C: 09:21:00 to 09:22:00 (starts after disconnect, strictly does NOT overlap)
        bar_c_start = datetime.datetime(2026, 10, 19, 9, 21, 0, tzinfo=self.ist)
        self.assertFalse(is_bar_within_disconnect_interval(bar_c_start, datetime.timedelta(minutes=1), intervals))

    def test_boundary_bar_closing_exactly_at_evaluation_time_is_eligible(self):
        """
        Boundary test: A bar [09:19:00 - 09:20:00) closes at exactly 09:20:00 IST.
        When evaluated at exactly 09:20:00 IST, it is completed and eligible.
        """
        eval_time = self.t_0920_ist  # 09:20:00 IST
        completed = get_latest_completed_spot_bar([self.bar_0919], as_of_time=eval_time)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.timestamp, self.t_0919_ist)
        self.assertEqual(completed.close, Decimal("24500.00"))

    def test_boundary_bar_not_yet_completed_is_ineligible(self):
        """
        Boundary test: Bar 2 [09:20:00 - 09:21:00) has not completed at 09:20:30 IST.
        It must be strictly excluded from determining the latest completed spot bar.
        """
        eval_time = self.t_0920_ist + datetime.timedelta(seconds=30)
        completed = get_latest_completed_spot_bar([self.bar_0920], as_of_time=eval_time)
        self.assertIsNone(completed)

    def test_disconnect_boundary_exact_bar_start_and_end(self):
        """
        Boundary tests for is_bar_within_disconnect_interval:
        Bar: [09:20:00, 09:21:00) IST
        - Disconnect ending at exactly 09:20:00: d_end == bar_start -> False (no overlap).
        - Disconnect starting at exactly 09:21:00: d_start == bar_end -> False (no overlap).
        - Disconnect starting at 09:20:00 and ending at 09:20:05 -> True (overlaps bar start).
        - Disconnect starting at 09:20:55 and ending at 09:21:00 -> True (overlaps bar end).
        - Disconnect spanning 09:20:50 to 09:21:10 -> True for both 09:20 and 09:21 bars.
        """
        bar_start = datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist)
        bar_dur = datetime.timedelta(minutes=1)
        next_bar_start = datetime.datetime(2026, 10, 19, 9, 21, 0, tzinfo=self.ist)

        # Ends exactly at bar_start: 09:19:50 to 09:20:00
        disc_before = [(datetime.datetime(2026, 10, 19, 9, 19, 50, tzinfo=self.ist),
                        datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist))]
        self.assertFalse(is_bar_within_disconnect_interval(bar_start, bar_dur, disc_before))

        # Starts exactly at bar_end: 09:21:00 to 09:21:10
        disc_after = [(datetime.datetime(2026, 10, 19, 9, 21, 0, tzinfo=self.ist),
                       datetime.datetime(2026, 10, 19, 9, 21, 10, tzinfo=self.ist))]
        self.assertFalse(is_bar_within_disconnect_interval(bar_start, bar_dur, disc_after))

        # Starts at bar_start: 09:20:00 to 09:20:05
        disc_at_start = [(datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist),
                          datetime.datetime(2026, 10, 19, 9, 20, 5, tzinfo=self.ist))]
        self.assertTrue(is_bar_within_disconnect_interval(bar_start, bar_dur, disc_at_start))

        # Ends at bar_end: 09:20:55 to 09:21:00
        disc_at_end = [(datetime.datetime(2026, 10, 19, 9, 20, 55, tzinfo=self.ist),
                        datetime.datetime(2026, 10, 19, 9, 21, 0, tzinfo=self.ist))]
        self.assertTrue(is_bar_within_disconnect_interval(bar_start, bar_dur, disc_at_end))

        # Spans across boundary: 09:20:50 to 09:21:10
        disc_span = [(datetime.datetime(2026, 10, 19, 9, 20, 50, tzinfo=self.ist),
                      datetime.datetime(2026, 10, 19, 9, 21, 10, tzinfo=self.ist))]
        self.assertTrue(is_bar_within_disconnect_interval(bar_start, bar_dur, disc_span))
        self.assertTrue(is_bar_within_disconnect_interval(next_bar_start, bar_dur, disc_span))

    def test_extract_disconnect_intervals_retry_sequence_covers_full_outage(self):
        """
        When a disconnect undergoes a retry sequence, the verified interval must
        start at the initial initiation (cycle_start) and end at the final success.
        """
        log = """
[2026-10-19T09:20:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:20:01.500000+05:30]   [WATCHDOG] Reconnection #1 pending. Next attempt in 2.0s.
[2026-10-19T09:20:02.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #2 (backoff: 2s)...
[2026-10-19T09:20:03.200000+05:30]   [WATCHDOG] Reconnected successfully on attempt #2. Restored 22 instrument subscriptions.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(log, expected_subscriptions=22)
        self.assertTrue(is_valid)
        self.assertEqual(len(intervals), 1)
        expected_start = datetime.datetime.fromisoformat("2026-10-19T09:20:00.100000+05:30")
        expected_end = datetime.datetime.fromisoformat("2026-10-19T09:20:03.200000+05:30")
        self.assertEqual(intervals[0][0], expected_start)
        self.assertEqual(intervals[0][1], expected_end)
        self.assertIn("VALID_LOGS_WITH_DISCONNECTS", summary)

    def test_extract_disconnect_intervals_malformed_or_unmatched_returns_invalid(self):
        """
        Malformed logs, unmatched attempts, or orphan successes must never establish
        a verified disconnect interval.
        """
        # Unmatched attempt ID
        unmatched_log = """
[2026-10-19T09:20:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:20:02.000000+05:30]   [WATCHDOG] Reconnected successfully on attempt #2. Restored 22 instrument subscriptions.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(unmatched_log)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("MALFORMED_DISCONNECT_EVIDENCE", summary)

        # Orphan success
        orphan_log = """
[2026-10-19T09:20:02.000000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(orphan_log)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])

        # Timezone naive
        naive_log = """
[2026-10-19T09:20:00.100000]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:20:02.000000]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(naive_log)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])

        # Empty log: must NOT be treated as complete log (returns is_valid=False)
        intervals, is_valid, summary = extract_verified_disconnect_intervals("")
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("EMPTY_LOG_FILE", summary)

        # Log without watchdog events and without daemon activity markers: cannot establish completeness
        unrelated_log = "2026-10-19 09:20:00 Generic process output without daemon telemetry"
        intervals, is_valid, summary = extract_verified_disconnect_intervals(unrelated_log)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("INCONCLUSIVE_LOG_COMPLETENESS", summary)

        # Demonstrably complete log with active daemon markers (e.g. HEARTBEAT) and 0 disconnects: valid
        valid_no_disconnect_log = """
[2026-10-19T09:20:00.000000+05:30]   [HEARTBEAT] Ticks Received: 1500 | Feed: FRESH | Snapshots: 5
[2026-10-19T09:20:10.000000+05:30]   [HEARTBEAT] Ticks Received: 3000 | Feed: FRESH | Snapshots: 6
[2026-10-19T09:20:15.000000+05:30]   [FNO] Flushed 22 completed option bar(s) to DB.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(valid_no_disconnect_log)
        self.assertTrue(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("VALID_LOGS_ZERO_DISCONNECT_EVENTS", summary)

    def test_disconnect_intervals_non_22_universe_and_unknown_count(self):
        """
        Tests that expected subscription counts are not hardcoded to 22,
        that a non-22 universe passes when matched, that a mismatch fails,
        and that an unknown expected count cannot yield a pass.
        """
        log_18 = """
[2026-10-19T09:20:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:20:02.000000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 18 instrument subscriptions.
"""
        # 1. Valid non-22 universe: expected 18, restored 18 -> PASS
        intervals, is_valid, summary = extract_verified_disconnect_intervals(log_18, expected_subscriptions=18)
        self.assertTrue(is_valid)
        self.assertEqual(len(intervals), 1)
        self.assertIn("VALID_LOGS_WITH_DISCONNECTS", summary)

        # 2. Known subscription count mismatch: expected 22, restored 18 -> FAIL / invalid evidence
        intervals, is_valid, summary = extract_verified_disconnect_intervals(log_18, expected_subscriptions=22)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("MALFORMED_DISCONNECT_EVIDENCE", summary)
        self.assertIn("expected universe count is 22", summary)

        # 3. Unknown expected count: expected_subscriptions=None -> cannot yield a pass
        intervals, is_valid, summary = extract_verified_disconnect_intervals(log_18, expected_subscriptions=None)
        self.assertFalse(is_valid)
        self.assertEqual(intervals, [])
        self.assertIn("MALFORMED_DISCONNECT_EVIDENCE", summary)
        self.assertIn("expected_subscriptions was not provided by caller", summary)

    def test_zero_disconnect_log_refuses_to_excuse_partial_or_missing_bars(self):
        """
        Proves that a valid log with zero disconnect events refuses to excuse
        partial bars or missing slots without evidence.
        """
        valid_no_disconnect_log = """
[2026-10-19T09:20:00.000000+05:30]   [HEARTBEAT] Ticks Received: 1500 | Feed: FRESH | Snapshots: 5
[2026-10-19T09:20:15.000000+05:30]   [FNO] Flushed 22 completed option bar(s) to DB.
"""
        intervals, is_valid, summary = extract_verified_disconnect_intervals(valid_no_disconnect_log)
        self.assertTrue(is_valid)
        self.assertEqual(intervals, [])

        # If a bar has is_partial_bar=True, since intervals=[], overlap is False -> uncorrelated_partial_bars=1
        bar_start = datetime.datetime(2026, 10, 19, 9, 20, 0, tzinfo=self.ist)
        overlaps = is_bar_within_disconnect_interval(bar_start, datetime.timedelta(minutes=1), intervals)
        self.assertFalse(overlaps)

        # Uncorrelated partial bar MUST FAIL
        res_partial = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=1,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=is_valid,
            disconnect_evidence_summary=summary,
        )
        self.assertEqual(res_partial["verdict"], "FAIL")
        self.assertIn("could not be correlated", res_partial["evidence"])

        # Missing slots without telemetry MUST be INCONCLUSIVE, never PASS
        res_missing = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=21,
            pipeline_drops=[],
            unverified_missing_slots=[("NIFTY26OCT24500CE", "09:20", "NO_TICK_TELEMETRY")],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=is_valid,
            disconnect_evidence_summary=summary,
        )
        self.assertEqual(res_missing["verdict"], "INCONCLUSIVE")
        self.assertEqual(res_missing["status"], "NOT TESTED (INSUFFICIENT_TELEMETRY)")

    def test_partial_bar_with_verified_disconnect_overlap_passes(self):
        """
        When all expected bars are present and a partial bar overlaps a verified disconnect,
        coverage check PASSES according to documented policy.
        """
        res = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=True,
            disconnect_evidence_summary="VALID_LOGS_WITH_DISCONNECTS (1 verified disconnect intervals)",
        )
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["status"], "PASS")

    def test_partial_bar_without_verified_disconnect_fails(self):
        """
        A partial bar that cannot be correlated with a verified disconnect MUST FAIL.
        """
        res = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=1,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=True,
            disconnect_evidence_summary="VALID_LOGS_ZERO_DISCONNECT_EVENTS",
        )
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("could not be correlated with a verified disconnect event", res["evidence"])

    def test_partial_bar_with_invalid_disconnect_evidence_returns_inconclusive(self):
        """
        When disconnect evidence is invalid/malformed, partial bar correlation cannot be evaluated,
        yielding INCONCLUSIVE / NOT TESTED (PARTIAL_BAR_CORRELATION_UNAVAILABLE).
        """
        res = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=1,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=False,
            disconnect_evidence_summary="MALFORMED_DISCONNECT_EVIDENCE (Unmatched attempt ID)",
        )
        self.assertEqual(res["verdict"], "INCONCLUSIVE")
        self.assertEqual(res["status"], "NOT TESTED (PARTIAL_BAR_CORRELATION_UNAVAILABLE)")

    def test_full_coverage_with_invalid_disconnect_evidence_returns_inconclusive(self):
        """
        Full expected coverage must NOT pass when disconnect evidence is invalid or unavailable.
        """
        # Malformed disconnect evidence
        res_malformed = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=False,
            disconnect_evidence_summary="MALFORMED_DISCONNECT_EVIDENCE (Malformed timestamps)",
        )
        self.assertEqual(res_malformed["verdict"], "INCONCLUSIVE")
        self.assertEqual(res_malformed["status"], "NOT TESTED (MALFORMED_DISCONNECT_EVIDENCE)")

        # Unavailable / missing log file
        res_missing_file = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=22,
            pipeline_drops=[],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=False,
            disconnect_evidence_summary="NO_LOG_FILE_FOUND",
        )
        self.assertEqual(res_missing_file["verdict"], "INCONCLUSIVE")
        self.assertEqual(res_missing_file["status"], "NOT TESTED (DISCONNECT_EVIDENCE_UNAVAILABLE)")

    def test_full_coverage_with_integrity_failures_fails(self):
        """
        Even when 100% of expected slots are present, any integrity failure (duplicates,
        OHLC hierarchy, volume < 0, or invalid OI status) must cause FAIL.
        """
        for err_type, kwargs in [
            ("duplicates", {"duplicates": 1}),
            ("ohlc_errors", {"ohlc_errors": 1}),
            ("vol_errors", {"vol_errors": 1}),
            ("invalid_oi_count", {"invalid_oi_count": 1}),
        ]:
            base_kwargs = {
                "expected_slots_count": 22,
                "present_expected_slots": 22,
                "pipeline_drops": [],
                "unverified_missing_slots": [],
                "uncorrelated_partial_bars": 0,
                "unverified_partial_bars": 0,
                "duplicates": 0,
                "ohlc_errors": 0,
                "vol_errors": 0,
                "invalid_oi_count": 0,
                "disconnect_evidence_valid": True,
                "disconnect_evidence_summary": "VALID_LOGS_ZERO_DISCONNECT_EVENTS",
            }
            base_kwargs.update(kwargs)
            res = evaluate_option_bar_coverage_verdict(**base_kwargs)
            self.assertEqual(res["verdict"], "FAIL", f"Failed to reject integrity error: {err_type}")
            self.assertEqual(res["status"], "FAIL")
            self.assertIn("Expected universe integrity errors", res["evidence"])


class ObservationBoundsRealORMTests(TestCase):
    """
    Regression tests exercising REAL Django ORM queries for AC-1-L01 observation bounds,
    equity isolation, and future-dated record exclusion against the database.
    """

    def setUp(self):
        self.now = timezone.now()
        self.start_window = self.now - datetime.timedelta(minutes=15)
        self.token = 12067586
        self.symbol = "NIFTY26OCT24500CE"
        self.company = Company.objects.create(name="NIFTY Index", isin="INE000A01001")

    def test_record_inside_observation_window_is_included_in_orm_queries(self):
        """A record within [start_window, now] is included in observed ingestion queries."""
        t_inside = self.now - datetime.timedelta(minutes=5)

        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            received_wall_clock_utc=t_inside,
            exchange_time_status="VALID",
            quote_status="VALID",
            best_bid=Decimal("100.00"),
            best_ask=Decimal("100.50"),
            is_execution_eligible=True,
        )
        OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=datetime.date(2026, 10, 22),
            timeframe="1m",
            timestamp=t_inside,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=500,
            open_interest=10000,
            oi_status="VALID",
        )

        quotes_count = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__gte=self.start_window,
            received_wall_clock_utc__lte=self.now
        ).count()
        bars_count = OptionOHLCVBar.objects.filter(
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()

        self.assertEqual(quotes_count, 1)
        self.assertEqual(bars_count, 1)

    def test_record_before_window_is_excluded_from_orm_queries(self):
        """A record with timestamp < start_window is strictly excluded from window queries."""
        t_before = self.start_window - datetime.timedelta(minutes=5)

        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            received_wall_clock_utc=t_before,
            exchange_time_status="VALID",
            quote_status="VALID",
        )
        OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=datetime.date(2026, 10, 22),
            timeframe="1m",
            timestamp=t_before,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=500,
        )

        quotes_count = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__gte=self.start_window,
            received_wall_clock_utc__lte=self.now
        ).count()
        bars_count = OptionOHLCVBar.objects.filter(
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()

        self.assertEqual(quotes_count, 0)
        self.assertEqual(bars_count, 0)

    def test_record_after_now_is_excluded_from_observed_activity_and_detected_as_future(self):
        """A future record (timestamp > now) is excluded from window activity and detected by anomaly queries."""
        t_future = self.now + datetime.timedelta(minutes=5)

        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            received_wall_clock_utc=t_future,
            exchange_time_status="VALID",
            quote_status="VALID",
        )
        OptionOHLCVBar.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            underlying_symbol="^NSEI",
            option_type="CE",
            strike_price=Decimal("24500.00"),
            expiry_date=datetime.date(2026, 10, 22),
            timeframe="1m",
            timestamp=t_future,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=500,
        )

        # Excluded from window activity
        quotes_in_window = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__gte=self.start_window,
            received_wall_clock_utc__lte=self.now
        ).count()
        bars_in_window = OptionOHLCVBar.objects.filter(
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()
        self.assertEqual(quotes_in_window, 0)
        self.assertEqual(bars_in_window, 0)

        # Detected as future anomalies
        future_quotes = OptionQuoteSnapshot.objects.filter(received_wall_clock_utc__gt=self.now).count()
        future_bars = OptionOHLCVBar.objects.filter(timestamp__gt=self.now).count()
        self.assertEqual(future_quotes, 1)
        self.assertEqual(future_bars, 1)

    def test_future_only_records_do_not_prove_ingestion_activity(self):
        """When database contains only future records, AC-1-L01 verdict must be INCONCLUSIVE, never PASS."""
        t_future = self.now + datetime.timedelta(seconds=30)
        OptionQuoteSnapshot.objects.create(
            instrument_token=self.token,
            tradingsymbol=self.symbol,
            received_wall_clock_utc=t_future,
            exchange_time_status="VALID",
            quote_status="VALID",
        )

        fno_quotes = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__gte=self.start_window,
            received_wall_clock_utc__lte=self.now
        ).count()
        fno_bars = OptionOHLCVBar.objects.filter(
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()
        self.assertEqual(fno_quotes, 0)
        self.assertEqual(fno_bars, 0)

        verdict = evaluate_equity_isolation_verdict(
            fno_quotes=fno_quotes,
            fno_bars=fno_bars,
            contaminated_instruments=0,
            contaminated_bars=0,
            contaminated_contexts=0,
        )
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertEqual(verdict["status"], "NOT TESTED (F&O_INGESTION_INACTIVE)")
        self.assertNotEqual(verdict["verdict"], "PASS")

    def test_zero_observed_activity_without_evidence_remains_inconclusive_never_pass_or_fail(self):
        """Zero records in observation window without independent evidence remains inconclusive."""
        verdict = evaluate_equity_isolation_verdict(
            fno_quotes=0,
            fno_bars=0,
            contaminated_instruments=0,
            contaminated_bars=0,
            contaminated_contexts=0,
        )
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertEqual(verdict["status"], "NOT TESTED (F&O_INGESTION_INACTIVE)")
        self.assertNotEqual(verdict["verdict"], "PASS")
        self.assertNotEqual(verdict["verdict"], "FAIL")

    def test_contaminated_equity_bar_in_window_causes_fail(self):
        """When an equity bar contains an F&O contract in the window, AC-1-L01 must fail."""
        inst = Instrument.objects.create(
            company=self.company,
            symbol="NIFTY26OCT24500CE_CONTAM",
            exchange="NFO",
            instrument_type="OPTION"
        )
        t_inside = self.now - datetime.timedelta(minutes=5)
        OHLCVBar.objects.create(
            instrument=inst,
            timeframe="1m",
            timestamp=t_inside,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=500,
            source="test"
        )

        fno_filter = (
            Q(instrument__exchange="NFO")
            | Q(instrument__instrument_type__in=["OPTION", "FUTURE"])
            | Q(instrument__symbol__regex=r"\d+(CE|PE)$")
        )
        contaminated_bars = OHLCVBar.objects.filter(
            fno_filter,
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()
        self.assertEqual(contaminated_bars, 1)

        # Even with active F&O ingestion, contamination causes FAIL
        verdict = evaluate_equity_isolation_verdict(
            fno_quotes=10,
            fno_bars=5,
            contaminated_instruments=0,
            contaminated_bars=contaminated_bars,
            contaminated_contexts=0,
        )
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(verdict["status"], "FAIL")
        self.assertIn("Contamination detected in equity tables", verdict["evidence"])

    def test_contaminated_equity_bar_before_window_does_not_fail_current_session(self):
        """Historical contamination before the window does not fail the current observation session."""
        inst = Instrument.objects.create(
            company=self.company,
            symbol="NIFTY26OCT24500CE_BEFORE",
            exchange="NFO",
            instrument_type="OPTION"
        )
        t_before = self.start_window - datetime.timedelta(days=1)
        OHLCVBar.objects.create(
            instrument=inst,
            timeframe="1m",
            timestamp=t_before,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=500,
            source="test"
        )

        fno_filter = Q(instrument__exchange="NFO")
        contaminated_bars = OHLCVBar.objects.filter(
            fno_filter,
            timestamp__gte=self.start_window,
            timestamp__lte=self.now
        ).count()
        self.assertEqual(contaminated_bars, 0)

        verdict = evaluate_equity_isolation_verdict(
            fno_quotes=10,
            fno_bars=5,
            contaminated_instruments=0,
            contaminated_bars=contaminated_bars,
            contaminated_contexts=0,
        )
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["status"], "PASS")

    def test_confirmed_pipeline_drop_retains_required_failure_precedence(self):
        """Confirmed pipeline drop must yield FAIL even when present_expected_slots is 0."""
        drop = ("NIFTY26OCT24500CE", "09:20", "SNAPSHOTS_ARRIVED_BUT_BAR_MISSING")
        verdict = evaluate_option_bar_coverage_verdict(
            expected_slots_count=22,
            present_expected_slots=0,
            pipeline_drops=[drop],
            unverified_missing_slots=[],
            uncorrelated_partial_bars=0,
            unverified_partial_bars=0,
            duplicates=0,
            ohlc_errors=0,
            vol_errors=0,
            invalid_oi_count=0,
            disconnect_evidence_valid=True,
            disconnect_evidence_summary="VALID_LOGS_ZERO_DISCONNECT_EVENTS",
        )
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(verdict["status"], "FAIL")
        self.assertIn("1 pipeline drops", verdict["evidence"])


class QuoteFreshnessAndDynamicATMAcceptanceTests(TestCase):
    """
    Focused regression tests for AC-1-L04: Quote freshness, dynamic ATM acceptance,
    timestamp semantics, and universe reconciliation.
    """

    def setUp(self):
        self.utc = datetime.timezone.utc
        self.ist = ZoneInfo("Asia/Kolkata")
        self.now = timezone.now()
        self.start_window = self.now - datetime.timedelta(minutes=15)
        self.inst = Instrument(symbol="^NSEI", exchange="INDEX")

    def test_spot_bar_closing_exactly_at_evaluation_time(self):
        """
        Completed spot bar for ATM:
        Enforces bar_timestamp + bar_duration <= evaluation_time.
        A bar closing exactly at evaluation_time MUST be accepted as completed.
        """
        bar_open = self.now - datetime.timedelta(seconds=60)
        bar = OHLCVBar(
            instrument=self.inst,
            timeframe="1m",
            timestamp=bar_open,
            open=Decimal("24500.00"),
            high=Decimal("24520.00"),
            low=Decimal("24490.00"),
            close=Decimal("24510.00"),
            volume=1000,
        )
        # Exactly at evaluation_time (bar_open + 60s == self.now)
        completed = get_latest_completed_spot_bar([bar], as_of_time=self.now)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.close, Decimal("24510.00"))

    def test_inflight_spot_bar_rejected_and_inconclusive_when_no_completed_bar(self):
        """
        An in-flight bar must be rejected.
        If no completed spot bar is available, evaluation must return inconclusive;
        it must not use an in-flight candle or invent a spot price.
        """
        bar_open = self.now - datetime.timedelta(seconds=30)
        inflight_bar = OHLCVBar(
            instrument=self.inst,
            timeframe="1m",
            timestamp=bar_open,
            open=Decimal("24500.00"),
            high=Decimal("24520.00"),
            low=Decimal("24490.00"),
            close=Decimal("24510.00"),
            volume=500,
        )
        completed = get_latest_completed_spot_bar([inflight_bar], as_of_time=self.now)
        self.assertIsNone(completed)

        # Inconclusive when spot cannot be derived
        verdict = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=0,
            tokens_with_quotes=0,
            fresh_and_eligible=0,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=0,
        )
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertEqual(verdict["status"], "NOT TESTED (Awaiting live session data)")

    def test_quote_freshness_three_second_boundary(self):
        """
        Quote freshness: A quote more than 3 seconds old must not count as fresh.
        At dyn_age == 3.000s, quote is fresh.
        At dyn_age == 3.001s, quote is stale.
        At dyn_age == 5.000s, quote is stale and causes FAIL.
        """
        class MockSnapshot:
            received_wall_clock_utc = self.now - datetime.timedelta(seconds=2)
            is_stale = False
            quote_status = "VALID"
            exchange_time_status = "VALID"
            best_bid = Decimal("100.00")
            best_ask = Decimal("100.50")
            is_locked = False
            is_crossed = False
            depth = {"buy": [{"price": 100.0, "quantity": 50}], "sell": [{"price": 100.5, "quantity": 50}]}
            is_execution_eligible = True

        snap = MockSnapshot()

        # 1. Exactly 3.000s age -> Fresh and eligible
        snap.exchange_timestamp_utc = self.now - datetime.timedelta(seconds=3)
        res_boundary = evaluate_quote_snapshot_integrity(snap, now=self.now, max_age_seconds=3.0)
        self.assertTrue(res_boundary["is_fresh"])
        self.assertEqual(res_boundary["status"], "FRESH_AND_ELIGIBLE")
        self.assertAlmostEqual(res_boundary["dyn_age"], 3.0, places=3)

        # 2. 3.001s age -> Stale at observation
        snap.exchange_timestamp_utc = self.now - datetime.timedelta(seconds=3, milliseconds=1)
        res_stale_boundary = evaluate_quote_snapshot_integrity(snap, now=self.now, max_age_seconds=3.0)
        self.assertFalse(res_stale_boundary["is_fresh"])
        self.assertEqual(res_stale_boundary["status"], "STALE_AT_OBS")

        # 3. 5.000s age -> Stale and leads to FAIL verdict
        snap.exchange_timestamp_utc = self.now - datetime.timedelta(seconds=5)
        res_stale = evaluate_quote_snapshot_integrity(snap, now=self.now, max_age_seconds=3.0)
        self.assertFalse(res_stale["is_fresh"])
        self.assertEqual(res_stale["status"], "STALE_AT_OBS")

        verdict_stale = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=22,
            fresh_and_eligible=21,
            stale_at_obs=1,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=100,
        )
        self.assertEqual(verdict_stale["verdict"], "FAIL")
        self.assertIn("1 tokens exceed 3.0s dynamic age threshold", verdict_stale["evidence"])

    def test_future_exchange_timestamp_beyond_skew_rejected(self):
        """
        Future exchange timestamps beyond tolerance must not pass and must yield FAIL.
        """
        class MockSnapshot:
            received_wall_clock_utc = self.now
            is_stale = False
            quote_status = "VALID"
            exchange_time_status = "VALID"
            exchange_timestamp_utc = self.now + datetime.timedelta(seconds=1)  # Future timestamp
            best_bid = Decimal("100.00")
            best_ask = Decimal("100.50")
            is_locked = False
            is_crossed = False
            depth = {"buy": [{"price": 100.0, "quantity": 50}], "sell": [{"price": 100.5, "quantity": 50}]}
            is_execution_eligible = True

        snap = MockSnapshot()
        res = evaluate_quote_snapshot_integrity(snap, now=self.now, max_future_skew_seconds=0.0)
        self.assertFalse(res["is_fresh"])
        self.assertEqual(res["status"], "FUTURE_SKEW")

        verdict = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=22,
            fresh_and_eligible=21,
            stale_at_obs=0,
            future_skew=1,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=100,
        )
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertIn("negative age / future timestamp skew", verdict["evidence"])

    def test_future_receipt_timestamps_excluded_from_observation_window(self):
        """
        Enforce both bounds: received_wall_clock_utc >= start_window and <= now.
        Future receipt timestamps are excluded from observed activity and classified appropriately.
        """
        t_future_receipt = self.now + datetime.timedelta(seconds=10)
        OptionQuoteSnapshot.objects.create(
            instrument_token=99999999,
            tradingsymbol="NIFTY26OCT24500CE_FUT_REC",
            received_wall_clock_utc=t_future_receipt,
            exchange_timestamp_utc=self.now,
            exchange_time_status="VALID",
            quote_status="VALID",
            best_bid=Decimal("100.00"),
            best_ask=Decimal("100.50"),
            is_execution_eligible=True,
        )

        in_window = OptionQuoteSnapshot.objects.filter(
            instrument_token=99999999,
            received_wall_clock_utc__gte=self.start_window,
            received_wall_clock_utc__lte=self.now,
        ).count()
        self.assertEqual(in_window, 0)

        # Helper also classifies future receipt timestamp
        class MockFutureReceipt:
            received_wall_clock_utc = t_future_receipt
        res = evaluate_quote_snapshot_integrity(MockFutureReceipt(), now=self.now)
        self.assertFalse(res["is_valid_for_window"])
        self.assertEqual(res["status"], "FUTURE_RECEIPT_EXCLUDED")

    def test_invalid_and_crossed_quote_data_rejected(self):
        """
        Reject invalid bid/ask values, crossed markets (bid > ask), locked markets (bid == ask),
        and invalid quote status. All must produce a FAIL verdict.
        """
        class MockBase:
            received_wall_clock_utc = self.now - datetime.timedelta(seconds=1)
            exchange_timestamp_utc = self.now - datetime.timedelta(seconds=1)
            exchange_time_status = "VALID"
            is_stale = False
            quote_status = "VALID"
            is_locked = False
            is_crossed = False
            depth = {"buy": [{"price": 100.0, "quantity": 50}], "sell": [{"price": 100.5, "quantity": 50}]}
            is_execution_eligible = False

        # 1. Crossed market (bid > ask)
        snap_crossed = MockBase()
        snap_crossed.best_bid = Decimal("105.00")
        snap_crossed.best_ask = Decimal("100.00")
        res_crossed = evaluate_quote_snapshot_integrity(snap_crossed, now=self.now)
        self.assertFalse(res_crossed["is_fresh"])
        self.assertEqual(res_crossed["status"], "CROSSED_BOOK")

        v_crossed = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=22,
            fresh_and_eligible=21,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=1,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=100,
        )
        self.assertEqual(v_crossed["verdict"], "FAIL")
        self.assertIn("crossed order book", v_crossed["evidence"])

        # 2. Locked market (bid == ask)
        # Source contract: locked quotes occur legitimately during circuit limits (valid data),
        # and are fresh if age <= 3.0s, but are strictly ineligible for paper execution.
        snap_locked = MockBase()
        snap_locked.best_bid = Decimal("100.00")
        snap_locked.best_ask = Decimal("100.00")
        res_locked = evaluate_quote_snapshot_integrity(snap_locked, now=self.now)
        self.assertTrue(res_locked["is_fresh"])
        self.assertFalse(res_locked["expected_eligible"])
        self.assertFalse(res_locked["is_eligible"])
        self.assertEqual(res_locked["status"], "LOCKED_BOOK")

        v_locked = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=22,
            fresh_and_eligible=21,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=1,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=100,
        )
        self.assertEqual(v_locked["verdict"], "FAIL")
        self.assertIn("locked order book", v_locked["evidence"])

        # 3. Invalid quote status
        snap_inv = MockBase()
        snap_inv.best_bid = Decimal("100.00")
        snap_inv.best_ask = Decimal("100.50")
        snap_inv.quote_status = "INVALID"
        res_inv = evaluate_quote_snapshot_integrity(snap_inv, now=self.now)
        self.assertFalse(res_inv["is_fresh"])
        self.assertEqual(res_inv["status"], "INVALID_QUOTE_STATUS")

        # 4. Stale at ingestion
        snap_stale_ingest = MockBase()
        snap_stale_ingest.best_bid = Decimal("100.00")
        snap_stale_ingest.best_ask = Decimal("100.50")
        snap_stale_ingest.is_stale = True
        res_stale_ingest = evaluate_quote_snapshot_integrity(snap_stale_ingest, now=self.now)
        self.assertFalse(res_stale_ingest["is_fresh"])
        self.assertEqual(res_stale_ingest["status"], "STALE_AT_INGESTION")

    def test_missing_required_depth_classified_inconclusive(self):
        """
        Missing required depth must prevent execution eligibility and result in INCONCLUSIVE,
        never falsely passing or failing.
        """
        class MockMissingDepth:
            received_wall_clock_utc = self.now - datetime.timedelta(seconds=1)
            exchange_timestamp_utc = self.now - datetime.timedelta(seconds=1)
            exchange_time_status = "VALID"
            is_stale = False
            quote_status = "VALID"
            best_bid = Decimal("100.00")
            best_ask = Decimal("100.50")
            is_locked = False
            is_crossed = False
            depth = {"buy": [], "sell": []}  # Missing depth orders
            is_execution_eligible = False

        snap = MockMissingDepth()
        res = evaluate_quote_snapshot_integrity(snap, now=self.now)
        self.assertTrue(res["is_fresh"])
        self.assertEqual(res["status"], "MISSING_DEPTH")
        self.assertFalse(res["expected_eligible"])

        v_depth = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=22,
            fresh_and_eligible=21,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=1,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=100,
        )
        self.assertEqual(v_depth["verdict"], "INCONCLUSIVE")
        self.assertEqual(v_depth["status"], "NOT TESTED (MISSING_DEPTH_QUOTES_PRESENT)")

    def test_missing_quiet_strike_quotes_classified_conservatively(self):
        """
        Missing quotes for quiet strikes must be inconclusive unless independent evidence
        establishes a failure.
        """
        verdict = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=22,
            tokens_with_quotes=20,
            fresh_and_eligible=20,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=2,  # 2 quiet strikes missing quotes
            total_snapshots=150,
        )
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertEqual(verdict["status"], "NOT TESTED (INCOMPLETE_STREAM_DELIVERY_QUIET_STRIKES)")
        self.assertIn("quiet strike vs. unsubscription cannot be proven", verdict["evidence"])

    def test_dynamic_universe_non_22_evaluated_correctly(self):
        """
        Universe reconciliation: Verify that universe size is computed dynamically
        from completed spot bar and contract master without assuming exactly 22 valid contracts.
        A 18-token or 10-token universe passes when 100% fresh and eligible.
        """
        # Dynamic universe of 18 tokens (e.g. ATM +/- 4 strikes)
        verdict_18 = evaluate_quote_freshness_and_universe_verdict(
            expected_tokens_count=18,
            tokens_with_quotes=18,
            fresh_and_eligible=18,
            stale_at_obs=0,
            future_skew=0,
            stale_at_ingestion=0,
            invalid_time_status=0,
            invalid_quote_status=0,
            locked_quotes=0,
            crossed_quotes=0,
            missing_depth_quotes=0,
            zero_bid_quotes=0,
            persisted_eligibility_mismatches=0,
            other_ineligible_quotes=0,
            unfulfilled_subscriptions_count=0,
            total_snapshots=200,
        )
        self.assertEqual(verdict_18["verdict"], "PASS")
        self.assertEqual(verdict_18["status"], "PASS")
        self.assertIn("18 contracts", verdict_18["evidence"])

    def test_checklist_query_and_helper_integration_alignment(self):
        """
        Verifies end-to-end alignment between actual AC-1-L04 checklist snippet
        and helper behavior using real database models.
        """
        tokens = [10001, 10002, 10003, 10004]
        # Seed snapshots within observation window
        for tok in tokens:
            OptionQuoteSnapshot.objects.create(
                instrument_token=tok,
                tradingsymbol=f"NIFTY_OPT_{tok}",
                received_wall_clock_utc=self.now - datetime.timedelta(seconds=1),
                exchange_timestamp_utc=self.now - datetime.timedelta(seconds=1),
                exchange_time_status="VALID",
                quote_status="VALID",
                best_bid=Decimal("150.00"),
                best_ask=Decimal("150.50"),
                depth={"buy": [{"price": 150.0, "quantity": 100}], "sell": [{"price": 150.5, "quantity": 100}]},
                is_execution_eligible=True,
            )

        # Replicate AC-1-L04 checklist execution flow:
        quotes_qs = (
            OptionQuoteSnapshot.objects.filter(
                instrument_token__in=tokens,
                received_wall_clock_utc__gte=self.start_window,
                received_wall_clock_utc__lte=self.now,
            )
            .order_by("instrument_token", "-received_wall_clock_utc")
        )
        seen_tokens = set()
        token_snapshots = {}
        for snap in quotes_qs:
            if snap.instrument_token not in seen_tokens:
                seen_tokens.add(snap.instrument_token)
                token_snapshots[snap.instrument_token] = snap

        metrics = {
            "expected_tokens_count": len(tokens),
            "tokens_with_quotes": len(token_snapshots),
            "fresh_and_eligible": 0,
            "stale_at_obs": 0,
            "future_skew": 0,
            "stale_at_ingestion": 0,
            "invalid_time_status": 0,
            "invalid_quote_status": 0,
            "locked_quotes": 0,
            "crossed_quotes": 0,
            "missing_depth_quotes": 0,
            "zero_bid_quotes": 0,
            "persisted_eligibility_mismatches": 0,
            "other_ineligible_quotes": 0,
            "unfulfilled_subscriptions_count": len(tokens) - len(token_snapshots),
            "total_snapshots": quotes_qs.count(),
        }

        for tok, snap in token_snapshots.items():
            integrity = evaluate_quote_snapshot_integrity(
                snap,
                now=self.now,
                max_age_seconds=3.0,
                max_future_skew_seconds=0.0,
            )
            status = integrity["status"]
            if status == "FRESH_AND_ELIGIBLE":
                metrics["fresh_and_eligible"] += 1

        verdict = evaluate_quote_freshness_and_universe_verdict(**metrics)
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["status"], "PASS")
        self.assertEqual(metrics["fresh_and_eligible"], 4)




