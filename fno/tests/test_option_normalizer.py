"""
Unit Tests for AC-1-U02: OptionNormalizer.
Verifies 184-byte packet unpacking, OI semantics, sparse depth, locked/crossed quotes,
independent quote age, and execution eligibility.
"""

import struct
from datetime import datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from fno.services.option_normalizer import (
    DEPTH_ITEM_STRUCT,
    EXPECTED_PACKET_LEN,
    HEADER_STRUCT,
    OptionNormalizer,
    OptionTick,
)


def build_184_byte_packet(
    token=12067586,
    last_price=12550,     # 125.50
    last_qty=50,
    avg_price=12400,      # 124.00
    vol_traded=5000,
    buy_qty=2000,
    sell_qty=1800,
    open_p=11000,
    high_p=13000,
    low_p=10500,
    close_p=11200,
    last_trade_ts=1792135000,
    oi=150000,
    oi_high=160000,
    oi_low=140000,
    exch_ts=1792135005,
    bids=None,
    asks=None,
) -> bytes:
    """Helper to build an authentic 184-byte MODE_FULL binary packet."""
    header = HEADER_STRUCT.pack(
        token,
        last_price,
        last_qty,
        avg_price,
        vol_traded,
        buy_qty,
        sell_qty,
        open_p,
        high_p,
        low_p,
        close_p,
        last_trade_ts,
        oi,
        oi_high,
        oi_low,
        exch_ts
    )

    if bids is None:
        bids = [
            (250, 12540, 5), # 125.40
            (500, 12520, 8),
            (100, 12500, 2),
            (0, 0, 0),       # Sparse empty level
            (0, 0, 0),
        ]
    if asks is None:
        asks = [
            (300, 12560, 4), # 125.60
            (450, 12580, 6),
            (200, 12600, 3),
            (0, 0, 0),       # Sparse empty level
            (0, 0, 0),
        ]

    depth_bytes = bytearray()
    for qty, p, orders in bids[:5]:
        depth_bytes.extend(DEPTH_ITEM_STRUCT.pack(qty, p, orders))
    # Pad to 5 bids if needed
    while len(depth_bytes) < 60:
        depth_bytes.extend(DEPTH_ITEM_STRUCT.pack(0, 0, 0))

    for qty, p, orders in asks[:5]:
        depth_bytes.extend(DEPTH_ITEM_STRUCT.pack(qty, p, orders))
    while len(depth_bytes) < 120:
        depth_bytes.extend(DEPTH_ITEM_STRUCT.pack(0, 0, 0))

    return header + bytes(depth_bytes)


