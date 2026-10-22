# Nomad Analyst — Strategy Interface Specification (v1.2.0)

**Document ID:** `SPEC-STRAT-INTF-V1`  
**Specification Status:** Final Architecture Specification (Documentation Only — No Code Implementation)  
**Author:** Senior Quantitative Systems Engineer  
**Date:** 2026-10-22 (Revision 1.2.0)  
**Target Systems:** `fno/research/interfaces.py`, `fno/research/strategies/`

---

## 1. Executive Summary & Design Principles

The Strategy Interface defines the contract between quantitative trading strategies and the shared Research Engine. In Nomad Analyst, all strategies operating within the options backtesting environment must adhere to strict principles of determinism, data isolation, and execution standardization.

### Core Interface Principles
1. **Signal-Only Mandate:** Strategies evaluate index price action and emit high-level trading signals (`BUY_CE`, `BUY_PE`). They are strictly prohibited from selecting option contracts, accessing option prices during signal evaluation, calculating fees, or simulating order execution.
2. **Strict Non-Look-Ahead:** Strategies receive 1-minute index candles strictly sequentially. A signal generated on candle $T$ (spanning $t_0$ to $t_1$) can only inspect information known up to $t_1$. Order execution is simulated at candle $T+1$ open.
3. **Pure Functional Determinism:** Given the same historical candle sequence, a strategy must produce the exact same signals, timestamps, and parameters every time. No random state, asynchronous threading, or floating-point non-determinism is permitted.
4. **Encapsulated Configuration:** Strategy-specific parameters (such as the 150-point ORB range limit) reside strictly within that strategy's configuration and cannot leak into or constrain other strategy families.
5. **Data Reality & Ground Truth:** The spot index dataset is empirically confirmed to have zero volume (`volume = 0`). Indicators requiring volume (such as VWAP) are disallowed on spot data. Only verified price-action indicators are permitted.
6. **Evaluation & Prospective Testing:** The historical dataset available in local storage ends on `2026-07-03`. Prospective evaluation must strictly use data collected or acquired after strategy code and parameters are frozen. We do not describe July 3, 2026 onward as a future period or claim prospective data exists without verifying it.

---

## 2. Core Dataclasses & Types

```python
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class SignalDirection(str, Enum):
    """Direction of the option buying intent."""
    BUY_CE = "BUY_CE"  # Bullish index intent -> Buy Near-the-Money Call Option
    BUY_PE = "BUY_PE"  # Bearish index intent -> Buy Near-the-Money Put Option


class ExecutionOutcomeType(str, Enum):
    """Categorization of intraday execution resolution."""
    NO_SIGNAL = "NO_SIGNAL"
    REJECTED_ENTRY = "REJECTED_ENTRY"                     # Cutoff breached, contract selector failed
    UNFILLED_ENTRY = "UNFILLED_ENTRY"                     # Option bar missing at T+1 (EXPIRED_UNFILLED_NO_LIQUIDITY_BAR)
    EXECUTED_CLEAN = "EXECUTED_CLEAN"                     # Standard clean trade
    EXECUTED_QUARANTINED = "EXECUTED_QUARANTINED"         # Trade with missing intermediate candles


@dataclass(frozen=True)
class StrategySignal:
    """
    Standardized, immutable trade signal emitted by a strategy plugin.
    """
    signal_id: str                      # Unique identifier (e.g., "SIG-ORB-20251001-0935")
    strategy_id: str                    # Registered strategy code (e.g., "STRAT-ORB-15M")
    signal_timestamp_ist: datetime      # Timestamp of the closed index bar that generated the signal
    direction: SignalDirection          # BUY_CE or BUY_PE
    index_spot_price: Decimal           # Closing price of the signal index bar
    
    # Risk and Exit Parameters (Configured per Strategy)
    stop_loss_pct: Decimal              # Option stop-loss threshold (e.g., Decimal("0.15") for 15%)
    profit_target_pct: Decimal          # Option profit target threshold (e.g., Decimal("0.20") for 20%)
    max_holding_minutes: int            # Maximum duration before forced time-based exit
    entry_cutoff_time: time             # Hard time cutoff for simulated entry fill (e.g., 14:30:00)
    
    # Metadata & Auditing
    trigger_reason: str                 # Human-readable trigger explanation
    metadata: Dict[str, Any] = field(default_factory=dict) # Strategy-specific indicator values at trigger minute


@dataclass(frozen=True)
class SessionContext:
    """
    Contextual information provided to the strategy at session start and during bar evaluation.
    """
    trading_day: date                   # Active session date
    is_expiry_day: bool                 # True if today is the scheduled weekly expiry
    nearest_expiry: date                # Current active weekly expiry date
    initial_capital: Decimal            # Available capital at session open
    max_trades_per_session: int = 1     # Global platform restriction
```

