# Nomad Analyst — Phase 0.1 Contract Correction Report

**Document Reference:** `docs/research/fno/fno_phase0_1_contract_correction_report.md`  
**Execution Date:** 2026-10-17  
**Revision Version:** 1.3.0 (Final Phase 0.1 Review Corrections)  
**Author:** Quantitative Researcher & Systems Architect  
**Task Type:** Documentation-Only Contract Correction & Scope Clarification  
**Status:** COMPLETE & CERTIFIED  

---

## 1. Executive Summary & Purpose

This report documents the completion of **Phase 0.1 Final Contract Corrections**, an authoritative refinement pass performed on the ratified architectural specifications prior to commencing Phase 1 implementation.

All revisions maintain strict zero-code compliance: zero application code, configuration, tests, migrations, dependencies, or database records were modified. All pre-existing working-tree changes in `market/` and untracked audit documents were strictly preserved.

### Canonical Specification Reference:
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md) (Version 1.3.0)

---

## 2. Detailed Technical Decisions & Contract Corrections

### A. Quote Freshness, Timestamps & Execution Eligibility
- **Independent Definition of Quote Age vs. Last-Trade Age:**
  - In Indian derivatives, an option contract may have an actively quoting, competitive order book even if no trade has executed for several minutes or hours. Conversely, a trade may have occurred recently while order book updates have since halted. Conflating the two metrics using a composite $\max()$ function was mathematically unsound.
  - **Quote Age (Price/Depth Freshness):** Measured strictly from the quote packet's exchange timestamp, **independently of last-trade age**:
    $$\Delta_{\text{quote\_age\_s}} = \max\left(0.0, (\text{evaluation\_wall\_clock\_utc} - \text{exchange\_timestamp\_utc}).\text{total\_seconds}()\right)$$
  - **Last-Trade Age (Transaction Activity):** Measured strictly from the last trade timestamp:
    $$\Delta_{\text{trade\_age\_s}} = \max\left(0.0, (\text{evaluation\_wall\_clock\_utc} - \text{last\_trade\_timestamp\_utc}).\text{total\_seconds}()\right) \quad (\text{if } \text{last\_trade\_timestamp\_utc} \text{ exists, else } \text{None})$$
- **Four Separate Temporal Metrics:**
  1. `feed_latency_ms`: $(\text{received\_wall\_clock\_utc} - \text{exchange\_timestamp\_utc}).\text{total\_seconds}() \times 1000$. Measures transit/network latency from exchange matching engine to Nomad's socket.
  2. `quote_age_seconds`: Elapsed time since exchange quote timestamp. Measures whether the limit order book prices and depth are fresh.
  3. `last_trade_age_seconds`: Elapsed time since last trade. Measures execution recency.
  4. `pipeline_latency_ms`: $(\text{monotonic\_now\_ns} - \text{received\_monotonic\_ns}) / 1{,}000{,}000$. Measures internal daemon processing elapsed time.
- **Timestamp Validation, Fallback Semantics & Execution Eligibility:**
  > [!CRITICAL]
  > **Receipt Fallback Rule: Never Treat Fallback as Freshness.**  
  > If a packet lacks an exchange timestamp ($\text{packet\_ts} == 0$ or null), Nomad falls back to `received_wall_clock_utc` purely to maintain internal event queue ordering.  
  > **A receipt-time fallback can NEVER be treated as proof that an exchange quote is fresh.** The quote is flagged `exchange_time_status = "FALLBACK_TO_RECEIVED"`, `is_quote_fresh = False`, and marked **`EXECUTION_INELIGIBLE_UNVERIFIED_TIMESTAMP`**.
  - `VALID`: $0 < \text{packet\_ts}$ and $-300\text{s} \le \text{exchange\_ts} - \text{received\_utc} \le +2.0\text{s}$. Eligible for quote freshness certification and execution if $\Delta_{\text{quote\_age\_s}} \le 3.0\text{s}$.
  - `INVALID`: $\text{packet\_ts} < 0$. Flagged `EXECUTION_INELIGIBLE_INVALID_TIMESTAMP`.
  - `FUTURE_SKEW_REJECTED`: $\text{exchange\_ts} > \text{received\_utc} + 2.0\text{s}$. Discarded from rollups and snapshots; flagged `EXECUTION_INELIGIBLE_FUTURE_SKEW`.
  - `HISTORICAL_SKEW_REJECTED`: $\text{exchange\_ts} < \text{session\_open} - 300\text{s}$. Discarded as stale delayed replay; flagged `EXECUTION_INELIGIBLE_HISTORICAL_SKEW`.
  - **Mathematical Rule:** Monotonic timestamps have arbitrary reference points. **Never subtract an epoch timestamp from a monotonic timestamp.**

