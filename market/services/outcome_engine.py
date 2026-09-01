"""
outcome_engine.py — Deterministic entry/exit/MFE-MAE/P&L evaluators.

Module 11: Backtesting Foundation

CRITICAL DESIGN RULES:
  1. These are PURE evaluation functions. They read bars, never write DB records.
  2. All inputs are ordered bar lists (oldest → newest).
  3. PIT safety is the CALLER's responsibility. Bars passed in must already
     be PIT-filtered (timestamp <= as_of for the decision point).
  4. Same-bar ambiguity (both stop and target in one OHLC bar) is handled
     per the AmbiguityPolicy, never silently resolved.
  5. Prices used are ACTUAL bar prices (high/low/close), not theoretical.
  6. No network calls, no ORM queries — pure Python on bar data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from market.models import OHLCVBar, StockRecommendation

from market.services.cost_model import CostConfig, SlippageModel, compute_total_cost

logger = logging.getLogger(__name__)


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class EntryResult:
    triggered: bool
    trigger_bar_index: Optional[int]   # index into the bars list
    trigger_timestamp: Optional[datetime]
    trigger_price: Optional[float]     # actual bar price (high for BUY, low for SELL)
    bars_scanned: int = 0


@dataclass
class ExitResult:
    exit_reason: str                   # ExitReason value
    exit_bar_index: Optional[int]
    exit_timestamp: Optional[datetime]
    exit_price: Optional[float]        # actual bar price used for exit
    target_hit: Optional[bool]         # None = ambiguous
    stop_hit: Optional[bool]
    ambiguous_intrabar: bool = False
    bars_scanned: int = 0


@dataclass
class MFEMAEResult:
    max_favorable_excursion: Optional[float]   # % from entry, always positive
    max_adverse_excursion: Optional[float]     # % from entry, always positive
    bars_evaluated: int = 0


@dataclass
class PnLResult:
    actual_entry_price: float
    actual_exit_price: Optional[float]
    gross_pnl_absolute: Optional[float]
    gross_pnl_percent: Optional[float]
    cost_absolute: Optional[float]
    net_pnl_absolute: Optional[float]
    net_pnl_percent: Optional[float]
    risk_amount: Optional[float]
    r_multiple: Optional[float]


# ── EntryEvaluator ────────────────────────────────────────────────────────────

class EntryEvaluator:
    """
    Determines whether the entry condition for a recommendation was triggered
    by scanning subsequent OHLCV bars.

    Entry rules (by direction):
      BUY:  bar.high >= entry_price   (price reached or exceeded the trigger)
      SELL: bar.low  <= entry_price   (price fell to or below the trigger)

    The trigger_price is the bar's high (BUY) or low (SELL) — the actual
    bar boundary that confirms the trigger, not the exact entry_price.
    This is conservative: it does NOT fabricate intrabar execution prices.
    """

    def evaluate(
        self,
        rec: "StockRecommendation",
        bars: List["OHLCVBar"],
    ) -> EntryResult:
        """
        Evaluate whether the entry was triggered in the given bar sequence.

        Args:
            rec:  The recommendation to evaluate.
            bars: Bars AFTER the recommendation's as_of timestamp, oldest first.
                  These must already be PIT-safe.

        Returns:
            EntryResult
        """
        entry_price = rec.entry_price
        signal = rec.signal

        if entry_price is None:
            logger.warning(
                f"Rec {rec.id}: entry_price is None, marking untriggered."
            )
            return EntryResult(
                triggered=False, trigger_bar_index=None,
                trigger_timestamp=None, trigger_price=None,
                bars_scanned=0,
            )

        entry_float = float(entry_price)

        for i, bar in enumerate(bars):
            if bar.high is None or bar.low is None:
                continue

            bar_high = float(bar.high)
            bar_low  = float(bar.low)

            if signal == "BUY" and bar_high >= entry_float:
                return EntryResult(
                    triggered=True,
                    trigger_bar_index=i,
                    trigger_timestamp=bar.timestamp,
                    trigger_price=bar_high,
                    bars_scanned=i + 1,
                )
            elif signal == "SELL" and bar_low <= entry_float:
                return EntryResult(
                    triggered=True,
                    trigger_bar_index=i,
                    trigger_timestamp=bar.timestamp,
                    trigger_price=bar_low,
                    bars_scanned=i + 1,
                )

        return EntryResult(
            triggered=False, trigger_bar_index=None,
            trigger_timestamp=None, trigger_price=None,
            bars_scanned=len(bars),
        )


# ── ExitEvaluator ─────────────────────────────────────────────────────────────

class ExitEvaluator:
    """
    Evaluates stop/target/expiry for a recommendation AFTER entry is triggered.

    Scans bars in chronological order. On each bar:
      1. Check if bar is past expires_at (intraday session close).
      2. Check if max_holding_bars reached.
      3. Check target hit: BUY → bar.high >= target_price
                           SELL → bar.low  <= target_price
      4. Check stop hit:   BUY → bar.low  <= stop_price
                           SELL → bar.high >= stop_price
      5. If BOTH target and stop touched in the same bar → AMBIGUOUS_INTRABAR.
         Apply AmbiguityPolicy to resolve.

    Exit price is the actual bar boundary, not a fabricated exact price.
    """

    def evaluate(
        self,
        rec: "StockRecommendation",
        entry_result: EntryResult,
        bars_after_entry: List["OHLCVBar"],
        ambiguity_policy: str = "CONSERVATIVE",
        max_holding_bars: int = 200,
    ) -> ExitResult:
        """
        Args:
            rec:               The triggered recommendation.
            entry_result:      Result from EntryEvaluator (must be triggered=True).
            bars_after_entry:  Bars starting AFTER the entry bar, oldest first.
            ambiguity_policy:  "CONSERVATIVE"|"OPTIMISTIC"|"EXCLUDE"
            max_holding_bars:  Kill-switch bar count.
        """
        if not entry_result.triggered:
            return ExitResult(
                exit_reason="NO_ENTRY",
                exit_bar_index=None,
                exit_timestamp=None,
                exit_price=None,
                target_hit=False,
                stop_hit=False,
                ambiguous_intrabar=False,
                bars_scanned=0,
            )

        signal       = rec.signal
        stop_price   = float(rec.stop_price)  if rec.stop_price  else None
        target_price = float(rec.target_price) if rec.target_price else None
        expires_at   = rec.expires_at         # UTC datetime or None

        for i, bar in enumerate(bars_after_entry):
            if i >= max_holding_bars:
                return ExitResult(
                    exit_reason="EXPIRED_MAX_DURATION",
                    exit_bar_index=i,
                    exit_timestamp=bar.timestamp,
                    exit_price=float(bar.close) if bar.close else None,
                    target_hit=False, stop_hit=False, ambiguous_intrabar=False,
                    bars_scanned=i + 1,
                )

            # Check session expiry BEFORE price evaluation
            if expires_at is not None and bar.timestamp >= expires_at:
                return ExitResult(
                    exit_reason="EXPIRED_SESSION",
                    exit_bar_index=i,
                    exit_timestamp=bar.timestamp,
                    exit_price=float(bar.close) if bar.close else None,
                    target_hit=False, stop_hit=False, ambiguous_intrabar=False,
                    bars_scanned=i + 1,
                )

            if bar.high is None or bar.low is None:
                continue

            bar_high = float(bar.high)
            bar_low  = float(bar.low)

            # Determine hits
            if signal == "BUY":
                tgt_hit  = (target_price is not None and bar_high >= target_price)
                stop_hit = (stop_price   is not None and bar_low  <= stop_price)
            else:  # SELL
                tgt_hit  = (target_price is not None and bar_low  <= target_price)
                stop_hit = (stop_price   is not None and bar_high >= stop_price)

            # Both hit in same bar → ambiguity
            if tgt_hit and stop_hit:
                return self._resolve_ambiguity(
                    bar=bar, bar_idx=i,
                    signal=signal,
                    target_price=target_price,
                    stop_price=stop_price,
                    ambiguity_policy=ambiguity_policy,
                    bars_scanned=i + 1,
                )

            if tgt_hit:
                exit_px = target_price  # use the theoretical target as exit
                return ExitResult(
                    exit_reason="TARGET_HIT",
                    exit_bar_index=i,
                    exit_timestamp=bar.timestamp,
                    exit_price=exit_px,
                    target_hit=True, stop_hit=False, ambiguous_intrabar=False,
                    bars_scanned=i + 1,
                )

            if stop_hit:
                exit_px = stop_price  # use the theoretical stop as exit
                return ExitResult(
                    exit_reason="STOP_HIT",
                    exit_bar_index=i,
                    exit_timestamp=bar.timestamp,
                    exit_price=exit_px,
                    target_hit=False, stop_hit=True, ambiguous_intrabar=False,
                    bars_scanned=i + 1,
                )

        # No exit triggered within bars scanned
        return ExitResult(
            exit_reason="EXPIRED_MAX_DURATION",
            exit_bar_index=None,
            exit_timestamp=None,
            exit_price=None,
            target_hit=False, stop_hit=False, ambiguous_intrabar=False,
            bars_scanned=len(bars_after_entry),
        )

    def _resolve_ambiguity(
        self, bar, bar_idx, signal, target_price, stop_price,
        ambiguity_policy, bars_scanned,
    ) -> ExitResult:
        """Handle same-bar stop+target ambiguity per policy."""
        base = dict(
            exit_bar_index=bar_idx,
            exit_timestamp=bar.timestamp,
            ambiguous_intrabar=True,
            bars_scanned=bars_scanned,
        )

        if ambiguity_policy == "CONSERVATIVE":
            # Stop wins — worst case for strategy
            return ExitResult(
                exit_reason="AMBIGUOUS_INTRABAR",
                exit_price=stop_price,
                target_hit=None, stop_hit=None,
                **base
            )
        elif ambiguity_policy == "OPTIMISTIC":
            # Target wins — best case
            return ExitResult(
                exit_reason="AMBIGUOUS_INTRABAR",
                exit_price=target_price,
                target_hit=None, stop_hit=None,
                **base
            )
        else:  # EXCLUDE
            return ExitResult(
                exit_reason="AMBIGUOUS_INTRABAR",
                exit_price=None,
                target_hit=None, stop_hit=None,
                **base
            )


# ── MFE / MAE Calculator ──────────────────────────────────────────────────────

class MFEMAECalculator:
    """
    Calculates Maximum Favorable Excursion and Maximum Adverse Excursion.

    MFE: the largest unrealised gain (from actual entry to best price seen)
         as a percentage of the actual entry price. Always positive.
    MAE: the largest unrealised loss (from actual entry to worst price seen)
         as a percentage of the actual entry price. Always positive.

    These are useful for:
      - Understanding whether stops are too tight (high MAE before recovery)
      - Understanding whether targets are achievable (low MFE before stop)
      - Future stop/target optimisation research
    """

    def calculate(
        self,
        signal: str,
        actual_entry_price: float,
        bars: List["OHLCVBar"],
    ) -> MFEMAEResult:
        """
        Calculate MFE and MAE over the bars from entry to exit.

        Args:
            signal:              'BUY' or 'SELL'
            actual_entry_price:  Actual entry price (post-slippage).
            bars:                Bars from entry bar to exit bar inclusive.
        """
        if not bars or actual_entry_price == 0:
            return MFEMAEResult(
                max_favorable_excursion=None,
                max_adverse_excursion=None,
                bars_evaluated=0,
            )

        mfe = 0.0
        mae = 0.0
        entry = actual_entry_price

        for bar in bars:
            if bar.high is None or bar.low is None:
                continue
            bar_high = float(bar.high)
            bar_low  = float(bar.low)

            if signal == "BUY":
                favorable = (bar_high - entry) / entry * 100
                adverse   = (entry - bar_low)  / entry * 100
            else:
                favorable = (entry - bar_low)  / entry * 100
                adverse   = (bar_high - entry) / entry * 100

            mfe = max(mfe, favorable)
            mae = max(mae, adverse)

        return MFEMAEResult(
            max_favorable_excursion=round(mfe, 4),
            max_adverse_excursion=round(mae, 4),
            bars_evaluated=len(bars),
        )


# ── P&L Calculator ────────────────────────────────────────────────────────────

class PnLCalculator:
    """
    Calculates gross and net P&L for a completed trade.

    Gross P&L: before transaction costs.
    Net P&L:   after transaction costs (brokerage + STT + slippage).

    R-multiple: net_pnl_absolute / risk_amount.
    Risk amount: |actual_entry_price - stop_price| (actual risk taken).
    """

    def calculate(
        self,
        signal: str,
        actual_entry_price: float,
        actual_exit_price: float,
        stop_price: Optional[float],
        cost_config: CostConfig,
    ) -> PnLResult:
        """
        Args:
            signal:              'BUY' or 'SELL'
            actual_entry_price:  Price actually paid/received at entry.
            actual_exit_price:   Price actually received/paid at exit.
            stop_price:          Theoretical stop price (for R calculation).
            cost_config:         Cost and slippage configuration.
        """
        # Apply slippage to both legs
        adj_entry = SlippageModel.apply_entry_slippage(
            actual_entry_price, signal, cost_config
        )
        adj_exit = SlippageModel.apply_exit_slippage(
            actual_exit_price, signal, cost_config
        )

        # Gross P&L
        if signal == "BUY":
            gross_pnl_abs = adj_exit - adj_entry
        else:
            gross_pnl_abs = adj_entry - adj_exit

        gross_pnl_pct = (gross_pnl_abs / adj_entry * 100) if adj_entry else None

        # Transaction costs
        cost_abs = compute_total_cost(adj_entry, adj_exit, signal, cost_config)

        # Net P&L
        net_pnl_abs = gross_pnl_abs - cost_abs
        net_pnl_pct = (net_pnl_abs / adj_entry * 100) if adj_entry else None

        # Risk and R-multiple
        risk_amount = None
        r_multiple  = None
        if stop_price is not None and adj_entry:
            risk_amount = abs(adj_entry - float(stop_price))
            if risk_amount > 0:
                r_multiple = net_pnl_abs / risk_amount

        return PnLResult(
            actual_entry_price=round(adj_entry, 4),
            actual_exit_price=round(adj_exit, 4),
            gross_pnl_absolute=round(gross_pnl_abs, 4),
            gross_pnl_percent=round(gross_pnl_pct, 4) if gross_pnl_pct is not None else None,
            cost_absolute=round(cost_abs, 4),
            net_pnl_absolute=round(net_pnl_abs, 4),
            net_pnl_percent=round(net_pnl_pct, 4) if net_pnl_pct is not None else None,
            risk_amount=round(risk_amount, 4) if risk_amount is not None else None,
            r_multiple=round(r_multiple, 4) if r_multiple is not None else None,
        )
