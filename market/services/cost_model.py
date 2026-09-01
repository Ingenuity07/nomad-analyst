"""
cost_model.py — Configurable transaction cost and slippage models.

Module 11: Backtesting Foundation

CRITICAL DESIGN RULES:
  1. Never hardcode current broker charges. The backtest MUST declare its cost
     assumptions explicitly via CostConfig.
  2. NO_COST mode is valid for pure strategy research (ignores transaction costs).
  3. REALISTIC mode applies documented NSE equity assumptions — these are
     illustrative estimates, not live broker quotes.
  4. All costs are applied symmetrically (entry + exit).

Documentation of REALISTIC_NSE_EQUITY assumptions:
  - brokerage_percent: 0.03% per leg (both entry and exit) — flat-fee discount broker
  - stt_percent: 0.025% on sell-side only for delivery; 0.01% for intraday
  - slippage_bps: 5 basis points (0.05%) per leg for liquid NSE equities
  These are ESTIMATES for backtesting purposes. Actual costs vary by broker.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class CostConfig:
    """
    Configuration for transaction costs and slippage.

    All rates are expressed as PERCENTAGES (not basis points) per leg.
    Both entry and exit legs are costed.

    mode:
        NO_COST    — zero brokerage, zero STT, zero slippage.
                     Use for pure strategy signal research.
        REALISTIC  — uses the brokerage/stt/slippage values set below.
    """
    mode: Literal["NO_COST", "REALISTIC"] = "NO_COST"

    # Brokerage per leg as a % of trade value
    brokerage_percent: float = 0.0

    # Securities Transaction Tax (STT) as a % of trade value
    # Typically applied on sell-side only; set to 0 for NO_COST.
    stt_percent: float = 0.0

    # Slippage in basis points per leg (1 bps = 0.01%)
    slippage_bps: float = 0.0

    @classmethod
    def no_cost(cls) -> "CostConfig":
        """Zero-cost configuration for pure strategy signal research."""
        return cls(mode="NO_COST")

    @classmethod
    def realistic_nse_equity(cls) -> "CostConfig":
        """
        Illustrative realistic cost config for NSE equity backtesting.

        Assumptions (ESTIMATES — not live broker quotes):
          - Discount broker flat brokerage: 0.03% per leg
          - STT on sell-side: 0.025% (delivery) / 0.01% (intraday)
          - Slippage: 5 bps per leg for liquid large-cap equities
        """
        return cls(
            mode="REALISTIC",
            brokerage_percent=0.03,
            stt_percent=0.025,
            slippage_bps=5.0,
        )

    @classmethod
    def realistic_nse_intraday(cls) -> "CostConfig":
        """
        Illustrative realistic cost config for NSE intraday backtesting.

        Intraday STT is lower (0.01% vs 0.025% for delivery).
        """
        return cls(
            mode="REALISTIC",
            brokerage_percent=0.03,
            stt_percent=0.01,   # intraday STT rate
            slippage_bps=5.0,
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "brokerage_percent": self.brokerage_percent,
            "stt_percent": self.stt_percent,
            "slippage_bps": self.slippage_bps,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CostConfig":
        return cls(
            mode=d.get("mode", "NO_COST"),
            brokerage_percent=d.get("brokerage_percent", 0.0),
            stt_percent=d.get("stt_percent", 0.0),
            slippage_bps=d.get("slippage_bps", 0.0),
        )


class SlippageModel:
    """
    Simple percentage / basis-point slippage model.

    For BUY entry: execution price is HIGHER than signal price (fills worse).
    For SELL entry: execution price is LOWER than signal price.
    For exits the direction reverses.

    Architecture allows replacement with more realistic models (e.g.
    volume-weighted impact) in future without changing callers.
    """

    @staticmethod
    def apply_entry_slippage(price: float, direction: str, config: CostConfig) -> float:
        """
        Adjust entry price for slippage.

        BUY  → price * (1 + slippage_bps / 10000)
        SELL → price * (1 - slippage_bps / 10000)
        """
        if config.mode == "NO_COST" or config.slippage_bps == 0:
            return price
        factor = config.slippage_bps / 10_000
        if direction == "BUY":
            return price * (1 + factor)
        else:
            return price * (1 - factor)

    @staticmethod
    def apply_exit_slippage(price: float, direction: str, config: CostConfig) -> float:
        """
        Adjust exit price for slippage.

        BUY  position exits as SELL: price * (1 - slippage_bps / 10000)
        SELL position exits as BUY:  price * (1 + slippage_bps / 10000)
        """
        if config.mode == "NO_COST" or config.slippage_bps == 0:
            return price
        factor = config.slippage_bps / 10_000
        if direction == "BUY":
            # Exiting a long: sell side is worse (lower)
            return price * (1 - factor)
        else:
            # Exiting a short: buy side is worse (higher)
            return price * (1 + factor)


def compute_total_cost(
    entry_price: float,
    exit_price: float,
    direction: str,
    config: CostConfig,
) -> float:
    """
    Compute the absolute total transaction cost for a round trip.

    Includes:
      - Brokerage (entry leg + exit leg)
      - STT (sell-side only)
      - Slippage cost (approximated as impact vs theoretical mid-price)

    Returns the total cost in price units (same units as entry/exit price).
    The caller divides by quantity to get per-share cost, or multiplies by
    quantity to get total cost for the position.

    Cost = (entry_brokerage + exit_brokerage + stt + slippage_cost_entry + slippage_cost_exit)
    """
    if config.mode == "NO_COST":
        return 0.0

    bkr_entry = entry_price * (config.brokerage_percent / 100)
    bkr_exit  = exit_price  * (config.brokerage_percent / 100)

    # STT: applied on sell-side only
    if direction == "BUY":
        stt = exit_price * (config.stt_percent / 100)   # exit is the sell
    else:
        stt = entry_price * (config.stt_percent / 100)  # entry is the sell

    slip_factor = config.slippage_bps / 10_000
    slip_entry = entry_price * slip_factor
    slip_exit  = exit_price  * slip_factor

    total = bkr_entry + bkr_exit + stt + slip_entry + slip_exit
    return round(total, 6)
