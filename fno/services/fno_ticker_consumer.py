"""
fno/services/fno_ticker_consumer.py — Isolated F&O WebSocket Tick Consumer & Ingestion Pipeline.

Guarantees 100% runtime isolation between NFO derivative ticks and NSE equity processing.
Routes incoming NFO ticks strictly to OptionNormalizer, OptionQuoteManager, and OptionBarAggregator.
Prevents any mutation of IntradayStateManager or pollution of market_ohlcvbar.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import zoneinfo

from fno.execution.paper_engine import PaperExecutionEngine
from fno.models import OptionOHLCVBar
from fno.services.desired_universe import DesiredUniverseManager, UnderlyingAssetConfig, CONFIG_NIFTY
from fno.services.feature_engine import OptionFeatureEngine
from fno.services.option_bar_aggregator import OptionBarAggregator
from fno.services.option_normalizer import OptionNormalizer, OptionTick
from fno.services.option_quote_manager import OptionQuoteManager
from fno.services.option_registry import OptionInstrumentRegistry
from fno.strategies.base import OptionSignal, PaperTradeEvent
from fno.strategies.manager import StrategyManager
from fno.strategies.nifty_orb_breakout import NiftyOrbBreakoutStrategy
from fno.strategies.validator import SignalValidator

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class FnoTickerConsumer:
    """
    Isolated consumer and lifecycle manager for NFO options on Kite WebSocket.
    Coordinates tick normalization, bar aggregation, quote snapshot capture,
    and runtime strategy evaluation / paper execution.
    """

    def __init__(
        self,
        registry: Optional[OptionInstrumentRegistry] = None,
        universe_manager: Optional[DesiredUniverseManager] = None,
        normalizer: Optional[OptionNormalizer] = None,
        bar_aggregator: Optional[OptionBarAggregator] = None,
        quote_manager: Optional[OptionQuoteManager] = None,
        config: Optional[UnderlyingAssetConfig] = None,
        enable_strategy: bool = True,
        strategy_manager: Optional[StrategyManager] = None,
        execution_engine: Optional[PaperExecutionEngine] = None,
        feature_engine: Optional[OptionFeatureEngine] = None,
        validator: Optional[SignalValidator] = None,
        clock: Optional[Any] = None,
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

        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.enable_strategy = enable_strategy
        self.feature_engine = feature_engine or OptionFeatureEngine()
        self.execution_engine = execution_engine or PaperExecutionEngine(clock=self.clock)
        self.validator = validator or SignalValidator(clock=self.clock)

        if enable_strategy:
            if strategy_manager is not None:
                self.strategy_manager = strategy_manager
            else:
                self.strategy_manager = StrategyManager(
                    validator=self.validator,
                    on_signal_accepted=self._on_signal_accepted,
                    clock=self.clock,
                )
                self.strategy = NiftyOrbBreakoutStrategy()
                self.strategy_manager.register_strategy(self.strategy)
            self.strategy = self.strategy_manager.get_strategy("STRAT-ORB-15M")
        else:
            self.strategy_manager = None
            self.strategy = None

        self._evaluated_bar_keys: Set[Tuple[int, datetime]] = set()

        self.latest_underlying_spot: Optional[Decimal] = None
        self.stats = {
            "ticks_received": 0,
            "quotes_recorded": 0,
            "bars_created": 0,
            "rebalances_triggered": 0,
            "errors": 0,
            "strategy_registered": self.strategy is not None,
            "strategy_evaluations": 0,
            "strategy_eligible_evaluated": 0,
            "strategy_signals_generated": 0,
            "strategy_rejections": 0,
            "paper_trades_executed": 0,
            "strategy_exceptions": 0,
            "last_evaluation_timestamp": None,
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
        if to_unsub:
            self.bar_aggregator.handle_tokens_unsubscribed(to_unsub)
            try:
                self.flush_completed_bars()
            except Exception as e:
                logger.error(f"FnoTickerConsumer.on_connect: Failed to flush unsubscribed token bars: {e}")

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

        # Track live spot high/low for monitoring during 09:15-09:30 IST window
        if self.strategy:
            as_of_ist = as_of_datetime.astimezone(IST)
            spot_session_date = as_of_ist.date()
            if (
                self.strategy.opening_range_session_date is not None
                and self.strategy.opening_range_session_date != spot_session_date
            ):
                self.strategy.opening_range_high = None
                self.strategy.opening_range_low = None
                self.strategy.opening_range_established = False
                self.strategy.opening_range_session_date = spot_session_date

            t = as_of_ist.time()
            if time(9, 15, 0) <= t < time(9, 30, 0):
                if self.strategy.opening_range_high is None or spot_price > self.strategy.opening_range_high:
                    self.strategy.opening_range_high = spot_price
                if self.strategy.opening_range_low is None or spot_price < self.strategy.opening_range_low:
                    self.strategy.opening_range_low = spot_price
            elif t >= time(9, 30, 0) and not self.strategy.opening_range_established:
                self._seed_opening_range_if_needed(as_of_datetime)

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

        # Evacuate and persist partial bars for dropped contracts before losing tick continuity
        if to_unsub:
            self.bar_aggregator.handle_tokens_unsubscribed(to_unsub, as_of_datetime=as_of_datetime)
            try:
                self.flush_completed_bars(as_of_datetime=as_of_datetime)
            except Exception as e:
                logger.error(f"FnoTickerConsumer: Failed to flush unsubscribed token bars: {e}")

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
            if isinstance(raw_tick, OptionTick):
                norm_tick = raw_tick
            elif isinstance(raw_tick, bytes):
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
        """Flushes completed 1-minute option OHLCV bars to PostgreSQL and evaluates registered strategies."""
        created_count = self.bar_aggregator.flush_completed_bars(as_of_datetime=as_of_datetime)
        self.stats["bars_created"] += created_count
        if created_count > 0 and self.strategy_manager:
            flushed_bars = getattr(self.bar_aggregator, "last_flushed_bars", [])
            if flushed_bars:
                self.evaluate_strategies(flushed_bars, as_of_datetime=as_of_datetime)
        return created_count

    def force_close_and_flush_all(self) -> int:
        """Closes all in-flight option bars, marks them partial, and flushes to PostgreSQL."""
        created_count = self.bar_aggregator.force_close_and_flush_all()
        self.stats["bars_created"] += created_count
        return created_count

    def _seed_opening_range_if_needed(self, current_dt: datetime) -> bool:
        """
        Enforces complete 09:15-09:30 IST opening range validation for STRAT-ORB-15M.
        Requires exactly 15 complete, contiguous 1-minute ^NSEI bars
        covering timestamps 09:15:00 through 09:29:00 IST.

        If current time is < 09:30 IST, returns False (range cannot be established early).
        If fewer than 15 bars exist, or any minute is missing/partial, fails closed:
        sets opening_range_established = False and returns False.
        """
        if not self.strategy:
            return False

        current_ist = current_dt.astimezone(IST)
        session_date = current_ist.date()

        # Reset range if session date has rolled over (prevents carrying stale range across sessions)
        if (
            self.strategy.opening_range_session_date is not None
            and self.strategy.opening_range_session_date != session_date
        ):
            self.strategy.opening_range_high = None
            self.strategy.opening_range_low = None
            self.strategy.opening_range_established = False
            self.strategy.opening_range_session_date = session_date

        if self.strategy.opening_range_established:
            return True

        if current_ist.time() < time(9, 30, 0):
            self.strategy.opening_range_established = False
            return False

        try:
            from market.models import Instrument, OHLCVBar
            start_or = datetime.combine(session_date, time(9, 15, 0), tzinfo=IST)
            end_or = datetime.combine(session_date, time(9, 30, 0), tzinfo=IST)

            instrument = Instrument.objects.filter(symbol="^NSEI").first()
            if not instrument:
                logger.warning("FnoTickerConsumer: ^NSEI instrument not found in DB. Opening range unverified.")
                self.strategy.opening_range_established = False
                return False

            bars = list(
                OHLCVBar.objects.filter(
                    instrument=instrument,
                    timeframe="1m",
                    timestamp__gte=start_or,
                    timestamp__lt=end_or,
                ).order_by("timestamp")
            )

            # Strict 15-minute bar completeness validation
            EXPECTED_BAR_COUNT = 15
            if len(bars) != EXPECTED_BAR_COUNT:
                logger.warning(
                    "FnoTickerConsumer: Incomplete opening range for %s. Found %d/%d bars for 09:15-09:30 IST. "
                    "Failing closed: breakout entries prohibited.",
                    session_date,
                    len(bars),
                    EXPECTED_BAR_COUNT,
                )
                self.strategy.opening_range_established = False
                return False

            # Verify exact contiguous minute sequence: 09:15, 09:16, ..., 09:29
            actual_timestamps = [b.timestamp.astimezone(IST) for b in bars]
            expected_timestamps = [start_or + timedelta(minutes=i) for i in range(EXPECTED_BAR_COUNT)]

            if actual_timestamps != expected_timestamps:
                logger.warning(
                    "FnoTickerConsumer: Opening range timestamp mismatch for %s. Expected continuous 09:15-09:29. "
                    "Failing closed: breakout entries prohibited.",
                    session_date,
                )
                self.strategy.opening_range_established = False
                return False

            # Validate bar data integrity: no nulls, high >= low, positive prices
            for b in bars:
                if (
                    b.open is None
                    or b.high is None
                    or b.low is None
                    or b.close is None
                    or b.high < b.low
                    or b.low <= Decimal("0.0")
                ):
                    logger.warning(
                        "FnoTickerConsumer: Invalid bar data in opening range at %s. Failing closed.",
                        b.timestamp,
                    )
                    self.strategy.opening_range_established = False
                    return False

            high = max(b.high for b in bars)
            low = min(b.low for b in bars)
            self.strategy.set_opening_range(high=high, low=low, session_date=session_date)
            logger.info(
                "FnoTickerConsumer: Verified complete 15-bar opening range for %s: High=%.2f, Low=%.2f (15/15 bars verified)",
                session_date,
                high,
                low,
            )
            return True

        except Exception as e:
            logger.error("FnoTickerConsumer: Error verifying opening range from DB: %s", e, exc_info=True)
            self.strategy.opening_range_established = False
            return False

    def evaluate_strategies(
        self,
        bars: List[OptionOHLCVBar],
        as_of_datetime: Optional[datetime] = None,
    ) -> int:
        """
        Evaluates registered strategies against newly completed, eligible OptionOHLCVBar records.
        Constructs OptionFeatureSnapshot instances and forwards them through StrategyManager.
        Enforces:
        - Duplicate bar prevention via _evaluated_bar_keys.
        - Strict skip of partial bars.
        - Accurate opening range establishment (09:15-09:30 IST).
        - Execution dispatch via PaperExecutionEngine.
        - Exception safety ensuring no ticker crash.
        """
        if not self.strategy_manager or not bars:
            return 0

        evaluated_count = 0
        now_utc = as_of_datetime or datetime.now(timezone.utc)
        session_date = now_utc.astimezone(IST).date()

        # Seed opening range from DB if needed
        self._seed_opening_range_if_needed(now_utc)

        spot = self.latest_underlying_spot
        if spot is None:
            try:
                from market.models import OHLCVBar, MarketSnapshot
                symbol = getattr(self.config, "underlying_symbol", "^NSEI")
                bar = OHLCVBar.objects.filter(instrument__symbol=symbol).order_by("-timestamp").first()
                if bar and bar.close:
                    spot = Decimal(str(bar.close))
                    self.latest_underlying_spot = spot
                else:
                    snap = MarketSnapshot.objects.filter(instrument__symbol=symbol).order_by("-timestamp").first()
                    if snap and snap.close:
                        spot = Decimal(str(snap.close))
                        self.latest_underlying_spot = spot
            except Exception:
                pass

        if spot is None:
            logger.debug("FnoTickerConsumer.evaluate_strategies: No underlying spot available. Skipping evaluation.")
            return 0

        for bar in bars:
            # 1. Duplicate evaluation gate
            bar_key = (bar.instrument_token, bar.timestamp)
            if bar_key in self._evaluated_bar_keys:
                continue
            self._evaluated_bar_keys.add(bar_key)

            if len(self._evaluated_bar_keys) > 10000:
                self._evaluated_bar_keys.clear()
                self._evaluated_bar_keys.add(bar_key)

            # 2. Strict skip of partial bars (completed bars only)
            if bar.is_partial_bar:
                logger.debug("FnoTickerConsumer: Skipping partial bar for %s at %s", bar.tradingsymbol, bar.timestamp)
                continue

            try:
                # 3. Fetch latest quote snapshot for execution pricing and depth
                quote = self.quote_manager.get_latest_quote(bar.instrument_token)

                # 4. Build standardized OptionFeatureSnapshot
                feature_snap = self.feature_engine.build_snapshot(
                    bar=bar,
                    quote=quote,
                    underlying_spot=spot,
                    calculation_time=now_utc,
                )

                self.stats["strategy_evaluations"] += 1
                self.stats["last_evaluation_timestamp"] = now_utc.isoformat()

                # 5. Process through StrategyManager
                accepted_signals = self.strategy_manager.process_feature_snapshot(feature_snap)
                evaluated_count += 1
                self.stats["strategy_eligible_evaluated"] += 1

                if accepted_signals:
                    self.stats["strategy_signals_generated"] += len(accepted_signals)
                    logger.info(
                        "FnoTickerConsumer: Strategy generated %d accepted signal(s) on %s at spot %s",
                        len(accepted_signals),
                        bar.tradingsymbol,
                        spot,
                    )

            except Exception as e:
                self.stats["strategy_exceptions"] += 1
                logger.error(
                    "FnoTickerConsumer: Unhandled error evaluating strategy on bar %s (%s): %s",
                    bar.tradingsymbol,
                    bar.timestamp,
                    e,
                    exc_info=True,
                )

        # Update Redis health telemetry for this session
        self._update_strategy_health_telemetry(session_date, now_utc)

        return evaluated_count

    def _on_signal_accepted(self, signal: OptionSignal) -> None:
        """
        Callback invoked when StrategyManager validates and accepts an OptionSignal.
        Executes signal via PaperExecutionEngine against authentic Quote Snapshot.
        """
        try:
            quote = self.quote_manager.get_latest_quote(signal.instrument_token)
            if quote is None:
                logger.warning(
                    "FnoTickerConsumer: No quote snapshot found for signal %s on %s. Cannot execute paper trade.",
                    signal.signal_id,
                    signal.tradingsymbol,
                )
                return

            event = self.execution_engine.process_signal(signal, quote=quote)
            if event:
                if event.event_type == "ORDER_FILLED":
                    self.stats["paper_trades_executed"] += 1
                    logger.info(
                        "FnoTickerConsumer: Paper order filled for %s (%s) @ %s (qty=%d)",
                        signal.tradingsymbol,
                        signal.action,
                        event.fill_price,
                        event.fill_quantity,
                    )
                elif event.event_type == "ORDER_REJECTED":
                    self.stats["strategy_rejections"] += 1
                    logger.info(
                        "FnoTickerConsumer: Paper order rejected for %s: %s",
                        signal.tradingsymbol,
                        event.message,
                    )
                if self.strategy_manager:
                    self.strategy_manager.broadcast_trade_event(event)

        except Exception as e:
            self.stats["strategy_exceptions"] += 1
            logger.error(
                "FnoTickerConsumer: Error executing paper order for signal %s: %s",
                signal.signal_id,
                e,
                exc_info=True,
            )

    def _update_strategy_health_telemetry(self, session_date: date, now_utc: datetime) -> None:
        """Publishes health telemetry to Django cache for cross-process auditing."""
        try:
            from django.core.cache import cache
            rejection_breakdown: Dict[str, int] = {}
            if self.strategy_manager:
                for entry in self.strategy_manager.audit_log:
                    if entry.status == "REJECTED" and entry.rejection_code:
                        rejection_breakdown[entry.rejection_code] = rejection_breakdown.get(entry.rejection_code, 0) + 1

            health_payload = {
                "strategy_id": self.strategy.strategy_id if self.strategy else "STRAT-ORB-15M",
                "strategy_version": self.strategy.strategy_version if self.strategy else "1.0.0",
                "session_date": str(session_date),
                "is_registered": self.strategy is not None,
                "is_enabled": self.strategy.is_enabled if self.strategy else False,
                "opening_range_established": self.strategy.opening_range_established if self.strategy else False,
                "opening_range_high": float(self.strategy.opening_range_high) if (self.strategy and self.strategy.opening_range_high) else None,
                "opening_range_low": float(self.strategy.opening_range_low) if (self.strategy and self.strategy.opening_range_low) else None,
                "evaluations_count": self.stats.get("strategy_evaluations", 0),
                "eligible_evaluations": self.stats.get("strategy_eligible_evaluated", 0),
                "signals_count": self.stats.get("strategy_signals_generated", 0),
                "trades_count": self.stats.get("paper_trades_executed", 0),
                "rejections_count": self.stats.get("strategy_rejections", 0),
                "rejection_breakdown": rejection_breakdown,
                "exceptions_count": self.stats.get("strategy_exceptions", 0),
                "last_evaluation_time": self.stats.get("last_evaluation_timestamp"),
            }
            cache_key = f"fno_strategy_health:{session_date}:{health_payload['strategy_id']}"
            cache.set(cache_key, health_payload, timeout=86400 * 7)
        except Exception as e:
            logger.debug("Could not publish strategy health telemetry: %s", e)
