# Nomad Analyst — Experiment Tracking & Evaluation Framework Specification (v1.2.0)

**Document ID:** `SPEC-EXP-EVAL-V1`  
**Specification Status:** Final Architecture Specification (Documentation Only — No Code Implementation)  
**Author:** Senior Quantitative Systems Engineer  
**Date:** 2026-10-22 (Revision 1.2.0)  
**Target Systems:** `fno/research/registry.py`, `fno/research/comparator.py`, `docs/audits/`

---

## 1. Executive Summary & Philosophy of Quantitative Rigor

The Nomad Analyst Experiment Tracking and Evaluation Framework establishes a disciplined, audit-grade methodology for evaluating quantitative options-buying strategies. In algorithmic research, backtest results that look stellar on paper frequently fail in live production due to four common vulnerabilities:

1. **Look-Ahead Bias & Information Contamination:** Evaluating signals using future candle information.
2. **Overfitting & P-Hacking:** Repeatedly tuning indicators until they fit historical noise, masking lack of true alpha.
3. **Survivor & Selection Bias:** Hiding unprofitable experiments and presenting only the best-performing iteration.
4. **Unrealistic Execution Assumptions:** Ignoring market friction, statutory taxes, and slippage.

This framework mandates transparent logging of all runs, standardized risk-adjusted evaluation metrics, dual-scorecard cross-strategy benchmarking, and explicit classification of previously observed historical data.

---

## 2. Authoritative Baseline Reconciliation (Phase 2.4.2 Ground Truth)

To establish an uncompromised acceptance benchmark for Phase 3.1 regression, the authoritative baseline metrics are reconciled directly from [`docs/audits/fno_backtest_report_orb15m.json`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/fno_backtest_report_orb15m.json):

### A. Authoritative Ground Truth Metrics Table
| Metric Description | Exact Authoritative Value | Source Key in `fno_backtest_report_orb15m.json` |
| :--- | :---: | :--- |
| **Strategy Configuration** | `STRAT-ORB-15M` (150-pt cap) | `config.max_orb_range_pts = "150.00"` |
| **Total Trading Days** | 242 | `session_accounting.total_trading_days` |
| **Qualified Sessions** | **204** | `session_accounting.qualified_sessions` |
| **Excluded Sessions** | **38** | `session_accounting.excluded_sessions` (19 missing expiry, 18 wide range, 1 index gap) |
| **Total Executed Trades** | **200** | `metrics.standard_clean_ledger.total_trades` |
| **Winning Trades** | **82** (41.00%) | `metrics.standard_clean_ledger.winning_trades` |
| **Losing Trades** | **118** (59.00%) | `metrics.standard_clean_ledger.losing_trades` |
| **Profit Factor** | **0.7714** | `metrics.standard_clean_ledger.profit_factor` |
| **Gross P&L** | **₹-29,562.25** | `metrics.standard_clean_ledger.total_gross_pnl` |
| **Total Frictions** | **₹12,518.49** | `metrics.standard_clean_ledger.total_frictions` (Brokerage: ₹8,000; Taxes: ₹4,518.49) |
| **Net P&L (0.5% Slippage)** | **₹-42,080.74** | `metrics.standard_clean_ledger.total_net_pnl` |
| **Maximum Drawdown Amount**| **₹42,256.82** | `metrics.standard_clean_ledger.max_drawdown_amount` |
| **Maximum Drawdown %** | **21.13%** | `metrics.standard_clean_ledger.max_drawdown_pct` (₹42,256.82 / ₹200,000.00) |
| **Expectancy per Trade** | **₹-210.40** | `metrics.standard_clean_ledger.expectancy_per_trade` |
| **Quarantined Impaired Trades**| **0** | `metrics.quarantined_impaired_ledger.total_trades` |
| **Unfilled Entry Attempts** | **4** | `session_summaries` where `breakout_detected=True` and `trade_executed=False` |

### B. Reconciliation of Discrepancies
- **Profit Factor (0.7714 vs 0.81):** The value `0.81` cited in preliminary documentation was an unrounded estimate from the **uncapped exploration run** (`fno_backtest_report_orb15m_nolimit.json`), which admitted 17 additional trades. In the authoritative 150-pt capped baseline, the Profit Factor is strictly **`0.7714`**.
- **Maximum Drawdown (₹42,256.82 vs ₹46,876.54):** The value `₹46,876.54` belonged strictly to the **uncapped exploration run**, where high-volatility wide-ORB days deepened drawdowns. In the authoritative 150-pt capped baseline, Maximum Drawdown is strictly **`₹42,256.82` (21.13%)**.

---

## 3. Execution Outcome Classification & Auditing

To eliminate ambiguities between non-breakout sessions and execution failures, every session and trade attempt is audited into mutually exclusive categories:

