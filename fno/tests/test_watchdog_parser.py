"""
Regression tests for single shared watchdog reconnection parser (AC-1-L03).
"""

from django.test import SimpleTestCase
from fno.services.log_parsers import evaluate_watchdog_log


class WatchdogParserTests(SimpleTestCase):
    """
    Validates that evaluate_watchdog_log correctly evaluates valid recoveries,
    timing violations, malformed timestamps, timezone-naive entries,
    and out-of-order events.
    """

    def test_valid_recovery_passes(self):
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["evidence"], "DATA_CHECK_PASS")
        self.assertEqual(len(res["pairs"]), 1)
        self.assertAlmostEqual(res["pairs"][0]["duration"], 1.720, places=3)
        self.assertEqual(res["pairs"][0]["count"], 22)

    def test_slow_recovery_fails(self):
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:05.600000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["evidence"], "DATA_CHECK_FAIL")
        self.assertGreater(res["pairs"][0]["duration"], 5.0)

    def test_duplicate_initiation_inconclusive(self):
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:02.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #2 (backoff: 2s)...
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (DUPLICATE_INITIATION_UNMATCHED)")
        self.assertEqual(res["status"], "NOT TESTED (DUPLICATE_INITIATION_UNMATCHED)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_orphan_success_inconclusive(self):
        log = """
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (ORPHAN_SUCCESS_EVENT)")
        self.assertEqual(res["status"], "NOT TESTED (ORPHAN_SUCCESS_EVENT)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_out_of_order_events_inconclusive(self):
        log = """
[2026-10-19T09:30:05.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.000000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (INVALID_CHRONOLOGICAL_ORDER)")
        self.assertEqual(res["status"], "NOT TESTED (INVALID_CHRONOLOGICAL_ORDER)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_timezone_naive_inconclusive(self):
        log = """
[2026-10-19T09:30:00.100000]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (MISSING_TIMEZONE_OFFSET)")
        self.assertEqual(res["status"], "NOT TESTED (MISSING_TIMEZONE_OFFSET)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_malformed_timestamp_inconclusive(self):
        log = """
[invalid_timestamp]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (MALFORMED_TIMESTAMPS)")
        self.assertEqual(res["status"], "NOT TESTED (MALFORMED_TIMESTAMPS)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_unrecognized_watchdog_event_inconclusive(self):
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Unknown watchdog internal failure / malformed message text
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (UNRECOGNIZED_WATCHDOG_EVENT)")
        self.assertEqual(res["status"], "NOT TESTED (UNRECOGNIZED_WATCHDOG_EVENT)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_malformed_event_with_valid_pair_inconclusive(self):
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
[2026-10-19T09:30:02.000000+05:30]   [WATCHDOG] Corrupt unparseable event text here
"""
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "INCONCLUSIVE (UNRECOGNIZED_WATCHDOG_EVENT)")
        self.assertEqual(res["status"], "NOT TESTED (UNRECOGNIZED_WATCHDOG_EVENT)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_empty_log_no_events(self):
        log = "No relevant lines in this log file.\n"
        res = evaluate_watchdog_log(log)
        self.assertEqual(res["verdict"], "NOT TESTED (NO_EVENTS)")
        self.assertEqual(res["status"], "NOT TESTED (NO_NATURAL_DISCONNECT)")

    def test_smaller_supported_universe_passes_when_configured(self):
        """When supported universe is smaller (e.g. 6 contracts), caller can configure expected count."""
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 6 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=6)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["pairs"][0]["count"], 6)

    def test_subscription_count_mismatch_fails_when_18_restored_for_22_expected(self):
        """Proves that 18 restored subscriptions when 22 are expected MUST fail and cannot produce PASS."""
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 18 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["evidence"], "DATA_CHECK_FAIL")
        self.assertIn("restored 18 subscriptions, but expected universe count is 22", res["details"])

    def test_unverified_subscription_count_without_expected_subscriptions_cannot_pass(self):
        """Proves that missing or unverified expected subscriptions never produces a PASS verdict."""
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=None)
        self.assertNotEqual(res["verdict"], "PASS")
        self.assertEqual(res["verdict"], "INCONCLUSIVE (UNVERIFIED_SUBSCRIPTION_COUNT)")
        self.assertEqual(res["status"], "NOT TESTED (UNVERIFIED_SUBSCRIPTION_COUNT)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_attempt_id_mismatch_cannot_pass(self):
        """Proves that initiation #1 followed by success #2 (mismatched attempt ID) cannot pass."""
        log = """
[2026-10-19T09:30:00.100000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.820000+05:30]   [WATCHDOG] Reconnected successfully on attempt #2. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertNotEqual(res["verdict"], "PASS")
        self.assertEqual(res["verdict"], "INCONCLUSIVE (ATTEMPT_ID_MISMATCH)")
        self.assertEqual(res["status"], "NOT TESTED (ATTEMPT_ID_MISMATCH)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_retry_sequence_with_successful_recovery_passes_within_threshold(self):
        """Proves that a valid retry sequence (attempt #1 pending, attempt #2 success) passes if total duration <= 5s."""
        log = """
[2026-10-19T09:30:00.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.000000+05:30]   [WATCHDOG] Reconnection #1 pending. Next attempt in 2.0s.
[2026-10-19T09:30:02.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #2 (backoff: 2s)...
[2026-10-19T09:30:03.500000+05:30]   [WATCHDOG] Reconnected successfully on attempt #2. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["evidence"], "DATA_CHECK_PASS")
        self.assertEqual(len(res["pairs"]), 1)
        self.assertAlmostEqual(res["pairs"][0]["duration"], 3.5, places=2)

    def test_retry_sequence_exceeding_threshold_fails(self):
        """Proves that a retry sequence taking > 5s from initial disconnect fails."""
        log = """
[2026-10-19T09:30:00.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.000000+05:30]   [WATCHDOG] Reconnection #1 pending. Next attempt in 2.0s.
[2026-10-19T09:30:04.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #2 (backoff: 2s)...
[2026-10-19T09:30:06.500000+05:30]   [WATCHDOG] Reconnected successfully on attempt #2. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["evidence"], "DATA_CHECK_FAIL")
        self.assertGreater(res["pairs"][0]["duration"], 5.0)

    def test_unresolved_retry_sequence_cannot_pass(self):
        """Proves that an incomplete retry sequence (pending without subsequent success) cannot pass."""
        log = """
[2026-10-19T09:30:00.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.000000+05:30]   [WATCHDOG] Reconnection #1 pending. Next attempt in 2.0s.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertNotEqual(res["verdict"], "PASS")
        self.assertEqual(res["verdict"], "INCONCLUSIVE (UNRESOLVED_RETRY_SEQUENCE)")
        self.assertEqual(res["status"], "NOT TESTED (UNRESOLVED_RETRY_SEQUENCE)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")

    def test_contradictory_pending_and_success_for_same_attempt_cannot_pass(self):
        """Proves that an attempt marked both pending and success is rejected as contradictory."""
        log = """
[2026-10-19T09:30:00.000000+05:30]   [WATCHDOG] Connection inactive. Attempting reconnect #1 (backoff: 1s)...
[2026-10-19T09:30:01.000000+05:30]   [WATCHDOG] Reconnection #1 pending. Next attempt in 2.0s.
[2026-10-19T09:30:01.500000+05:30]   [WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.
"""
        res = evaluate_watchdog_log(log, expected_subscriptions=22)
        self.assertNotEqual(res["verdict"], "PASS")
        self.assertEqual(res["verdict"], "INCONCLUSIVE (CONTRADICTORY_WATCHDOG_EVENTS)")
        self.assertEqual(res["evidence"], "DATA_CHECK_INCONCLUSIVE")
