"""
setup_detectors.py — Deterministic setup pattern detectors for Module 8.

Each detector:
  1. Receives pre-loaded technical features (dict) and bars context
  2. Returns a structured SetupResult with conditions_met, conditions_failed,
     relevant_values, and a transparent score (0–100)
  3. Does NOT call any external service or LLM

All logic is explicit and auditable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from market.signal_enums import SetupType

logger = logging.getLogger(__name__)


@dataclass
class SetupResult:
    """
    Structured output from a single setup detector.

    Attributes:
        setup_type: Which pattern was evaluated
        detected: Whether the setup conditions are considered met
        score: 0–100 alignment score (NOT probability)
        conditions_met: Human-readable list of conditions that passed
        conditions_failed: Human-readable list of conditions that failed
        relevant_values: Key indicator values used in the evaluation
    """
    setup_type: SetupType
    detected: bool
    score: float
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    relevant_values: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "setup_type": self.setup_type.value,
            "detected": self.detected,
            "score": round(self.score, 2),
            "conditions_met": self.conditions_met,
            "conditions_failed": self.conditions_failed,
            "relevant_values": {k: (round(v, 4) if isinstance(v, float) else v)
                                for k, v in self.relevant_values.items()},
        }


def _safe(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Return val as float, or default if None/NaN."""
    if val is None:
        return default
    try:
        f = float(val)
        import math
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


# ─── BREAKOUT DETECTOR ────────────────────────────────────────────────────────

def detect_breakout(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    BREAKOUT — price approaching or clearing defined resistance with volume.

    Conditions required:
      1. Price within 2% of 20-day rolling high (near resistance) OR above it
      2. Relative volume > 1.2 (volume confirmation)
      3. RSI > 50 (momentum not exhausted)
      4. Price above SMA-50 (trend confirmation)

    Optional booster:
      - Price above SMA-200 (long-term trend alignment)
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma50 = _safe(tf.get("SMA_50"))
    sma200 = _safe(tf.get("SMA_200"))
    rel_vol = _safe(tf.get("relative_volume_20"), 1.0)
    rolling_high = _safe(tf.get("rolling_high_20"))

    score = 0.0

    # Condition 1 — Near or above 20-day high
    near_resistance = False
    if rolling_high and rolling_high > 0:
        pct_from_high = (close_f - rolling_high) / rolling_high
        if pct_from_high >= -0.02:  # Within 2% below or already breaking out
            near_resistance = True
            met.append(f"Price within 2% of 20-day high (dist={pct_from_high:.2%})")
            score += 30.0
        else:
            failed.append(f"Price too far from 20-day high (dist={pct_from_high:.2%})")
    else:
        failed.append("20-day rolling high unavailable")

    # Condition 2 — Volume confirmation
    if rel_vol is not None and rel_vol >= 1.2:
        met.append(f"Volume confirmation (rel_vol={rel_vol:.2f})")
        score += 25.0
    else:
        failed.append(f"Insufficient volume confirmation (rel_vol={rel_vol})")

    # Condition 3 — RSI momentum
    if rsi is not None and rsi > 50:
        met.append(f"Momentum not exhausted (RSI={rsi:.1f})")
        score += 25.0
    elif rsi is not None and rsi > 70:
        failed.append(f"RSI overbought — may be extended (RSI={rsi:.1f})")
        score -= 10.0
    else:
        failed.append(f"RSI below 50 (RSI={rsi})")

    # Condition 4 — Above SMA-50
    if sma50 and close_f > sma50:
        met.append(f"Above SMA-50 (close={close_f:.2f}, SMA50={sma50:.2f})")
        score += 15.0
    else:
        failed.append(f"Below SMA-50 (close={close_f:.2f}, SMA50={sma50})")

    # Optional — SMA-200
    if sma200 and close_f > sma200:
        met.append(f"Long-term trend confirmed (above SMA-200={sma200:.2f})")
        score += 5.0

    score = max(0.0, min(100.0, score))
    detected = near_resistance and (rel_vol is not None and rel_vol >= 1.2) and (rsi is not None and rsi > 50)

    return SetupResult(
        setup_type=SetupType.BREAKOUT,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma50": sma50, "sma200": sma200,
            "relative_volume": rel_vol, "rolling_high_20": rolling_high
        }
    )


# ─── BREAKDOWN DETECTOR ───────────────────────────────────────────────────────

