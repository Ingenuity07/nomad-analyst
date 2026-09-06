"""
Intraday State Manager for Nomad Analyst.

Coordinates real-time streaming market data flow:
1. Ingests normalized NomadMarketTick instances from KiteTickerManager
2. Dispatches ticks to IntradayBarAggregator for 1m, 5m, and 15m OHLCV bars
3. Maintains live constituent and index states in Redis cache
4. Computes live market context, breadth, sector ranking, and market regimes
5. Evaluates data freshness (FRESH, STALE, UNAVAILABLE)
6. Broadcasts throttled updates to Django Channels group 'intraday_market'
7. Persists periodic MarketContextSnapshot and StockIntradayContext database records
"""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.conf import settings

from market.models import Instrument, Company, MarketContextSnapshot, StockIntradayContext
from market.normalizers.kite import NomadMarketTick
from market.services.intraday_aggregator import IntradayBarAggregator
from market.services.intraday_context_engine import IntradayMarketContextEngine
from market.services.intraday_config import (
    FRESH_THRESHOLD_SEC,
    STALE_THRESHOLD_SEC,
    WS_CONTEXT_THROTTLE_SEC,
    WS_STOCKS_THROTTLE_SEC,
)
from market.services.intraday_opportunity_engine import IntradayOpportunityEngine
from market.services.intraday_opportunity_config import WS_OPPORTUNITY_THROTTLE_SEC
from market.services.trading_session import TradingSessionService, IST_TIMEZONE

logger = logging.getLogger(__name__)


