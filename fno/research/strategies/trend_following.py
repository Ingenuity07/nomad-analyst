"""
Nomad Analyst — NIFTY Intraday Dual EMA & Donchian Breakout Strategy Plugin
Reference: docs/architecture/strategy_interface_v1.md (Strategy Family 2)
Strategy ID: STRAT-TREND-EMA-DONCHIAN
"""

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fno.backtester.models import SessionQualification
from fno.research.interfaces import (
    BaseNiftyOptionStrategy,
    BaseStrategyConfig,
    SessionContext,
    SignalDirection,
    StrategySignal,
)


@dataclass(frozen=True)
class TrendStrategyConfig(BaseStrategyConfig):
    """
    Configuration for NIFTY Intraday Dual EMA & Donchian Trend strategy.
    Isolated from ORB configuration — no ORB range limits or filters apply.
    """
    strategy_id: str = "STRAT-TREND-EMA-DONCHIAN"
    strategy_name: str = "NIFTY Intraday Dual EMA & Donchian Trend"
    strategy_version: str = "1.0.0"
    
    # Indicator Parameters
    fast_ema_period: int = 9
    slow_ema_period: int = 21
    donchian_period: int = 20
    candle_body_threshold_pct: Decimal = Decimal("0.70")  # Candle closes in upper/lower 30% of range
    
    # Timing & Warm-up
    minimum_warmup_bars: int = 21                         # 21 bars to seed 21-EMA (09:15 to 09:35)
    entry_window_start: time = time(9, 45, 0)             # Entries allowed from 09:45:00 IST
    entry_window_end: time = time(14, 0, 0)               # Hard cutoff for simulated fill timestamp
    
    # Risk & Exit Parameters
    stop_loss_pct: Decimal = Decimal("0.15")              # 15% stop-loss on option entry price
    profit_target_pct: Decimal = Decimal("0.30")          # 30% profit target (asymmetric risk/reward)
    max_holding_minutes: int = 60                         # 60 minutes maximum holding duration
    eod_square_off_time: time = time(15, 15, 0)           # Mandatory square-off at 15:15:00 IST


