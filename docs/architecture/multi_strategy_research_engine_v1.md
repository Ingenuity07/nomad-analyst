# Nomad Analyst — Multi-Strategy Historical Research Engine Architecture (v1.2.0)

**Document ID:** `ARCH-MSRE-V1`  
**Specification Status:** Final Architecture Specification (Documentation Only — No Code Implementation)  
**Author:** Senior Quantitative Systems Engineer  
**Date:** 2026-10-22 (Revision 1.2.0)  
**Target Systems:** `fno/backtester/`, `fno/research/`, `fno/services/`

---

## 1. Executive Summary & Architectural Vision

The Nomad Analyst Phase 2 backtester demonstrated deterministic, auditable simulation of the NIFTY 15-minute Opening Range Breakout (ORB) strategy over the `2025-07-01` to `2026-07-02` historical window. However, the Phase 2 implementation closely coupled strategy-specific breakout mechanics to the core simulation engine loop.

The objective of **Phase 3.0** is to specify a **reusable, modular Multi-Strategy Research Engine (MSRE)** that allows quantitative analysts to research, backtest, evaluate, and benchmark multiple deterministic NIFTY options-buying strategies through a single, shared, rigorously audited execution, cost, and reporting framework.

```
+-----------------------------------------------------------------------------------+
|                        NOMAD ANALYST RESEARCH ENGINE                             |
+-----------------------------------------------------------------------------------+
                                          │
    ┌─────────────────────────────────────┼────────────────────────────────────┐
    │                                     │                                    │
┌───▼─────────────────┐        ┌──────────▼──────────┐       ┌─────────────────▼───┐
│  STRATEGY PLUGINS   │        │ SHARED RESEARCH HUB │       │   DATA FOUNDATION   │
│ (ORB, Trend, Fade)  │        │ (Runner, Registry)  │       │ (Index, Options, DB)│
└───┬─────────────────┘        └──────────┬──────────┘       └─────────────────┬───┘
    │                                     │                                    │
    └───────────────────► [ Strategy Interface: on_bar() ]                      │
                                          │                                    │
                               ┌──────────▼──────────┐                         │
                               │ Contract Selection  │◄────────────────────────┘
                               │ (Weekly ATM, Roll)  │
                               └──────────┬──────────┘
                                          │
                               ┌──────────▼──────────┐
                               │ Execution Simulator │
                               │ (Stop-First, Fees)  │
                               └──────────┬──────────┘
                                          │
                               ┌──────────▼──────────┐
                               │ Evaluation Engine   │
                               │ (Splits, Regimes)   │
                               └──────────┬──────────┘
                                          │
                               ┌──────────▼──────────┐
                               │ Audit Artifacts &   │
                               │ Dual Scorecards     │
                               └─────────────────────┘
```

### Core Architecture Axioms
1. **Separation of Signal vs. Execution:** Strategies generate abstract, deterministic intent signals on index candles (`BUY_CE`, `BUY_PE`, or `None`). Strategies **never** simulate fills, select contracts directly, manipulate timestamps, compute fees, or access option books.
2. **Centralized, Non-Bypassable Platform Controls:** Contract selection, tick-rounding, next-candle fills, statutory taxes, dual-model slippage, intra-bar stop-loss priority, and position exits are executed strictly by shared core components.
3. **Encapsulated Strategy Configurations:** Hyperparameters such as the 150-point ORB range width filter, EMA periods, or RSI thresholds belong exclusively to individual strategy configurations and **must never pollute shared engine logic or impact other strategy families**.
4. **Data Reality & Zero Fabrication:** Spot index volume is empirically confirmed to be identically zero (`volume = 0`) across all 486,050 rows in `NIFTY.parquet`. The engine explicitly rejects indicators relying on spot index volume (such as index VWAP) and uses verified price-action alternatives.
5. **Rigorous Evaluation & Previously Observed Holdout:** The historical dataset available in local storage ends on `2026-07-03`. The `2026-04-01` to `2026-07-02` period is explicitly classified as **previously observed historical data** (evaluated during Phase 2). Prospective evaluation must use data collected or acquired after strategy code and parameters are frozen. We do not describe July 3, 2026 onward as a future period or claim prospective data exists without verifying it.
6. **Dynamic Common-Sample Comparison:** Comparative strategy benchmarking produces two synchronized reports: (1) strategy-specific full sample and (2) dynamically calculated intersection of eligible sessions across all compared strategies.
7. **Git & Operational Safety:** Preserve all pre-existing working tree modifications, especially the six known frontend files; introduce no unrelated changes; do not stage, commit, push, reset, or revert; maintain operational ledgers (`PaperTradeLedger = 0`) and live runtime untouched.

