"""
Regression tests for reconciliation log parser (AC-1-L05).
Validates pre-detection of relevant reconciliation messages and fail-safe invalidation.
"""

from decimal import Decimal
from django.test import SimpleTestCase
from fno.services.log_parsers import parse_reconciliation_events, evaluate_reconciliation_verdict


class ReconciliationParserTests(SimpleTestCase):
    """
    Validates that parse_reconciliation_events pre-detects relevant lines
    and that malformed, unrecognized, timezone-naive, or out-of-order events
    strictly prevent a PASS outcome.
    """

    def test_clean_single_reconciliation_event(self):
        log = """
[2026-10-19T09:30:00.000000+05:30] Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22 (ATM: 24500.0)
"""
        matches, error = parse_reconciliation_events(log)
        self.assertIsNone(error)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["active"], 22)
        self.assertEqual(matches[0]["atm"], Decimal("24500.0"))

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertTrue(verdict["can_pass"])
        self.assertEqual(verdict["status"], "VALID_LOG_EVENTS")
        self.assertEqual(verdict["evidence"], "DATA_CHECK_PASS")

    def test_clean_reconciliation_event_with_logger_prefix(self):
        log = """
[2026-10-19T09:30:00.123456+05:30] [fno.services.desired_universe] INFO: Universe reconciled: +2 subscribed, -2 unsubscribed. Active tokens: 22 (ATM: 24550.0)
"""
        matches, error = parse_reconciliation_events(log)
        self.assertIsNone(error)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["sub"], 2)
        self.assertEqual(matches[0]["unsub"], 2)
        self.assertEqual(matches[0]["active"], 22)
        self.assertEqual(matches[0]["atm"], Decimal("24550.0"))

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertTrue(verdict["can_pass"])

    def test_valid_event_followed_by_malformed_reconciliation_event_cannot_pass(self):
        """
        Required Fix 3: Synthetic regression case containing a valid reconciliation event
        followed by a malformed or unrecognized relevant reconciliation event.
        Assert that the result cannot be PASS and is reported as inconclusive or failed.
        """
        log = """
[2026-10-19T09:30:00.000000+05:30] Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22 (ATM: 24500.0)
[2026-10-19T09:31:00.000000+05:30] Universe reconciled: corrupt unparseable message text without active tokens
"""
        matches, error = parse_reconciliation_events(log)
        # Error must be detected because the second line has "Universe reconciled" but fails pattern
        self.assertIsNotNone(error)
        self.assertIn("Unrecognized or malformed reconciliation event text", error)
        self.assertEqual(len(matches), 0)

        # Verdict must strictly prevent PASS
        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertFalse(verdict["can_pass"])
        self.assertEqual(verdict["status"], "NOT TESTED (RECONCILIATION_EVIDENCE_INCONCLUSIVE)")
        self.assertEqual(verdict["evidence"], "DATA_CHECK_INCONCLUSIVE")
        self.assertIn("Reconciliation evidence invalidated", verdict["details"])

    def test_valid_event_followed_by_malformed_timestamp_cannot_pass(self):
        log = """
[2026-10-19T09:30:00.000000+05:30] Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22 (ATM: 24500.0)
[invalid_timestamp] Universe reconciled: +2 subscribed, -2 unsubscribed. Active tokens: 22 (ATM: 24550.0)
"""
        matches, error = parse_reconciliation_events(log)
        self.assertIsNotNone(error)
        self.assertIn("Malformed reconciliation timestamp", error)

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertFalse(verdict["can_pass"])
        self.assertEqual(verdict["status"], "NOT TESTED (RECONCILIATION_EVIDENCE_INCONCLUSIVE)")

    def test_valid_event_followed_by_timezone_naive_timestamp_cannot_pass(self):
        log = """
[2026-10-19T09:30:00.000000+05:30] Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22 (ATM: 24500.0)
[2026-10-19T09:31:00.000000] Universe reconciled: +2 subscribed, -2 unsubscribed. Active tokens: 22 (ATM: 24550.0)
"""
        matches, error = parse_reconciliation_events(log)
        self.assertIsNotNone(error)
        self.assertIn("Timezone-naive timestamp", error)

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertFalse(verdict["can_pass"])
        self.assertEqual(verdict["status"], "NOT TESTED (RECONCILIATION_EVIDENCE_INCONCLUSIVE)")

    def test_valid_event_followed_by_out_of_order_event_cannot_pass(self):
        log = """
[2026-10-19T09:30:00.000000+05:30] Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22 (ATM: 24500.0)
[2026-10-19T09:29:00.000000+05:30] Universe reconciled: +2 subscribed, -2 unsubscribed. Active tokens: 22 (ATM: 24550.0)
"""
        matches, error = parse_reconciliation_events(log)
        self.assertIsNotNone(error)
        self.assertIn("Out-of-order reconciliation event", error)

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertFalse(verdict["can_pass"])
        self.assertEqual(verdict["status"], "NOT TESTED (RECONCILIATION_EVIDENCE_INCONCLUSIVE)")

    def test_empty_log_returns_no_events_cannot_pass(self):
        log = "INFO: Ticker started.\nINFO: Feed running.\n"
        matches, error = parse_reconciliation_events(log)
        self.assertIsNone(error)
        self.assertEqual(len(matches), 0)

        verdict = evaluate_reconciliation_verdict(matches, error)
        self.assertFalse(verdict["can_pass"])
        self.assertEqual(verdict["status"], "NOT TESTED (NO_RECONCILIATION_EVENTS)")