### B. Underlying Volume & VWAP Semantics
- **No Native Volume on Cash Indices:**
  - A statistical index such as NIFTY 50 (`^NSEI`) has no traded volume or native order book.
  - **Summing constituent equity volume does NOT produce an index VWAP.** An index is an equity market-capitalization divisor benchmark, not a volume-weighted composite.
- **Explicit Volume Sourcing:**
  - Volume-weighted underlying momentum context is strictly sourced from the **active near-month NIFTY Futures contract (`NIFTY-FUT`)**, which is a real traded instrument with native volume, open interest, and market VWAP (`underlying_vwap_source = "NIFTY_FUTURES_ACTIVE_MONTH"`).
  - Constituent equity volume sum is preserved strictly as a distinct market breadth metric (`nifty_constituent_total_volume`), never labeled as index VWAP.
  - If the futures feed is unpopulated or unavailable, `underlying_bar_vwap`, `underlying_session_vwap`, and `underlying_rvol_5m` are set to `None` with `underlying_vwap_source = "UNAVAILABLE"`. Volume-dependent strategy rules reject signal generation when unavailable.

### C. Quote Snapshot Persistence Placed in Phase 1
- **Ownership & Phase Placement:**
  - High-frequency quote capture and persistence (`fno_option_quote_snapshot`) is explicitly assigned to **Phase 1 (Isolated Options Data Foundation, Bars & Quote Snapshots)**.
  - **Fundamental Reality:** Realistic taker fills in Phase 4 cannot be evaluated from OHLCV candles alone. Capturing bid/ask and depth snapshots in Phase 1 ensures Phase 4 has authentic tick-level execution data.
- **Schema & Indexing:**
  - Stores `instrument_token`, `tradingsymbol`, `exchange_timestamp_utc`, `received_wall_clock_utc`, `best_bid`, `best_ask`, `bid_quantity_l1`, `ask_quantity_l1`, `depth` (JSONB up to 5 levels), `quote_status`, `is_stale`, `is_locked`, `is_crossed`.
  - Compound indexes: `(instrument_token, exchange_timestamp_utc DESC)` and `(tradingsymbol, exchange_timestamp_utc DESC)`.
- **Retention & Storage:**
  - Hot tier retained for 5 trading sessions in PostgreSQL.
  - Automated weekly Celery task purges or archives snapshot partitions following contract settlement.
  - Debounce threshold: 250ms per token during quote flickering without price/depth changes.

### D. Expiry, Settlement Lifecycle & Unexecutable Exits
- **Separation of Continuous Market Exits from Official Expiry Settlement:**
  - Continuous market exits occur during market hours (before 15:30:00 IST) by crossing the order book bid: $P_{\text{exit}} = \text{Best Bid} - \text{Slippage}$ (`fill_type = "MARKET_TAKER"`).
  - Official expiry settlement is an administrative cash settlement determined by the clearing corporation after trading ceases. It does **not** cross an order book, does **not** consume bid liquidity, and does **not** incur market slippage.
  - **Never record settlement as a bid-side fill.** Recorded as `fill_type = "SETTLEMENT"` with $\text{exit\_slippage} = \text{Decimal("0.00")}$.
- **Pending Settlement State & Zero-Fabrication Invariant:**
  - At 15:30:00 IST on expiry day, all open positions in the expiring contract transition to **`PENDING_EXPIRY_SETTLEMENT`**.
  - **Never fabricate a settlement price, fill, or settlement value.**
  - If official settlement price (the NSE final settlement index value based on the 15:00–15:30 IST VWAP) or verified statutory exercise fee schedule is not yet ingested, the position remains in `PENDING_EXPIRY_SETTLEMENT`.
  - Once verified settlement value is available:
    - OTM/ATM: $\text{settlement\_price} = 0.00$, $\text{status} = \text{"CLOSED_EXPIRED_WORTHLESS"}$.
    - ITM: $\text{settlement\_price} = \max(0, S_{\text{settlement}} - K)$, $\text{status} = \text{"CLOSED_EXPIRED_ITM_SETTLED"}$ (subject to 0.15% STT).
- **Prohibition of Next-Session Exit Retries for Expired Contracts:**
  - An expired contract is permanently inactive.
  - **Under no circumstances can an expired contract enter `UNEXECUTABLE_OVERNIGHT_CARRY` or next-session exit retries.**
  - `UNEXECUTABLE_OVERNIGHT_CARRY` is strictly restricted to **unexpired** contracts on regular non-expiry trading days where a 15:15 policy exit could not find an executable bid.