class NiftyTrendFollowingPlugin(BaseNiftyOptionStrategy):
    """
    Deterministic trend-following strategy combining Dual EMAs (9 & 21) for trend
    direction with a 20-period Donchian Channel for volatility breakout confirmation.
    Operates strictly on 1-minute NIFTY spot index candles with no spot-volume reliance.
    """

    def __init__(self, config: Optional[TrendStrategyConfig] = None):
        cfg = config or TrendStrategyConfig()
        super().__init__(cfg)
        self.config: TrendStrategyConfig = cfg
        
        # State tracking (intraday only, reset per session)
        self._history: List[Dict[str, Any]] = []
        self._closes: List[Decimal] = []
        self._fast_ema: Optional[Decimal] = None
        self._slow_ema: Optional[Decimal] = None
        self._signal_emitted: bool = False
        
        # Multipliers
        self._alpha_fast = Decimal("2") / Decimal(str(self.config.fast_ema_period + 1))
        self._alpha_slow = Decimal("2") / Decimal(str(self.config.slow_ema_period + 1))

    def initialize_session(self, context: SessionContext) -> None:
        """
        Called at 09:15:00 IST before the first bar of each trading session.
        Resets intraday indicator state, rolling windows, and signal flags.
        """
        self._history.clear()
        self._closes.clear()
        self._fast_ema = None
        self._slow_ema = None
        self._signal_emitted = False

    @property
    def fast_ema(self) -> Optional[Decimal]:
        return self._fast_ema

    @property
    def slow_ema(self) -> Optional[Decimal]:
        return self._slow_ema

    @property
    def history_count(self) -> int:
        return len(self._history)

    def evaluate_session_qualification(
        self,
        index_bars: List[Dict[str, Any]],
        context: SessionContext,
    ) -> Tuple[bool, Optional[str], Optional[SessionQualification]]:
        """
        Trend strategy does not enforce ORB range width filters.
        Qualifies all sessions that passed core calendar and data gating.
        """
        return True, None, None

    def on_index_bar(
        self,
        bar: Dict[str, Any],
        context: SessionContext,
    ) -> Optional[StrategySignal]:
        """
        Processes a single closed 1-minute NIFTY index bar sequentially.
        Updates EMA-9, EMA-21, and Donchian channel state.
        Emits BUY_CE or BUY_PE if trend breakout conditions are met.
        """
        close = Decimal(str(bar["close"]))
        high = Decimal(str(bar["high"]))
        low = Decimal(str(bar["low"]))
        bar_time = bar["timestamp_ist"].time()

        # Update closes history for EMA initialization
        self._closes.append(close)
        
        # Update Fast EMA (9)
        if self._fast_ema is None:
            if len(self._closes) >= self.config.fast_ema_period:
                seed_slice = self._closes[:self.config.fast_ema_period]
                self._fast_ema = sum(seed_slice) / Decimal(str(self.config.fast_ema_period))
        else:
            self._fast_ema = (self._alpha_fast * close) + ((Decimal("1") - self._alpha_fast) * self._fast_ema)

        # Update Slow EMA (21)
        if self._slow_ema is None:
            if len(self._closes) >= self.config.slow_ema_period:
                seed_slice = self._closes[:self.config.slow_ema_period]
                self._slow_ema = sum(seed_slice) / Decimal(str(self.config.slow_ema_period))
        else:
            self._slow_ema = (self._alpha_slow * close) + ((Decimal("1") - self._alpha_slow) * self._slow_ema)

        # Check entry gating
        # 1. Single trade per session restriction
        if self._signal_emitted:
            self._history.append(bar)
            return None

        # 2. Timing window: active entry window is [09:45:00, 14:00:00)
        if bar_time < self.config.entry_window_start or bar_time >= self.config.entry_window_end:
            self._history.append(bar)
            return None

        # 3. Minimum warm-up check: both EMAs and Donchian window must be fully initialized
        if (
            self._fast_ema is None
            or self._slow_ema is None
            or len(self._history) < self.config.donchian_period
        ):
            self._history.append(bar)
            return None

        # 4. Donchian Channel over PREVIOUS 20 closed index bars (strictly excluding bar T)
        donchian_window = self._history[-self.config.donchian_period:]
        donchian_high = max(Decimal(str(b["high"])) for b in donchian_window)
        donchian_low = min(Decimal(str(b["low"])) for b in donchian_window)

        # 5. Candle range & body close position
        candle_range = high - low
        if candle_range > Decimal("0"):
            bullish_body = (close - low) >= (self.config.candle_body_threshold_pct * candle_range)
            bearish_body = (high - close) >= (self.config.candle_body_threshold_pct * candle_range)
        else:
            bullish_body = True
            bearish_body = True

        signal: Optional[StrategySignal] = None

        # Bullish Trend Trigger: EMA9 > EMA21, Close > Donchian High, Bullish Body Close
        if self._fast_ema > self._slow_ema and close > donchian_high and bullish_body:
            self._signal_emitted = True
            signal = StrategySignal(
                signal_id=f"SIG-TREND-{context.trading_day.strftime('%Y%m%d')}-{bar['timestamp_ist'].strftime('%H%M')}",
                strategy_id=self.strategy_id,
                signal_timestamp_ist=bar["timestamp_ist"],
                direction=SignalDirection.BUY_CE,
                index_spot_price=close,
                stop_loss_pct=self.config.stop_loss_pct,
                profit_target_pct=self.config.profit_target_pct,
                max_holding_minutes=self.config.max_holding_minutes,
                entry_cutoff_time=self.config.entry_window_end,
                trigger_reason=f"Bullish Trend: EMA9 ({self._fast_ema:.2f}) > EMA21 ({self._slow_ema:.2f}), Close ({close}) > DonchianHigh ({donchian_high})",
                metadata={
                    "fast_ema": str(self._fast_ema),
                    "slow_ema": str(self._slow_ema),
                    "donchian_high": str(donchian_high),
                    "donchian_low": str(donchian_low),
                    "candle_body_ratio": str((close - low) / candle_range) if candle_range > 0 else "1.00",
                },
            )

        # Bearish Trend Trigger: EMA9 < EMA21, Close < Donchian Low, Bearish Body Close
        elif self._fast_ema < self._slow_ema and close < donchian_low and bearish_body:
            self._signal_emitted = True
            signal = StrategySignal(
                signal_id=f"SIG-TREND-{context.trading_day.strftime('%Y%m%d')}-{bar['timestamp_ist'].strftime('%H%M')}",
                strategy_id=self.strategy_id,
                signal_timestamp_ist=bar["timestamp_ist"],
                direction=SignalDirection.BUY_PE,
                index_spot_price=close,
                stop_loss_pct=self.config.stop_loss_pct,
                profit_target_pct=self.config.profit_target_pct,
                max_holding_minutes=self.config.max_holding_minutes,
                entry_cutoff_time=self.config.entry_window_end,
                trigger_reason=f"Bearish Trend: EMA9 ({self._fast_ema:.2f}) < EMA21 ({self._slow_ema:.2f}), Close ({close}) < DonchianLow ({donchian_low})",
                metadata={
                    "fast_ema": str(self._fast_ema),
                    "slow_ema": str(self._slow_ema),
                    "donchian_high": str(donchian_high),
                    "donchian_low": str(donchian_low),
                    "candle_body_ratio": str((high - close) / candle_range) if candle_range > 0 else "1.00",
                },
            )

        # Append current bar to history after evaluating Donchian channel
        self._history.append(bar)
        return signal
