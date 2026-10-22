"""
Nomad Analyst — Research Strategy Plugins
"""

from fno.research.strategies.orb_15m import NiftyOrbStrategyPlugin, OrbStrategyConfig
from fno.research.strategies.trend_following import (
    NiftyTrendFollowingPlugin,
    TrendStrategyConfig,
)

__all__ = [
    "NiftyOrbStrategyPlugin",
    "OrbStrategyConfig",
    "NiftyTrendFollowingPlugin",
    "TrendStrategyConfig",
]