---

## 3. Abstract Strategy Base Contract (`BaseNiftyOptionStrategy`)

```python
from abc import ABC, abstractmethod


class BaseStrategyConfig:
    """Base dataclass for strategy configuration."""
    strategy_id: str
    strategy_name: str
    strategy_version: str = "1.0.0"
    minimum_warmup_bars: int = 15
    entry_window_start: time = time(9, 30, 0)
    entry_window_end: time = time(14, 30, 0)
    stop_loss_pct: Decimal = Decimal("0.15")
    profit_target_pct: Decimal = Decimal("0.20")
    max_holding_minutes: int = 45


class BaseNiftyOptionStrategy(ABC):
    """
    Abstract base class for all deterministic NIFTY options-buying research strategies.
    """

    def __init__(self, config: BaseStrategyConfig):
        self.config = config
        self.strategy_id: str = config.strategy_id
        self.strategy_name: str = config.strategy_name
        self.strategy_version: str = config.strategy_version

    @abstractmethod
    def initialize_session(self, context: SessionContext) -> None:
        """
        Called at 09:15:00 IST before the first bar of each trading session.
        Resets all intraday indicator accumulators, rolling windows, and state flags.
        """
        pass

    @abstractmethod
    def on_index_bar(
        self,
        bar: Dict[str, Any],
        context: SessionContext,
    ) -> Optional[StrategySignal]:
        """
        Processes a single closed 1-minute NIFTY index bar.
        
        Args:
            bar: Dict containing 'timestamp_ist', 'open', 'high', 'low', 'close', 'volume'.
            context: SessionContext for the current trading day.
            
        Returns:
            StrategySignal if an entry trigger condition is satisfied; otherwise None.
        """
        pass

    def on_session_complete(self, context: SessionContext) -> None:
        """
        Optional teardown hook called at 15:30:00 IST after session replay finishes.
        """
        pass
```

---

## 4. Initial Strategy Family Specifications

In accordance with Phase 3.0 requirements and empirical data audits, three controlled strategy families are specified:
1. **Baseline Benchmark:** NIFTY 15-Minute Opening Range Breakout (`STRAT-ORB-15M`)
2. **Trend-Following:** NIFTY Intraday Dual EMA & Donchian Breakout (`STRAT-TREND-EMA-DONCHIAN`)
3. **Mean-Reversion:** NIFTY Intraday Bollinger/RSI Range Fade (`STRAT-FADE-BB-RSI`)

---

### Strategy Family 1: NIFTY 15-Minute ORB (Baseline Benchmark)
- **Strategy ID:** `STRAT-ORB-15M`
- **Family:** Volatility Breakout
- **Rule Set:**
  1. **Formation Period:** Exactly 15 1-minute index bars with timestamps `09:15` to `09:29` IST (spanning `09:15:00` to `09:29:59.999`).
  2. **Range Definition:**
     $$\text{ORB High} = \max(\text{high}_{09:15 \dots 09:29}), \quad \text{ORB Low} = \min(\text{low}_{09:15 \dots 09:29})$$
     $$\text{ORB Width} = \text{ORB High} - \text{ORB Low}$$
  3. **Strategy-Specific Volatility Filters (Encapsulated in `OrbStrategyConfig`):**
     - Reject session if $\text{ORB Width} < \text{min\_orb\_range\_pts}$ (default `15.00` pts).
     - Reject session if $\text{ORB Width} > \text{max\_orb\_range\_pts}$ (default `150.00` pts).
     - *Isolation Guarantee:* These filters belong strictly to `OrbStrategyConfig` and **cannot affect other strategy families**.
  4. **Signal Trigger (Evaluated 09:30:00 to 14:30:00 IST):**
     - First post-ORB candle is bar `09:30` (closing at `09:31:00`).
     - If $\text{Close}_T > \text{ORB High} \implies \text{BUY\_CE}$
     - If $\text{Close}_T < \text{ORB Low} \implies \text{BUY\_PE}$
  5. **Risk & Exits:**
     - Stop Loss: 15% of option entry price.
     - Profit Target: 20% of option entry price.
     - Max Duration: 45 minutes.
     - EOD Square-Off: 15:15:00 IST.