def detect_breakdown(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    BREAKDOWN — price at/below support with volume, signalling SELL side.

    Conditions required:
      1. Price within 2% of 20-day rolling low OR already below
      2. Relative volume > 1.2 (distribution confirmation)
      3. RSI < 50 (downward momentum)
      4. Price below SMA-50 (trend in decline)
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma50 = _safe(tf.get("SMA_50"))
    rel_vol = _safe(tf.get("relative_volume_20"), 1.0)
    rolling_low = _safe(tf.get("rolling_low_20"))

    score = 0.0

    # Condition 1 — Near or below 20-day low
    near_support = False
    if rolling_low and rolling_low > 0:
        pct_from_low = (close_f - rolling_low) / rolling_low
        if pct_from_low <= 0.02:  # Within 2% above or already breaking
            near_support = True
            met.append(f"Price at/near 20-day low (dist={pct_from_low:.2%})")
            score += 30.0
        else:
            failed.append(f"Price too far from 20-day low (dist={pct_from_low:.2%})")
    else:
        failed.append("20-day rolling low unavailable")

    # Condition 2 — Volume
    if rel_vol is not None and rel_vol >= 1.2:
        met.append(f"Distribution volume (rel_vol={rel_vol:.2f})")
        score += 25.0
    else:
        failed.append(f"Low volume breakdown — unreliable (rel_vol={rel_vol})")

    # Condition 3 — RSI
    if rsi is not None and rsi < 50:
        met.append(f"Downward momentum (RSI={rsi:.1f})")
        score += 25.0
    else:
        failed.append(f"RSI not bearish (RSI={rsi})")

    # Condition 4 — Below SMA-50
    if sma50 and close_f < sma50:
        met.append(f"Below SMA-50 (close={close_f:.2f}, SMA50={sma50:.2f})")
        score += 20.0
    else:
        failed.append(f"Above SMA-50 — trend not bearish (close={close_f:.2f}, SMA50={sma50})")

    score = max(0.0, min(100.0, score))
    detected = near_support and (rel_vol is not None and rel_vol >= 1.2) and (rsi is not None and rsi < 50)

    return SetupResult(
        setup_type=SetupType.BREAKDOWN,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma50": sma50,
            "relative_volume": rel_vol, "rolling_low_20": rolling_low
        }
    )


# ─── PULLBACK DETECTOR ────────────────────────────────────────────────────────

def detect_pullback(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    PULLBACK — established uptrend + controlled retracement near support.

    Conditions required:
      1. Long-term trend is bullish: close > SMA-200
      2. Short-term retracement: close < SMA-20 but not catastrophically so (<5% below)
      3. Momentum stabilising: RSI between 35–55 (not oversold, not overbought)
      4. Price above SMA-50 or within 3% of it (structural support near)
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma20 = _safe(tf.get("SMA_20"))
    sma50 = _safe(tf.get("SMA_50"))
    sma200 = _safe(tf.get("SMA_200"))

    score = 0.0

    # Condition 1 — Established uptrend (above SMA-200)
    bullish_trend = sma200 is not None and close_f > sma200
    if bullish_trend:
        met.append(f"Long-term trend bullish (above SMA-200={sma200:.2f})")
        score += 35.0
    else:
        failed.append(f"No long-term uptrend (close={close_f:.2f}, SMA200={sma200})")

    # Condition 2 — Short-term retracement (below SMA-20 but not too far)
    retracing = False
    if sma20 and sma20 > 0:
        pct_from_sma20 = (close_f - sma20) / sma20
        if -0.05 <= pct_from_sma20 <= 0.02:  # Slight retracement zone
            retracing = True
            met.append(f"Healthy retracement near SMA-20 (dist={pct_from_sma20:.2%})")
            score += 25.0
        elif pct_from_sma20 < -0.05:
            failed.append(f"Deep retracement — may be more than pullback (dist={pct_from_sma20:.2%})")
        else:
            failed.append(f"No retracement — price above SMA-20 (dist={pct_from_sma20:.2%})")
    else:
        failed.append("SMA-20 unavailable")

    # Condition 3 — Momentum stabilising
    rsi_ok = rsi is not None and 35.0 <= rsi <= 55.0
    if rsi_ok:
        met.append(f"Momentum stabilising (RSI={rsi:.1f})")
        score += 25.0
    else:
        failed.append(f"RSI not in pullback zone 35–55 (RSI={rsi})")

    # Condition 4 — Support nearby (SMA-50)
    if sma50 and sma50 > 0:
        pct_from_sma50 = (close_f - sma50) / sma50
        if pct_from_sma50 >= -0.03:
            met.append(f"Near SMA-50 support (dist={pct_from_sma50:.2%})")
            score += 15.0
        else:
            failed.append(f"Below SMA-50 support zone (dist={pct_from_sma50:.2%})")
    else:
        failed.append("SMA-50 unavailable")

    score = max(0.0, min(100.0, score))
    detected = bullish_trend and retracing and rsi_ok

    return SetupResult(
        setup_type=SetupType.PULLBACK,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma20": sma20, "sma50": sma50, "sma200": sma200
        }
    )