```
+-------------------------------------------------------------------------------------------------------+
|                                     INTRADAY EXECUTION RESOLUTION                                     |
+----------------------+--------------------+--------------------+--------------------+-----------------+
| 1. NO SIGNAL         | 2. REJECTED ENTRY  | 3. UNFILLED ENTRY  | 4. CLEAN TRADE     | 5. QUARANTINED  |
| (No Condition Met)   | (Cutoff / Expiry)  | (No Liquidity Bar) | (Normal Execution) | (Data Incident) |
+----------------------+--------------------+--------------------+--------------------+-----------------+
| Baseline Count: 0    | Baseline Count: 0  | Baseline Count: 4  | Baseline Count: 200| Baseline Count: 0|
+----------------------+--------------------+--------------------+--------------------+-----------------+
```

### Detailed Classification Definitions:
1. **No Signal Sessions:** Qualified sessions where price action remained within bounds and generated zero entry triggers during the allowed entry window (0 sessions in Phase 2 baseline).
2. **Rejected Entry Attempts:** Sessions where a valid breakout/signal occurred, but entry was rejected prior to simulated order routing due to hard platform constraints:
   - `REJECTED_FILL_PAST_ENTRY_CUTOFF`: Fill timestamp ($T+1$) exceeded entry window end (e.g. `14:30:00 IST`).
   - `REJECTED_CONTRACT_SELECTION_FAILED`: Option contract could not be resolved (e.g. missing weekly file on post-13:00 rollover).
3. **Unfilled Entry Attempts:** Sessions where a valid breakout occurred and a contract was successfully resolved, but the simulated order could not be executed due to the complete absence of a traded option candle at $T+1$ open:
   - Reason Code: `EXPIRED_UNFILLED_NO_LIQUIDITY_BAR`
   - **Empirical Baseline Ground Truth:** Exactly **4 sessions** exhibited this behavior in the Phase 2 dataset:
     - `2026-06-04` (ORB High: 23362.50, Low: 23249.60, Breakout: True, Filled: False)
     - `2026-06-05` (ORB High: 23513.65, Low: 23440.20, Breakout: True, Filled: False)
     - `2026-06-08` (ORB High: 23156.75, Low: 23071.50, Breakout: True, Filled: False)
     - `2026-06-09` (ORB High: 23244.35, Low: 23199.00, Breakout: True, Filled: False)
   - *These sessions are strictly classified as **Unfilled Entry Attempts**, never as "no-breakout sessions".*
4. **Clean Executed Trades:** Standard trades with continuous authentic option bars from entry to exit (200 trades in baseline).
5. **Quarantined Impaired Trades:** Trades with missing intermediate option candles requiring synthetic mark-to-market interpolation (0 trades in baseline).

---

## 4. Dataset Partitioning, Previously Observed Data & Prospective Governance

### A. Transparent Classification of the Historical Window
The total available historical window spans `2025-07-01` to `2026-07-02` (242 trading days).  
**Explicit Audit Reality:** The entire window—including the `2026-04-01` to `2026-07-02` period—was already evaluated in Phase 2 baseline runs.  
**Mandatory Classification:** The period `2026-04-01` to `2026-07-02` is **strictly labeled as "Previously Observed Historical Data"**. It cannot be represented as a clean, untouched, or blind holdout.

```
+----------------------------------------------------------------------------------------------------+
|                       PREVIOUSLY OBSERVED HISTORICAL WINDOW (242 TRADING DAYS)                     |
+------------------------------------+----------------------------------+----------------------------+
|        SPLIT 1: IN-SAMPLE          |       SPLIT 2: VALIDATION        |   SPLIT 3: PREV. OBSERVED  |
|           (TRAINING)               |        (PARAMETER TUNING)        |      TEST PARTITION        |
|     2025-07-01 to 2025-11-30       |     2025-12-01 to 2026-03-31     |   2026-04-01 to 2026-07-02 |
|       ~105 Trading Days            |        ~81 Trading Days          |      ~56 Trading Days      |
+------------------------------------+----------------------------------+----------------------------+
| - Strategy conception & hypothesis | - Sensitivity testing            | - Retrospective benchmark  |
| - Baseline parameter setting       | - Slippage stability checks      | - PREVIOUSLY OBSERVED DATA |
| - Indicator window calibration     | - Cross-validation rejection     | - NOT AN UNTOUCHED HOLDOUT |
+------------------------------------+----------------------------------+----------------------------+
```

### B. Prospective Out-of-Sample Policy & Parameter Freezing
Because the current dataset ends on `2026-07-03`, **no prospective out-of-sample data exists within the current repository**.  
To establish genuinely out-of-sample statistical validity:
1. **Pre-Evaluation Parameter Freeze:**
   - Once a strategy passes In-Sample and Validation partitions, all strategy logic, indicators, hyperparameters, and risk rules are **permanently frozen**.
   - A cryptographic SHA-256 fingerprint of the strategy code and configuration is recorded in `docs/audits/frozen_strategies.json`.