---

### Strategy Family 2: NIFTY Intraday Dual EMA & Donchian Breakout (`STRAT-TREND-EMA-DONCHIAN`)
- **Strategy ID:** `STRAT-TREND-EMA-DONCHIAN`
- **Family:** Momentum / Trend Following
- **Data Reality Audit & VWAP Rejection:**
  - An empirical query of all 486,050 rows in `data/historical/fno/nifty/index/NIFTY.parquet` confirmed that **`volume = 0` identically for every single row**.
  - Spot indices do not trade directly and have no traded volume in the source dataset.
  - Computing an index-based VWAP is mathematically impossible ($\sum (\text{Price} \times 0) / \sum 0$).
  - Because Phase 3 excludes futures, no futures volume is available.
  - **Data-Supported Solution:** The strategy is formulated using pure price-action indicators: **Dual Exponential Moving Averages (9 & 21 EMA)** for trend direction combined with a **20-period Donchian Channel** for breakout confirmation.
- **Rule Set:**
  1. **Indicators (Computed on 1-minute index bars):**
     - Fast EMA: 9-period Exponential Moving Average on Close.
     - Slow EMA: 21-period Exponential Moving Average on Close.
     - Donchian Channel (20-period):
       $$\text{Donchian High} = \max(\text{high}_{T-20 \dots T-1}), \quad \text{Donchian Low} = \min(\text{low}_{T-20 \dots T-1})$$
  2. **Signal Conditions (Evaluated 09:45:00 to 14:00:00 IST):**
     - Minimum warm-up: 21 closed bars (first evaluation at 09:36 IST; active entry window starts 09:45 IST).
     - **Bullish Trend Trigger (`BUY_CE`):**
       - Fast EMA is above Slow EMA ($\text{EMA}_9 > \text{EMA}_{21}$).
       - Current Index Close exceeds the 20-period Donchian High ($\text{Close}_T > \text{Donchian High}$).
       - Bar closes in upper 30% of its candle range ($\text{Close} - \text{Low} \ge 0.70 \times (\text{High} - \text{Low})$).
     - **Bearish Trend Trigger (`BUY_PE`):**
       - Fast EMA is below Slow EMA ($\text{EMA}_9 < \text{EMA}_{21}$).
       - Current Index Close falls below the 20-period Donchian Low ($\text{Close}_T < \text{Donchian Low}$).
       - Bar closes in lower 30% of its candle range ($\text{High} - \text{Close} \ge 0.70 \times (\text{High} - \text{Low})$).
  3. **Risk & Exits:**
     - Stop Loss: 15% of option entry price.
     - Profit Target: 30% of option entry price (asymmetric risk/reward).
     - Max Duration: 60 minutes.
     - EOD Square-Off: 15:15:00 IST.
  4. **Limits:** Maximum 1 trade per session.

---

