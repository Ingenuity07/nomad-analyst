"""
backtest_config.py — Backtest configuration dataclass.

Module 11: Backtesting Foundation

All backtest parameters are explicit and versioned. There are no hidden defaults.
The config is serialised into BacktestRun.config (JSONField) so every result
is permanently tied to the exact configuration that produced it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from market.services.cost_model import CostConfig


@dataclass
class BacktestConfig:
    """
    Full configuration for a deterministic backtest run.

    Every field is documented. No field has a hidden or undocumented default.

    PIT safety is mandatory — the strategy engine must only see data
    available at each as_of timestamp. This is enforced by the BacktestRunner.
    """
    # ── Universe & scope ──────────────────────────────────────────────────
    universe_name: str
    """Name of the universe to scan. Must exist in UniverseMembership."""

    timeframe: str
    """Bar timeframe (e.g. '5m', '15m', '1d')."""

    horizon: str
    """SignalHorizon value (e.g. 'INTRADAY', 'DELIVERY_SWING', 'LONG_TERM')."""

    start_date: date
    """First calendar date to generate signals (inclusive)."""

    end_date: date
    """Last calendar date to generate signals (inclusive)."""

    # ── Strategy versioning ───────────────────────────────────────────────
    strategy_version: str = "1.0"
    """Strategy config version. Written to every BacktestRun for traceability."""

    # ── Data quality ──────────────────────────────────────────────────────
    min_bars_required: int = 30
    """Minimum bars required at each as_of timestamp to generate a signal."""

    # ── Transaction costs ─────────────────────────────────────────────────
    cost_config: CostConfig = field(default_factory=CostConfig.no_cost)
    """Cost configuration. Default: NO_COST. Use realistic_nse_equity() for
    realistic simulation."""

    # ── Ambiguity handling ────────────────────────────────────────────────
    ambiguity_policy: str = "CONSERVATIVE"
    """Policy when stop and target are both touched in the same OHLC bar.
    CONSERVATIVE: stop wins (worst case, default).
    OPTIMISTIC:   target wins (best case, sensitivity only).
    EXCLUDE:      exclude from win rate & R calculations."""

    # ── Exit constraints ──────────────────────────────────────────────────
    max_holding_bars: int = 200
    """Kill-switch: exit any open position after this many bars regardless of
    stop/target. Prevents positions from running indefinitely in edge cases."""

    session_rules_active: bool = True
    """If True, intraday recommendations are expired at session close (15:30 IST).
    Must be True for INTRADAY horizon."""

    # ── Walk-forward step ─────────────────────────────────────────────────
    walk_forward_step_bars: int = 1
    """How many bars to advance the as_of pointer on each step.
    Default: 1 (bar-by-bar walk-forward). Set higher for faster runs."""

    def to_dict(self) -> dict:
        return {
            "universe_name": self.universe_name,
            "timeframe": self.timeframe,
            "horizon": self.horizon,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "strategy_version": self.strategy_version,
            "min_bars_required": self.min_bars_required,
            "cost_config": self.cost_config.to_dict(),
            "ambiguity_policy": self.ambiguity_policy,
            "max_holding_bars": self.max_holding_bars,
            "session_rules_active": self.session_rules_active,
            "walk_forward_step_bars": self.walk_forward_step_bars,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestConfig":
        return cls(
            universe_name=d["universe_name"],
            timeframe=d["timeframe"],
            horizon=d["horizon"],
            start_date=date.fromisoformat(d["start_date"]),
            end_date=date.fromisoformat(d["end_date"]),
            strategy_version=d.get("strategy_version", "1.0"),
            min_bars_required=d.get("min_bars_required", 30),
            cost_config=CostConfig.from_dict(d.get("cost_config", {})),
            ambiguity_policy=d.get("ambiguity_policy", "CONSERVATIVE"),
            max_holding_bars=d.get("max_holding_bars", 200),
            session_rules_active=d.get("session_rules_active", True),
            walk_forward_step_bars=d.get("walk_forward_step_bars", 1),
        )
