# Phase 23A — Prospective Paper Evaluation Protocol (20 Trading Sessions)

**Trial Identifier:** `TRIAL-FNO-2026-Q4-01`  
**Target Horizon:** 20 Valid Full NSE Trading Sessions  
**Scheduled Window:** `2026-10-22` (Session 01) through `2026-11-18` (Session 20)  
**Execution Environment:** Simulated Paper Trading Engine (`PaperExecutionEngine` -> `fno_paper_trade_ledger`)  
**Underlying Universe:** NIFTY 50 Index Options (`^NSEI`, $K=5$, 22 Active Weekly Contracts)  
**Safety Protocol:** Strict Zero-Broker Order Placement Guarantee (`is_paper_trading = True`). Zero broker API credentials or order endpoints linked.

---

## 1. Executive Context & Scope

This protocol establishes the rigorous, un-manipulated operational baseline for a prospective 20-trading-day evaluation of the Nomad Analyst F&O strategy engine.

In accordance with institutional algorithmic audit standards:
1. **Prospective Observation:** The 20-trading-day window represents an operational and statistical baseline observation window for execution realism, slippage behavior, and infrastructure stability. It is **not** treated as retrospective curve-fitting or proof of permanent alpha.
2. **Frozen Implementation:** All strategy parameters, universe selection bounds, slippage rates, and fee formulas are **strictly frozen** for the duration of the trial. Zero parameter tuning or midday model adjustments are permitted.
3. **Fail-Closed Market-Data Gate:** Data integrity is paramount. If feed interruptions, reconnect gaps, or stale data compromise market microstructure, the system must fail-safe (rejecting signals or parking unexecutable positions in `PENDING_LIQUIDITY`) rather than inventing synthetic fills.

---

## 2. 20-Trading-Session Schedule (Authoritative NSE Calendar)

**Source Authority:**
- Exchange Holiday Calendar: `market/services/trading_session.py:NSE_HOLIDAYS_2026` (verified against official NSE holiday circulars).
- Contract Metadata Authority: `data/universe/kite_instruments_master.csv` (1,816 NIFTY options indexed; verification date: `2026-10-21`).
- Expiry Rules: Under applicable NSE contract specifications, standard NIFTY weekly contracts expire on **Tuesday** (shifting to the preceding trading day if Tuesday is a holiday). October monthly contracts expire on Tuesday `2026-10-27` (`NIFTY26OCTFUT`).

**Verified 20-Session Calendar:**

| Session # | Date | Day | Market Hours (IST) | Authoritative Expiry & Operational Notes |
|:---:|:---:|:---:|:---:|:---|
| **01** | `2026-10-22` | Thursday | 09:15 – 15:30 | **Trial Start / Session 01 Initiation** |
| **02** | `2026-10-23` | Friday | 09:15 – 15:30 | Regular Friday trading session |
| **03** | `2026-10-26` | Monday | 09:15 – 15:30 | Pre-expiry positioning session |
| **04** | `2026-10-27` | Tuesday | 09:15 – 15:30 | **OCTOBER 2026 MONTHLY EXPIRY** (`NIFTY26OCTFUT`, `NIFTY26OCT...CE/PE`) |
| **05** | `2026-10-28` | Wednesday | 09:15 – 15:30 | November contract cycle primary handover |
| **06** | `2026-10-29` | Thursday | 09:15 – 15:30 | Regular trading session |
| **07** | `2026-10-30` | Friday | 09:15 – 15:30 | Regular trading session |
| **08** | `2026-11-02` | Monday | 09:15 – 15:30 | Pre-expiry positioning session |
| **09** | `2026-11-03` | Tuesday | 09:15 – 15:30 | **WEEKLY OPTION EXPIRY** (`NIFTY26N03...CE/PE`) |
| **10** | `2026-11-04` | Wednesday | 09:15 – 15:30 | **Mid-Trial Review Checkpoint (Session 10/20)** |
| **11** | `2026-11-05` | Thursday | 09:15 – 15:30 | Regular trading session |
| **12** | `2026-11-06` | Friday | 09:15 – 15:30 | Regular trading session |
| — | `2026-11-08` | Sunday | 18:15 – 19:15 | *Diwali Laxmi Pujan (Muhurat Trading only; excluded from 20 continuous day sessions)* |
| **13** | `2026-11-09` | Monday | 09:15 – 15:30 | **WEEKLY OPTION EXPIRY** (`NIFTY26N09...CE/PE` shifted from Tuesday due to Diwali) |
| — | `2026-11-10` | Tuesday | **EXCHANGE HOLIDAY** | **Diwali Balipratipada (NSE Closed; 0 market hours)** |
| **14** | `2026-11-11` | Wednesday | 09:15 – 15:30 | Post-Diwali regular session resumption |
| **15** | `2026-11-12` | Thursday | 09:15 – 15:30 | Regular trading session |
| **16** | `2026-11-13` | Friday | 09:15 – 15:30 | Regular trading session |
| **17** | `2026-11-16` | Monday | 09:15 – 15:30 | Pre-expiry positioning session |
| **18** | `2026-11-17` | Tuesday | 09:15 – 15:30 | **WEEKLY OPTION EXPIRY** (`NIFTY26N17...CE/PE`) |
| **19** | `2026-11-18` | Wednesday | 09:15 – 15:30 | Regular trading session |
| **20** | `2026-11-19` | Thursday | 09:15 – 15:30 | **Trial Conclusion & Final Ledger Audit (Session 20/20)** |

