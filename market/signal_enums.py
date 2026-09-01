"""
signal_enums.py — All signal/recommendation domain enumerations for Module 8.

These are deliberately not Django model choices so they can be imported freely
anywhere without triggering the ORM. Each enum has a .label property for
human-readable display.
"""
from enum import Enum


class SignalDirection(str, Enum):
    """Directional view of the recommendation."""
    BUY = "BUY"
    SELL = "SELL"
    NO_ACTION = "NO_ACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_READY = "NOT_READY"

    @property
    def label(self) -> str:
        return {
            "BUY": "Buy",
            "SELL": "Sell",
            "NO_ACTION": "No Action",
            "INSUFFICIENT_DATA": "Insufficient Data",
            "NOT_READY": "Not Ready",
        }[self.value]


class SignalHorizon(str, Enum):
    """Investment time horizon for a recommendation."""
    INTRADAY = "INTRADAY"
    DELIVERY_SWING = "DELIVERY_SWING"
    LONG_TERM = "LONG_TERM"


class SetupType(str, Enum):
    """
    Classification of the technical/fundamental setup pattern detected.

    Each setup requires explicit deterministic conditions to be met — a setup
    is never assumed to be active just because the enum value exists.
    """
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    PULLBACK = "PULLBACK"
    MOMENTUM = "MOMENTUM"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    FUNDAMENTAL_MOMENTUM = "FUNDAMENTAL_MOMENTUM"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    RECOVERY_REVERSAL = "RECOVERY_REVERSAL"
    MEAN_REVERSION = "MEAN_REVERSION"
    NONE = "NONE"

    # ── Intraday-only setups (Module 10) ──────────────────────────────────────
    # These MUST NOT be run against daily candles or used in daily detectors.
    OPENING_RANGE_BREAKOUT = "OPENING_RANGE_BREAKOUT"
    OPENING_RANGE_BREAKDOWN = "OPENING_RANGE_BREAKDOWN"
    INTRADAY_MOMENTUM_CONTINUATION = "INTRADAY_MOMENTUM_CONTINUATION"
    INTRADAY_PULLBACK = "INTRADAY_PULLBACK"
    VWAP_RECLAIM = "VWAP_RECLAIM"
    VWAP_REJECTION = "VWAP_REJECTION"
    INTRADAY_RANGE_BREAKOUT = "INTRADAY_RANGE_BREAKOUT"


