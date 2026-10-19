# Nomad Analyst — F&O Architecture Reconciliation Report (Step 1 & Phase 0.1)

**Document Reference:** `docs/research/fno/fno_architecture_reconciliation_report.md`  
**Execution Date:** 2026-10-17  
**Revision Version:** 1.3.0 (Final Phase 0.1 Review Corrections)  
**Author:** Quantitative Researcher & Systems Architect  
**Task Type:** Documentation-Only Reconciliation & Audit  
**Status:** COMPLETE & CERTIFIED  

---

## 1. Executive Summary of Architectural Decisions

Nomad Analyst's F&O pillar has been reconciled and formalized into four core architectural pillars governed by a canonical technical specification:

### A. Shared Core Intelligence Engine
- **Decoupled Normalization:** Ingests raw Kite Connect WebSocket binary packets in `MODE_FULL` (184 bytes), unpacking fixed quote fields (bytes 0–64) and market depth (bytes 64–184: 120 bytes total across 10 levels of 12 bytes each).
- **Strict Pipeline Isolation:** Option ticks are isolated immediately upon reception; they are **never** passed into `IntradayStateManager.on_tick()`, protecting equity market breadth, advance/decline counts, and sector momentum.
- **Dedicated Persistence (Bars & Quote Snapshots):** Option 1-minute bars persist strictly to `fno_option_ohlcvbar`. High-frequency quote snapshots persist in `fno_option_quote_snapshot` starting in Phase 1 with rolling 5-day retention, ensuring realistic taker execution in Phase 4.
- **Unified Feature Contract:** Emits standardized, immutable `OptionFeatureSnapshot` contracts combining underlying cash index price context (`^NSEI`), active futures volume/VWAP (`NIFTY-FUT`), market regime, India VIX, market breadth, technical features, Black-Scholes Greeks, provenance metadata, and quote quality flags.

### B. Extensible Instrument Universe
- **Configuration Boundary:** The initial scope of NIFTY 50 index options, CE and PE, buying only, with an ATM $\pm 5$ strike window (22 contracts) is an **initial configuration boundary**, not a hardcoded architecture limitation.
- **Generic Engine Architecture:** Registries, strike resolvers, and subscription managers operate using generic parameters (`underlying_symbol`, `strike_step`, `lot_size`, `tick_size`), enabling future support for `BANKNIFTY`, `FINNIFTY`, or stock options without core redesign.
- **Partial Chain Disclaimer:** The ATM $\pm 5$ strike window is an **initial capture window**, not a complete option chain. Full-chain surface metrics (such as full skew or complete market PCR) are not claimed from this partial window.

### C. Independent Strategy Modules
- **Modular Class Hierarchy:** All strategies inherit from `BaseStrategy`, with independent configuration, semantic versioning, and enabled/disabled controls.
- **Strict Isolation:** Strategies consume the same standardized `OptionFeatureSnapshot` and emit standardized `OptionSignal` instances. Strategies cannot establish private data connections or share position state with each other.
- **Zero Concrete Rules in Phase 0:** Candidate strategies (`FNO-HYP-01` 15m ORB, `FNO-HYP-02` VWAP Reclaim) are cataloged as falsifiable hypotheses to be implemented in Phase 3 and evaluated in Phase 5.

### D. Shared Paper-Trading & Evaluation Framework
- **Independent Simulated Ledgers:** Each strategy writes exclusively to its own rows in `fno_paper_trade_ledger`, tracking entry/exit prices, slippage, holding durations, and regime tags.
- **Realistic Taker Fills & Settlement Separation:** Evaluates fills against captured quote snapshots at `Best Ask + Slippage` on entry and `Best Bid - Slippage` on continuous market exits. Official expiry settlement is an administrative cash settlement recorded as `fill_type = "SETTLEMENT"` with zero slippage. Settlement is never recorded as a bid-side fill.
- **Protocol for Zero-Bid & Pending Settlement:** If an exit triggers but bids are 0.00 or missing during market hours, the system never fabricates a fill (`PENDING_LIQUIDITY`). Post-15:30 IST on expiry day, positions enter `PENDING_EXPIRY_SETTLEMENT` without fabricating prices until official exchange settlement values/fees are verified. Expired contracts are strictly prevented from entering next-session exit retries.
- **Statutory Fee Verification Mandate:** Exact effective-dated schedules accounting for NSE Circular `NSE/FA/73061` (effective 1 March 2026: ₹3,552.99 exchange fee + ₹0.01 IPFT = ₹3,553/crore), STT (effective 1 April 2026: 0.15% on sell premium), and 18% GST are documented as assumptions requiring pre-implementation verification against actual broker contract notes and circulars prior to Phase 4.
- **Prospective One-Month Parallel Evaluation Window (Phase 5):** Multi-strategy parallel execution over 20–22 trading sessions, evaluated across a 7-dimensional decision matrix with explicit sample size tiers ($N < 20$ rejected, $20 \le N \le 29$ conditional with 2-week extension, $N \ge 30$ adequate). Anti-curve-fitting rule strictly enforced: no winner selected on total P&L alone.

