"""
Configuration constants and thresholds for Phase 17D: Intraday Opportunity Engine.

All scoring weights, detection thresholds, confirmation parameters, and penalties
are defined here to ensure discoverability and prevent hardcoded magic numbers.
"""

from decimal import Decimal
from typing import Dict

# ── 1. Opportunity Score Component Weights (Total: 100%) ─────────────────────
# These weights govern the composite 0-100 opportunity score.
OPPORTUNITY_SCORE_WEIGHTS: Dict[str, Decimal] = {
    "momentum": Decimal("0.20"),          # Directional momentum persistence (5m/15m)
    "relative_strength": Decimal("0.20"), # Performance relative to NIFTY and Sector
    "volume": Decimal("0.15"),            # RVOL participation confirmation
    "vwap": Decimal("0.10"),              # Price position vs session VWAP
    "market_alignment": Decimal("0.10"),  # Alignment with broader NIFTY / breadth
    "sector_alignment": Decimal("0.10"),  # Alignment with sector trend
    "orb": Decimal("0.05"),               # 15m Opening range structure
    "data_quality": Decimal("0.10"),      # Data completeness, recency, and depth
}

from market.services.intraday_config import UNAVAILABLE_THRESHOLD_SEC

# ── 2. Candidate Eligibility & Filtering Thresholds ──────────────────────────
# Minimum criteria a stock must satisfy to be eligible for opportunity evaluation.
MIN_PRICE_INR = Decimal("10.0")
MAX_FRESHNESS_AGE_SECONDS = UNAVAILABLE_THRESHOLD_SEC       # Ineligible if data older than 180 seconds (3 mins)
MIN_CUMULATIVE_VOLUME = 1000            # Flag / exclude extreme low liquidity
MIN_INTRADAY_BARS_REQUIRED = 3          # At least three 1m/5m observations

# ── 3. Detection & Technical Thresholds ─────────────────────────────────────────
# Momentum thresholds (%)
MOMENTUM_MIN_5M_PCT = Decimal("0.20")
MOMENTUM_STRONG_5M_PCT = Decimal("0.50")
MOMENTUM_MIN_15M_PCT = Decimal("0.35")
MOMENTUM_STRONG_15M_PCT = Decimal("0.75")

# Relative Strength thresholds (%)
RS_MIN_OUTPERFORM_PCT = Decimal("0.30")
RS_STRONG_OUTPERFORM_PCT = Decimal("0.80")
RS_MIN_UNDERPERFORM_PCT = Decimal("-0.30")
RS_STRONG_UNDERPERFORM_PCT = Decimal("-0.80")

# Volume & RVOL thresholds
RVOL_CONFIRMED_THRESHOLD = Decimal("1.20")
RVOL_HIGH_CONFIRMED_THRESHOLD = Decimal("1.80")
RVOL_WEAK_THRESHOLD = Decimal("0.80")

# VWAP thresholds (%)
VWAP_PROXIMITY_PCT = Decimal("0.15")    # Within 0.15% is considered at VWAP
VWAP_TREND_MIN_PCT = Decimal("0.30")    # Distance confirming directional VWAP trend
VWAP_MEAN_REVERSION_EXTREME_PCT = Decimal("2.50") # Extreme stretch for mean-reversion context

# Opening Range Breakout (ORB) confirmation
ORB_BREAKOUT_BUFFER_PCT = Decimal("0.10") # Required margin beyond 15m high/low

# ── 4. Score Deductions & Penalties ───────────────────────────────────────────
PENALTY_STALE_DATA_POINTS = Decimal("25.0")
PENALTY_MISSING_SECTOR_POINTS = Decimal("15.0")
PENALTY_MISSING_INDEX_POINTS = Decimal("15.0")
PENALTY_WEAK_VOLUME_POINTS = Decimal("10.0")
PENALTY_MARKET_DIVERGENCE_POINTS = Decimal("12.0")
PENALTY_SECTOR_DIVERGENCE_POINTS = Decimal("10.0")

# ── 5. Confidence Weights ─────────────────────────────────────────────────────
CONFIDENCE_DATA_WEIGHT = Decimal("0.30")
CONFIDENCE_EVIDENCE_AGREEMENT_WEIGHT = Decimal("0.40")
CONFIDENCE_VOLUME_WEIGHT = Decimal("0.30")

# ── 6. State Transition Thresholds ────────────────────────────────────────────
# Minimum score thresholds required for opportunity states
STATE_CONFIRMED_MIN_SCORE = Decimal("70.0")
STATE_CONFIRMED_MIN_CONFIDENCE = Decimal("0.65")
STATE_EMERGING_MIN_SCORE = Decimal("50.0")
STATE_WEAKENING_SCORE_DROP = Decimal("10.0") # Drop from peak score to trigger WEAKENING

# ── 7. Ranking & Throttling Limits ───────────────────────────────────────────
DEFAULT_TOP_OPPORTUNITIES_LIMIT = 10
MAX_TOP_OPPORTUNITIES_LIMIT = 50
WS_OPPORTUNITY_THROTTLE_SEC = 2.0        # Broadcast at most once every 2 seconds
DB_SNAPSHOT_INTERVAL_SEC = 60.0          # Persist snapshots at most once every 60 seconds
SCORE_CHANGE_BROADCAST_THRESHOLD = Decimal("3.0") # Broadcast if score moves by >= 3 points
