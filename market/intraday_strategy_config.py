"""
intraday_strategy_config.py — Versioned, explicit intraday strategy configuration.

All tunable parameters live here. Setup detectors and signal engine
read from this config — nothing is hardcoded inside detector logic.

Version history:
  1.0 — Module 10 initial release (2026-08)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

STRATEGY_VERSION = "1.0"

# ── Supported timeframes ───────────────────────────────────────────────────────

SUPPORTED_INTRADAY_TIMEFRAMES: List[str] = ["5m", "15m"]
DEFAULT_INTRADAY_TIMEFRAME: str = "5m"

# 1h is contextual only — not used as primary execution timeframe
CONTEXTUAL_TIMEFRAMES: List[str] = ["1h"]

# ── Session window definitions (minutes from session open, 09:15 IST) ─────────

SESSION_WINDOWS = {
    # window_name: (start_min_inclusive, end_min_exclusive)
    "OPENING":   (0,   30),    # 09:15–09:45 — OR formation
    "MORNING":   (30,  135),   # 09:45–11:30
    "MIDDAY":    (135, 225),   # 11:30–13:00 — typically lower volume
    "AFTERNOON": (225, 315),   # 13:00–14:30
    "CLOSING":   (315, 375),   # 14:30–15:30 — closing dynamics
}

# ── Indicator parameters (intraday-specific, NOT to be used on daily bars) ────

@dataclass(frozen=True)
class IndicatorParams:
    rsi_period: int = 7              # Faster RSI for intraday (daily uses 14)
    ema_fast: int = 9                # Fast EMA
    ema_slow: int = 21               # Slow EMA
    atr_period: int = 10             # ATR period for intraday stops
    adx_period: int = 10             # ADX for range detection
    macd_fast: int = 5               # MACD fast — intraday params
    macd_slow: int = 13              # MACD slow
    macd_signal: int = 3             # MACD signal
    bb_period: int = 20              # Bollinger Band period
    bb_std: float = 2.0              # Bollinger Band std deviation
    volume_lookback: int = 20        # Bars for avg volume
    rs_lookback: int = 20            # Bars for relative strength calc

INDICATOR_PARAMS = IndicatorParams()

# ── Opening Range configuration (per timeframe) ───────────────────────────────

OPENING_RANGE_MINUTES: Dict[str, int] = {
    "5m": 15,     # First 15 minutes = 3 bars
    "15m": 30,    # First 30 minutes = 2 bars
}

# ── Breakout / detection parameters ───────────────────────────────────────────

BREAKOUT_LOOKBACK_BARS: Dict[str, int] = {
    "5m": 20,
    "15m": 20,
}

# Minimum relative volume to confirm breakout/momentum
MIN_RELATIVE_VOLUME = 1.2

# Minimum relative volume to even trade (below this = dead tape)
MIN_TAPE_VOLUME = 0.5

# VWAP tolerance — price within X% of VWAP counts as "at VWAP"
VWAP_PROXIMITY_PCT = 0.003   # 0.3%

# ATR/price ratio above this signals extreme intraday volatility → no-trade
MAX_VOLATILITY_RATIO = 0.05  # 5%

# RSI bands for intraday
RSI_OVERSOLD = 35.0
RSI_OVERBOUGHT = 70.0
RSI_MOMENTUM_MIN = 50.0
RSI_MOMENTUM_MAX = 72.0
RSI_PULLBACK_MIN = 35.0
RSI_PULLBACK_MAX = 55.0

# ADX threshold — below this = ranging market (favour range strategies)
ADX_RANGE_THRESHOLD = 20.0

# ── Risk management ───────────────────────────────────────────────────────────

MIN_RISK_REWARD_INTRADAY: float = 1.5

# ATR multipliers for stop and target
STOP_ATR_MULTIPLIER: float = 1.5   # stop = entry ± 1.5 × ATR
TARGET_1_ATR_MULTIPLIER: float = 2.5
TARGET_2_ATR_MULTIPLIER: float = 4.0  # T2 — partial exit

# ── Lifecycle ─────────────────────────────────────────────────────────────────

# Maximum intraday holding in minutes before recommendation is considered stale
MAX_HOLDING_MINUTES: int = 180   # 3 hours

# Cooldown window — prevent repeated identical recommendations
COOLDOWN_MINUTES: int = 30

# ── Session filters per setup type ────────────────────────────────────────────
# Maps setup name → set of session windows where it is valid.
# Restricts setups to their statistically meaningful session windows.

SETUP_SESSION_FILTERS: Dict[str, Set[str]] = {
    "OPENING_RANGE_BREAKOUT":          {"MORNING", "MIDDAY"},        # Only valid after OR forms (09:45+)
    "OPENING_RANGE_BREAKDOWN":         {"MORNING", "MIDDAY"},
    "INTRADAY_MOMENTUM_CONTINUATION":  {"MORNING", "MIDDAY", "AFTERNOON"},
    "INTRADAY_PULLBACK":               {"MORNING", "MIDDAY", "AFTERNOON"},
    "VWAP_RECLAIM":                    {"MORNING", "MIDDAY", "AFTERNOON", "CLOSING"},
    "VWAP_REJECTION":                  {"MORNING", "MIDDAY", "AFTERNOON", "CLOSING"},
    "INTRADAY_RANGE_BREAKOUT":         {"MORNING", "MIDDAY", "AFTERNOON"},
}

# ── Minimum bars required before analysis ─────────────────────────────────────
# Must be >= max indicator period + lookback

MIN_BARS_FOR_ANALYSIS: Dict[str, int] = {
    "5m":  30,   # At least 2.5 hours of 5m history
    "15m": 20,   # At least 5 hours of 15m history
}

# Minimum bars for opening range to be considered "complete"
MIN_OR_BARS_COMPLETE: Dict[str, int] = {
    "5m":  3,   # 15 min / 5m = 3 bars
    "15m": 2,   # 30 min / 15m = 2 bars
}

# ── Regime Gate Rules ──────────────────────────────────────────────────────────
# Defines which market regimes allow / block intraday signals.
# If a regime is listed under 'block', no recommendation is generated.
# If a regime is not listed, all signals are allowed (permissive default).
#
# Regime values align with MarketContextSnapshot.regime field:
#   TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY

REGIME_GATE_RULES: Dict[str, list] = {
    # Setups allowed in all regimes except extreme illiquidity
    "OPENING_RANGE_BREAKOUT": {
        "allow": ["TRENDING_UP", "RANGING", "HIGH_VOLATILITY"],
        "block": [],
    },
    "OPENING_RANGE_BREAKDOWN": {
        "allow": ["TRENDING_DOWN", "RANGING", "HIGH_VOLATILITY"],
        "block": [],
    },
    "INTRADAY_MOMENTUM_CONTINUATION": {
        "allow": ["TRENDING_UP", "TRENDING_DOWN"],
        "block": ["RANGING", "LOW_VOLATILITY"],
    },
    "INTRADAY_PULLBACK": {
        "allow": ["TRENDING_UP"],
        "block": ["TRENDING_DOWN", "RANGING"],
    },
    "VWAP_RECLAIM": {
        "allow": ["TRENDING_UP", "RANGING"],
        "block": [],
    },
    "VWAP_REJECTION": {
        "allow": ["TRENDING_DOWN", "RANGING"],
        "block": [],
    },
    "INTRADAY_RANGE_BREAKOUT": {
        "allow": ["RANGING", "LOW_VOLATILITY"],
        "block": ["TRENDING_UP", "TRENDING_DOWN"],
    },
}

# ── Second target multiplier (intraday partial exits) ─────────────────────────
# target_2 = entry + ATR * TARGET_2_ATR_MULTIPLIER (bullish)
# target_2 = entry - ATR * TARGET_2_ATR_MULTIPLIER (bearish)
TARGET_2_ATR_MULTIPLIER: float = 3.0