---

## 2. Phase 0.1 Contract Corrections Detail

| Dimension | Previous State | Corrected Contract State | Technical Rationale |
| :--- | :--- | :--- | :--- |
| **Quote Classification** | Grouped `bid >= ask` under crossed quotes. | Distinguishes locked quotes (`bid == ask`) from crossed quotes (`bid > ask`). Added explicit states: `VALID`, `EMPTY_BOOK`, `ZERO_BID`, `STALE`, `LOCKED`, `CROSSED`, `INVALID`. | Locked quotes occur legitimately during circuit limits; crossed quotes indicate data corruption. Both block fills, but have distinct operational causes. |
| **Quote Freshness & Timestamps** | Conflated quote age with last trade time; epoch subtracted from monotonic. | Separated `exchange_timestamp_utc`, `last_trade_timestamp_utc`, `received_wall_clock_utc`, and local `received_monotonic_ns`. Defined quote age strictly from exchange timestamp independently of last trade time. Fallback timestamps do not certify freshness and are marked execution-ineligible. Never subtract epoch from monotonic. | Distinguishes trade activity from quote refreshes and prevents treating local receipt fallback as proof of exchange quote freshness. |
| **Session Volume & Resets** | Mentioned simple reset logging. | Formalized 09:15:00 IST volume reset: resets bar delta accumulator without recording negative volume. Discards late ticks arriving after closed bar grace period. Flags partial bars across reconnection gaps. | Guarantees candle volume accuracy, avoids negative volume anomalies, and ensures bar immutability in PostgreSQL. |
| **Underlying Volume Semantics** | Implied constituent volume sum equals index VWAP. | Established that cash indices (`^NSEI`) have NO traded volume; constituent volume sum does NOT equal index VWAP. Traded volume and VWAP are strictly sourced from active futures (`NIFTY-FUT`), setting to `None` if unavailable. | Eliminates mathematically invalid cash-index volume metrics; prevents false strategy triggers. |
| **Quote Snapshot Persistence** | Persisted only 1m OHLCV bars; Phase 4 needed bid/ask. | Explicitly assigned `fno_option_quote_snapshot` capture and persistence to **Phase 1** with compound indexing and rolling 5-day retention. | 1m bars cannot simulate realistic taker fills at arbitrary signal arrival times. Quote snapshots provide authentic execution prices. |
| **Expiry & Settlement Lifecycle** | Unclear distinction between market exits and settlement; implied overnight retries for expired options. | Separated continuous market exits (`MARKET_TAKER` fill type) from official expiry settlement (`SETTLEMENT` fill type, 0 slippage). Defined `PENDING_EXPIRY_SETTLEMENT` when official settlement price/fees are uningested. Never fabricate fills or settlement values. Expired contracts are strictly prevented from entering next-session exit retries. Labeled 13:00 staging and 15:15 square-off as configurable Nomad policies. | Adheres to real clearinghouse settlement rules; prevents synthetic P&L fabrication; stops dead contracts from trading. |
| **Universe Reconciliation** | Ad-hoc 50-point spot delta trigger. | Formalized stateful Desired-Universe Reconciliation Loop ($\mathcal{U}_{\text{desired}} \setminus \mathcal{U}_{\text{active}}$ and $\mathcal{U}_{\text{active}} \setminus \mathcal{U}_{\text{desired}}$) triggered by ATM shift, 60s heartbeat, reconnect, and policy staging times. | Robust against dropped packets, prevents desynchronization with broker state, and cleanly handles rollover. |
| **Generic Asset Parameterization** | Hardcoded `^NSEI` defaults in classes. | Fully parameterized via `UnderlyingAssetConfig`. Preserved NIFTY CE/PE buying as initial configuration. | Prevents architectural lock-in; allows seamless onboarding of other indices in future phases. |
| **Greeks & Failure Handling** | Idealized Black-Scholes inversion. | Defined explicit inputs, Brent's method inversion, and failure handling setting Greeks to `None` with `greeks_status = "CALCULATION_FAILED"` on arbitrage violations or non-convergence. | Prevents zero-bid or deep-OTM anomalies from crashing the feature pipeline. Added provenance metadata to snapshots. |
| **Evaluation Sample Size Tiers** | Ambiguous treatment of 20–29 trades. | Resolved into 3 strict tiers: $N < 20$ (Rejected), $20 \le N \le 29$ (Conditional; requires 2-week extension), $N \ge 30$ (Adequate for certification). | Removes evaluation ambiguity and enforces statistical rigor while acknowledging 1-month sample limitations. |
| **Regulatory Fee Verification** | Certified fee numbers without qualification. | Marked all fee formulas and rates as assumptions requiring pre-implementation verification against contract notes and circulars in Phase 4. | Avoids false certainty on regulatory tax changes and brokerage schedules. |
| **Criteria Disentanglement** | Combined unit and live criteria in rows. | Disentangled into distinct `[Unit-Test Requirement]` and `[Live Acceptance Test]` categories across all phases. | Enables automated CI execution of unit tests independent of live market access. |

