"""
Configuration and Threshold Parameters for Phase 17C Intraday Market Context & Signal Foundation.

All thresholds and heuristics are declared explicitly here with zero magic numbers.
Can be overridden via Django settings or environment variables where applicable.
"""

from decimal import Decimal
from typing import Dict, Any

# ==============================================================================
# Data Freshness Thresholds (in seconds)
# ==============================================================================
FRESH_THRESHOLD_SEC = 5.0        # < 5s: Active streaming, highly reliable
STALE_THRESHOLD_SEC = 30.0       # 5s - 30s: Delayed or intermittent feed
UNAVAILABLE_THRESHOLD_SEC = 60.0 # > 60s: Disconnected or inactive feed

# ==============================================================================
# Market Breadth Thresholds
# ==============================================================================
UNCHANGED_TOLERANCE_PCT = Decimal("0.05") # Price change within ±0.05% counts as unchanged

# Advance / Decline Ratio thresholds
BREADTH_STRONG_RATIO = Decimal("2.0")  # A/D >= 2.0 -> Strong positive; <= 0.5 -> Strong negative
BREADTH_MODERATE_RATIO = Decimal("1.3") # A/D >= 1.3 -> Positive; <= 0.77 -> Negative

# Advance Percentage thresholds
BREADTH_STRONG_PCT = Decimal("70.0")   # >= 70% advancing
BREADTH_MODERATE_PCT = Decimal("55.0") # >= 55% advancing
BREADTH_WEAK_PCT = Decimal("45.0")     # <= 45% advancing

# Highs / Lows proximity threshold
PROXIMITY_TO_EXTREME_PCT = Decimal("0.25") # Within 0.25% of day high/low is considered at high/low

# ==============================================================================
# Relative Strength Thresholds (Stock vs NIFTY / Stock vs Sector)
# ==============================================================================
RS_STRONG_OUTPERFORM_PCT = Decimal("1.0")  # >= +1.0% excess return
RS_OUTPERFORM_PCT = Decimal("0.3")         # >= +0.3% excess return
RS_UNDERPERFORM_PCT = Decimal("-0.3")      # <= -0.3% excess return
RS_STRONG_UNDERPERFORM_PCT = Decimal("-1.0")# <= -1.0% excess return

# ==============================================================================
# Volume Confirmation Thresholds
# ==============================================================================
RVOL_CONFIRMED_HIGH = Decimal("1.2") # Relative volume >= 1.2x confirms move
RVOL_WEAK_LOW = Decimal("0.8")       # Relative volume < 0.8x indicates weak volume

# ==============================================================================
# Opening Range Breakout (ORB) Intervals (IST market time)
# ==============================================================================
ORB_5M_MINUTES = 5   # 09:15 to 09:20 IST
ORB_15M_MINUTES = 15 # 09:15 to 09:30 IST

# ==============================================================================
# Market Regime Classification Thresholds
# ==============================================================================
# NIFTY Day Range Volatility Thresholds (% of open)
REGIME_VOLATILE_RANGE_PCT = Decimal("1.5") # Day range > 1.5% is high volatility
REGIME_NIFTY_MOMENTUM_MIN_PCT = Decimal("0.2") # 15m momentum needed for trending

# ==============================================================================
# WebSocket Broadcast Frequencies (in seconds)
# ==============================================================================
WS_CONTEXT_THROTTLE_SEC = 1.0  # Throttle context broadcast to browser to 1Hz
WS_STOCKS_THROTTLE_SEC = 2.0   # Throttle full constituent table push to 0.5Hz

# ==============================================================================
# Intraday Opportunity Foundation Decomposition Weights
# (Total = 1.0; used for composite explainable intraday context score)
# ==============================================================================
CONTEXT_FOUNDATION_WEIGHTS: Dict[str, float] = {
    "momentum": 0.20,
    "relative_strength": 0.25,
    "volume_confirmation": 0.15,
    "vwap_alignment": 0.15,
    "sector_alignment": 0.15,
    "market_alignment": 0.10,
}