class ConfidenceLevel(str, Enum):
    """
    Bounded confidence classification.

    CRITICAL: These labels do NOT represent probability of profit.
    They represent alignment of multiple deterministic evidence dimensions.
    LOW  = 1-2 dimensions aligned
    MEDIUM = 3 dimensions aligned
    HIGH = 4-5 dimensions aligned
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationStatus(str, Enum):
    """
    Lifecycle state of a recommendation.

    States are only transitioned when market data reliably confirms the event.
    No speculative transitions.
    """
    ACTIVE = "ACTIVE"          # Generated, not yet acted on
    TRIGGERED = "TRIGGERED"    # Price entered entry zone
    TARGET_HIT = "TARGET_HIT"  # Target price reached (confirmed by market data)
    STOPPED = "STOPPED"        # Stop loss hit (confirmed by market data)
    EXPIRED = "EXPIRED"        # Validity period elapsed without trigger
    INVALIDATED = "INVALIDATED"  # Setup conditions violated (market data changed)
    CANCELLED = "CANCELLED"    # Manually/programmatically cancelled
    # Module 11: same-bar ambiguity — stop AND target touched in same OHLC bar
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"


class ExitReason(str, Enum):
    """
    Reason a position was exited or considered closed.

    Used in RecommendationOutcome to record WHY the position ended.
    AMBIGUOUS_INTRABAR is set when both stop and target are touched in the
    same OHLC bar and bar-level ordering cannot be determined.
    """
    TARGET_HIT           = "TARGET_HIT"
    TARGET_2_HIT         = "TARGET_2_HIT"         # Intraday partial target 2
    STOP_HIT             = "STOP_HIT"
    EXPIRED_SESSION      = "EXPIRED_SESSION"       # Intraday: session close
    EXPIRED_MAX_DURATION = "EXPIRED_MAX_DURATION"  # Held too long (kill switch)
    AMBIGUOUS_INTRABAR   = "AMBIGUOUS_INTRABAR"    # Both stop+target in same bar
    CANCELLED            = "CANCELLED"             # Manually cancelled
    NO_ENTRY             = "NO_ENTRY"              # Entry was never triggered


class AmbiguityPolicy(str, Enum):
    """
    Policy for resolving same-bar ambiguity (stop and target touched in one bar).

    CONSERVATIVE: Treat as stop hit — worst case for the strategy.
                  This is the DEFAULT for honest backtesting.
    OPTIMISTIC:   Treat as target hit — best case (use only for sensitivity).
    EXCLUDE:      Exclude ambiguous outcomes from win rate and R calculations.
                  Ambiguous outcomes are still recorded.
    """
    CONSERVATIVE = "CONSERVATIVE"   # Stop wins (default)
    OPTIMISTIC   = "OPTIMISTIC"     # Target wins
    EXCLUDE      = "EXCLUDE"        # Exclude from aggregates


class EntryType(str, Enum):
    """Describes how the entry price/condition is determined."""
    BREAKOUT_CONFIRMATION = "BREAKOUT_CONFIRMATION"
    SUPPORT_RETEST = "SUPPORT_RETEST"
    MOMENTUM_CONFIRMATION = "MOMENTUM_CONFIRMATION"
    CURRENT_MARKET_PRICE = "CURRENT_MARKET_PRICE"
    LIMIT_ORDER_ZONE = "LIMIT_ORDER_ZONE"


class StopMethod(str, Enum):
    """Method used to derive the stop loss level."""
    STRUCTURAL = "STRUCTURAL"          # Recent swing low/high or key support/resistance
    ATR_BASED = "ATR_BASED"            # Multiple of ATR below/above entry
    SWING_HIGH_LOW = "SWING_HIGH_LOW"  # Recent N-day swing high or low
    PERCENTAGE_FALLBACK = "PERCENTAGE_FALLBACK"  # Only when structural stop unavailable


class TargetMethod(str, Enum):
    """Method used to derive the price target."""
    RESISTANCE_LEVEL = "RESISTANCE_LEVEL"    # Next structural resistance level
    MEASURED_MOVE = "MEASURED_MOVE"          # Pattern height projected from breakout
    ATR_MULTIPLE = "ATR_MULTIPLE"            # Entry ± N * ATR
    RISK_REWARD_DERIVED = "RISK_REWARD_DERIVED"  # Target = entry + N * risk


# ─── Minimum R:R thresholds ──────────────────────────────────────────────────
MIN_RISK_REWARD = {
    SignalHorizon.DELIVERY_SWING: 1.5,
    SignalHorizon.LONG_TERM: 2.0,
    SignalHorizon.INTRADAY: 1.5,
}

# ─── Confidence dimension weights ────────────────────────────────────────────
CONFIDENCE_WEIGHTS = {
    "technical_confirmation": 0.30,
    "market_alignment": 0.25,
    "sector_alignment": 0.20,
    "fundamental_support": 0.15,
    "news_support": 0.10,
}

# ─── Market regime multipliers for confidence ─────────────────────────────────
# These are gating adjustments, NOT score multiplications.
# Applied as additive/subtractive to the confirmation score.
REGIME_GATE_RULES = {
    "BULLISH_BUY_BOOST": 10.0,       # Bullish market aligns with BUY setups
    "BEARISH_BUY_PENALTY": -20.0,    # Bearish market penalises BUY confidence
    "HIGH_VOL_PENALTY": -10.0,       # High volatility reduces confidence on all
    "WEAK_SECTOR_PENALTY": -10.0,    # Deteriorating sector penalises BUY confidence
    "STRONG_SECTOR_BOOST": 5.0,      # Strong sector boosts BUY confidence
}

# ─── Confidence scoring thresholds ───────────────────────────────────────────
CONFIDENCE_THRESHOLD = {
    ConfidenceLevel.HIGH: 70.0,
    ConfidenceLevel.MEDIUM: 45.0,
    ConfidenceLevel.LOW: 0.0,
}

# ─── Module 11: Outcome tracking constants ───────────────────────────────────
# Minimum sample count before statistical warnings are suppressed
MIN_SAMPLE_FOR_STATS = 30
# Sample below this: SMALL_SAMPLE_WARNING is appended to any report
SMALL_SAMPLE_WARNING_THRESHOLD = 10