- **Configurable Operational & Risk Policies:**
  - *13:00 IST Staging:* Labeled as a Nomad **configurable operational policy** (`next_weekly_staging_policy_time = time(13, 0)`), NOT an exchange rule. Purpose: pre-subscribe next-weekly contracts to warm up local data pipelines during afternoon liquidity rollover.
  - *15:15 IST Square-Off:* Labeled as a Nomad **configurable risk management policy** (`intraday_square_off_policy_time = time(15, 15)`), reflecting a prudent operational buffer prior to broker RMS auto-square-offs, NOT a universal exchange mandate.

### E. Sample Size Tiers & One-Month Limitations
- **Sample Size Tier Resolution:**
  - $N < 20$ Trades: **REJECTED (Insufficient Sample / Inconclusive)**.
  - $20 \le N \le 29$ Trades: **CONDITIONAL / PROVISIONAL (Underpowered Sample)**. Requires mandatory **2-week paper-trading extension** until $N \ge 30$; cannot proceed to Phase 6 certification.
  - $N \ge 30$ Trades: **ADEQUATE SAMPLE FOR EVALUATION**. Full 7-dimensional decision matrix is evaluated.
- **Epistemic Constraint:** A 1-month window covers only 20–22 sessions and 1–2 market regimes. It serves to filter out non-viable strategies (negative expectancy, excessive friction drag) rather than prove long-term alpha.

---

## 3. Exact Inventory of Files Changed

| File Path | Version | Summary of Changes |
| :--- | :---: | :--- |
| [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md) | **v1.3.0** | Canonical specification updated with independent quote age, execution eligibility, settlement separation, configurable policies, and unexecutable exit rules. |
| [`docs/research/fno/fno_phase_roadmap.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase_roadmap.md) | **v1.3.0** | Added quote snapshot capture and retrieval in Phase 1 (`AC-1-U05`, `AC-1-L04`); added settlement separation and expired contract prohibition in Phase 4 (`AC-4-U02`, `AC-4-U03`). |
| [`docs/research/fno/fno_chatgpt_handoff.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_chatgpt_handoff.md) | **v1.3.0** | Documented final review corrections; updated Phase 1 recommendation and acceptance criteria matrix. |
| [`docs/research/fno/fno_architecture_reconciliation_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_architecture_reconciliation_report.md) | **v1.3.0** | Incorporated final review corrections detail, decisions made, and disentangled checklist. |
| [`docs/research/fno/fno_phase0_1_contract_correction_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase0_1_contract_correction_report.md) | **v1.3.0** | This formal report detailing all final Phase 0.1 contract corrections, settlement lifecycle, and Phase 1 readiness. |

---

## 4. Remaining Questions & Unresolved Blockers

1. **Broker Historical Expired Options Limit (Permanent Constraint):**  
   Kite Connect historical candle endpoints do not serve expired derivative contracts once settlement concludes. Quantitative strategy validation will proceed strictly via forward paper trading in Phase 5 using prospectively captured live ticks.
2. **Statutory Fee Schedule Verification (Phase 4 Prerequisite):**  
   While regulatory circular numbers (NSE `NSE/FA/73061`, STT under Finance Act) have been documented from official sources, the exact deduction formulas must be cross-verified against actual Zerodha contract notes before Phase 4 paper execution is deployed.
3. **Phase 1 Authorization Gate:**  
   Phase 1 implementation (`fno/` application creation, `OptionOHLCVBar` model, `OptionQuoteSnapshot` model, `OptionNormalizer`, dynamic token subscription) remains on hold pending explicit operator authorization following ChatGPT review.

---

## 5. Phase 1 Implementation Recommendation & Acceptance Checklist

### Verdict: **RECOMMEND IMMEDIATE APPROVAL TO COMMENCE PHASE 1.**