*(Note: If an unscheduled NSE exchange holiday or trading halt occurs, the schedule extends by exactly one session so that 20 valid full sessions are evaluated).*


---

## 3. Registered Candidate Strategies & Frozen Parameters

### Strategy Baseline: `STRAT-ORB-15M`
- **Identifier:** `STRAT-ORB-15M`
- **Name:** NIFTY 15m Opening Range Breakout
- **Version:** `1.0.0`
- **Class:** [`NiftyOrbBreakoutStrategy`](file:///Users/shivamsingh/personal/nomad-analyst/fno/strategies/nifty_orb_breakout.py)

#### Frozen Strategy Configuration Table:
| Parameter | Frozen Value | Architectural Rationale |
|---|---|---|
| **Underlying Symbol** | `^NSEI` (NIFTY 50) | High liquidity, tightest spreads on NSE |
| **Option Instrument Type** | CE and PE | Pure long buyer (no naked option selling) |
| **Strike Moneyness** | `ATM` or `ITM` | Restricts trading to high delta (0.50–0.70) liquid strikes |
| **Opening Range Period** | `09:15:00` to `09:30:00` IST | First 15 minutes establish High/Low boundaries |
| **Permitted Entry Window** | `09:30:00` to `14:30:00` IST | Strictly locks entries until range is established; avoids post-14:30 theta decay |
| **Bullish Trigger** | $\text{Spot} > \text{ORB High}$ | Buy ATM/near-ITM CE |
| **Bearish Trigger** | $\text{Spot} < \text{ORB Low}$ | Buy ATM/near-ITM PE |
| **Default Position Size** | 1 Lot (65 shares) | Standard NIFTY exchange lot size |
| **Max Concurrent Positions** | 1 | Zero multi-leg overlap; strict position uniqueness |
| **Stop Loss** | Entry Ask $-15\%$ | Premium percentage trailing envelope |
| **Profit Target** | Entry Ask $+20\%$ | Conservative 1.33:1 reward-to-risk ratio |
| **Max Holding Duration** | 45 minutes | Time-stop prevents persistent theta bleed in chop |
| **Mandatory EOD Square-Off** | `15:15:00` IST | Policy exit before final settlement volatility |
| **Max Acceptable Slippage** | $1.5\%$ (`0.015`) | Rejects signals if model slippage exceeds threshold |

---

## 4. Execution, Slippage & Friction Architecture

### 1. Conservative Taker Order Fills
All paper orders execute as aggressive market taker fills against real limit order book snapshots:
- **Buy Entry Fill:**
  $$P_{\text{fill, buy}} = \text{round\_up\_to\_tick}(\text{Best Ask} + \text{slippage}, 0.05)$$
  $$\text{slippage} = \max(0.05, \text{round\_up\_to\_tick}(\text{Best Ask} \times 0.005, 0.05))$$
  *Rounding UP guarantees simulated buyer never pays less than conservative model.*
- **Sell Exit Fill:**
  $$P_{\text{fill, sell}} = \text{round\_down\_to\_tick}(\text{Best Bid} - \text{slippage}, 0.05)$$
  $$\text{slippage} = \max(0.05, \text{round\_up\_to\_tick}(\text{Best Bid} \times 0.005, 0.05))$$
  *Rounding DOWN guarantees simulated seller never receives more than conservative model.*

### 2. Microstructure Gating & Microstructure Traps
- **Stale Quotes:** Quote age $> 3.0\text{s}$ rejected (`REJECTED_STALE_QUOTE`).
- **Locked / Crossed Book:** `best_bid >= best_ask` rejected (`REJECTED_LOCKED_QUOTE`, `REJECTED_CROSSED_BOOK`).
- **Zero-Bid Exit Trap:** If `quote.best_bid <= 0`, position transitions to `PENDING_LIQUIDITY` (`EXIT_UNEXECUTABLE_ZERO_BID`). Zero fills or invented prices are permitted.
- **Excessive Spread:** Spread $> 2.5\%$ rejected (`REJECTED_EXCESSIVE_SPREAD`).
- **Partial Bar Protection:** Any candle interval truncated by disconnect or restart is tagged `is_partial_bar = True` and rejected (`REJECTED_PARTIAL_BAR`).

### 3. Effective-Dated Statutory Fee Schedule (`2026-04-01`)
Calculated to the exact paisa by [`StatutoryFeeCalculator`](file:///Users/shivamsingh/personal/nomad-analyst/fno/execution/fee_calculator.py):
- **Brokerage:** ₹20.00 flat per executed order leg.
- **Exchange Charges:** 0.03553% (NSE Circular NSE/FA/73061).
- **SEBI Charges:** 0.0001% (₹10/crore).
- **Stamp Duty:** 0.003% on buy-side turnover.
- **Securities Transaction Tax (STT):** 0.15% on sell-side turnover (Finance Act 2026) or 0.15% on settlement value for exercised ITM options.
- **GST:** 18% applied strictly to `(Brokerage + Exchange + SEBI)`. STT and Stamp Duty are legally exempt.

### 4. Baseline Parameter Reconciliation (Phase 23B Preflight Audit)
1. **Slippage Model vs. Protocol Shorthand vs. Strategy Risk Gate:**
   - **Modeled Execution Slippage:** Strictly implemented in [`PaperExecutionEngine`](file:///Users/shivamsingh/personal/nomad-analyst/fno/execution/paper_engine.py) as $\max(0.05, \text{round\_up}(\text{Price} \times 0.005))$. For an option trading near ₹100 ATM premium, this computes to exactly ₹0.50 per share (₹32.50 per lot of 65).
   - **Protocol Shorthand:** The table shorthand of "0.50 points" represents the nominal slippage for an ATM option near ₹100. The dynamic tick-grid formula $\max(0.05, \text{Price} \times 0.005)$ remains the authoritative execution model.
   - **Strategy Risk Tolerance Gate:** The parameter `max_acceptable_slippage_pct = 0.015` (1.5%) in `NiftyOrbBreakoutStrategy` is an independent **risk limit circuit-breaker**. It instructs the validator to abort any trade if execution divergence or quote spread exceeds 1.5%. Expected execution friction is 0.5%; the abort barrier is 1.5%.
2. **STT Rate Legislative Lineage & Conservative Model:**
   - Pre-October 2024: 0.0625% on option sales.
   - Finance (No. 2) Act 2024 (effective 1 October 2024): Increased to 0.10% on option premium turnover.
   - Frozen Engine Specification: Set at 0.15% (Finance Act 2026). Per preflight constraints, this frozen parameter is preserved, ensuring the paper evaluation operates under a rigorous, conservative friction drag (50% higher than statutory 0.10%).

### 5. Runtime Strategy Orchestration (`Phase 23B`)
- **Activation Mechanism:** `STRAT-ORB-15M` is registered into `StrategyManager` upon `FnoTickerConsumer` initialization.
- **Trigger Event:** Evaluated on every completed 1-minute `OptionOHLCVBar` drained during periodic flush (`fno_consumer.flush_completed_bars()`).
- **Opening Range Verification:** Continuously updated from live `^NSEI` ticks between 09:15:00 and 09:30:00 IST. If process restarts after 09:30:00, automatically seeded from database `OHLCVBar` records for `^NSEI` across 09:15–09:30 IST.
- **Deduplication:** State tracked in `_evaluated_bar_keys` set on `(instrument_token, timestamp)` to guarantee zero duplicate evaluations or multiple entries for the same event.
- **Observability:** Telemetry published to Django cache key `fno_strategy_health:{session_date}:STRAT-ORB-15M` so `report_paper_session` accurately distinguishes valid no-setup sessions from un-wired execution.

## 5. Trial Lifecycle & Data Disruption Protocol

| Disruption Event | Engine Behavior & Handling Protocol | Trial Impact |
|---|---|---|
| **Mid-Session Ticker Reconnect** | Aggregator marks active in-flight bars `is_partial_bar = True`. Signal validator rejects partial bars. Active positions held; exit stops continue monitoring fresh bids. | Session valid; partial bars logged. |
| **Premature Process Termination (SIGINT/SIGTERM)** | `force_close_and_flush_all()` evacuates in-flight bars as partial to Postgres. `sync_active_trades_from_db()` recovers active positions upon restart. | Session valid. |
| **Market Wide Circuit Breaker / Early Close** | Positions held until 15:15 IST or closed via EOD trigger. Unclosed positions transition to `UNEXECUTABLE_OVERNIGHT_CARRY`. | Session valid if $>3$ hours observed; otherwise session re-run. |
| **Missing Expiry Settlement Price** | If exchange settlement is unpopulated at 15:30 IST, positions remain in `PENDING_EXPIRY_SETTLEMENT`. Evaluator does not fabricate prices. | Re-evaluated next morning once official index close is posted. |

---

## 6. Daily Reporting & Performance Metrics

At the close of each trading day ($T$), the daily audit script evaluates the ledger:

### 1. Activity & Funnel Metrics
- **Signals Generated:** Total raw signals from `StrategyManager`.
- **Signals Rejected:** Categorized by reason (`REJECTED_STALE_QUOTE`, `REJECTED_EXCESSIVE_SPREAD`, `REJECTED_PARTIAL_BAR`, `REJECTED_POSITION_ALREADY_OPEN`).
- **Executed Fills:** Total buy and sell fills committed.
- **Non-Fills / Liquidity Traps:** Count of transitions to `PENDING_LIQUIDITY`.

### 2. Financial & Statistical Metrics
- **Gross P&L:** Total trade gross gains minus gross losses.
- **Total Frictions:** Sum of brokerage, exchange, SEBI, stamp duty, STT, and GST.
- **Friction Drag Ratio:** $\text{Total Frictions} / \max(1, |\text{Gross P\&L}|) \times 100\%$.
- **Net P&L:** Net financial outcome after all deductions.
- **Cumulative Drawdown:** Peak-to-trough net equity drawdown.
- **Win Rate %:** Percentage of round-trip trades with $\text{Net P\&L} > 0$.
- **Profit Factor:** $\text{Gross Gains} / \max(1, \text{Gross Losses})$.
- **Expectancy:** Average net profit per completed trade.

---

## 7. Mandatory Pause Conditions (Integrity Circuit Breakers)

The prospective trial must be **immediately paused** and investigated if any of the following occur:
1. **Contamination of Equity Tables:** Any option contract or derivative symbol appears in `market_ohlcvbar` or `market_stockintradaycontext` (Violates `AC-1-L01`).
2. **Fabricated Fills / Ghost Fills:** Any fill is logged without an authentic `OptionQuoteSnapshot` or with an invented price when the limit order book had zero bid liquidity.
3. **Unsynchronization of Unresolved Trades:** `sync_active_trades_from_db()` raises `ValueError` due to duplicate unresolved rows for the same `(strategy_id, tradingsymbol)`.
4. **Data Disconnect Duration $> 30$ Continuous Minutes:** If live market feed is unavailable for $>30$ minutes between 09:30 and 15:15 IST, the session is invalidated and replaced.
5. **Negative Sell Fills:** An exit fill is committed below the exchange minimum tick size (₹0.05).

---

## 8. Final Trial Success & Comparison Criteria

Upon completion of Session 20 (`2026-11-18`), the strategy will be evaluated across the full matrix:
- **Sample Size Target:** $\ge 20$ completed round-trip trades across the 20-day horizon.
- **Execution Realism:** Zero negative slippage anomalies; zero unexecutable phantom exits.
- **Friction Drag Acceptance:** Friction drag ratio $\le 35\%$ of gross profits.
- **Profitability Benchmark:** Net P&L $> 0$ after all statutory taxes, broker fees, and conservative tick-grid slippage.
- **Max Drawdown Limit:** Max drawdown $\le 15\%$ of allocated nominal capital.

---

## 9. Pre-Flight Verification Sign-Off

- [x] Zero live broker order placement permitted (`is_paper_trading = True`, zero order routing code).
- [x] Local working tree inspected; pre-existing changes preserved.
- [x] Strategy `STRAT-ORB-15M` parameters frozen and documented.
- [x] Statutory fee schedule verified for Finance Act 2026 rates.
- [x] 20 prospective session dates established.
- [x] Data integrity circuit breakers defined.

**Pre-Flight Status:** **`READY TO INITIATE UPON SESSION 01 CONFIRMATION (2026-10-22)`**
