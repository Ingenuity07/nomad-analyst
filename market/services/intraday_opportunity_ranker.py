"""
Intraday Opportunity Ranking and Diversification Engine for Nomad Analyst.

Provides deterministic ordering (Score DESC -> Confidence DESC -> Symbol ASC)
with support for both RAW_RANKING and SECTOR_DIVERSIFIED modes.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from collections import Counter

from market.services.intraday_opportunity_config import (
    DEFAULT_TOP_OPPORTUNITIES_LIMIT,
    MAX_TOP_OPPORTUNITIES_LIMIT,
)

logger = logging.getLogger(__name__)


class IntradayOpportunityRanker:
    """
    Ranks intraday opportunities with deterministic tie-breaking and optional sector diversification.
    """

    @classmethod
    def rank_opportunities(
        cls,
        opportunities: List[Dict[str, Any]],
        mode: str = "RAW_RANKING",
        limit: int = DEFAULT_TOP_OPPORTUNITIES_LIMIT,
        sector_filter: Optional[str] = None,
        opportunity_type_filter: Optional[str] = None,
        state_filter: Optional[str] = None,
        min_score: Optional[float] = None,
        max_per_sector: int = 3,
    ) -> Dict[str, Any]:
        """
        Filters and orders candidates.
        Returns dict containing:
        - ranked_opportunities: List[Dict[str, Any]] with 1-indexed rank
        - total_evaluated: int
        - sector_concentration: Dict[str, int]
        - mode: str
        """
        def _get_sec_name(item: Dict[str, Any]) -> str:
            sec = item.get("sector")
            if isinstance(sec, dict):
                return str(sec.get("name") or "Unknown")
            return str(sec or "Unknown")

        filtered = list(opportunities)

        # Apply filters
        if sector_filter:
            filtered = [o for o in filtered if _get_sec_name(o).lower() == sector_filter.lower()]

        if opportunity_type_filter:
            filtered = [o for o in filtered if o.get("opportunity_type") == opportunity_type_filter]

        if state_filter:
            filtered = [o for o in filtered if o.get("state") == state_filter]

        if min_score is not None:
            filtered = [o for o in filtered if float(o.get("score", 0.0)) >= float(min_score)]

        # Deterministic sorting key: Score DESC, Confidence DESC, Symbol ASC
        def sort_key(item: Dict[str, Any]):
            score = float(item.get("score", 0.0))
            conf = float(item.get("confidence", 0.0))
            sym = str(item.get("symbol", ""))
            return (-score, -conf, sym)

        sorted_items = sorted(filtered, key=sort_key)

        effective_limit = min(max(1, limit), MAX_TOP_OPPORTUNITIES_LIMIT)

        if mode == "SECTOR_DIVERSIFIED":
            ranked: List[Dict[str, Any]] = []
            sector_counts: Counter = Counter()
            overflow: List[Dict[str, Any]] = []

            for item in sorted_items:
                sec_name = _get_sec_name(item)
                if sector_counts[sec_name] < max_per_sector:
                    ranked.append(item)
                    sector_counts[sec_name] += 1
                else:
                    overflow.append(item)
                
                if len(ranked) >= effective_limit:
                    break

            # If limit not met and overflow exists, append overflow
            if len(ranked) < effective_limit and overflow:
                for item in overflow:
                    ranked.append(item)
                    if len(ranked) >= effective_limit:
                        break
        else:
            # RAW_RANKING
            ranked = sorted_items[:effective_limit]

        # Assign 1-indexed rank and calculate sector concentration
        final_list = []
        sector_dist: Counter = Counter()

        for idx, item in enumerate(ranked, start=1):
            copy_item = dict(item)
            copy_item["rank"] = idx
            final_list.append(copy_item)
            sector_dist[_get_sec_name(copy_item)] += 1

        return {
            "mode": mode,
            "total_evaluated": len(opportunities),
            "total_matches": len(final_list),
            "sector_concentration": dict(sector_dist),
            "opportunities": final_list,
        }