### Disentangled Acceptance Checklist for Phase 1:
- [ ] **AC-1-U01** `[Unit-Test Requirement]`: `OptionInstrumentRegistry` parses daily CSV, treats master `expiry` date as authoritative, and detects stale master files.
- [ ] **AC-1-U02** `[Unit-Test Requirement]`: `OptionNormalizer` unpacks 184-byte packets with valid zero OI, unpopulated OI (`None`), sparse depth (120 bytes), locked/crossed quote classification, and anomaly detection.
- [ ] **AC-1-U03** `[Unit-Test Requirement]`: Desired-universe reconciliation correctly calculates tokens to subscribe and unsubscribe on spot movements and expiry rolls.
- [ ] **AC-1-U04** `[Unit-Test Requirement]`: 1-minute `OptionOHLCVBar` persistence engine is idempotent and prevents duplicate rows under compound unique constraint.
- [ ] **AC-1-U05** `[Unit-Test Requirement]`: `OptionQuoteSnapshot` persists depth JSONB and bid/ask, rejects timestamps with future skew $>2.0$s, handles fallback timestamps without marking them fresh, and supports fast indexed queries.
- [ ] **AC-1-L01** `[Live Acceptance Test]`: Streaming live NFO option ticks concurrently produces zero errors or state mutations in `IntradayStateManager` and zero rows in `market_ohlcvbar`.
- [ ] **AC-1-L02** `[Live Acceptance Test]`: 1-minute `OptionOHLCVBar` records persist with strictly accurate `open_interest` and volume deltas across continuous trading.
- [ ] **AC-1-L03** `[Live Acceptance Test]`: Reconnection recovery resubscribes all active tokens in `MODE_FULL` within 5 seconds of WebSocket reconnect during market hours.
- [ ] **AC-1-L04** `[Live Acceptance Test]`: `OptionQuoteSnapshot` records persist with valid quote classifications and $\le 3.0$s quote ages during live trading.

---

## 6. Actual Git Status & Working-Tree Evidence

### Working-Tree Baseline Limitation Notice:
> [!NOTE]
> **Baseline Limitation:**  
> Prior to the commencement of this F&O documentation session, the repository working tree was already in a modified state with 19 tracked files under `market/` and `data/universe/`, alongside untracked files in `docs/audits/` and `HANDOFF_report.md`. Because no git stash or clean commit checkpoint was captured before starting, we cannot mathematically claim that every non-F&O file was verified via git history prior to this session. However, we definitively confirm that:
> 1. All tool operations executed in this task strictly targeted markdown files within `docs/research/fno/`.
> 2. Zero modifications were made to any application code (`.py`), database migrations, settings, or dependencies.
> 3. All pre-existing user modifications have been strictly preserved.

### Git Status (`git status --porcelain`):
```
 M data/universe/kite_nifty50_mapping.json
 M market/management/commands/ingest_kite_historical.py
 M market/management/commands/run_intraday_ticker.py
 M market/normalizers/kite.py
 M market/services/context_service.py
 M market/services/intraday_aggregator.py
 M market/services/intraday_context_engine.py
 M market/services/intraday_indicators.py
 M market/services/intraday_quality.py
 M market/services/intraday_readiness.py
 M market/services/intraday_signal_engine.py
 M market/services/intraday_state_manager.py
 M market/services/kite_historical.py
 M market/services/kite_registry.py
 M market/services/kite_ticker.py
 M market/services/recommendation_service.py
 M market/tasks.py
 M market/tests.py
 M market/views.py
?? HANDOFF_report.md
?? docs/audits/...
?? docs/research/
?? market/management/commands/cleanup_contaminated_preopen_bars.py
```

### Distinction of Pre-Existing Changes vs. This Task:
- **Pre-Existing Uncommitted Changes:** 19 tracked files under `market/` and `data/universe/`, plus untracked files under `docs/audits/` and `HANDOFF_report.md`. None of these files were touched or altered during this task.
- **Changes Made in This Task:** Strictly confined to markdown research and specification files in `docs/research/fno/`:
  - `docs/research/fno/fno_core_engine_and_strategy_lab_spec.md` (Updated)
  - `docs/research/fno/fno_phase_roadmap.md` (Updated)
  - `docs/research/fno/fno_chatgpt_handoff.md` (Updated)
  - `docs/research/fno/fno_architecture_reconciliation_report.md` (Updated)
  - `docs/research/fno/fno_phase0_1_contract_correction_report.md` (Updated)

### Commands Actually Executed:
1. `git status --porcelain`: Checked exact status of all tracked and untracked files.
2. `find docs/research -type f`: Verified inventory of research documents.
3. `write_to_file`: Updated markdown specifications in `docs/research/fno/`.

---

## 7. Tests Run & Actual Results

- **Unit Tests Run:** **NONE.**
- **Live Acceptance Tests Run:** **NONE.**
- **Rationale:** Phase 0.1 is strictly a documentation-only contract refinement pass. In accordance with Antigravity integrity standards, **zero tests are claimed as passed**. All Phase 1 through Phase 6 acceptance tests remain categorized as `PENDING IMPLEMENTATION`.

---

## 8. Formal Certification of Zero Code Changes

I formally certify that:
- Application code modified: **0 lines.**
- Settings / configuration modified: **0 lines.**
- Test files modified: **0 files.**
- Database migrations generated or applied: **0 migrations.**
- Third-party packages installed or removed: **0 packages.**
- Database records altered: **0 records.**
- Active running daemons modified: **0 processes.**

Implementation has **NOT started**. Phase 1 awaits explicit operator approval.