class TestOptionNormalizer(SimpleTestCase):
    """Test suite for OptionNormalizer meeting AC-1-U02."""

    def setUp(self):
        self.normalizer = OptionNormalizer()
        self.arrival_time = datetime.fromtimestamp(1792135006, tz=timezone.utc)
        self.arrival_monotonic = 100_000_000

    def test_unpack_valid_mode_full_packet(self):
        """Must correctly unpack fixed fields, depth, and compute temporal metrics."""
        packet = build_184_byte_packet(
            token=12067586,
            last_price=12550,
            exch_ts=1792135005,
            oi=50000,
        )
        self.assertEqual(len(packet), EXPECTED_PACKET_LEN)

        tick = self.normalizer.unpack_mode_full(
            packet, 
            received_wall_clock_utc=self.arrival_time,
            received_monotonic_ns=self.arrival_monotonic
        )

        self.assertEqual(tick.instrument_token, 12067586)
        self.assertEqual(tick.last_price, Decimal("125.50"))
        self.assertEqual(tick.average_price, Decimal("124.00"))
        self.assertEqual(tick.open_interest, 50000)
        self.assertEqual(tick.oi_status, "VALID")
        self.assertEqual(tick.best_bid, Decimal("125.40"))
        self.assertEqual(tick.best_ask, Decimal("125.60"))
        self.assertEqual(tick.bid_quantity_l1, 250)
        self.assertEqual(tick.ask_quantity_l1, 300)
        self.assertEqual(tick.quote_status, "VALID")
        self.assertFalse(tick.is_locked)
        self.assertFalse(tick.is_crossed)
        self.assertFalse(tick.is_stale)
        self.assertEqual(tick.exchange_time_status, "VALID")
        self.assertTrue(tick.is_execution_eligible)
        self.assertEqual(tick.quote_age_seconds, Decimal("1.0")) # 1792135006 - 1792135005

    def test_valid_zero_open_interest_semantics(self):
        """Reported OI of 0 must be preserved as 0 with ZERO_ACTIVITY status, NOT None."""
        packet = build_184_byte_packet(oi=0, oi_high=0, oi_low=0)
        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        
        self.assertEqual(tick.open_interest, 0)
        self.assertEqual(tick.oi_status, "ZERO_ACTIVITY")

    def test_unpopulated_open_interest_semantics(self):
        """Unpopulated/missing OI must be preserved as None with UNPOPULATED status."""
        packet = build_184_byte_packet(oi=-1) # raw negative or flag indicates unpopulated
        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        
        self.assertIsNone(tick.open_interest)
        self.assertEqual(tick.oi_status, "UNPOPULATED")

    def test_sparse_depth_handling(self):
        """Empty depth levels (qty=0, price=0) must be handled gracefully without index error."""
        bids = [(100, 12000, 2), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]
        asks = [(150, 12100, 3), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]
        packet = build_184_byte_packet(bids=bids, asks=asks)

        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertEqual(len(tick.depth["buy"]), 1)
        self.assertEqual(len(tick.depth["sell"]), 1)
        self.assertEqual(tick.best_bid, Decimal("120.00"))
        self.assertEqual(tick.best_ask, Decimal("121.00"))

    def test_locked_quote_classification(self):
        """When best_bid == best_ask, quote must be classified as LOCKED."""
        bids = [(100, 12500, 2)]
        asks = [(100, 12500, 2)] # Same price
        packet = build_184_byte_packet(bids=bids, asks=asks)

        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertTrue(tick.is_locked)
        self.assertFalse(tick.is_crossed)
        self.assertEqual(tick.quote_status, "LOCKED")
        self.assertFalse(tick.is_execution_eligible)

    def test_crossed_quote_classification(self):
        """When best_bid > best_ask, quote must be classified as CROSSED."""
        bids = [(100, 12600, 2)] # Bid higher than ask
        asks = [(100, 12500, 2)]
        packet = build_184_byte_packet(bids=bids, asks=asks)

        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertFalse(tick.is_locked)
        self.assertTrue(tick.is_crossed)
        self.assertEqual(tick.quote_status, "CROSSED")
        self.assertFalse(tick.is_execution_eligible)

    def test_future_skew_rejection(self):
        """Timestamps > 2.0s ahead of arrival wall clock must be marked FUTURE_SKEW_REJECTED."""
        # Exchange timestamp is 5.0 seconds ahead of arrival
        future_exch_ts = 1792135006 + 5
        packet = build_184_byte_packet(exch_ts=future_exch_ts)

        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertEqual(tick.exchange_time_status, "FUTURE_SKEW_REJECTED")
        self.assertFalse(tick.is_execution_eligible)

    def test_fallback_timestamp_never_certifies_freshness(self):
        """Packets lacking exchange timestamp fall back to arrival time but are NOT execution eligible."""
        packet = build_184_byte_packet(exch_ts=0) # Missing timestamp

        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertEqual(tick.exchange_time_status, "FALLBACK_TO_RECEIVED")
        self.assertFalse(tick.is_execution_eligible)

    def test_session_volume_reset_detection(self):
        """When volume_traded drops below previous volume, is_session_reset must be True."""
        packet1 = build_184_byte_packet(token=1001, vol_traded=50000)
        tick1 = self.normalizer.unpack_mode_full(packet1, received_wall_clock_utc=self.arrival_time)
        self.assertFalse(tick1.is_session_reset)

        # New session opens, volume resets to 100
        packet2 = build_184_byte_packet(token=1001, vol_traded=100)
        tick2 = self.normalizer.unpack_mode_full(packet2, received_wall_clock_utc=self.arrival_time)
        self.assertTrue(tick2.is_session_reset)

    def test_zero_bid_illiquid_quote_classification(self):
        """
        Illiquid contract with sellers (asks) but zero bids must be classified as ZERO_BID
        and must NEVER be execution eligible.
        """
        # 1. Binary packet
        packet = build_184_byte_packet(
            bids=[(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
            asks=[(100, 50, 1), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],  # Ask at 0.50
        )
        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertIsNone(tick.best_bid)
        self.assertEqual(tick.best_ask, Decimal("0.50"))
        self.assertEqual(tick.quote_status, "ZERO_BID")
        self.assertFalse(tick.is_execution_eligible)

        # 2. Dictionary tick
        dict_tick = {
            "instrument_token": 12067586,
            "last_price": 0.50,
            "volume_traded": 100,
            "oi": 150000,
            "timestamp": self.arrival_time,
            "depth": {
                "buy": [],
                "sell": [{"quantity": 100, "price": 0.50, "orders": 1}]
            }
        }
        tick_dict = self.normalizer.normalize_dict(dict_tick, received_wall_clock_utc=self.arrival_time)
        self.assertIsNone(tick_dict.best_bid)
        self.assertEqual(tick_dict.best_ask, Decimal("0.50"))
        self.assertEqual(tick_dict.quote_status, "ZERO_BID")
        self.assertFalse(tick_dict.is_execution_eligible)

    def test_empty_book_classification(self):
        """Empty books (no bids and no asks) must be classified as EMPTY_BOOK and not execution eligible."""
        packet = build_184_byte_packet(
            bids=[(0, 0, 0)] * 5,
            asks=[(0, 0, 0)] * 5,
        )
        tick = self.normalizer.unpack_mode_full(packet, received_wall_clock_utc=self.arrival_time)
        self.assertIsNone(tick.best_bid)
        self.assertIsNone(tick.best_ask)
        self.assertEqual(tick.quote_status, "EMPTY_BOOK")
        self.assertFalse(tick.is_execution_eligible)

    def test_normalize_dict_valid_tick(self):
        """Dictionary ticks emitted by KiteTicker must normalize identically to binary packets."""
        dict_tick = {
            "instrument_token": 12067586,
            "last_price": 125.50,
            "last_traded_quantity": 50,
            "average_traded_price": 124.00,
            "volume_traded": 5000,
            "buy_quantity": 2000,
            "sell_quantity": 1800,
            "ohlc": {"open": 110.0, "high": 130.0, "low": 105.0, "close": 112.0},
            "last_trade_time": datetime.fromtimestamp(1792135000, tz=timezone.utc),
            "oi": 150000,
            "oi_day_high": 160000,
            "oi_day_low": 140000,
            "timestamp": datetime.fromtimestamp(1792135005, tz=timezone.utc),
            "depth": {
                "buy": [{"quantity": 250, "price": 125.40, "orders": 5}],
                "sell": [{"quantity": 300, "price": 125.60, "orders": 4}],
            }
        }
        tick = self.normalizer.normalize_dict(dict_tick, received_wall_clock_utc=self.arrival_time)
        self.assertEqual(tick.instrument_token, 12067586)
        self.assertEqual(tick.last_price, Decimal("125.50"))
        self.assertEqual(tick.best_bid, Decimal("125.40"))
        self.assertEqual(tick.best_ask, Decimal("125.60"))
        self.assertEqual(tick.open_interest, 150000)
        self.assertEqual(tick.oi_status, "VALID")
        self.assertEqual(tick.quote_status, "VALID")
        self.assertTrue(tick.is_execution_eligible)
