"""
fno/services/fno_ticker_consumer.py — Isolated F&O WebSocket Tick Consumer & Ingestion Pipeline.

Guarantees 100% runtime isolation between NFO derivative ticks and NSE equity processing.
Routes incoming NFO ticks strictly to OptionNormalizer, OptionQuoteManager, and OptionBarAggregator.
Prevents any mutation of IntradayStateManager or pollution of market_ohlcvbar.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from fno.services.desired_universe import DesiredUniverseManager, UnderlyingAssetConfig, CONFIG_NIFTY
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionNormalizer, OptionTick
from fno.services.option_quote_manager import OptionQuoteManager
from fno.services.option_registry import OptionInstrumentRegistry

logger = logging.getLogger(__name__)


class FnoTickerConsumer:
    """
    Isolated consumer and lifecycle manager for NFO options on Kite WebSocket.
    """

    def __init__(
        self,
        registry: Optional[OptionInstrumentRegistry] = None,
        universe_manager: Optional[DesiredUniverseManager] = None,
        normalizer: Optional[OptionNormalizer] = None,
        bar_aggregator: Optional[OptionBarAggregator] = None,
        quote_manager: Optional[OptionQuoteManager] = None,
        config: Optional[UnderlyingAssetConfig] = None,
    ):
        self.config = config or CONFIG_NIFTY
        self.registry = registry or OptionInstrumentRegistry()
        if self.registry._loaded_at is None:
            try:
                self.registry.load_master(max_age_hours=999999)
            except Exception as e:
                logger.warning(f"FnoTickerConsumer: Registry master file not loaded: {e}")

        self.universe_manager = universe_manager or DesiredUniverseManager(self.registry, self.config)
        self.normalizer = normalizer or OptionNormalizer()
        self.bar_aggregator = bar_aggregator or OptionBarAggregator()
        self.quote_manager = quote_manager or OptionQuoteManager()

        self.latest_underlying_spot: Optional[Decimal] = None
        self.stats = {
            "ticks_received": 0,
            "quotes_recorded": 0,
            "bars_created": 0,
            "rebalances_triggered": 0,
            "errors": 0,
        }

    @property
    def active_tokens(self) -> Set[int]:
        """Returns currently active/subscribed NFO option instrument tokens."""
        return self.universe_manager.active_tokens

    def is_fno_token(self, token: Optional[int]) -> bool:
        """
        Determines whether a token belongs to the F&O option universe.
        Checks active universe tokens or instrument registry lookup.
        """
        if token is None:
            return False
        if token in self.universe_manager.active_tokens:
            return True
        lookup = getattr(self.registry, "get_by_token", None) or getattr(self.registry, "get_contract_by_token", None)
        if lookup:
            return lookup(token) is not None
        return False

    def on_connect(self, ws: Any) -> Set[int]:
        """
        Lifecycle hook invoked when Kite WebSocket connects or reconnects.
        Resolves current desired universe tokens and resubscribes in MODE_FULL.
        """
        spot = self.latest_underlying_spot or getattr(self.config, "initial_spot_estimate", None)
        if spot is None:
            # Fall back to database query for latest underlying close price
            try:
                from market.models import OHLCVBar, MarketSnapshot
                symbol = getattr(self.config, "underlying_symbol", "^NSEI")
                bar = OHLCVBar.objects.filter(instrument__symbol=symbol).order_by("-timestamp").first()
                if bar and bar.close:
                    spot = Decimal(str(bar.close))
                else:
                    snap = MarketSnapshot.objects.filter(instrument__symbol=symbol).order_by("-timestamp").first()
                    if snap and snap.close:
                        spot = Decimal(str(snap.close))
            except Exception as e:
                logger.debug(f"FnoTickerConsumer.on_connect: Could not fetch fallback spot from DB: {e}")

        if spot is None:
            logger.warning("FnoTickerConsumer.on_connect: No underlying spot available for universe resolution. Subscriptions will trigger on first spot tick.")
            return set()

        desired_tokens = self.universe_manager.calculate_desired_tokens(spot)
        if not desired_tokens:
            logger.warning(f"FnoTickerConsumer.on_connect: 0 desired tokens resolved for spot {spot}.")
            return set()

        token_list = list(desired_tokens)
        logger.info(
            f"FnoTickerConsumer.on_connect: Subscribing {len(token_list)} NFO option tokens in MODE_FULL "
            f"(underlying={self.config.master_name}, spot={spot})"
        )
        try:
            ws.subscribe(token_list)
            ws.set_mode(ws.MODE_FULL, token_list)
        except Exception as e:
            logger.error(f"FnoTickerConsumer.on_connect: Failed to subscribe tokens on WebSocket: {e}", exc_info=True)

        to_sub, to_unsub = self.universe_manager.reconcile(spot, force=True)
        self.universe_manager.apply_reconciliation(to_sub, to_unsub, spot)

        # Mark in-flight active option bars as partial across reconnects
        if self.bar_aggregator._active_bars:
            logger.info("FnoTickerConsumer.on_connect: Reconnected with active bars present. Marking active bars as partial.")
            self.bar_aggregator.mark_partial_bars()

        return desired_tokens

    def on_disconnect(self, code: Optional[int] = None, reason: Optional[str] = None) -> None:
        """
        Called when WebSocket connection is closed or dropped.
        Marks in-flight active option bars as partial to preserve data integrity across reconnects.
        """
        logger.warning(
            f"FnoTickerConsumer: Disconnect detected (code={code}, reason={reason}). "
            f"Marking active option bars as partial."
        )
        self.bar_aggregator.mark_partial_bars()

    def on_reconnect(self, attempts_count: Optional[int] = None) -> None:
        """
        Called when WebSocket is attempting reconnection.
        Marks in-flight active option bars as partial to ensure bars affected by data gap are flagged.
        """
        logger.info(
            f"FnoTickerConsumer: Reconnect detected (attempt={attempts_count}). "
            f"Marking active option bars as partial."
        )
        self.bar_aggregator.mark_partial_bars()

    def on_underlying_spot_update(
        self,
        spot_price: Decimal,
        ws: Optional[Any] = None,
        as_of_datetime: Optional[datetime] = None
    ) -> Tuple[Set[int], Set[int]]:
        """
        Updates underlying index/stock spot price. Evaluates dynamic rebalancing.
        If ATM strikes shift or drift exceeds threshold, issues subscribe/unsubscribe calls on ws.
        """
        self.latest_underlying_spot = spot_price
        if as_of_datetime is None:
            as_of_datetime = datetime.now(timezone.utc)

        if not self.universe_manager.should_rebalance(spot_price, as_of_datetime):
            return set(), set()

        to_sub, to_unsub = self.universe_manager.reconcile(spot_price, as_of_datetime)
        if not to_sub and not to_unsub:
            return set(), set()

        self.stats["rebalances_triggered"] += 1
        logger.info(
            f"FnoTickerConsumer: Dynamic rebalance triggered at spot {spot_price} "
            f"(ATM: {self.universe_manager.calculate_atm_strike(spot_price)}). "
            f"+{len(to_sub)} to subscribe, -{len(to_unsub)} to unsubscribe."
        )

        if ws is not None:
            if to_sub:
                sub_list = list(to_sub)
                try:
                    ws.subscribe(sub_list)
                    ws.set_mode(ws.MODE_FULL, sub_list)
                except Exception as e:
                    logger.error(f"FnoTickerConsumer: Failed to subscribe new tokens {sub_list}: {e}")

            if to_unsub:
                unsub_list = list(to_unsub)
                try:
                    ws.unsubscribe(unsub_list)
                except Exception as e:
                    logger.error(f"FnoTickerConsumer: Failed to unsubscribe stale tokens {unsub_list}: {e}")

        self.universe_manager.apply_reconciliation(to_sub, to_unsub, spot_price, as_of_datetime)
        return to_sub, to_unsub

    def on_tick(
        self,
        raw_tick: Union[bytes, Dict[str, Any]],
        ws: Optional[Any] = None,
        received_wall_clock_utc: Optional[datetime] = None
    ) -> Optional[OptionTick]:
        """
        Processes an incoming NFO option tick.
        Normalizes tick, updates bar aggregator, records quote snapshot.
        Guarantees zero execution in IntradayStateManager or market_ohlcvbar.
        """
        try:
            self.stats["ticks_received"] += 1
            if isinstance(raw_tick, bytes):
                norm_tick = self.normalizer.unpack_mode_full(
                    raw_tick,
                    received_wall_clock_utc=received_wall_clock_utc
                )
            elif isinstance(raw_tick, dict):
                norm_tick = self.normalizer.normalize_dict(
                    raw_tick,
                    received_wall_clock_utc=received_wall_clock_utc
                )
            else:
                logger.error(f"FnoTickerConsumer: Unsupported raw_tick type: {type(raw_tick)}")
                return None

            # 1. Update 1-minute candle aggregator
            self.bar_aggregator.on_tick(norm_tick)

            # 2. Record quote snapshot for point-in-time depth and execution eligibility
            self.quote_manager.record_quote_snapshot(norm_tick)
            self.stats["quotes_recorded"] += 1

            return norm_tick

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"FnoTickerConsumer: Error processing NFO tick: {e}", exc_info=True)
            return None

    def flush_completed_bars(self, as_of_datetime: Optional[datetime] = None) -> int:
        """Flushes completed 1-minute option OHLCV bars to PostgreSQL."""
        created_count = self.bar_aggregator.flush_completed_bars(as_of_datetime=as_of_datetime)
        self.stats["bars_created"] += created_count
        return created_count
