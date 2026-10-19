"""
F&O Option Normalizer Service.
Unpacks 184-byte KiteConnect MODE_FULL binary packets for NFO derivative contracts.
Enforces rigorous timestamp separation, quote classification, and missing-OI semantics.
"""

import logging
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fixed header structure for bytes 0-64 (16 4-byte integers = 64 bytes)
# >: Big Endian
# I: uint32 (token)
# i: int32 (last_price)
# i: int32 (last_quantity)
# i: int32 (average_price)
# I: uint32 (volume_traded)
# I: uint32 (buy_quantity)
# I: uint32 (sell_quantity)
# i: int32 (open)
# i: int32 (high)
# i: int32 (low)
# i: int32 (close)
# i: int32 (last_trade_time)
# i: int32 (oi)
# i: int32 (oi_day_high)
# i: int32 (oi_day_low)
# i: int32 (exchange_timestamp)
HEADER_STRUCT = struct.Struct(">IiiiIIIiiiiiiiii")

# Depth item structure: 12 bytes
# i: int32 (quantity)
# i: int32 (price)
# h: int16 (orders)
# 2x: 2 padding bytes
DEPTH_ITEM_STRUCT = struct.Struct(">iih2x")

EXPECTED_PACKET_LEN = 184


@dataclass
class OptionTick:
    """Canonical normalized option tick data contract."""
    instrument_token: int
    last_price: Decimal
    last_quantity: int
    average_price: Decimal              # Exchange session ATP (bytes 12-15)
    volume_traded: int
    buy_quantity: int
    sell_quantity: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    last_trade_timestamp_utc: Optional[datetime]
    open_interest: Optional[int]        # None if unpopulated; 0 if reported zero activity
    oi_day_high: Optional[int]
    oi_day_low: Optional[int]
    oi_status: str                      # "VALID", "ZERO_ACTIVITY", "UNPOPULATED"
    exchange_timestamp_utc: Optional[datetime]
    received_wall_clock_utc: datetime
    received_monotonic_ns: int
    exchange_time_status: str           # "VALID", "FALLBACK_TO_RECEIVED", "INVALID", "FUTURE_SKEW_REJECTED", "HISTORICAL_SKEW_REJECTED"
    feed_latency_ms: Optional[int]
    quote_age_seconds: Optional[Decimal] # Independent quote age from exchange ts
    last_trade_age_seconds: Optional[Decimal] # Independent age of last executed trade
    pipeline_latency_ms: Decimal
    best_bid: Optional[Decimal]
    best_ask: Optional[Decimal]
    bid_quantity_l1: Optional[int]
    ask_quantity_l1: Optional[int]
    depth: Dict[str, List[Dict[str, Any]]]
    quote_status: str                   # "VALID", "EMPTY_BOOK", "ZERO_BID", "STALE", "LOCKED", "CROSSED", "INVALID"
    is_stale: bool = False
    is_locked: bool = False
    is_crossed: bool = False
    is_execution_eligible: bool = False
    is_session_reset: bool = False