2. **Prospective Forward Evaluation Requirement:**
   - Prospective evaluation must strictly use data collected or acquired after the strategy code and parameters are frozen. We do not describe July 3, 2026 onward as a future period or claim prospective data exists without verifying it.
   - If a frozen strategy fails its prospective evaluation period, it is **discarded**. Post-hoc modifications to salvage performance on prospective data are strictly prohibited.
3. **Walk-Forward Analysis (WFA) Policy:**
   - Research models utilize rolling or anchored walk-forward splits where optimization windows strictly precede test windows:
     $$\text{Train}_k \implies \text{Test}_k \quad \text{with } \text{Date}(\text{Train}_k) < \text{Date}(\text{Test}_k)$$

---

## 5. Dual-Scorecard Comparative Benchmarking & Common-Sample Definition

To ensure scientific comparability, the research comparator produces two distinct, synchronized evaluation scorecards:

```
+-----------------------------------------------------------------------------------+
|                        DUAL COMPARATIVE SCORECARDS                                |
+-----------------------------------------+-----------------------------------------+
|     1. FULL-SAMPLE SCORECARD            |      2. COMMON-SAMPLE SCORECARD         |
|  (Strategy-Specific Qualified Sessions) | (Intersection of All Qualified Sessions)|
+-----------------------------------------+-----------------------------------------+
| - Evaluates each strategy across its    | - Evaluates all compared strategies on  |
|   own valid eligible dataset.           |   the EXACT SAME set of sessions.       |
| - Standalone strategy reporting.        | - Apple-to-apple competitive edge.      |
+-----------------------------------------+-----------------------------------------+
```

### Dynamic Calculation of Common Sample Intersection
The engine **never assumes the common sample size in advance**. Instead, it dynamically calculates the mathematical set intersection of qualified session dates across all compared strategies at runtime:

$$\mathcal{S}_{\text{common}} = \bigcap_{i=1}^M \mathcal{S}_{\text{qualified}}(S_i)$$

Where:
- $S_i$ represents candidate strategy $i \in \{1, \dots, M\}$.
- $\mathcal{S}_{\text{qualified}}(S_i)$ is the exact set of ISO date strings (`"YYYY-MM-DD"`) deemed qualified under strategy $S_i$'s session and data filters.
- $N_{\text{common}} = |\mathcal{S}_{\text{common}}|$ is dynamically reported along with the full list of evaluated session identifiers.
- *Preservation of Hard Exclusions:* The 19 missing weekly expiry sessions (`EXCLUDED_MISSING_EXPIRY_DATA`) and the 1 index data gap session (`EXCLUDED_DATA_GAP`) are excluded across **both** scorecards. Zero synthetic contract substitution is permitted.

---

## 6. Regression Acceptance Criteria for Phase 3.1

To authorize Phase 3.1, the newly refactored ORB plugin (`fno/research/strategies/orb_15m.py`) evaluated under `fno/research/engine.py` must meet the following strict regression acceptance criteria:

| Dimension | Verification Requirement | Exact Authoritative Threshold |
| :--- | :--- | :---: |
| **Trade-Level Equivalence** | Trade-by-trade match against `docs/audits/fno_backtest_report_orb15m.json` | **100% bit-for-bit match across all 200 trades** |
| **Session Gating** | Qualification and exclusion counts | **204 Qualified / 38 Excluded (19 missing, 18 wide, 1 gap)** |
| **Financial Output** | Net P&L at 0.5% baseline slippage | **₹-42,080.74 (exact to the paisa)** |
| **Profit Factor** | Authoritative Profit Factor | **0.7714** |
| **Maximum Drawdown** | Authoritative Drawdown Amount & Pct | **₹42,256.82 (21.13%)** |
| **Win / Loss Breakdown** | Exact trade outcomes | **82 Wins (41.00%) / 118 Losses (59.00%)** |
| **Slippage Sensitivity** | Net P&L across all 6 sensitivity scenarios | **100% match across 0%, 0.5%, 1%, 1.5%, ₹0.50, ₹1.00** |
| **Execution Resolution** | Breakdown of non-traded sessions | **0 No Signal / 0 Rejected / 4 Unfilled / 0 Quarantined** |
| **Existing Test Suite** | All unit tests in `fno/tests/` | **40 passing tests / 0 failures / 0 regressions** |
| **Git & Worktree Safety** | Working tree and operational boundaries | **Preserve all pre-existing modifications, especially the six known frontend files; zero unrelated changes; no staging, commits, pushes, resets, or reverts; operational ledgers (`PaperTradeLedger = 0`) untouched** |