# ─── MOMENTUM DETECTOR ────────────────────────────────────────────────────────

def detect_momentum(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    MOMENTUM — price in strong trend with confirming indicators.

    Conditions required:
      1. Trend alignment: close > SMA-50 AND SMA-50 > SMA-200
      2. RSI in momentum zone: 55–75
      3. Relative volume > 1.0 (not declining)
      4. MACD above signal line (directional confirmation)
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma50 = _safe(tf.get("SMA_50"))
    sma200 = _safe(tf.get("SMA_200"))
    rel_vol = _safe(tf.get("relative_volume_20"), 1.0)
    macd_line = _safe(tf.get("MACD_line"))
    macd_sig = _safe(tf.get("MACD_signal"))

    score = 0.0

    # Condition 1 — Trend alignment
    trend_aligned = sma50 is not None and sma200 is not None and close_f > sma50 and sma50 > sma200
    if trend_aligned:
        met.append(f"Golden cross alignment (close>{sma50:.2f}>SMA200={sma200:.2f})")
        score += 35.0
    elif sma50 and close_f > sma50:
        met.append(f"Above SMA-50 but SMA-50 not yet > SMA-200")
        score += 15.0
        failed.append("No golden cross — SMA50 not > SMA200")
    else:
        failed.append(f"No trend alignment (close={close_f:.2f}, SMA50={sma50})")

    # Condition 2 — RSI momentum zone
    rsi_ok = rsi is not None and 55.0 <= rsi <= 75.0
    if rsi_ok:
        met.append(f"RSI in momentum zone (RSI={rsi:.1f})")
        score += 30.0
    elif rsi is not None and rsi > 75:
        failed.append(f"RSI overbought — risk of reversal (RSI={rsi:.1f})")
        score -= 5.0
    else:
        failed.append(f"RSI not in momentum zone 55–75 (RSI={rsi})")

    # Condition 3 — Volume
    if rel_vol is not None and rel_vol >= 1.0:
        met.append(f"Supporting volume (rel_vol={rel_vol:.2f})")
        score += 20.0
    else:
        failed.append(f"Volume declining (rel_vol={rel_vol})")

    # Condition 4 — MACD
    if macd_line is not None and macd_sig is not None:
        if macd_line > macd_sig:
            met.append(f"MACD above signal ({macd_line:.4f} > {macd_sig:.4f})")
            score += 15.0
        else:
            failed.append(f"MACD below signal ({macd_line:.4f} < {macd_sig:.4f})")
    else:
        failed.append("MACD unavailable (insufficient history)")

    score = max(0.0, min(100.0, score))
    detected = trend_aligned and rsi_ok and (rel_vol is not None and rel_vol >= 1.0)

    return SetupResult(
        setup_type=SetupType.MOMENTUM,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma50": sma50, "sma200": sma200,
            "relative_volume": rel_vol, "macd_line": macd_line, "macd_signal": macd_sig
        }
    )


# ─── REVERSAL DETECTOR ────────────────────────────────────────────────────────

def detect_reversal(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    RECOVERY_REVERSAL — oversold condition with reversal confirmation signals.

    Conditions required:
      1. RSI < 35 (oversold territory)
      2. Price near 20-day low (extended on the downside)
      3. MACD histogram turning (signal of momentum shift) OR RSI divergence proxy
      4. Not in freefall: close not more than 30% below SMA-200

    This setup generates a BUY signal against the dominant bearish structure.
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma200 = _safe(tf.get("SMA_200"))
    rolling_low = _safe(tf.get("rolling_low_20"))
    macd_hist = _safe(tf.get("MACD_hist"))

    score = 0.0

    # Condition 1 — Oversold RSI
    oversold = rsi is not None and rsi < 35.0
    if oversold:
        met.append(f"Oversold RSI (RSI={rsi:.1f} < 35)")
        score += 35.0
    else:
        failed.append(f"Not sufficiently oversold (RSI={rsi})")

    # Condition 2 — Near 20-day low
    near_low = False
    if rolling_low and rolling_low > 0:
        pct_from_low = (close_f - rolling_low) / rolling_low
        if pct_from_low <= 0.03:
            near_low = True
            met.append(f"Price near 20-day low (dist={pct_from_low:.2%})")
            score += 25.0
        else:
            failed.append(f"Not near 20-day low (dist={pct_from_low:.2%})")
    else:
        failed.append("20-day rolling low unavailable")

    # Condition 3 — Momentum shift (MACD histogram turning)
    if macd_hist is not None:
        if macd_hist > -0.01:  # Histogram approaching zero from below = momentum shift
            met.append(f"MACD histogram turning (hist={macd_hist:.4f})")
            score += 25.0
        else:
            failed.append(f"MACD histogram still deeply negative (hist={macd_hist:.4f})")
    else:
        failed.append("MACD histogram unavailable")

    # Condition 4 — Not in freefall
    if sma200 and sma200 > 0:
        pct_from_sma200 = (close_f - sma200) / sma200
        if pct_from_sma200 >= -0.30:
            met.append(f"Not in freefall ({pct_from_sma200:.1%} from SMA-200)")
            score += 15.0
        else:
            failed.append(f"Deep freefall below SMA-200 ({pct_from_sma200:.1%}) — dangerous reversal attempt")
            score -= 10.0
    else:
        failed.append("SMA-200 unavailable — cannot assess structural damage")

    score = max(0.0, min(100.0, score))
    detected = oversold and near_low

    return SetupResult(
        setup_type=SetupType.RECOVERY_REVERSAL,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma200": sma200,
            "rolling_low_20": rolling_low, "macd_hist": macd_hist
        }
    )