class OptionNormalizer:
    """
    Unpacks and defensively normalizes 184-byte binary MODE_FULL packets for NFO options.
    Guarantees strict isolation from equity normalizers and state managers.
    """

    def __init__(self):
        # Per-token state to track cumulative session volume resets
        self._last_volume_by_token: Dict[int, int] = {}

    def unpack_mode_full(
        self, 
        packet: bytes, 
        received_wall_clock_utc: Optional[datetime] = None,
        received_monotonic_ns: Optional[int] = None,
        oi_unpopulated_override: bool = False
    ) -> OptionTick:
        """
        Unpacks a single 184-byte binary packet.
        Throws ValueError if packet length is invalid.
        """
        if len(packet) != EXPECTED_PACKET_LEN:
            raise ValueError(
                f"Invalid NFO MODE_FULL packet length: expected {EXPECTED_PACKET_LEN} bytes, got {len(packet)} bytes"
            )

        # Capture arrival timestamps if not injected
        if received_wall_clock_utc is None:
            received_wall_clock_utc = datetime.now(timezone.utc)
        if received_monotonic_ns is None:
            received_monotonic_ns = time.monotonic_ns()

        # 1. Unpack 64-byte Header
        (
            token,
            raw_last_price,
            last_qty,
            raw_avg_price,
            vol_traded,
            buy_qty,
            sell_qty,
            raw_open,
            raw_high,
            raw_low,
            raw_close,
            last_trade_ts_raw,
            raw_oi,
            raw_oi_high,
            raw_oi_low,
            exch_ts_raw
        ) = HEADER_STRUCT.unpack_from(packet, 0)

        # Convert prices (scaled by 100.0)
        last_price = Decimal(raw_last_price) / Decimal("100.0")
        avg_price = Decimal(raw_avg_price) / Decimal("100.0")
        open_price = Decimal(raw_open) / Decimal("100.0")
        high_price = Decimal(raw_high) / Decimal("100.0")
        low_price = Decimal(raw_low) / Decimal("100.0")
        close_price = Decimal(raw_close) / Decimal("100.0")

        # 2. Open Interest Semantics (Keep None distinct from 0)
        if oi_unpopulated_override or raw_oi < 0:
            open_interest = None
            oi_day_high = None
            oi_day_low = None
            oi_status = "UNPOPULATED"
        elif raw_oi == 0:
            open_interest = 0
            oi_day_high = raw_oi_high if raw_oi_high >= 0 else 0
            oi_day_low = raw_oi_low if raw_oi_low >= 0 else 0
            oi_status = "ZERO_ACTIVITY"
        else:
            open_interest = raw_oi
            oi_day_high = raw_oi_high
            oi_day_low = raw_oi_low
            oi_status = "VALID"

        # 3. Timestamps & Temporal Metrics
        # Last trade timestamp
        last_trade_ts: Optional[datetime] = None
        if last_trade_ts_raw > 0:
            try:
                last_trade_ts = datetime.fromtimestamp(last_trade_ts_raw, tz=timezone.utc)
            except (ValueError, OverflowError):
                last_trade_ts = None

        # Exchange timestamp validation & status
        exch_ts: Optional[datetime] = None
        exchange_time_status = "VALID"

        if exch_ts_raw <= 0:
            # Fallback to received wall clock purely for queuing/ordering
            exch_ts = received_wall_clock_utc
            exchange_time_status = "FALLBACK_TO_RECEIVED"
        else:
            try:
                exch_ts = datetime.fromtimestamp(exch_ts_raw, tz=timezone.utc)
                delta_from_arrival = (exch_ts - received_wall_clock_utc).total_seconds()
                # Reject future skew > +2.0s
                if delta_from_arrival > 2.0:
                    exchange_time_status = "FUTURE_SKEW_REJECTED"
                elif delta_from_arrival < -86400.0: # Extreme historical replay
                    exchange_time_status = "HISTORICAL_SKEW_REJECTED"
                else:
                    exchange_time_status = "VALID"
            except (ValueError, OverflowError):
                exch_ts = received_wall_clock_utc
                exchange_time_status = "INVALID"

        # Metric 1: Feed Latency (transport delay)
        feed_latency_ms: Optional[int] = None
        if exch_ts and exchange_time_status == "VALID":
            feed_latency_ms = int((received_wall_clock_utc - exch_ts).total_seconds() * 1000)

        # Metric 2: Quote Age (measured strictly from exchange ts independently of last trade)
        quote_age_seconds: Optional[Decimal] = None
        if exch_ts and exchange_time_status == "VALID":
            quote_age_s = max(0.0, (received_wall_clock_utc - exch_ts).total_seconds())
            quote_age_seconds = Decimal(str(round(quote_age_s, 3)))

        # Metric 3: Last-Trade Age (time since last transaction)
        last_trade_age_seconds: Optional[Decimal] = None
        if last_trade_ts:
            trade_age_s = max(0.0, (received_wall_clock_utc - last_trade_ts).total_seconds())
            last_trade_age_seconds = Decimal(str(round(trade_age_s, 3)))

        # Metric 4: Pipeline Latency (monotonic duration)
        pipeline_duration_ns = max(0, time.monotonic_ns() - received_monotonic_ns)
        pipeline_latency_ms = Decimal(str(round(pipeline_duration_ns / 1_000_000.0, 3)))

        # 4. Parse 120-byte Depth (10 entries: 5 Bids + 5 Asks)
        bids: List[Dict[str, Any]] = []
        asks: List[Dict[str, Any]] = []
        offset = 64

        # 5 Bids (Buy levels)
        for _ in range(5):
            qty, raw_p, orders = DEPTH_ITEM_STRUCT.unpack_from(packet, offset)
            offset += 12
            if qty > 0 and raw_p > 0:
                p = Decimal(raw_p) / Decimal("100.0")
                bids.append({"quantity": qty, "price": p, "orders": orders})

        # 5 Asks (Sell levels)
        for _ in range(5):
            qty, raw_p, orders = DEPTH_ITEM_STRUCT.unpack_from(packet, offset)
            offset += 12
            if qty > 0 and raw_p > 0:
                p = Decimal(raw_p) / Decimal("100.0")
                asks.append({"quantity": qty, "price": p, "orders": orders})

        best_bid = bids[0]["price"] if bids else None
        bid_qty_l1 = bids[0]["quantity"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        ask_qty_l1 = asks[0]["quantity"] if asks else None

        depth_dict = {"buy": bids, "sell": asks}

        # 5. Quote Classification & Execution Eligibility
        is_stale = False
        if quote_age_seconds is not None and quote_age_seconds > Decimal("3.0"):
            is_stale = True

        is_locked = False
        is_crossed = False
        quote_status = "VALID"

        if last_price < Decimal("0.0"):
            quote_status = "INVALID"
        elif best_bid is None and best_ask is None:
            # Both sides empty
            quote_status = "EMPTY_BOOK"
        elif best_ask is not None and (best_bid is None or best_bid == Decimal("0.0")):
            # Asks exist, but zero positive bids in order book (zero-bid illiquid contract)
            quote_status = "ZERO_BID"
        elif best_bid is not None and best_ask is None:
            # Bids exist, but no ask (rare circuit / no-sellers condition)
            quote_status = "EMPTY_BOOK"
        elif best_bid is not None and best_ask is not None:
            if best_bid == best_ask:
                is_locked = True
                quote_status = "LOCKED"
            elif best_bid > best_ask:
                is_crossed = True
                quote_status = "CROSSED"
            elif is_stale:
                quote_status = "STALE"
            else:
                quote_status = "VALID"

        # Execution Eligibility Gate:
        # A quote is execution-eligible IF AND ONLY IF:
        # exchange_time_status == "VALID" AND quote_status == "VALID" AND NOT is_stale
        # NEVER treat a receipt-time fallback as proof of freshness!
        is_execution_eligible = (
            exchange_time_status == "VALID"
            and quote_status == "VALID"
            and not is_stale
            and quote_age_seconds is not None
            and quote_age_seconds <= Decimal("3.0")
        )

        # 6. Session Volume Reset Detection
        is_session_reset = False
        prev_vol = self._last_volume_by_token.get(token)
        if prev_vol is not None and vol_traded < prev_vol:
            is_session_reset = True
            logger.info(
                f"Session volume reset detected on token {token}: "
                f"prev={prev_vol}, new={vol_traded}"
            )
        self._last_volume_by_token[token] = vol_traded

        return OptionTick(
            instrument_token=token,
            last_price=last_price,
            last_quantity=last_qty,
            average_price=avg_price,
            volume_traded=vol_traded,
            buy_quantity=buy_qty,
            sell_quantity=sell_qty,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            last_trade_timestamp_utc=last_trade_ts,
            open_interest=open_interest,
            oi_day_high=oi_day_high,
            oi_day_low=oi_day_low,
            oi_status=oi_status,
            exchange_timestamp_utc=exch_ts,
            received_wall_clock_utc=received_wall_clock_utc,
            received_monotonic_ns=received_monotonic_ns,
            exchange_time_status=exchange_time_status,
            feed_latency_ms=feed_latency_ms,
            quote_age_seconds=quote_age_seconds,
            last_trade_age_seconds=last_trade_age_seconds,
            pipeline_latency_ms=pipeline_latency_ms,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_quantity_l1=bid_qty_l1,
            ask_quantity_l1=ask_qty_l1,
            depth=depth_dict,
            quote_status=quote_status,
            is_stale=is_stale,
            is_locked=is_locked,
            is_crossed=is_crossed,
            is_execution_eligible=is_execution_eligible,
            is_session_reset=is_session_reset,
        )

    def normalize_dict(
        self,
        raw_tick: Dict[str, Any],
        received_wall_clock_utc: Optional[datetime] = None,
        received_monotonic_ns: Optional[int] = None,
    ) -> OptionTick:
        """
        Normalizes a dictionary tick emitted by KiteConnect's KiteTicker WebSocket client.
        Enforces identical validation, OI handling, quote classification, and execution gating
        as the binary 184-byte normalizer.
        """
        if not raw_tick or "instrument_token" not in raw_tick:
            raise ValueError("Malformed WebSocket tick: missing instrument_token.")

        if received_wall_clock_utc is None:
            received_wall_clock_utc = datetime.now(timezone.utc)
        if received_monotonic_ns is None:
            received_monotonic_ns = time.monotonic_ns()

        token = int(raw_tick["instrument_token"])
        last_price_val = raw_tick.get("last_price")
        if last_price_val is None:
            raise ValueError(f"Missing last_price in tick for token {token}")
        last_price = Decimal(str(last_price_val))

        last_qty = int(raw_tick.get("last_traded_quantity", 0) or 0)
        avg_price = Decimal(str(raw_tick.get("average_traded_price", 0.0) or 0.0))
        vol_traded = int(raw_tick.get("volume_traded", raw_tick.get("volume", 0)) or 0)
        buy_qty = int(raw_tick.get("total_buy_quantity", raw_tick.get("buy_quantity", 0)) or 0)
        sell_qty = int(raw_tick.get("total_sell_quantity", raw_tick.get("sell_quantity", 0)) or 0)

        ohlc = raw_tick.get("ohlc", {}) or {}
        open_price = Decimal(str(ohlc.get("open", 0.0) or 0.0))
        high_price = Decimal(str(ohlc.get("high", 0.0) or 0.0))
        low_price = Decimal(str(ohlc.get("low", 0.0) or 0.0))
        close_price = Decimal(str(ohlc.get("close", 0.0) or 0.0))

        # 2. Open Interest Semantics
        raw_oi = raw_tick.get("oi")
        raw_oi_high = raw_tick.get("oi_day_high")
        raw_oi_low = raw_tick.get("oi_day_low")

        if raw_oi is None:
            open_interest = None
            oi_day_high = None
            oi_day_low = None
            oi_status = "UNPOPULATED"
        elif raw_oi == 0:
            open_interest = 0
            oi_day_high = int(raw_oi_high) if raw_oi_high is not None and raw_oi_high >= 0 else 0
            oi_day_low = int(raw_oi_low) if raw_oi_low is not None and raw_oi_low >= 0 else 0
            oi_status = "ZERO_ACTIVITY"
        else:
            open_interest = int(raw_oi)
            oi_day_high = int(raw_oi_high) if raw_oi_high is not None else None
            oi_day_low = int(raw_oi_low) if raw_oi_low is not None else None
            oi_status = "VALID"

        # 3. Timestamps & Temporal Metrics
        raw_last_trade = raw_tick.get("last_trade_time")
        last_trade_ts: Optional[datetime] = None
        if isinstance(raw_last_trade, datetime):
            last_trade_ts = raw_last_trade if raw_last_trade.tzinfo else raw_last_trade.replace(tzinfo=timezone.utc)
        elif isinstance(raw_last_trade, (int, float)) and raw_last_trade > 0:
            try:
                last_trade_ts = datetime.fromtimestamp(raw_last_trade, tz=timezone.utc)
            except (ValueError, OverflowError):
                last_trade_ts = None

        raw_exch_ts = raw_tick.get("exchange_timestamp") or raw_tick.get("timestamp")
        exch_ts: Optional[datetime] = None
        exchange_time_status = "VALID"

        if raw_exch_ts is None:
            exch_ts = received_wall_clock_utc
            exchange_time_status = "FALLBACK_TO_RECEIVED"
        elif isinstance(raw_exch_ts, datetime):
            exch_ts = raw_exch_ts if raw_exch_ts.tzinfo else raw_exch_ts.replace(tzinfo=timezone.utc)
            delta_from_arrival = (exch_ts - received_wall_clock_utc).total_seconds()
            if delta_from_arrival > 2.0:
                exchange_time_status = "FUTURE_SKEW_REJECTED"
            elif delta_from_arrival < -86400.0:
                exchange_time_status = "HISTORICAL_SKEW_REJECTED"
            else:
                exchange_time_status = "VALID"
        elif isinstance(raw_exch_ts, (int, float)) and raw_exch_ts > 0:
            try:
                exch_ts = datetime.fromtimestamp(raw_exch_ts, tz=timezone.utc)
                delta_from_arrival = (exch_ts - received_wall_clock_utc).total_seconds()
                if delta_from_arrival > 2.0:
                    exchange_time_status = "FUTURE_SKEW_REJECTED"
                elif delta_from_arrival < -86400.0:
                    exchange_time_status = "HISTORICAL_SKEW_REJECTED"
                else:
                    exchange_time_status = "VALID"
            except (ValueError, OverflowError):
                exch_ts = received_wall_clock_utc
                exchange_time_status = "INVALID"
        else:
            exch_ts = received_wall_clock_utc
            exchange_time_status = "FALLBACK_TO_RECEIVED"

        # Metric 1: Feed Latency
        feed_latency_ms: Optional[int] = None
        if exch_ts and exchange_time_status == "VALID":
            feed_latency_ms = int((received_wall_clock_utc - exch_ts).total_seconds() * 1000)

        # Metric 2: Quote Age
        quote_age_seconds: Optional[Decimal] = None
        if exch_ts and exchange_time_status == "VALID":
            quote_age_s = max(0.0, (received_wall_clock_utc - exch_ts).total_seconds())
            quote_age_seconds = Decimal(str(round(quote_age_s, 3)))

        # Metric 3: Last-Trade Age
        last_trade_age_seconds: Optional[Decimal] = None
        if last_trade_ts:
            trade_age_s = max(0.0, (received_wall_clock_utc - last_trade_ts).total_seconds())
            last_trade_age_seconds = Decimal(str(round(trade_age_s, 3)))

        # Metric 4: Pipeline Latency
        pipeline_duration_ns = max(0, time.monotonic_ns() - received_monotonic_ns)
        pipeline_latency_ms = Decimal(str(round(pipeline_duration_ns / 1_000_000.0, 3)))

        # 4. Parse Depth
        raw_depth = raw_tick.get("depth", {}) or {}
        raw_bids = raw_depth.get("buy", []) or []
        raw_asks = raw_depth.get("sell", []) or []

        bids: List[Dict[str, Any]] = []
        asks: List[Dict[str, Any]] = []

        for b in raw_bids[:5]:
            q = int(b.get("quantity", 0) or 0)
            p_val = b.get("price", 0.0) or 0.0
            p = Decimal(str(p_val))
            orders = int(b.get("orders", 0) or 0)
            if q > 0 and p > Decimal("0.0"):
                bids.append({"quantity": q, "price": p, "orders": orders})

        for a in raw_asks[:5]:
            q = int(a.get("quantity", 0) or 0)
            p_val = a.get("price", 0.0) or 0.0
            p = Decimal(str(p_val))
            orders = int(a.get("orders", 0) or 0)
            if q > 0 and p > Decimal("0.0"):
                asks.append({"quantity": q, "price": p, "orders": orders})

        best_bid = bids[0]["price"] if bids else None
        bid_qty_l1 = bids[0]["quantity"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        ask_qty_l1 = asks[0]["quantity"] if asks else None

        depth_dict = {"buy": bids, "sell": asks}

        # 5. Quote Classification & Execution Eligibility
        is_stale = False
        if quote_age_seconds is not None and quote_age_seconds > Decimal("3.0"):
            is_stale = True

        is_locked = False
        is_crossed = False
        quote_status = "VALID"

        if last_price < Decimal("0.0"):
            quote_status = "INVALID"
        elif best_bid is None and best_ask is None:
            quote_status = "EMPTY_BOOK"
        elif best_ask is not None and (best_bid is None or best_bid == Decimal("0.0")):
            quote_status = "ZERO_BID"
        elif best_bid is not None and best_ask is None:
            quote_status = "EMPTY_BOOK"
        elif best_bid is not None and best_ask is not None:
            if best_bid == best_ask:
                is_locked = True
                quote_status = "LOCKED"
            elif best_bid > best_ask:
                is_crossed = True
                quote_status = "CROSSED"
            elif is_stale:
                quote_status = "STALE"
            else:
                quote_status = "VALID"

        is_execution_eligible = (
            exchange_time_status == "VALID"
            and quote_status == "VALID"
            and not is_stale
            and quote_age_seconds is not None
            and quote_age_seconds <= Decimal("3.0")
        )

        is_session_reset = False
        prev_vol = self._last_volume_by_token.get(token)
        if prev_vol is not None and vol_traded < prev_vol:
            is_session_reset = True
            logger.info(
                f"Session volume reset detected on token {token}: "
                f"prev={prev_vol}, new={vol_traded}"
            )
        self._last_volume_by_token[token] = vol_traded

        return OptionTick(
            instrument_token=token,
            last_price=last_price,
            last_quantity=last_qty,
            average_price=avg_price,
            volume_traded=vol_traded,
            buy_quantity=buy_qty,
            sell_quantity=sell_qty,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            last_trade_timestamp_utc=last_trade_ts,
            open_interest=open_interest,
            oi_day_high=oi_day_high,
            oi_day_low=oi_day_low,
            oi_status=oi_status,
            exchange_timestamp_utc=exch_ts,
            received_wall_clock_utc=received_wall_clock_utc,
            received_monotonic_ns=received_monotonic_ns,
            exchange_time_status=exchange_time_status,
            feed_latency_ms=feed_latency_ms,
            quote_age_seconds=quote_age_seconds,
            last_trade_age_seconds=last_trade_age_seconds,
            pipeline_latency_ms=pipeline_latency_ms,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_quantity_l1=bid_qty_l1,
            ask_quantity_l1=ask_qty_l1,
            depth=depth_dict,
            quote_status=quote_status,
            is_stale=is_stale,
            is_locked=is_locked,
            is_crossed=is_crossed,
            is_execution_eligible=is_execution_eligible,
            is_session_reset=is_session_reset,
        )