---

## 2. Component Responsibilities & Layer Boundaries

```
+-----------------------------------------------------------------------------+
| LAYER 7: RESEARCH REPORTS & BENCHMARK COMPARATOR                            |
| - Dual Scorecards (Full & Common) | JSON Audit Artifacts | Invariant Checks |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 6: EVALUATION & METRICS ENGINE                                        |
| - Expectancy, Profit Factor, Max DD | Walk-Forward Splits | Regime Analysis |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 5: EXPERIMENT RUNNER & REGISTRY                                       |
| - Experiment Lifecycle | Configuration Hashes | Reproducibility Tracker     |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 4: EXECUTION SIMULATION & RISK ENGINE (SHARED PLATFORM)               |
| - T+1 Open Fill Timing | Stop-First Exit Priority | Dual-Model Slippage     |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 3: CONTRACT SELECTION ENGINE (SHARED PLATFORM)                        |
| - ATM Strike Selection | Expiry Resolution | 13:00 IST Roll Policy         |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 2: STRATEGY INTERFACE & PLUGINS                                       |
| - Abstract Strategy Base | Config Dataclasses | Deterministic Signal Gener. |
+-----------------------------------------------------------------------------+
                                      ^
                                      |
+-----------------------------------------------------------------------------+
| LAYER 1: DATA ACCESS & CALENDAR GATING (SHARED PLATFORM)                    |
| - DuckDB Historical Reader | Cached Query Provider | Exchange Calendar      |
+-----------------------------------------------------------------------------+
```