### Strategy Family 3: NIFTY Intraday Range Fade / Mean-Reversion (`STRAT-FADE-BB-RSI`)
- **Strategy ID:** `STRAT-FADE-BB-RSI`
- **Family:** Statistical Mean Reversion
- **Rationale:** Exploits intraday exhaustion extremes by fading temporary index extensions outside statistical volatility bands during non-trending market regimes.
- **Rule Set:**
  1. **Indicators (Computed on 1-minute index bars):**
     - Bollinger Bands: 20-period Simple Moving Average with 2.5 standard deviations width on Close:
       $$\text{UpperBand} = \text{SMA}_{20} + 2.5 \times \sigma_{20}, \quad \text{LowerBand} = \text{SMA}_{20} - 2.5 \times \sigma_{20}$$
     - Relative Strength Index (RSI): 14-period Wilder RSI on Close.
  2. **Signal Conditions (Evaluated 10:00:00 to 14:00:00 IST — excludes opening volatility):**
     - Minimum warm-up: 20 closed bars.
     - **Oversold Bounce Trigger (`BUY_CE`):**
       - Previous bar Low breached Lower Band ($\text{Low}_{T-1} < \text{LowerBand}_{T-1}$).
       - Current bar closes back inside the band ($\text{Close}_T > \text{LowerBand}_T$).
       - 14-period RSI is oversold ($\text{RSI}_{14} \le 30.0$).
     - **Overbought Exhaustion Trigger (`BUY_PE`):**
       - Previous bar High breached Upper Band ($\text{High}_{T-1} > \text{UpperBand}_{T-1}$).
       - Current bar closes back inside the band ($\text{Close}_T < \text{UpperBand}_T$).
       - 14-period RSI is overbought ($\text{RSI}_{14} \ge 70.0$).
  3. **Risk & Exits:**
     - Stop Loss: 12% of option entry price.
     - Profit Target: 18% of option entry price.
     - Max Duration: 30 minutes.
     - EOD Square-Off: 15:15:00 IST.
  4. **Limits:** Maximum 1 trade per session.

---

## 5. Minimum Historical Data Fields & Unavailable Inputs

### A. Minimum Historical Data Fields Required
| Strategy ID | Required Index Fields | Required Option Fields | Minimum Warm-Up Bars |
| :--- | :--- | :--- | :---: |
| `STRAT-ORB-15M` | `timestamp_ist`, `high`, `low`, `close` | 1-min option OHLCV at $T+1$ | 15 bars (09:15–09:30) |
| `STRAT-TREND-EMA-DONCHIAN` | `timestamp_ist`, `high`, `low`, `close` | 1-min option OHLCV at $T+1$ | 21 bars (09:15–09:36) |
| `STRAT-FADE-BB-RSI` | `timestamp_ist`, `high`, `low`, `close` | 1-min option OHLCV at $T+1$ | 20 bars (09:15–09:35) |

### B. Explicitly UNAVAILABLE Historical Inputs
To ensure strict realism, strategies must not request or rely upon the following inputs, which are **absent** from the historical Parquet dataset:
1. **Spot Index Volume:** Empirically verified as `volume = 0` across 100% of rows in `NIFTY.parquet`.
2. **Level-1 Order Book Quotes:** Real-time bid, ask, bid size, ask size, and market depth are **UNAVAILABLE**.
3. **Sub-Minute Tick Data:** Tick-by-tick trades and microsecond timestamps are **UNAVAILABLE**.
4. **Historical Option Greeks:** Pre-computed Delta, Gamma, Theta, Vega, and Rho are **UNAVAILABLE**.
5. **Implied Volatility (IV) Surfaces:** Strike-by-strike IV smiles and historical surface skews are **UNAVAILABLE**.
6. **Spot Index Open Interest:** Spot index open interest is zero and **UNAVAILABLE**.

---

## 6. Strict Determinism & Anti-Bias Verification

```
[Candle T: 09:35:00 - 09:35:59 IST] ──> Bar Closes at 09:36:00 IST
                                           │
                                           ▼ Strategy evaluates on_index_bar()
                                      Signal Emitted: BUY_CE at 09:36:00 IST
                                           │
[Candle T+1: 09:36:00 - 09:36:59 IST] ────┴─> Execution Simulator Fills at 09:36:00 Open
                                              (Zero Look-Ahead: Option Open Price)
```

1. **No Intra-Candle Look-Ahead:** Signals are evaluated on the `close` of bar $T$. The simulated fill is executed on the `open` of bar $T+1$. Bar $T+1$'s high, low, close, and volume are strictly concealed until the trade has already been filled.
2. **Entry Cutoff Verification:** If a signal occurs on candle `14:30` (closing at `14:31:00`), the fill attempt at `14:31:00` exceeds `14:30:00` and is rejected with `REJECTED_FILL_PAST_ENTRY_CUTOFF`.
3. **Idempotent Indicator Calculations:** Custom rolling indicators must use bounded deque buffers or mathematically closed formulas. Resetting indicators on `initialize_session()` must produce bit-for-bit identical results on repeated runs.
4. **No Dynamic Calibration on Today's Data:** Parameters may only use data from the current day up to bar $T$ or pre-defined historical training splits.