class IntradayStateManager:
    """
    Singleton-style live state manager coordinating tick flow, calculations, and broadcasts.
    """

    _instance: Optional["IntradayStateManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(IntradayStateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, aggregator: Optional[IntradayBarAggregator] = None):
        if getattr(self, "_initialized", False):
            return

        self.aggregator = aggregator or IntradayBarAggregator(persist_to_db=True)
        self.opportunity_engine = IntradayOpportunityEngine()
        self._last_tick_time: Optional[datetime] = None
        self._last_context_broadcast: float = 0.0
        self._last_stocks_broadcast: float = 0.0
        self._last_opportunity_broadcast: float = 0.0
        self._last_db_snapshot_time: Optional[datetime] = None
        
        # In-memory fast lookups
        self._stock_states: Dict[str, Dict[str, Any]] = {}
        self._index_states: Dict[str, Dict[str, Any]] = {}
        self._symbol_sector_map: Dict[str, str] = {}
        self._last_calculated_context: Optional[Dict[str, Any]] = None

        self._load_universe_sectors()
        self._initialized = True
        logger.info("IntradayStateManager initialized.")

    def _load_universe_sectors(self):
        """
        Loads NIFTY 50 constituent symbols and their deterministic sectors from database.
        """
        try:
            instruments = Instrument.objects.filter(
                universe_memberships__universe__name="NIFTY50",
                universe_memberships__is_active=True,
                is_active=True
            ).select_related("company")

            for inst in instruments:
                sec = inst.company.sector if inst.company and inst.company.sector else "Unknown"
                self._symbol_sector_map[inst.symbol] = sec
            
            logger.info(f"Loaded {len(self._symbol_sector_map)} NIFTY 50 symbols into sector mapping.")
        except Exception as e:
            logger.warning(f"Could not preload universe sectors: {e}")

    def on_tick(self, tick: NomadMarketTick):
        """
        Callback invoked for every normalized tick from KiteTickerManager.
        """
        now = datetime.now(timezone.utc)
        self._last_tick_time = now

        # 1. Update IntradayBarAggregator
        self.aggregator.process_tick(tick)

        # 2. Resolve sector
        symbol = tick.symbol
        sector = self._symbol_sector_map.get(symbol, "Unknown")

        # 3. Build state payload
        state_item = {
            "symbol": symbol,
            "last_price": float(tick.last_price),
            "open": float(tick.open) if tick.open else float(tick.last_price),
            "high": float(tick.high) if tick.high else float(tick.last_price),
            "low": float(tick.low) if tick.low else float(tick.last_price),
            "close": float(tick.close) if tick.close else float(tick.last_price),
            "change": float(tick.change) if tick.change else 0.0,
            "change_pct": float(tick.change_percent) if tick.change_percent else 0.0,
            "change_percent": float(tick.change_percent) if tick.change_percent else 0.0,
            "volume": tick.volume or 0,
            "vwap": float(tick.average_price) if tick.average_price else None,
            "average_price": float(tick.average_price) if tick.average_price else None,
            "sector": sector,
            "exchange_timestamp": tick.exchange_timestamp.isoformat() if tick.exchange_timestamp else None,
            "received_timestamp": tick.received_timestamp.isoformat(),
            "is_suspicious": tick.is_suspicious_timestamp,
        }

        # 4. Partition Index vs Equity
        is_index = symbol in ("^NSEI", "NIFTY", "NIFTY 50", "NIFTY50", "^NSEBANK", "BANKNIFTY", "NIFTY BANK")
        if is_index:
            idx_key = "NIFTY" if "NIFTY" in symbol and "BANK" not in symbol else "BANKNIFTY"
            self._index_states[idx_key] = state_item
            cache.set(f"index_state:{idx_key}", state_item, timeout=3600)
        else:
            self._stock_states[symbol] = state_item
            cache.set(f"stock_state:{symbol}", state_item, timeout=3600)

        # 5. Throttle real-time broadcast and periodic recalculation
        current_time = time.time()
        if (current_time - self._last_context_broadcast) >= WS_CONTEXT_THROTTLE_SEC:
            self._last_context_broadcast = current_time
            self.broadcast_market_context()

    def get_freshness_status(self) -> Dict[str, Any]:
        """
        Evaluates feed freshness based on elapsed time since the latest tick.
        """
        now = datetime.now(timezone.utc)
        if self._last_tick_time is None:
            # Check redis
            cached_last_tick = cache.get("kite_last_tick")
            if not cached_last_tick:
                return {
                    "freshness": "UNAVAILABLE",
                    "age_seconds": None,
                    "last_tick_at": None,
                    "is_fresh": False,
                }
            try:
                rec_ts = datetime.fromisoformat(cached_last_tick["received_timestamp"])
                age = (now - rec_ts).total_seconds()
            except Exception:
                age = 999.0
        else:
            age = (now - self._last_tick_time).total_seconds()

        if age < FRESH_THRESHOLD_SEC:
            freshness = "FRESH"
            is_fresh = True
        elif age <= STALE_THRESHOLD_SEC:
            freshness = "STALE"
            is_fresh = False
        else:
            freshness = "UNAVAILABLE"
            is_fresh = False

        return {
            "freshness": freshness,
            "age_seconds": round(age, 1) if age is not None else None,
            "last_tick_at": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "is_fresh": is_fresh,
        }

    def compute_current_context(self) -> Dict[str, Any]:
        """
        Runs IntradayMarketContextEngine over current memory/cache state.
        """
        # Collect stock states
        stock_list = list(self._stock_states.values())
        if not stock_list:
            # Try reloading from cache
            try:
                instruments = Instrument.objects.filter(
                    universe_memberships__universe__name="NIFTY50",
                    universe_memberships__is_active=True
                )
                for inst in instruments:
                    c = cache.get(f"stock_state:{inst.symbol}") or cache.get(f"live_tick:{inst.symbol}")
                    if c:
                        c["sector"] = self._symbol_sector_map.get(inst.symbol, "Unknown")
                        stock_list.append(c)
            except Exception as e:
                logger.warning(f"Error loading stock states from cache: {e}")

        # Collect index states
        index_states = dict(self._index_states)
        if not index_states:
            nifty_c = cache.get("index_state:NIFTY") or cache.get("live_tick:^NSEI")
            bank_c = cache.get("index_state:BANKNIFTY") or cache.get("live_tick:^NSEBANK")
            if nifty_c:
                index_states["NIFTY"] = nifty_c
            if bank_c:
                index_states["BANKNIFTY"] = bank_c

        context = IntradayMarketContextEngine.build_market_context_snapshot(
            constituent_states=stock_list,
            index_states=index_states,
            as_of=datetime.now(timezone.utc),
        )

        freshness_info = self.get_freshness_status()
        context["freshness"] = freshness_info["freshness"]
        context["freshness_age_seconds"] = freshness_info["age_seconds"]
        context["is_fresh"] = freshness_info["is_fresh"]

        self._last_calculated_context = context
        return context

    def broadcast_market_context(self):
        """
        Broadcasts market context payload to Django Channels group 'intraday_market'.
        """
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return

            context = self.compute_current_context()

            # Broadcast lightweight market summary
            summary_payload = {
                "type": "market_context_update",
                "data": {
                    "as_of": context["as_of"],
                    "freshness": context["freshness"],
                    "market_direction": context["market_direction"],
                    "market_regime": context["market_regime"],
                    "regime_confidence": context["regime_confidence"],
                    "regime_reasons": context["regime_reasons"],
                    "index_confirmation": context["index_confirmation"],
                    "market_volatility": context["market_volatility"],
                    "nifty": context["nifty"],
                    "banknifty": context["banknifty"],
                    "breadth": {
                        k: float(v) if isinstance(v, Decimal) else v
                        for k, v in context["breadth"].items()
                    },
                    "sector_leader": context["sector_leader"],
                    "sector_laggard": context["sector_laggard"],
                }
            }

            async_to_sync(channel_layer.group_send)("intraday_market", summary_payload)

            # Check if stock table broadcast is due
            now = time.time()
            if (now - self._last_stocks_broadcast) >= WS_STOCKS_THROTTLE_SEC:
                self._last_stocks_broadcast = now
                stocks_payload = {
                    "type": "stock_context_update",
                    "data": {
                        "as_of": context["as_of"],
                        "stocks": [
                            {
                                k: float(v) if isinstance(v, Decimal) else v
                                for k, v in st.items()
                            }
                            for st in context.get("stocks", [])
                        ]
                    }
                }
                async_to_sync(channel_layer.group_send)("intraday_market", stocks_payload)

            # Check if opportunity broadcast is due
            if (now - self._last_opportunity_broadcast) >= WS_OPPORTUNITY_THROTTLE_SEC:
                self._last_opportunity_broadcast = now
                opp_result = self.compute_current_opportunities(limit=10)
                opp_payload = {
                    "type": "opportunity_update",
                    "data": {
                        "timestamp": opp_result["timestamp"],
                        "market_context": opp_result["market_context"],
                        "total_eligible": opp_result["total_eligible"],
                        "opportunities": opp_result["opportunities"],
                    }
                }
                async_to_sync(channel_layer.group_send)("intraday_market", opp_payload)

        except Exception as e:
            logger.debug(f"Channels broadcast skipped or failed: {e}")

    def persist_snapshots(self) -> Optional[MarketContextSnapshot]:
        """
        Durable persistence of MarketContextSnapshot and StockIntradayContext models.
        """
        context = self.compute_current_context()
        as_of_dt = datetime.fromisoformat(context["as_of"])

        try:
            breadth_dict = {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in context["breadth"].items()
            }
            sectors_list = [
                {k: float(v) if isinstance(v, Decimal) else v for k, v in sec.items()}
                for sec in context["sectors"]
            ]

            snapshot = MarketContextSnapshot.objects.create(
                as_of=as_of_dt,
                universe="NIFTY50",
                calculations_version=2,
                market_direction=context["market_direction"],
                market_regime=context["market_regime"],
                nifty_return=Decimal(str(context["nifty"]["change_percent"])),
                banknifty_return=Decimal(str(context["banknifty"]["change_percent"])),
                advance_count=context["breadth"]["advance_count"],
                decline_count=context["breadth"]["decline_count"],
                unchanged_count=context["breadth"]["unchanged_count"],
                advance_decline_ratio=context["breadth"]["advance_decline_ratio"],
                above_vwap_pct=context["breadth"]["above_vwap_pct"],
                below_vwap_pct=context["breadth"]["below_vwap_pct"],
                sector_leader=context["sector_leader"] or "",
                sector_laggard=context["sector_laggard"] or "",
                market_volatility=context["market_volatility"],
                breadth_state=context["breadth"]["breadth_state"],
                index_confirmation=context["index_confirmation"],
                index_regimes={
                    "nifty": context["nifty"],
                    "banknifty": context["banknifty"],
                    "regime": context["market_regime"],
                    "confidence": context["regime_confidence"],
                    "reasons": context["regime_reasons"],
                },
                breadth=breadth_dict,
                sector_rankings=sectors_list,
                data_quality={"freshness": context["freshness"]},
            )

            # Persist StockIntradayContext entries
            stock_records = []
            instruments_map = {inst.symbol: inst for inst in Instrument.objects.filter(universe_memberships__universe__name="NIFTY50")}

            for st in context.get("stocks", []):
                inst = instruments_map.get(st["symbol"])
                if not inst:
                    continue

                stock_records.append(
                    StockIntradayContext(
                        instrument=inst,
                        timestamp=as_of_dt,
                        last_price=st["last_price"],
                        change_pct=st["change_pct"],
                        vwap=st["vwap"],
                        distance_from_vwap=st["distance_from_vwap"],
                        volume=st["volume"],
                        relative_volume=st["relative_volume"],
                        momentum_5m=st["momentum_5m"],
                        momentum_15m=st["momentum_15m"],
                        momentum_30m=st["momentum_30m"],
                        relative_strength_vs_market=st["relative_strength_vs_market"],
                        relative_strength_vs_sector=st["relative_strength_vs_sector"],
                        sector=st["sector"],
                        sector_return=st["sector_return"],
                        volume_confirmation=st["volume_confirmation"],
                        opening_range_state=st["opening_range_state"],
                        intraday_high=st["high"],
                        intraday_low=st["low"],
                        component_scores=st["component_scores"],
                        context_score=st["context_score"],
                    )
                )

            if stock_records:
                StockIntradayContext.objects.bulk_create(stock_records, ignore_conflicts=True)

            logger.info(f"Persisted MarketContextSnapshot and {len(stock_records)} StockIntradayContext records @ {as_of_dt}.")

            # Also persist top opportunities snapshot
            try:
                opp_eval = self.compute_current_opportunities(limit=20, as_of=as_of_dt)
                self.opportunity_engine._persist_opportunities(opp_eval.get("opportunities", []), as_of_dt)
            except Exception as e:
                logger.warning(f"Failed to persist opportunities snapshot: {e}")

            return snapshot

        except Exception as e:
            logger.error(f"Failed to persist intraday snapshots: {e}", exc_info=True)
            return None

    def compute_current_opportunities(
        self,
        mode: str = "RAW_RANKING",
        limit: int = 10,
        sector_filter: Optional[str] = None,
        opportunity_type_filter: Optional[str] = None,
        state_filter: Optional[str] = None,
        min_score: Optional[float] = None,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Runs IntradayOpportunityEngine over current market context and constituent contexts.
        Applies filtering, ranking, and returns structured opportunity evaluations.
        """
        context = self.compute_current_context()
        stock_contexts = context.get("stocks", [])
        freshness_info = self.get_freshness_status()

        result = self.opportunity_engine.evaluate_universe_opportunities(
            market_context=context,
            constituent_contexts=stock_contexts,
            freshness_info=freshness_info,
            as_of=as_of or datetime.now(timezone.utc),
            persist_to_db=False,
        )

        from market.services.intraday_opportunity_ranker import IntradayOpportunityRanker
        ranked = IntradayOpportunityRanker.rank_opportunities(
            opportunities=result.get("all_eligible_opportunities", []),
            mode=mode,
            limit=limit,
            sector_filter=sector_filter,
            opportunity_type_filter=opportunity_type_filter,
            state_filter=state_filter,
            min_score=min_score,
        )

        result["opportunities"] = ranked["opportunities"]
        result["ranking_mode"] = ranked["mode"]
        result["sector_concentration"] = ranked["sector_concentration"]
        self._last_opportunities_result = result
        return result
