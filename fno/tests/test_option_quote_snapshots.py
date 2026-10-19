"""
Unit Tests for AC-1-U05: OptionQuoteSnapshot & OptionQuoteManager.
Verifies authentic quote snapshot persistence, depth JSONB, future-skew rejection,
fallback timestamp ineligibility, point-in-time retrieval, and retention purge.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.test import TestCase

from fno.models import OptionQuoteSnapshot
from fno.services.option_normalizer import OptionNormalizer, OptionTick
from fno.services.option_quote_manager import OptionQuoteManager


def make_quote_tick(
    token=12067586,
    bid=Decimal("125.40"),
    ask=Decimal("125.60"),
    bid_qty=250,
    ask_qty=300,
    depth=None,
    exch_status="VALID",
    quote_status="VALID",
    quote_age_s=Decimal("0.5"),
    is_eligible=True,
    arrival_utc=None,
    exch_utc=None,
) -> OptionTick:
    """Helper to instantiate OptionTick for quote snapshot tests."""
    arrival = arrival_utc or datetime(2026, 10, 15, 9, 20, 0, tzinfo=timezone.utc)
    exch = exch_utc or (arrival - timedelta(seconds=float(quote_age_s)))
    return OptionTick(
        instrument_token=token,
        last_price=Decimal("125.50"),
        last_quantity=25,
        average_price=Decimal("124.00"),
        volume_traded=5000,
        buy_quantity=2000,
        sell_quantity=1800,
        open=Decimal("120.00"),
        high=Decimal("128.00"),
        low=Decimal("119.00"),
        close=Decimal("125.50"),
        last_trade_timestamp_utc=exch,
        open_interest=100000,
        oi_day_high=105000,
        oi_day_low=98000,
        oi_status="VALID",
        exchange_timestamp_utc=exch,
        received_wall_clock_utc=arrival,
        received_monotonic_ns=0,
        exchange_time_status=exch_status,
        feed_latency_ms=int(quote_age_s * 1000),
        quote_age_seconds=quote_age_s,
        last_trade_age_seconds=quote_age_s,
        pipeline_latency_ms=Decimal("0.2"),
        best_bid=bid,
        best_ask=ask,
        bid_quantity_l1=bid_qty,
        ask_quantity_l1=ask_qty,
        depth=depth or {
            "buy": [{"quantity": 250, "price": "125.40", "orders": 5}],
            "sell": [{"quantity": 300, "price": "125.60", "orders": 4}],
        },
        quote_status=quote_status,
        is_stale=quote_age_s > Decimal("3.0"),
        is_locked=bid == ask and bid is not None,
        is_crossed=bid > ask if (bid and ask) else False,
        is_execution_eligible=is_eligible,
        is_session_reset=False,
    )


class TestOptionQuoteSnapshots(TestCase):
    """Test suite for OptionQuoteManager meeting AC-1-U05."""

    def test_record_and_retrieve_valid_quote_snapshot(self):
        """Must record depth JSONB, bid/ask, and support latest quote lookup."""
        arrival = datetime(2026, 10, 15, 9, 20, 0, tzinfo=timezone.utc)
        tick = make_quote_tick(arrival_utc=arrival)

        snapshot = OptionQuoteManager.record_quote_snapshot(tick, "NIFTY26O1524500CE")
        self.assertIsNotNone(snapshot.id)
        self.assertEqual(snapshot.instrument_token, 12067586)
        self.assertEqual(snapshot.tradingsymbol, "NIFTY26O1524500CE")
        self.assertEqual(snapshot.best_bid, Decimal("125.40"))
        self.assertEqual(snapshot.best_ask, Decimal("125.60"))
        self.assertEqual(snapshot.bid_quantity_l1, 250)
        self.assertEqual(snapshot.ask_quantity_l1, 300)
        self.assertTrue(snapshot.is_execution_eligible)
        self.assertIn("buy", snapshot.depth)
        self.assertIn("sell", snapshot.depth)

        # Retrieval check
        latest = OptionQuoteManager.get_latest_quote(12067586)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.id, snapshot.id)

    def test_fallback_timestamp_is_ineligible_for_execution(self):
        """A fallback timestamp must never certify freshness or allow execution."""
        arrival = datetime(2026, 10, 15, 9, 20, 0, tzinfo=timezone.utc)
        tick = make_quote_tick(
            exch_status="FALLBACK_TO_RECEIVED",
            is_eligible=False,
            arrival_utc=arrival,
        )

        snapshot = OptionQuoteManager.record_quote_snapshot(tick, "NIFTY26O1524500CE")
        self.assertEqual(snapshot.exchange_time_status, "FALLBACK_TO_RECEIVED")
        self.assertIsNone(snapshot.exchange_timestamp_utc)
        self.assertFalse(snapshot.is_execution_eligible)

    def test_future_skew_rejected_is_ineligible_for_execution(self):
        """Future-skewed timestamps must be flagged and rejected from execution."""
        arrival = datetime(2026, 10, 15, 9, 20, 0, tzinfo=timezone.utc)
        tick = make_quote_tick(
            exch_status="FUTURE_SKEW_REJECTED",
            is_eligible=False,
            arrival_utc=arrival,
        )

        snapshot = OptionQuoteManager.record_quote_snapshot(tick, "NIFTY26O1524500CE")
        self.assertEqual(snapshot.exchange_time_status, "FUTURE_SKEW_REJECTED")
        self.assertIsNone(snapshot.exchange_timestamp_utc)
        self.assertFalse(snapshot.is_execution_eligible)

    def test_point_in_time_quote_retrieval(self):
        """get_quote_at_timestamp must return the exact nearest quote preceding target_timestamp."""
        token = 12067586
        base_time = datetime(2026, 10, 15, 9, 30, 0, tzinfo=timezone.utc)

        # Record quote at T+0s
        t0 = make_quote_tick(token=token, bid=Decimal("100.00"), ask=Decimal("101.00"), arrival_utc=base_time)
        s0 = OptionQuoteManager.record_quote_snapshot(t0)

        # Record quote at T+2s
        t2 = make_quote_tick(token=token, bid=Decimal("102.00"), ask=Decimal("103.00"), arrival_utc=base_time + timedelta(seconds=2))
        s2 = OptionQuoteManager.record_quote_snapshot(t2)

        # Record quote at T+6s
        t6 = make_quote_tick(token=token, bid=Decimal("105.00"), ask=Decimal("106.00"), arrival_utc=base_time + timedelta(seconds=6))
        s6 = OptionQuoteManager.record_quote_snapshot(t6)

        # Query at T+3s -> must return s2 (T+2s), not s0 or s6
        query_time = base_time + timedelta(seconds=3)
        found = OptionQuoteManager.get_quote_at_timestamp(token, query_time, max_lookback_seconds=5)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, s2.id)
        self.assertEqual(found.best_bid, Decimal("102.00"))

    def test_purge_expired_quotes_retention_policy(self):
        """purge_expired_quotes must delete snapshots older than 5 days and retain newer ones."""
        token = 12067586
        now = datetime.now(timezone.utc)

        # Old quote: 6 days ago
        old_time = now - timedelta(days=6)
        t_old = make_quote_tick(token=token, arrival_utc=old_time)
        s_old = OptionQuoteManager.record_quote_snapshot(t_old)
        # Update row directly because auto_now_add on created_at or received_wall_clock_utc filter
        OptionQuoteSnapshot.objects.filter(id=s_old.id).update(received_wall_clock_utc=old_time)

        # Fresh quote: 1 day ago
        fresh_time = now - timedelta(days=1)
        t_fresh = make_quote_tick(token=token, arrival_utc=fresh_time)
        s_fresh = OptionQuoteManager.record_quote_snapshot(t_fresh)
        OptionQuoteSnapshot.objects.filter(id=s_fresh.id).update(received_wall_clock_utc=fresh_time)

        # Execute purge (5-day window)
        deleted = OptionQuoteManager.purge_expired_quotes(days=5)
        self.assertEqual(deleted, 1)

        # Verify old quote is deleted, fresh quote is retained
        self.assertFalse(OptionQuoteSnapshot.objects.filter(id=s_old.id).exists())
        self.assertTrue(OptionQuoteSnapshot.objects.filter(id=s_fresh.id).exists())
