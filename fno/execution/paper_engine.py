"""
Nomad Analyst — F&O Paper Execution Engine
Reference: Phase 22D Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Simulates authentic taker order execution against persisted OptionQuoteSnapshots.
Enforces:
1. Strict Tick-Grid Rounding:
   - Buys round UP to next tick multiple (conservative: buyer never pays less than model).
   - Sells round DOWN to next tick multiple (conservative: seller never receives more than model).
   - Prevents negative, zero, or impossible fills when bid <= slippage or fill < TICK_SIZE (0.05).
   - Distinguishes explicit zero slippage (0.00) from default slippage using 'is None'.
2. Microstructure Rejections: Rejects stale (>3.0s), locked, crossed, empty, zero-bid, and wide (>2.5%) quotes.
3. Zero-Bid & Tiny-Bid Handling: Marks PENDING_LIQUIDITY without fabricating fills.
4. Terminal Lifecycle at 15:30 Session Close:
   - Expiring contracts: Transitions to PENDING_EXPIRY_SETTLEMENT.
   - Non-expiring contracts: Transitions to UNEXECUTABLE_OVERNIGHT_CARRY.
   - Emits observable CRITICAL_UNRESOLVED_EXPOSURE_ALERT logs.
   - Preserves active in-memory tracking of all unresolved positions (never blindly clears cache).
5. State Synchronization: sync_active_trades_from_db() recovers active positions on restart.
6. Expiry Cash Settlement:
   - Distinct from market taker exits (fill_type="SETTLEMENT", 0 market slippage).
   - Idempotent: settlement charges and P&L can never be applied twice.
   - If official settlement data is unavailable, remains in PENDING_EXPIRY_SETTLEMENT. Never fabricates prices.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import logging
import threading
from typing import Callable, Dict, List, Optional
import uuid
import zoneinfo

from django.db import IntegrityError, connection, transaction

from fno.models import OptionQuoteSnapshot, PaperTradeLedger
from fno.execution.fee_calculator import StatutoryFeeCalculator
from fno.strategies.base import OptionSignal, PaperTradeEvent

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")


PERMITTED_ROUNDING_DIRECTIONS = frozenset({"UP", "CEILING", "DOWN", "FLOOR", "NEAREST"})


def round_to_tick(
    price: Optional[Decimal],
    tick_size: Decimal = Decimal("0.05"),
    direction: str = "NEAREST",
) -> Optional[Decimal]:
    """
    Rounds a Decimal price to an exact multiple of the exchange tick size.
    direction:
      - 'UP' / 'CEILING': rounds up to next tick multiple (conservative for buys)
      - 'DOWN' / 'FLOOR': rounds down to previous tick multiple (conservative for sells)
      - 'NEAREST': rounds to nearest tick with ROUND_HALF_UP

    Validates:
      - tick_size must be positive (> 0)
      - direction must be in PERMITTED_ROUNDING_DIRECTIONS
    """
    if price is None:
        return None

    if tick_size is None or tick_size <= Decimal("0.00"):
        raise ValueError(f"tick_size must be positive, got {tick_size}")

    dir_norm = direction.upper() if direction else ""
    if dir_norm not in PERMITTED_ROUNDING_DIRECTIONS:
        raise ValueError(
            f"Invalid rounding direction '{direction}'. Permitted directions: {sorted(PERMITTED_ROUNDING_DIRECTIONS)}"
        )

    if dir_norm in ("UP", "CEILING"):
        mode = ROUND_CEILING
    elif dir_norm in ("DOWN", "FLOOR"):
        mode = ROUND_FLOOR
    else:
        mode = ROUND_HALF_UP

    ticks = (price / tick_size).quantize(Decimal("1"), rounding=mode)
    return (ticks * tick_size).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PaperExecutionEngine:
    """
    Realistic simulated order execution engine with strict tick-grid rounding
    and robust lifecycle synchronization.
    """

    TICK_SIZE = Decimal("0.05")
    DEFAULT_SLIPPAGE_RATE = Decimal("0.005")  # 0.5%
    MAX_ALLOWED_SPREAD_PCT = Decimal("0.025")  # 2.5%
    QUOTE_FRESHNESS_LIMIT_SEC = Decimal("3.0")

    def __init__(
        self,
        fee_calculator: Optional[StatutoryFeeCalculator] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.fee_calculator = fee_calculator or StatutoryFeeCalculator()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self.active_trades: Dict[str, PaperTradeLedger] = {}  # Key: f"{strategy_id}:{tradingsymbol}"
        self.sync_active_trades_from_db()

    def get_decision_time(self, validation_time: Optional[datetime] = None) -> datetime:
        """Returns authoritative decision-boundary clock used to evaluate quote freshness."""
        return validation_time if validation_time is not None else self.clock()

    def sync_active_trades_from_db(self) -> int:
        """
        Synchronizes in-memory active tracking with the database ledger.
        Loads all unresolved trades: OPEN, PENDING_LIQUIDITY,
        UNEXECUTABLE_OVERNIGHT_CARRY, and PENDING_EXPIRY_SETTLEMENT.
        Ensures restart/reload recovery without state divergence.

        Enforces the Uniqueness Invariant:
        At most one unresolved position can exist per (strategy_id, tradingsymbol).
        If duplicate unresolved rows are detected, raises ValueError to prevent
        silent dictionary-key collisions.
        """
        unresolved_trades = PaperTradeLedger.objects.filter(
            status__in=[
                "OPEN",
                "PENDING_LIQUIDITY",
                "UNEXECUTABLE_OVERNIGHT_CARRY",
                "PENDING_EXPIRY_SETTLEMENT",
            ]
        ).order_by("entry_timestamp")

        self.active_trades.clear()
        count = 0
        for trade in unresolved_trades:
            trade_key = f"{trade.strategy_id}:{trade.tradingsymbol}"
            if trade_key in self.active_trades:
                existing = self.active_trades[trade_key]
                raise ValueError(
                    f"Uniqueness invariant violated: Multiple unresolved ledger rows found for "
                    f"key '{trade_key}' (Trade #{existing.trade_id} with status '{existing.status}' "
                    f"and Trade #{trade.trade_id} with status '{trade.status}'). Cannot silently collide."
                )
            self.active_trades[trade_key] = trade
            count += 1

        logger.info("Synchronized %d active/unresolved trades from DB ledger into PaperExecutionEngine.", count)
        return count

    def calculate_taker_buy_fill(
        self,
        best_ask: Decimal,
        configured_slippage_rate: Optional[Decimal] = None,
        tick_size: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        P_fill_buy = round_up_to_tick(Best Ask + slippage, tick_size)
        where slippage = max(tick_size, round_up_to_tick(best_ask * rate, tick_size)) if rate > 0 else 0.
        Rounding UP guarantees fill is never more favorable than the conservative model.
        Returns None if best_ask is missing, invalid (<= 0), or non-numeric.
        """
        if best_ask is None or best_ask <= Decimal("0.00"):
            return None

        ts = tick_size if tick_size is not None else self.TICK_SIZE
        if ts <= Decimal("0.00"):
            raise ValueError(f"tick_size must be positive, got {ts}")

        rate = self.DEFAULT_SLIPPAGE_RATE if configured_slippage_rate is None else configured_slippage_rate
        if rate < Decimal("0.00"):
            raise ValueError(f"configured_slippage_rate must be non-negative, got {rate}")

        if rate > Decimal("0.00"):
            slippage = max(ts, round_to_tick(best_ask * rate, ts, direction="UP"))
        else:
            slippage = Decimal("0.00")

        fill = round_to_tick(best_ask + slippage, ts, direction="UP")
        return fill

    def calculate_taker_sell_fill(
        self,
        best_bid: Decimal,
        configured_slippage_rate: Optional[Decimal] = None,
        tick_size: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        P_fill_sell = round_down_to_tick(Best Bid - slippage, tick_size)
        where slippage = max(tick_size, round_up_to_tick(best_bid * rate, tick_size)) if rate > 0 else 0.
        Rounding DOWN guarantees fill is never more favorable than the conservative model.
        Returns None if best_bid is missing, zero, <= slippage, or resulting fill < tick_size (0.05).
        """
        if best_bid is None or best_bid <= Decimal("0.00"):
            return None

        ts = tick_size if tick_size is not None else self.TICK_SIZE
        if ts <= Decimal("0.00"):
            raise ValueError(f"tick_size must be positive, got {ts}")

        rate = self.DEFAULT_SLIPPAGE_RATE if configured_slippage_rate is None else configured_slippage_rate
        if rate < Decimal("0.00"):
            raise ValueError(f"configured_slippage_rate must be non-negative, got {rate}")

        if rate > Decimal("0.00"):
            slippage = max(ts, round_to_tick(best_bid * rate, ts, direction="UP"))
        else:
            slippage = Decimal("0.00")

        # If bid cannot cover slippage or bid - slippage < ts:
        if best_bid <= slippage:
            return None

        fill = round_to_tick(best_bid - slippage, ts, direction="DOWN")
        if fill < ts:
            return None

        return fill

    def process_signal(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        market_regime: Optional[str] = None,
        vix_level: Optional[Decimal] = None,
        execution_wall_time: Optional[datetime] = None,
    ) -> Optional[PaperTradeEvent]:
        """
        Executes an incoming OptionSignal against the current quote state.
        Enforces strict statutory fee-schedule date validation, exchange timestamp verification,
        and quote-freshness evaluation at the decision boundary using the engine's trusted clock.
        Returns a PaperTradeEvent reflecting the outcome.
        """
        return self._process_signal_internal(
            signal=signal,
            quote=quote,
            market_regime=market_regime,
            vix_level=vix_level,
            execution_wall_time=execution_wall_time,
            allow_default_schedule=False,
            validation_time=None,
        )

    def _test_only_process_signal_with_override(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        market_regime: Optional[str] = None,
        vix_level: Optional[Decimal] = None,
        execution_wall_time: Optional[datetime] = None,
        *,
        allow_default_schedule: bool = True,
        validation_time: Optional[datetime] = None,
    ) -> Optional[PaperTradeEvent]:
        """
        TEST-ONLY helper for synthetic unit tests requiring explicit fee schedule override.
        Strictly isolated from normal runtime execution interfaces.
        """
        return self._process_signal_internal(
            signal=signal,
            quote=quote,
            market_regime=market_regime,
            vix_level=vix_level,
            execution_wall_time=execution_wall_time,
            allow_default_schedule=allow_default_schedule,
            validation_time=validation_time,
        )

    def _process_signal_internal(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        market_regime: Optional[str] = None,
        vix_level: Optional[Decimal] = None,
        execution_wall_time: Optional[datetime] = None,
        allow_default_schedule: bool = False,
        validation_time: Optional[datetime] = None,
    ) -> Optional[PaperTradeEvent]:
        """
        Internal implementation of process_signal supporting explicit schedule override
        exclusively via isolated internal/test callers.
        """
        # Resolve authoritative execution time:
        # Precedence:
        # 1. Explicit caller-provided execution_wall_time (e.g. historical simulation or explicit test time).
        # 2. Authentic exchange matching engine timestamp (quote.exchange_timestamp_utc)
        #    IFF verified valid (quote.exchange_time_status == "VALID").
        # Local receipt wall clock (quote.received_wall_clock_utc) is daemon arrival telemetry,
        # NOT matching engine execution time, and must never be silently treated as equivalent.
        if execution_wall_time is not None:
            execution_time = execution_wall_time
        elif (
            quote is not None
            and quote.exchange_time_status == "VALID"
            and quote.exchange_timestamp_utc is not None
        ):
            execution_time = quote.exchange_timestamp_utc
        else:
            execution_time = None

        if allow_default_schedule:
            logger.warning(
                "TEST_OVERRIDE_ACTIVE: allow_default_schedule=True for %s signal on %s. "
                "This override is strictly prohibited in live market execution.",
                signal.action,
                signal.tradingsymbol,
            )

        trade_key = f"{signal.strategy_id}:{signal.tradingsymbol}"

        # --- Handle Exit Signals ---
        if signal.action.startswith("EXIT_"):
            return self._handle_exit_signal(
                signal=signal,
                quote=quote,
                trade_key=trade_key,
                execution_time=execution_time,
                allow_default_schedule=allow_default_schedule,
                validation_time=validation_time,
            )

        # --- Handle BUY_TO_OPEN Signal ---
        if signal.action == "BUY_TO_OPEN":
            return self._handle_buy_signal(
                signal=signal,
                quote=quote,
                trade_key=trade_key,
                market_regime=market_regime,
                vix_level=vix_level,
                execution_time=execution_time,
                validation_time=validation_time,
                allow_default_schedule=allow_default_schedule,
            )

        return None

    def _handle_buy_signal(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        trade_key: str,
        market_regime: Optional[str],
        vix_level: Optional[Decimal],
        execution_time: Optional[datetime],
        validation_time: Optional[datetime] = None,
        allow_default_schedule: bool = False,
    ) -> PaperTradeEvent:
        """Validates and executes entry buy taker fills with thread serialization."""
        with self._lock:
            return self._handle_buy_signal_locked(
                signal=signal,
                quote=quote,
                trade_key=trade_key,
                market_regime=market_regime,
                vix_level=vix_level,
                execution_time=execution_time,
                validation_time=validation_time,
                allow_default_schedule=allow_default_schedule,
            )

    def _handle_buy_signal_locked(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        trade_key: str,
        market_regime: Optional[str],
        vix_level: Optional[Decimal],
        execution_time: Optional[datetime],
        validation_time: Optional[datetime] = None,
        allow_default_schedule: bool = False,
    ) -> PaperTradeEvent:
        """Internal locked implementation enforcing position exclusivity and microstructure gating."""
        # 0. Check Authoritative Execution Timestamp
        if execution_time is None:
            rejection_code = (
                "ENTRY_UNVERIFIED_EXCHANGE_TIMESTAMP"
                if (quote and quote.exchange_time_status != "VALID")
                else "ENTRY_MISSING_EXECUTION_TIMESTAMP"
            )
            logger.warning("Rejecting entry signal %s: %s", signal.signal_id, rejection_code)
            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=None,
                message=rejection_code,
            )

        entry_trade_date = execution_time.date()
        if entry_trade_date < StatutoryFeeCalculator.EARLIEST_SUPPORTED_DATE:
            rejection_code = f"UNSUPPORTED_TRADE_DATE_{entry_trade_date}"
            logger.warning("Rejecting entry signal %s: %s", signal.signal_id, rejection_code)
            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=execution_time,
                message=rejection_code,
            )

        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        [f"fno_strategy_exclusive:{signal.strategy_id}"],
                    )

            # Check if already active in DB or memory (enforcing position uniqueness invariant)
            exact_active_trade = PaperTradeLedger.objects.filter(
                strategy_id=signal.strategy_id,
                tradingsymbol=signal.tradingsymbol,
                status__in=[
                    "OPEN",
                    "PENDING_LIQUIDITY",
                    "UNEXECUTABLE_OVERNIGHT_CARRY",
                    "PENDING_EXPIRY_SETTLEMENT",
                ],
            ).first()
            if not exact_active_trade:
                exact_active_trade = self.active_trades.get(trade_key)
            else:
                self.active_trades[trade_key] = exact_active_trade

            strategy_active_trade = exact_active_trade or PaperTradeLedger.objects.filter(
                strategy_id=signal.strategy_id,
                status__in=[
                    "OPEN",
                    "PENDING_LIQUIDITY",
                    "UNEXECUTABLE_OVERNIGHT_CARRY",
                    "PENDING_EXPIRY_SETTLEMENT",
                ],
            ).first()
            if not strategy_active_trade:
                strategy_active_trade = next(
                    (t for t in self.active_trades.values() if t.strategy_id == signal.strategy_id),
                    None
                )
            else:
                active_key = f"{strategy_active_trade.strategy_id}:{strategy_active_trade.tradingsymbol}"
                self.active_trades[active_key] = strategy_active_trade

            if strategy_active_trade:
                if exact_active_trade:
                    rejection_code = "REJECTED_POSITION_ALREADY_OPEN"
                    event_message = rejection_code
                    logger.warning(
                        "Rejecting entry signal %s: %s (Active: %s #%s [%s])",
                        signal.signal_id,
                        rejection_code,
                        exact_active_trade.tradingsymbol,
                        exact_active_trade.trade_id,
                        exact_active_trade.status,
                    )
                else:
                    rejection_code = "REJECTED_MAX_CONCURRENT_POSITIONS_EXCEEDED"
                    event_message = f"{rejection_code} (Active: {strategy_active_trade.tradingsymbol} #{strategy_active_trade.trade_id} [{strategy_active_trade.status}])"
                    logger.warning(
                        "Rejecting entry signal %s for %s: %s",
                        signal.signal_id,
                        signal.strategy_id,
                        event_message,
                    )
                try:
                    PaperTradeLedger.objects.create(
                        strategy_id=signal.strategy_id,
                        strategy_version=signal.strategy_version,
                        signal_id=uuid.UUID(str(signal.signal_id)),
                        instrument_token=signal.instrument_token,
                        tradingsymbol=signal.tradingsymbol,
                        option_type=signal.option_type,
                        strike_price=signal.strike_price,
                        expiry_date=signal.expiry_date,
                        entry_timestamp=execution_time,
                        entry_fill_price=Decimal("0.00"),
                        entry_slippage=Decimal("0.00"),
                        quantity=signal.suggested_lot_count * 65,
                        status="REJECTED",
                        rejection_reason=rejection_code,
                        market_regime_at_entry=market_regime,
                        vix_level_at_entry=vix_level,
                    )
                except Exception as e:
                    logger.error("Failed to record rejected paper trade in ledger: %s", e)

                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message=event_message,
                )

            # Microstructure Gating Checks
            rejection_reason = self._check_quote_execution_eligibility(
                quote,
                validation_time=validation_time,
                is_exit=False,
                allow_default_schedule=allow_default_schedule,
            )
            if rejection_reason is not None:
                logger.info("Entry signal %s rejected by quote gate: %s", signal.signal_id, rejection_reason)
                PaperTradeLedger.objects.create(
                    strategy_id=signal.strategy_id,
                    strategy_version=signal.strategy_version,
                    signal_id=uuid.UUID(signal.signal_id),
                    instrument_token=signal.instrument_token,
                    tradingsymbol=signal.tradingsymbol,
                    option_type=signal.option_type,
                    strike_price=signal.strike_price,
                    expiry_date=signal.expiry_date,
                    entry_timestamp=execution_time,
                    entry_fill_price=Decimal("0.00"),
                    entry_slippage=Decimal("0.00"),
                    quantity=signal.suggested_lot_count * 65,  # NIFTY lot
                    status="REJECTED",
                    rejection_reason=rejection_reason,
                    market_regime_at_entry=market_regime,
                    vix_level_at_entry=vix_level,
                )

                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message=rejection_reason,
                )

            # Calculate conservative fill with strict tick-grid rounding
            best_ask = quote.best_ask
            fill_price = self.calculate_taker_buy_fill(best_ask)
            if fill_price is None:
                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message="REJECTED_INVALID_ASK_PRICE",
                )

            slippage = fill_price - best_ask
            qty = signal.suggested_lot_count * 65

            # Check max acceptable slippage
            slippage_pct = slippage / best_ask
            if slippage_pct > signal.max_acceptable_slippage_pct:
                logger.info("Signal %s rejected: slippage %s exceeds max %s", signal.signal_id, slippage_pct, signal.max_acceptable_slippage_pct)
                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message="REJECTED_EXCESSIVE_SLIPPAGE",
                )

            # Create Open Trade Ledger Entry
            try:
                trade = PaperTradeLedger.objects.create(
                    strategy_id=signal.strategy_id,
                    strategy_version=signal.strategy_version,
                    signal_id=uuid.UUID(str(signal.signal_id)),
                    instrument_token=signal.instrument_token,
                    tradingsymbol=signal.tradingsymbol,
                    option_type=signal.option_type,
                    strike_price=signal.strike_price,
                    expiry_date=signal.expiry_date,
                    entry_timestamp=execution_time,
                    entry_fill_price=fill_price,
                    entry_slippage=slippage,
                    quantity=qty,
                    status="OPEN",
                    market_regime_at_entry=market_regime,
                    vix_level_at_entry=vix_level,
                )
            except IntegrityError:
                rejection_code = "REJECTED_MAX_CONCURRENT_POSITIONS_EXCEEDED"
                logger.warning(
                    "Concurrent collision detected: Database exclusivity constraint prevented duplicate open position for %s (signal %s)",
                    signal.strategy_id,
                    signal.signal_id,
                )
                self.sync_active_trades_from_db()
                winning_trade = next((t for t in self.active_trades.values() if t.strategy_id == signal.strategy_id), None)
                active_info = f"Active: {winning_trade.tradingsymbol} #{winning_trade.trade_id} [{winning_trade.status}]" if winning_trade else "Active position exists"
                event_message = f"{rejection_code} ({active_info})"

                try:
                    PaperTradeLedger.objects.create(
                        strategy_id=signal.strategy_id,
                        strategy_version=signal.strategy_version,
                        signal_id=uuid.UUID(str(signal.signal_id)),
                        instrument_token=signal.instrument_token,
                        tradingsymbol=signal.tradingsymbol,
                        option_type=signal.option_type,
                        strike_price=signal.strike_price,
                        expiry_date=signal.expiry_date,
                        entry_timestamp=execution_time,
                        entry_fill_price=Decimal("0.00"),
                        entry_slippage=Decimal("0.00"),
                        quantity=qty,
                        status="REJECTED",
                        rejection_reason=rejection_code,
                        market_regime_at_entry=market_regime,
                        vix_level_at_entry=vix_level,
                    )
                except Exception as e:
                    logger.error("Failed to record concurrent collision rejection in ledger: %s", e)

                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message=event_message,
                )

            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_FILLED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=fill_price,
                fill_quantity=qty,
                slippage=slippage,
                timestamp=execution_time,
                message="TAKER_BUY_FILLED",
            )

    def _handle_exit_signal(
        self,
        signal: OptionSignal,
        quote: OptionQuoteSnapshot,
        trade_key: str,
        execution_time: Optional[datetime],
        allow_default_schedule: bool = False,
        validation_time: Optional[datetime] = None,
    ) -> PaperTradeEvent:
        """Validates and executes exit orders against best bid."""
        trade = self.active_trades.get(trade_key)
        if not trade:
            trade = PaperTradeLedger.objects.filter(
                strategy_id=signal.strategy_id,
                tradingsymbol=signal.tradingsymbol,
                status__in=["OPEN", "PENDING_LIQUIDITY", "UNEXECUTABLE_OVERNIGHT_CARRY"],
            ).order_by("-entry_timestamp").first()

            if not trade:
                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ORDER_REJECTED",
                    strategy_id=signal.strategy_id,
                    signal_id=signal.signal_id,
                    tradingsymbol=signal.tradingsymbol,
                    fill_price=None,
                    fill_quantity=0,
                    slippage=Decimal("0.00"),
                    timestamp=execution_time,
                    message="NO_OPEN_POSITION_FOUND",
                )
            self.active_trades[trade_key] = trade

        # 0. Check Authoritative Execution Timestamp
        if execution_time is None and not allow_default_schedule:
            rejection_code = (
                "EXIT_UNVERIFIED_EXCHANGE_TIMESTAMP"
                if (quote and quote.exchange_time_status != "VALID")
                else "EXIT_MISSING_EXECUTION_TIMESTAMP"
            )
            logger.warning(
                "Authoritative execution timestamp unresolvable (%s) on exit signal %s for %s. "
                "Preserving trade in PENDING_LIQUIDITY.",
                rejection_code,
                signal.signal_id,
                trade.tradingsymbol,
            )
            trade.status = "PENDING_LIQUIDITY"
            trade.exit_trigger_reason = signal.action
            trade.rejection_reason = rejection_code
            trade.save()
            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=None,
                message=rejection_code,
            )

        # 1. Check Zero-Bid Microstructure Trap
        if quote.best_bid is None or quote.best_bid <= Decimal("0.00") or quote.quote_status == "ZERO_BID":
            logger.warning("Zero bid liquidity on exit trigger %s for %s. Marking PENDING_LIQUIDITY.", signal.signal_id, trade.tradingsymbol)
            trade.status = "PENDING_LIQUIDITY"
            trade.exit_trigger_reason = signal.action
            trade.rejection_reason = "EXIT_UNEXECUTABLE_ZERO_BID"
            trade.save()
            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=execution_time,
                message="EXIT_UNEXECUTABLE_ZERO_BID",
            )

        # 2. Check Tiny-Bid Slippage Floor
        fill_price = self.calculate_taker_sell_fill(quote.best_bid)
        if fill_price is None:
            logger.warning("Bid %s is below executable slippage threshold for %s. Marking PENDING_LIQUIDITY.", quote.best_bid, trade.tradingsymbol)
            trade.status = "PENDING_LIQUIDITY"
            trade.exit_trigger_reason = signal.action
            trade.rejection_reason = "EXIT_UNEXECUTABLE_TINY_BID"
            trade.save()
            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=execution_time,
                message="EXIT_UNEXECUTABLE_TINY_BID",
            )

        # 3. Symmetric quote freshness and microstructure eligibility gate for exit
        eligibility_reason = self._check_quote_execution_eligibility(
            quote,
            validation_time=validation_time,
            is_exit=True,
            allow_default_schedule=allow_default_schedule,
        )
        if eligibility_reason is not None:
            logger.warning(
                "Exit quote failed eligibility guard (%s) on signal %s for %s. Preserving trade in PENDING_LIQUIDITY.",
                eligibility_reason,
                signal.signal_id,
                trade.tradingsymbol,
            )
            trade.status = "PENDING_LIQUIDITY"
            trade.exit_trigger_reason = signal.action
            trade.rejection_reason = eligibility_reason
            trade.save()
            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=execution_time,
                message=eligibility_reason,
            )

        # 3. Valid Taker Sell Fill Execution
        best_bid = quote.best_bid
        slippage = best_bid - fill_price

        # Calculate PnL and statutory frictions
        exit_trade_date = execution_time.date() if execution_time else None
        gross_pnl = (fill_price - trade.entry_fill_price) * Decimal(str(trade.quantity))
        try:
            frictions = self.fee_calculator.calculate_round_trip(
                buy_price=trade.entry_fill_price,
                sell_price=fill_price,
                quantity=trade.quantity,
                is_exercise_settlement=False,
                trade_date=exit_trade_date,
                allow_default_schedule=allow_default_schedule,
            )
        except ValueError as exc:
            logger.error(
                "Fee calculation failed on exit for %s (trade_date=%s): %s. "
                "Preserving trade in PENDING_LIQUIDITY.",
                trade.tradingsymbol,
                exit_trade_date,
                exc,
            )
            trade.status = "PENDING_LIQUIDITY"
            trade.exit_trigger_reason = signal.action
            trade.rejection_reason = f"FEE_CALCULATION_FAILED: {exc}"
            trade.save()
            self.active_trades[trade_key] = trade

            return PaperTradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="ORDER_REJECTED",
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                tradingsymbol=signal.tradingsymbol,
                fill_price=None,
                fill_quantity=0,
                slippage=Decimal("0.00"),
                timestamp=execution_time,
                message=f"FEE_CALCULATION_FAILED: {exc}",
            )
        net_pnl = gross_pnl - frictions.total_frictions

        with transaction.atomic():
            trade.exit_timestamp = execution_time
            trade.exit_fill_price = fill_price
            trade.exit_slippage = slippage
            trade.exit_trigger_reason = signal.action
            trade.fill_type = "MARKET_TAKER"
            trade.gross_pnl = gross_pnl
            trade.total_frictions = frictions.total_frictions
            trade.net_pnl = net_pnl
            trade.friction_breakdown = frictions.to_dict()
            trade.status = "CLOSED"
            trade.rejection_reason = None
            trade.save()

        # Remove from active tracking only once terminal closed
        self.active_trades.pop(trade_key, None)

        return PaperTradeEvent(
            event_id=str(uuid.uuid4()),
            event_type="POSITION_CLOSED",
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            tradingsymbol=signal.tradingsymbol,
            fill_price=fill_price,
            fill_quantity=trade.quantity,
            slippage=slippage,
            timestamp=execution_time,
            message="TAKER_SELL_FILLED",
        )

    def handle_session_close_cutoff(self, session_close_dt: datetime) -> Dict[str, int]:
        """
        Enforces terminal and transition rules at 15:30 IST market close:
        1. Expiring contracts (expiry_date == today): Transition to PENDING_EXPIRY_SETTLEMENT.
           Expired contracts are strictly prohibited from overnight carry or next-session exit retries.
        2. Non-expiring contracts (expiry_date > today): Transition unexecutable positions
           (OPEN or PENDING_LIQUIDITY) to UNEXECUTABLE_OVERNIGHT_CARRY.
           A no-overnight policy cannot guarantee a market exit when no bid exists.
        3. Preserves active tracking in self.active_trades for all unresolved positions.
        4. Emits observable CRITICAL_UNRESOLVED_EXPOSURE_ALERT logs for auditability.
        Returns: {"pending_expiry_settlement": int, "unexecutable_overnight_carry": int}
        """
        session_date = session_close_dt.astimezone(IST).date()

        # 1. Expiring contracts -> PENDING_EXPIRY_SETTLEMENT
        expiring_trades = PaperTradeLedger.objects.filter(
            expiry_date=session_date,
            status__in=["OPEN", "PENDING_LIQUIDITY", "PENDING_EXPIRY_SETTLEMENT"],
        )
        expiring_count = 0
        for trade in expiring_trades:
            if trade.status != "PENDING_EXPIRY_SETTLEMENT":
                trade.status = "PENDING_EXPIRY_SETTLEMENT"
                trade.rejection_reason = "EXPIRY_SESSION_CLOSE_PENDING_SETTLEMENT"
                trade.save()
                logger.warning(
                    "CRITICAL_UNRESOLVED_EXPOSURE_ALERT [EXPIRING]: Strategy %s has unexecutable exposure in %s (%d qty). "
                    "Transitioned to PENDING_EXPIRY_SETTLEMENT at cutoff %s. Awaiting official settlement price.",
                    trade.strategy_id, trade.tradingsymbol, trade.quantity, session_close_dt
                )
            trade_key = f"{trade.strategy_id}:{trade.tradingsymbol}"
            self.active_trades[trade_key] = trade
            expiring_count += 1

        # 2. Non-expiring contracts with pending liquidity / open exit triggers -> UNEXECUTABLE_OVERNIGHT_CARRY
        carry_trades = PaperTradeLedger.objects.filter(
            expiry_date__gt=session_date,
            status__in=["OPEN", "PENDING_LIQUIDITY", "UNEXECUTABLE_OVERNIGHT_CARRY"],
        )
        carry_count = 0
        for trade in carry_trades:
            if trade.status != "UNEXECUTABLE_OVERNIGHT_CARRY":
                trade.status = "UNEXECUTABLE_OVERNIGHT_CARRY"
                trade.rejection_reason = "SESSION_CLOSE_UNEXECUTABLE_OVERNIGHT_CARRY"
                trade.save()
                logger.warning(
                    "CRITICAL_UNRESOLVED_EXPOSURE_ALERT [UNEXPIRED CARRY]: Strategy %s has unexecutable exposure in %s (%d qty). "
                    "No bid existed at 15:30 IST cutoff %s. Transitioned to UNEXECUTABLE_OVERNIGHT_CARRY. Exit attempts resume at 09:15 IST.",
                    trade.strategy_id, trade.tradingsymbol, trade.quantity, session_close_dt
                )
            trade_key = f"{trade.strategy_id}:{trade.tradingsymbol}"
            self.active_trades[trade_key] = trade
            carry_count += 1

        return {
            "pending_expiry_settlement": expiring_count,
            "unexecutable_overnight_carry": carry_count,
        }

    def transition_to_pending_expiry(self, expiry_cutoff_dt: datetime) -> int:
        """Backward-compatible helper transitioning expiry day contracts."""
        res = self.handle_session_close_cutoff(expiry_cutoff_dt)
        return res["pending_expiry_settlement"]

    def resolve_expiry_settlement(
        self,
        strategy_id: str,
        tradingsymbol: str,
        underlying_settlement_price: Optional[Decimal],
        settlement_timestamp: Optional[datetime],
    ) -> Optional[PaperTradeEvent]:
        """
        Resolves expired option contract via official exchange cash settlement.
        Enforces strict statutory fee-schedule date validation and timestamp checks.
        """
        return self._resolve_expiry_settlement_internal(
            strategy_id=strategy_id,
            tradingsymbol=tradingsymbol,
            underlying_settlement_price=underlying_settlement_price,
            settlement_timestamp=settlement_timestamp,
            allow_default_schedule=False,
        )

    def _test_only_resolve_expiry_settlement_with_override(
        self,
        strategy_id: str,
        tradingsymbol: str,
        underlying_settlement_price: Optional[Decimal],
        settlement_timestamp: Optional[datetime],
        *,
        allow_default_schedule: bool = True,
    ) -> Optional[PaperTradeEvent]:
        """
        TEST-ONLY helper for synthetic unit tests requiring explicit fee schedule override.
        Strictly isolated from normal runtime execution interfaces.
        """
        return self._resolve_expiry_settlement_internal(
            strategy_id=strategy_id,
            tradingsymbol=tradingsymbol,
            underlying_settlement_price=underlying_settlement_price,
            settlement_timestamp=settlement_timestamp,
            allow_default_schedule=allow_default_schedule,
        )

    def _resolve_expiry_settlement_internal(
        self,
        strategy_id: str,
        tradingsymbol: str,
        underlying_settlement_price: Optional[Decimal],
        settlement_timestamp: Optional[datetime],
        allow_default_schedule: bool = False,
    ) -> Optional[PaperTradeEvent]:
        """
        Internal implementation of resolve_expiry_settlement supporting explicit schedule override
        exclusively via isolated internal/test callers.
        """
        trade_key = f"{strategy_id}:{tradingsymbol}"
        if allow_default_schedule:
            logger.warning(
                "TEST_OVERRIDE_ACTIVE: allow_default_schedule=True for settlement on %s. "
                "This override is strictly prohibited in live market execution.",
                tradingsymbol,
            )
        trade = PaperTradeLedger.objects.filter(
            strategy_id=strategy_id,
            tradingsymbol=tradingsymbol,
            status__in=["OPEN", "PENDING_LIQUIDITY", "PENDING_EXPIRY_SETTLEMENT"],
        ).order_by("-entry_timestamp").first()

        if not trade:
            # Check if already settled (idempotency guard)
            already_settled = PaperTradeLedger.objects.filter(
                strategy_id=strategy_id,
                tradingsymbol=tradingsymbol,
                status__in=["CLOSED_EXPIRED_WORTHLESS", "CLOSED_EXPIRED_ITM_SETTLED"],
            ).order_by("-entry_timestamp").first()
            if already_settled:
                logger.info("Trade %s already settled with status %s. Ignoring duplicate settlement call.", tradingsymbol, already_settled.status)
                return PaperTradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="SETTLEMENT",
                    strategy_id=strategy_id,
                    signal_id=str(already_settled.signal_id),
                    tradingsymbol=tradingsymbol,
                    fill_price=already_settled.exit_fill_price,
                    fill_quantity=already_settled.quantity,
                    slippage=Decimal("0.00"),
                    timestamp=settlement_timestamp,
                    message=f"DUPLICATE_SETTLEMENT_IGNORED_{already_settled.status}",
                )
            return None

        if underlying_settlement_price is None:
            logger.warning("Settlement price unavailable for %s. Position remains PENDING_EXPIRY_SETTLEMENT.", tradingsymbol)
            if trade.status != "PENDING_EXPIRY_SETTLEMENT":
                trade.status = "PENDING_EXPIRY_SETTLEMENT"
            trade.rejection_reason = "SETTLEMENT_PRICE_UNAVAILABLE"
            trade.save()
            self.active_trades[trade_key] = trade
            return None

        if settlement_timestamp is None and not allow_default_schedule:
            logger.warning(
                "Settlement timestamp unavailable for %s. Position remains PENDING_EXPIRY_SETTLEMENT.",
                tradingsymbol,
            )
            if trade.status != "PENDING_EXPIRY_SETTLEMENT":
                trade.status = "PENDING_EXPIRY_SETTLEMENT"
            trade.rejection_reason = "SETTLEMENT_MISSING_TIMESTAMP"
            trade.save()
            self.active_trades[trade_key] = trade
            return None

        # Calculate intrinsic settlement price
        opt = trade.option_type.upper()
        if opt == "CE":
            intrinsic = max(Decimal("0.00"), underlying_settlement_price - trade.strike_price)
        else:
            intrinsic = max(Decimal("0.00"), trade.strike_price - underlying_settlement_price)

        settlement_fill = intrinsic.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gross_pnl = (settlement_fill - trade.entry_fill_price) * Decimal(str(trade.quantity))

        settle_trade_date = settlement_timestamp.date() if settlement_timestamp else None
        try:
            frictions = self.fee_calculator.calculate_round_trip(
                buy_price=trade.entry_fill_price,
                sell_price=settlement_fill,
                quantity=trade.quantity,
                is_exercise_settlement=True,
                trade_date=settle_trade_date,
                allow_default_schedule=allow_default_schedule,
            )
        except ValueError as exc:
            logger.error(
                "Fee calculation failed during settlement for %s (trade_date=%s): %s. "
                "Preserving trade in PENDING_EXPIRY_SETTLEMENT.",
                tradingsymbol,
                settle_trade_date,
                exc,
            )
            if trade.status != "PENDING_EXPIRY_SETTLEMENT":
                trade.status = "PENDING_EXPIRY_SETTLEMENT"
            trade.rejection_reason = f"SETTLEMENT_FEE_CALCULATION_FAILED: {exc}"
            trade.save()
            self.active_trades[trade_key] = trade
            return None

        net_pnl = gross_pnl - frictions.total_frictions
        new_status = "CLOSED_EXPIRED_ITM_SETTLED" if settlement_fill > Decimal("0.00") else "CLOSED_EXPIRED_WORTHLESS"

        with transaction.atomic():
            trade.exit_timestamp = settlement_timestamp
            trade.exit_fill_price = settlement_fill
            trade.exit_slippage = Decimal("0.00")  # Cash settlement incurs zero market slippage
            trade.exit_trigger_reason = "EXPIRY_CASH_SETTLED"
            trade.fill_type = "SETTLEMENT"
            trade.gross_pnl = gross_pnl
            trade.total_frictions = frictions.total_frictions
            trade.net_pnl = net_pnl
            trade.friction_breakdown = frictions.to_dict()
            trade.status = new_status
            trade.rejection_reason = None
            trade.save()

        # Remove from active unresolved cache now that it is resolved
        self.active_trades.pop(trade_key, None)

        return PaperTradeEvent(
            event_id=str(uuid.uuid4()),
            event_type="SETTLEMENT",
            strategy_id=strategy_id,
            signal_id=str(trade.signal_id),
            tradingsymbol=tradingsymbol,
            fill_price=settlement_fill,
            fill_quantity=trade.quantity,
            slippage=Decimal("0.00"),
            timestamp=settlement_timestamp,
            message=new_status,
        )

    def _check_quote_execution_eligibility(
        self,
        quote: OptionQuoteSnapshot,
        validation_time: Optional[datetime] = None,
        *,
        is_exit: bool = False,
        allow_default_schedule: bool = False,
    ) -> Optional[str]:
        """
        Validates quote freshness, timestamp integrity, and order-book microstructure
        at the execution decision boundary for taker fills.
        """
        if quote is None:
            return "REJECTED_MISSING_QUOTE"

        if not (allow_default_schedule and quote.exchange_timestamp_utc is None):
            if quote.exchange_time_status != "VALID" or quote.exchange_timestamp_utc is None:
                return "REJECTED_UNVERIFIED_TIMESTAMP"

            # Timezone verification - fail closed on naive datetimes
            if quote.exchange_timestamp_utc.tzinfo is None:
                return "REJECTED_TIMEZONE_AMBIGUOUS"

            decision_time = self.get_decision_time(validation_time)
            if decision_time.tzinfo is None:
                return "REJECTED_TIMEZONE_AMBIGUOUS"

            # Dynamically recalculate quote age at decision boundary
            quote_age_sec = Decimal(str(round((decision_time - quote.exchange_timestamp_utc).total_seconds(), 4)))
            if quote_age_sec < Decimal("0.0"):
                return "REJECTED_FUTURE_TIMESTAMP"

            if quote_age_sec > self.QUOTE_FRESHNESS_LIMIT_SEC:
                return "REJECTED_STALE_QUOTE"

        if quote.is_stale or quote.quote_status == "STALE":
            return "REJECTED_STALE_QUOTE"

        if quote.quote_status == "EMPTY_BOOK" or quote.best_ask is None or quote.best_bid is None:
            return "REJECTED_EMPTY_BOOK"

        if quote.quote_status == "ZERO_BID" or quote.best_bid <= Decimal("0.00"):
            return "REJECTED_ZERO_BID"

        if not is_exit and quote.best_ask <= Decimal("0.00"):
            return "REJECTED_INVALID_ASK_PRICE"

        if quote.is_locked or quote.quote_status == "LOCKED":
            return "REJECTED_LOCKED_QUOTE"

        if quote.is_crossed or quote.quote_status == "CROSSED":
            return "REJECTED_CROSSED_BOOK"

        spread = quote.best_ask - quote.best_bid
        if quote.best_bid > Decimal("0.00"):
            spread_pct = spread / quote.best_bid
            if spread_pct > self.MAX_ALLOWED_SPREAD_PCT:
                return "REJECTED_EXCESSIVE_SPREAD"

        return None