# ─── TREND CONTINUATION DETECTOR ─────────────────────────────────────────────

def detect_trend_continuation(tf: Dict[str, Any], close: float) -> SetupResult:
    """
    TREND_CONTINUATION — price in established trend without significant retracement.

    Conditions required:
      1. Golden cross: SMA-50 > SMA-200
      2. Price above SMA-50
      3. RSI 50–65 (healthy trend, not overbought)
      4. Not at extreme distance from SMA-50 (<8% above)
    """
    met: List[str] = []
    failed: List[str] = []

    close_f = _safe(close, 0.0)
    rsi = _safe(tf.get("RSI_14"))
    sma50 = _safe(tf.get("SMA_50"))
    sma200 = _safe(tf.get("SMA_200"))

    score = 0.0

    # Condition 1 — Golden cross
    golden_cross = sma50 is not None and sma200 is not None and sma50 > sma200
    if golden_cross:
        met.append(f"Golden cross active (SMA50={sma50:.2f} > SMA200={sma200:.2f})")
        score += 30.0
    else:
        failed.append(f"No golden cross (SMA50={sma50}, SMA200={sma200})")

    # Condition 2 — Price above SMA-50
    if sma50 and close_f > sma50:
        met.append(f"Price above SMA-50 (close={close_f:.2f})")
        score += 30.0
    else:
        failed.append(f"Price below SMA-50")

    # Condition 3 — RSI in healthy trend range
    rsi_ok = rsi is not None and 50.0 <= rsi <= 65.0
    if rsi_ok:
        met.append(f"RSI in healthy trend zone (RSI={rsi:.1f})")
        score += 25.0
    else:
        failed.append(f"RSI outside healthy trend zone (RSI={rsi})")

    # Condition 4 — Not extended
    if sma50 and sma50 > 0:
        pct_from_sma50 = (close_f - sma50) / sma50
        if pct_from_sma50 <= 0.08:
            met.append(f"Not overextended from SMA-50 (dist={pct_from_sma50:.1%})")
            score += 15.0
        else:
            failed.append(f"Overextended from SMA-50 ({pct_from_sma50:.1%}) — elevated risk")
            score -= 10.0

    score = max(0.0, min(100.0, score))
    detected = golden_cross and (sma50 is not None and close_f > sma50) and rsi_ok

    return SetupResult(
        setup_type=SetupType.TREND_CONTINUATION,
        detected=detected,
        score=score,
        conditions_met=met,
        conditions_failed=failed,
        relevant_values={
            "close": close_f, "rsi": rsi, "sma50": sma50, "sma200": sma200
        }
    )


# ─── ORCHESTRATOR ─────────────────────────────────────────────────────────────

def run_all_detectors(tf: Dict[str, Any], close: float) -> List[SetupResult]:
    """
    Runs all detectors and returns results sorted by score descending.
    The caller picks the best-detected setup.
    """
    detectors = [
        detect_breakout,
        detect_breakdown,
        detect_pullback,
        detect_momentum,
        detect_reversal,
        detect_trend_continuation,
    ]

    results = []
    for fn in detectors:
        try:
            results.append(fn(tf, close))
        except Exception as e:
            logger.warning(f"Setup detector {fn.__name__} failed: {e}")

    return sorted(results, key=lambda r: (r.detected, r.score), reverse=True)
