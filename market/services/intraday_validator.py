"""
intraday_validator.py — Deterministic candle validation for intraday bars.

Rules:
  - OHLC relationships must be internally consistent
  - Volume must be non-negative
  - Timestamp must be UTC-aware
  - Timestamp must align to the timeframe grid (e.g. 5m bars land on :00/:05/:10/...)
  - Timestamp must fall within a valid market session (optional check)
  - Prices must be strictly positive
  - No silent repair — invalid bars are rejected with explicit errors

This module never mutates data. It only validates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from market.services.market_session import IndianMarketSession, INTRADAY_TIMEFRAME_MINUTES


@dataclass
class ValidationResult:
    """
    Result of a single candle validation.

    is_valid  — True if the bar can be safely persisted.
    errors    — Hard failures that make the bar invalid.
    warnings  — Soft flags (e.g. zero volume) that are logged but don't reject.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


def validate_intraday_bar(
    bar: Dict[str, Any],
    timeframe: str,
    check_session: bool = False,
) -> ValidationResult:
    """
    Validate a single intraday OHLCV bar dict.

    Expected bar keys: timestamp (datetime), open, high, low, close (Decimal or float), volume (int).
    timeframe examples: '5m', '15m', '1h'.
    check_session: if True, reject bars that fall outside a valid NSE trading session.

    Returns ValidationResult — does NOT raise on failure.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # ── Timeframe supported ────────────────────────────────────────────────────
    if timeframe not in INTRADAY_TIMEFRAME_MINUTES:
        errors.append(f"Unsupported intraday timeframe: '{timeframe}'. "
                      f"Supported: {sorted(INTRADAY_TIMEFRAME_MINUTES.keys())}")
        return ValidationResult(is_valid=False, errors=errors)

    interval_minutes = INTRADAY_TIMEFRAME_MINUTES[timeframe]

    # ── Timestamp ──────────────────────────────────────────────────────────────
    ts = bar.get("timestamp")
    if ts is None:
        errors.append("Missing timestamp field.")
        return ValidationResult(is_valid=False, errors=errors)
    if not isinstance(ts, datetime):
        errors.append(f"timestamp must be a datetime object, got {type(ts).__name__}.")
        return ValidationResult(is_valid=False, errors=errors)
    if ts.tzinfo is None:
        errors.append("Timestamp is timezone-naive. All intraday timestamps must be UTC-aware.")
        return ValidationResult(is_valid=False, errors=errors)

    # Timestamp grid alignment: minute component must be divisible by interval
    # E.g. 5m bars: 09:15, 09:20, ... (minute % 5 == 0 for absolute minutes from epoch is not right;
    # use: (hour * 60 + minute) % interval == 0 as a practical grid check)
    ts_utc = ts.astimezone(timezone.utc)
    # Align check against IST (since NSE session starts at 09:15 IST)
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    ts_ist = ts.astimezone(IST)
    total_minutes = ts_ist.hour * 60 + ts_ist.minute
    # For NSE: session opens at 09:15 (555 min from midnight). Check offset from open.
    session_open_minutes = 9 * 60 + 15  # 555
    offset_from_open = total_minutes - session_open_minutes
    if offset_from_open >= 0 and offset_from_open % interval_minutes != 0:
        errors.append(
            f"Timestamp {ts_ist.strftime('%H:%M')} IST does not align to the "
            f"{timeframe} grid (offset from 09:15 = {offset_from_open} min, "
            f"interval = {interval_minutes} min)."
        )

    # Future timestamp check (5-minute clock skew tolerance)
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    if ts_utc > now_utc + timedelta(minutes=5):
        errors.append(f"Future timestamp detected: {ts_utc.isoformat()} "
                      f"(current UTC: {now_utc.isoformat()}).")

    # Session check (optional)
    if check_session:
        session = IndianMarketSession.session_date_for_bar(ts_utc)
        if session is None:
            errors.append(
                f"Timestamp {ts_utc.isoformat()} does not fall within a valid "
                f"NSE trading session (weekday, non-holiday, 09:15–15:30 IST)."
            )

    # ── OHLCV values ──────────────────────────────────────────────────────────
    def _to_decimal(key: str) -> Optional[Decimal]:
        val = bar.get(key)
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            errors.append(f"Cannot convert {key}={val!r} to Decimal.")
            return None

    o = _to_decimal("open")
    h = _to_decimal("high")
    l = _to_decimal("low")
    c = _to_decimal("close")

    # Presence checks
    for name, val in [("open", o), ("high", h), ("low", l), ("close", c)]:
        if val is None:
            errors.append(f"Missing or unconvertible '{name}' field.")

    if errors:
        return ValidationResult(is_valid=False, errors=errors)

    # Strictly positive prices
    for name, val in [("open", o), ("high", h), ("low", l), ("close", c)]:
        if val <= 0:
            errors.append(f"Non-positive {name} price: {val}.")

    if errors:
        return ValidationResult(is_valid=False, errors=errors)

    # OHLC consistency
    if l > h:
        errors.append(f"low ({l}) > high ({h}): impossible OHLC relationship.")
    if o > h:
        errors.append(f"open ({o}) > high ({h}): impossible OHLC relationship.")
    if c > h:
        errors.append(f"close ({c}) > high ({h}): impossible OHLC relationship.")
    if o < l:
        errors.append(f"open ({o}) < low ({l}): impossible OHLC relationship.")
    if c < l:
        errors.append(f"close ({c}) < low ({l}): impossible OHLC relationship.")

    # ── Volume ─────────────────────────────────────────────────────────────────
    volume = bar.get("volume")
    if volume is None:
        errors.append("Missing 'volume' field.")
    else:
        try:
            volume = int(volume)
        except (TypeError, ValueError):
            errors.append(f"Cannot convert volume={volume!r} to int.")
            volume = None

    if volume is not None and volume < 0:
        errors.append(f"Negative volume: {volume}.")
    elif volume == 0:
        warnings.append("Zero volume bar — this may indicate a stale or missing candle.")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