---

## 3. Exact Files Changed in Phase 0.1

| File Path | Status | Important Changes |
| :--- | :--- | :--- |
| [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md) | **Updated (v1.3.0)** | Canonical specification updated with independent quote age, execution eligibility, settlement separation, configurable policies, and unexecutable exit rules. |
| [`docs/research/fno/fno_phase_roadmap.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase_roadmap.md) | **Updated (v1.3.0)** | Added quote snapshot capture and retrieval in Phase 1 (`AC-1-U05`, `AC-1-L04`); added settlement separation and expired contract prohibition in Phase 4 (`AC-4-U02`, `AC-4-U03`). |
| [`docs/research/fno/fno_chatgpt_handoff.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_chatgpt_handoff.md) | **Updated (v1.3.0)** | Documented final review corrections; updated Phase 1 recommendation and acceptance criteria matrix. |
| [`docs/research/fno/fno_architecture_reconciliation_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_architecture_reconciliation_report.md) | **Updated (v1.3.0)** | Incorporated final review corrections detail, decisions made, and disentangled checklist. |
| [`docs/research/fno/fno_phase0_1_contract_correction_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase0_1_contract_correction_report.md) | **Updated (v1.3.0)** | Standalone formal report detailing Phase 0.1 contract corrections, settlement lifecycle, and Phase 1 readiness. |

---

## 4. Remaining Questions & Blockers

1. **Broker API Constraint (Permanent):**  
   Zerodha Kite Connect historical candle endpoints do not serve expired derivative contracts once settlement concludes. Quantitative strategy validation will proceed strictly via forward paper trading in Phase 5 using prospectively captured live ticks.
2. **Statutory Fee Schedule Verification (Phase 4 Prerequisite):**  
   The exact fee deduction formulas must be cross-verified against actual Zerodha contract notes before Phase 4 paper execution is deployed.
3. **Phase 1 Authorization Gate:**  
   Phase 1 implementation (`fno/` application creation, `OptionOHLCVBar` model, `OptionQuoteSnapshot` model, `OptionNormalizer`, dynamic token subscription) remains on hold pending explicit operator authorization following ChatGPT review.

---

## 5. Next Implementation Phase: Phase 1 & Acceptance Checklist

### Scope for Phase 1:
- Dedicated, isolated `fno/` Django application.
- `OptionInstrumentRegistry` parsing daily master CSV with authoritative expiry resolution and stale file detection.
- Stateful desired-universe reconciliation loop (ATM $\pm 5$ strikes, spot shift rebalancing, 60s periodic reconciliation, and configurable next-weekly staging policy).
- `OptionNormalizer` unpacking 184-byte `MODE_FULL` packets, defensively handling valid zero OI, unpopulated OI (`None`), sparse depth (120 bytes), locked quotes (`bid == ask`), crossed quotes (`bid > ask`), volume resets, and timestamp integrity (measuring quote age independently of last trade time, rejecting future skew $>2.0$s).
- Dedicated `OptionOHLCVBar` model and 1-minute candle rollup engine with compound unique constraints.
- Dedicated `OptionQuoteSnapshot` model and persistence engine with compound indexing and rolling 5-day retention.
- Reconnection and resubscription reconciliation.
- Dedicated unit-test suite in `fno/tests/`.

### Disentangled Acceptance Checklist:
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
> Prior to the commencement of this F&O documentation session, the repository working tree was already in a modified state with 19 tracked files under `market/` and `data/universe/`, alongside untracked files in `docs/audits/` and `HANDOFF_report.md`. Because no git stash or clean commit checkpoint was captured before starting, we cannot claim that every non-F&O file was verified via git history prior to this session. However, we definitively confirm that:
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

### Commands Executed in This Task:
1. `git status --porcelain`: Inspected exact working tree state.
2. `find docs/research -type f`: Cataloged all research and specification files.
3. `write_to_file`: Updated markdown documentation in `docs/research/fno/`.

---

## 7. Tests Run & Actual Results

- **Unit Tests Run:** **NONE.**
- **Live Acceptance Tests Run:** **NONE.**
- **Rationale:** This pass was strictly a documentation and contract refinement pass (Phase 0.1). In accordance with Antigravity integrity standards, **zero tests are claimed as passed**. All Phase 1 through Phase 6 acceptance tests remain categorized as `PENDING IMPLEMENTATION`.

---

## 8. Confirmation of Zero Implementation Changes

I formally certify that:
- Application code modified: **0 lines.**
- Settings / configuration modified: **0 lines.**
- Test files modified: **0 files.**
- Database migrations generated or applied: **0 migrations.**
- Third-party packages installed or removed: **0 packages.**
- Database records altered: **0 records.**
- Active running daemons modified: **0 processes.**

Implementation has **NOT started**. Phase 1 awaits explicit operator approval.