### Layer 1: Data Access & Calendar Gating (Shared Platform)
- **Responsibility:** Ingest, cache, and slice 1-minute OHLCV Parquet files for NIFTY spot index and option series.
- **Existing Components Reused:**
  - [`HistoricalParquetReader`](file:///Users/shivamsingh/personal/nomad-analyst/fno/services/historical_reader.py#L39)
  - [`CachedHistoricalReader`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/engine.py#L19)
  - [`NiftyExpiryCalendar`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/calendar.py#L22)
- **Hard Exclusions:**
  - Enforces `DEC-01`: Trading sessions lacking scheduled weekly expiry option files are immediately excluded with `SessionQualification.EXCLUDED_MISSING_EXPIRY_DATA`. (19 sessions across Oct 2025 and June 2026).
  - Truncated index sessions lacking continuous opening bars (e.g. `2026-06-03`) are excluded with `SessionQualification.EXCLUDED_DATA_GAP`.

### Layer 2: Strategy Interface Layer (Plugin Boundary)
- **Responsibility:** Provides clean interfaces for strategy indicator state, warm-up, and signal generation.
- **Specification:** Defined in [`docs/architecture/strategy_interface_v1.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/architecture/strategy_interface_v1.md).

### Layer 3: Contract Selection Layer (Shared Platform)
- **Responsibility:** Resolves index signals to executable option contract metadata (`tradingsymbol`, `strike`, `expiry`, `lot_size`).
- **Existing Components Reused:**
  - [`OptionContractSelector`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/contract_selector.py#L21)
- **Standard Rules & Roll Logic:**
  - **ATM Strike:** Nearest 50-point strike using explicit `ROUND_HALF_UP` tie-breaking.
  - **Expiry:** Active weekly expiry.
  - **13:00 IST Expiry-Day Roll Policy:** Signals triggered at or after `13:00:00 IST` on expiry day roll to the subsequent scheduled weekly contract.
  - **Missing Roll Data Behavior:** If the next weekly expiry file is missing from local storage, contract selection returns `None` (fail-closed rejection), and the trade attempt is logged as `REJECTED_CONTRACT_SELECTION_FAILED`.

### Layer 4: Execution Simulation & Risk Engine (Shared Platform)
- **Responsibility:** Deterministic trade replay, next-candle fill simulation, statutory fee calculation, and dual-model slippage.
- **Existing Components Reused:**
  - [`HistoricalExecutionSimulator`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/execution_simulator.py#L42)
  - [`StatutoryFeeCalculator`](file:///Users/shivamsingh/personal/nomad-analyst/fno/execution/fee_calculator.py#L34)
  - [`calculate_order_fees`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/fee_model.py#L18)
- **Non-Bypassable Invariants:**
  - Entry Fill: Next available option candle open ($T+1$) strictly after signal candle close ($T$).
  - Intra-bar Stop Priority: Stop-loss is evaluated before profit target if both prices fall within the same 1-minute high-low candle bar.
  - Global Limits: Max 1 trade per session enforced globally across all strategies.
  - EOD Square-Off: Forced exit at 15:15:00 IST.
  - Execution Outcome Tracking: Separate auditing of (1) No Signal, (2) Rejected Entry, (3) Unfilled Entry, (4) Quarantined Trade, and (5) Clean Executed Trade.

### Layer 5: Experiment Runner & Registry (Shared Platform)
- **Responsibility:** Orchestrates reproducible experiment execution, manages configuration hashes, and coordinates multi-scenario sensitivity grids.
- **Specification:** Defined in [`docs/architecture/experiment_tracking_and_evaluation_v1.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/architecture/experiment_tracking_and_evaluation_v1.md).

### Layer 6: Evaluation & Metrics Engine (Shared Platform)
- **Responsibility:** Computes institutional-grade performance, risk-adjusted returns, drawdown profiles, regime breakdowns, and dual scorecards.
- **Existing Components Reused:**
  - [`BacktestMetricsCalculator`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/metrics.py#L22)

### Layer 7: Research Reports & Benchmark Comparator (Shared Platform)
- **Responsibility:** Produces structured JSON artifacts and comparative scorecards across both full and common eligible samples.

---

## 3. Shared Infrastructure vs. Strategy Configuration

To prevent strategy logic from bypassing risk and data-integrity controls, system components are partitioned into **Shared/Enforced Platform Core** versus **Strategy-Customizable Parameters**:

| Architectural Component | Platform Core (Enforced & Shared) | Strategy-Specific Config | Customization Constraints & Isolation |
| :--- | :---: | :---: | :--- |
| **Data Ingestion & Slicing** | **YES** | NO | Strategies cannot alter raw historical candles or inject synthetic bars. |
| **Session Eligibility Gating** | **YES** | NO | Calendar exclusions (`EXCLUDED_MISSING_EXPIRY_DATA`, `EXCLUDED_DATA_GAP`) are hard platform barriers. |
| **Intraday Bar Delivery** | **YES** | NO | Index bars are delivered strictly sequentially to prevent look-ahead. |
| **Strategy Indicator Logic** | NO | **YES** | Strategies define indicators computed solely from past closed bars. |
| **Entry Signal Triggers** | NO | **YES** | Strategies define entry direction (`BUY_CE`, `BUY_PE`) and trigger rules. |
| **Strategy Range/Volatility Filters** | NO | **YES** | **Strictly isolated.** The 150-pt ORB filter belongs exclusively to ORB config and **cannot affect other strategies**. |
| **Stop-Loss & Profit-Target %** | NO | **YES** | Attached to `StrategySignal` (e.g. 15%/20% for ORB vs. 15%/30% for Trend). |
| **Max Holding Minutes** | NO | **YES** | Attached to `StrategySignal` (e.g. 45m for ORB, 60m for Trend, 30m for Fade). |
| **Allowed Entry Window** | NO | **YES** | Configurable per strategy (e.g. 09:30–14:30 for ORB vs. 09:45–14:00 for Trend). |
| **Session Trade Limits** | **YES** | NO | Global cap of max 1 trade per session enforced platform-wide. |
| **Contract Strike & Expiry** | **YES** | NO | All strategies trade ATM front-weekly contracts with 13:00 expiry roll. |
| **Fill Execution Timing** | **YES** | NO | Fill occurs strictly at $T+1$ open price with tick rounding. |
| **Slippage & Cost Models** | **YES** | NO | Shared 6-scenario slippage grid and statutory tax calculator. |
| **Exit Evaluation Order** | **YES** | NO | Stop-loss checked before target within each candle bar; EOD square-off enforced at 15:15 IST. |
| **Metric Calculations** | **YES** | NO | Standardized formulas applied uniformly across all strategies. |

---

## 4. Precise Candle Timing & Execution Semantics

To prevent look-ahead bias across all strategy families, precise candle boundaries and timestamps are strictly formalized:

```
[Candle T: Index Bar 09:35]
Interval: 09:35:00.000 to 09:35:59.999 IST
Bar closes at 09:36:00.000 IST
  │
  ▼ Strategy evaluates on_index_bar() at 09:36:00 IST
Signal Emitted: BUY_CE (Timestamp: 09:35 IST / Close: 09:36 IST)
  │
  ▼ Passed to Execution Simulator
[Candle T+1: Option Bar 09:36]
Interval: 09:36:00.000 to 09:36:59.999 IST
Fill Simulated at 09:36:00.000 Open Price (plus slippage)
(Future T+1 high, low, close, and volume are strictly concealed at fill time)
```

### Detailed Timing Rules:
1. **ORB Formation Window:** Exactly 15 1-minute bars with timestamps `09:15` through `09:29` IST (spanning `09:15:00` to `09:29:59.999`).
2. **ORB Evaluation Minute:** Occurs at `09:30:00 IST` when the 15th bar closes.
3. **Indicator Warm-Up:** Strategies specify `minimum_warmup_bars`. No signals may be emitted until this bar count is satisfied.
4. **Entry Cutoff Enforcement:** Entry cutoff (e.g. `14:30:00 IST`) applies to the **simulated fill timestamp ($T+1$)**, not the signal timestamp ($T$).
   - A signal triggered on candle `14:30` (closing at `14:31:00`) attempts fill at `14:31:00`. Because $14:31:00 > 14:30:00$, the attempt is rejected with `REJECTED_FILL_PAST_ENTRY_CUTOFF`.
5. **EOD Square-Off:** At `15:15:00 IST`, any active position is unconditionally closed at the option bar's open price.

---

## 5. Execution Outcome Classification

To maintain auditable precision, the research engine categorizes each session and trade attempt into unambiguous states:

```
                                  [ Trading Session ]
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
          [ Excluded Session ]                          [ Qualified Session ]
       (Missing Expiry, Data Gap,                                 │
         Strategy Range Filter)                                   ▼
                                                      [ Evaluated by Strategy ]
                                                                  │
                                           ┌──────────────────────┴──────────────────────┐
                                           ▼                                             ▼
                                  [ No Signal Today ]                            [ Signal Emitted ]
                                (Indicator conditions                                    │
                                     not satisfied)                                      ▼
                                                                               [ Contract Selector ]
                                                                                         │
                                                    ┌────────────────────────────────────┴────────────────────────────────────┐
                                                    ▼                                                                         ▼
                                    [ Rejected Entry Attempt ]                                                        [ Contract Resolved ]
                             (e.g., REJECTED_CONTRACT_SELECTION_FAILED,                                                       │
                                   REJECTED_FILL_PAST_ENTRY_CUTOFF)                                                           ▼
                                                                                                                   [ Option T+1 Open Fill ]
                                                                                                                              │
                                                                           ┌──────────────────────────────────────────────────┴──────────────────────────────────┐
                                                                           ▼                                                                                     ▼
                                                               [ Unfilled Entry Attempt ]                                                             [ Executed Trade ]
                                                          (EXPIRED_UNFILLED_NO_LIQUIDITY_BAR:                                                                    │
                                                           Option candle absent at T+1)                                            ┌─────────────────────────────┴─────────────────────────────┐
                                                                                                                                   ▼                                                           ▼
                                                                                                                        [ Standard Clean Trade ]                                  [ Quarantined Trade ]
                                                                                                                          (Continuous Candles)                                     (Missing Candle Hole)
```

### Definitions:
- **No Signal Sessions:** Qualified sessions where the strategy generated zero entry triggers during the trading day.
- **Rejected Entry Attempts:** Sessions where a signal was emitted, but was rejected by system barriers before order routing (e.g., `REJECTED_FILL_PAST_ENTRY_CUTOFF` or `REJECTED_CONTRACT_SELECTION_FAILED`).
- **Unfilled Entry Attempts:** Sessions where a valid signal was emitted and contract resolved, but the option candle was missing at $T+1$ open (`EXPIRED_UNFILLED_NO_LIQUIDITY_BAR` — verified in exactly 4 sessions in Phase 2 baseline: `2026-06-04`, `2026-06-05`, `2026-06-08`, `2026-06-09`).
- **Quarantined Trades:** Trades that filled successfully but experienced missing intermediate option candles during the trade lifetime, requiring synthetic mark-to-market.
- **Standard Clean Trades:** Trades that filled and closed with 100% continuous authentic option candles (200 trades in Phase 2 baseline).

---

## 6. Expiry-Day Rollover Policy (13:00 IST Rule)

### A. Authoritative Verification
The 13:00 IST roll rule is implemented in [`OptionContractSelector`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/contract_selector.py#L98) and [`NiftyExpiryCalendar`](file:///Users/shivamsingh/personal/nomad-analyst/fno/backtester/calendar.py#L154):
- **Condition:** Applies strictly when `nearest_scheduled_expiry == session_date` (Expiry Day).
- **Cutoff:** For signals with timestamp $t < 13:00:00 \text{ IST}$, the active contract is the 0-DTE expiry (nearest).
- **Rollover:** For signals with timestamp $t \ge 13:00:00 \text{ IST}$, the active contract rolls to the subsequent weekly expiry (`get_next_scheduled_expiry`).

### B. Missing-Expiry Rollover Behavior
- Pre-session gating checks availability of the *primary* expiry (`has_rolled=False`).
- If an expiry-day breakout occurs at or after 13:00 IST, the selector queries the *next* weekly expiry file.
- If that next expiry file is missing from local storage (e.g., expiry day `2026-06-09`, where the next weekly `2026-06-16` is missing upstream):
  - `resolve_session_expiry()` returns `None`.
  - The selector returns `None`.
  - The trade attempt is rejected fail-closed as `REJECTED_CONTRACT_SELECTION_FAILED`.
  - **Zero substitution of distant monthly contracts is permitted.**

---

## 7. Proposed Package & Module Layout

```
fno/
├── backtester/                     # Existing core backtester (stable, reused)
│   ├── calendar.py                 # NiftyExpiryCalendar
│   ├── contract_selector.py        # OptionContractSelector
│   ├── engine.py                   # HistoricalBacktestEngine (retained for regression)
│   ├── execution_simulator.py      # HistoricalExecutionSimulator
│   ├── fee_model.py                # Statutory fee calculator
│   ├── metrics.py                  # Metrics calculator
│   └── models.py                   # Trade, session, and incident models
│
├── research/                       # New Phase 3 Multi-Strategy Research Engine
│   ├── __init__.py
│   ├── interfaces.py               # Abstract Base Strategy & Signal dataclasses
│   ├── registry.py                 # Strategy and experiment registry
│   ├── engine.py                   # Reusable MultiStrategyBacktestEngine
│   ├── runner.py                   # Multi-strategy CLI / experiment runner
│   ├── comparator.py               # Dual-scorecard comparator (Full & Common)
│   └── strategies/                 # Strategy Plugin Implementations
│       ├── __init__.py
│       ├── orb_15m.py              # Ported NIFTY 15m ORB plugin (Baseline Benchmark)
│       ├── trend_following.py      # NIFTY Intraday Trend Following plugin
│       └── mean_reversion.py       # NIFTY Intraday Range Fade plugin
│
└── tests/
    ├── test_backtester.py          # Existing 40 tests (must never break)
    ├── test_research_engine.py     # Engine unit and lifecycle tests
    ├── test_strategy_plugins.py    # Determinism and signal tests for each plugin
    └── test_comparator.py          # Scorecard and dual-sample tests
```

---

## 8. Phased Implementation Roadmap (Minimal Scope)

```
Phase 3.0 (Current)  ──> Architecture & Specification Approval (Documentation Only)
                              │
Phase 3.1            ──> Strategy Interface & Baseline Regression Acceptance
                         - Implement fno/research/interfaces.py & engine.py
                         - Wrap existing ORB as NiftyOrbStrategyPlugin
                         - Regression Gate: Reproduce Phase 2.4.2 baseline 100% bit-for-bit
                         - Retain all 40 passing backend tests
                              │
Phase 3.2            ──> Implement Controlled Strategy Portfolio
                         - Add Trend-Following & Mean-Reversion plugins
                         - Unit tests verifying deterministic signal generation
                              │
Phase 3.3            ──> Experiment Runner, Dual Scorecards & Prospective Policy
                         - Walk-forward splits (Train, Val, Previously Observed Test)
                         - Dual scorecards (Full sample vs. Dynamically calculated Common sample)
                         - Prospective evaluation parameter freeze tooling
```

---

## 9. Decisions Requiring Explicit Stakeholder Approval Before Implementation

1. **DEC-05 (Package Architecture):** Confirm the creation of `fno/research/` as a sibling package to guarantee zero disruption to existing `fno/backtester/` code and tests.
2. **DEC-06 (Position Exit Mechanism):** Confirm that for initial multi-strategy evaluation, position exits remain standardized to Stop-Loss %, Profit-Target %, Max Holding Minutes, and 15:15 EOD square-off (evaluated stop-first at 1-minute resolution).
3. **DEC-07 (Holdout Classification & Prospective Freeze):** Confirm that `2026-04-01` to `2026-07-02` is recognized as **previously observed**, and that prospective evaluation must use data collected or acquired after strategy code and parameters are frozen, without describing July 3, 2026 onward as a future period or claiming prospective data exists without verifying it.
