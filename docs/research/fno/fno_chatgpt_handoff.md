# Nomad Analyst — F&O Phase 0: ChatGPT Architectural Handoff (Final Reconciliation)

**Document Reference:** `docs/research/fno/fno_chatgpt_handoff.md`  
**Revision Date:** 2026-10-17  
**Revision Version:** 1.3.0 (Final Phase 0.1 Review Corrections)  
**Auditor:** Quantitative Researcher & Systems Architect  
**Status:** RATIFIED & RECONCILED WITH CANONICAL ARCHITECTURE SPECIFICATION  

---

## 1. Executive Summary & Recommended Decision

This document transfers technical and architectural oversight of the researched **Nomad Analyst F&O Options Intelligence & Strategy Lab Pillar** to ChatGPT.

### Canonical Specification Reference:
The full data contracts, feature schemas, strategy interfaces, execution models, and evaluation matrix are authoritatively specified in:  
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

### Executive Recommendation:
**APPROVE PROCEEDING TO PHASE 1 (Isolated Options Data Foundation, Bars & Quote Snapshots) UNDER AN ISOLATED `fno/` APP BOUNDARY GOVERNED BY THE CANONICAL ARCHITECTURE SPECIFICATION.**

### Core Rationale:
1. **Zero-Code Phase 0 Compliance:** All repository audits, empirical regulatory reviews, and architectural blueprints have been completed with **zero application code changes, zero test alterations, zero migration creations, zero configuration modifications, and zero database mutations**.
2. **Four-Pillar Architecture:**
   - **Shared Core Intelligence Engine:** Reusable source of validated, timestamped market features emitted as immutable `OptionFeatureSnapshot` contracts. Completely decoupled from equity pipelines; zero option tick routing to `IntradayStateManager`.
   - **Extensible Instrument Universe:** Generic asset configuration where NIFTY index options buying (ATM $\pm 5$ strikes) is an **initial configuration boundary**, not a hardcoded architecture limitation.
   - **Independent Strategy Modules:** Versioned, configurable, isolated strategies inheriting from `BaseStrategy`, consuming standard feature contracts and emitting standardized `OptionSignal` instances without private data feeds or shared state.
   - **Shared Paper-Trading & Evaluation Framework:** Independent simulated trade ledgers per strategy, conservative taker fill models (`Best Ask + Slippage` / `Best Bid - Slippage`) evaluated against captured quote snapshots, handling unexecutable zero-bid exits without fabrication, verified statutory fee assumptions, and an anti-curve-fitting multi-metric decision matrix across a 1-month prospective parallel paper experiment.
3. **Final Review Corrections Formalized:**
   - **Independent Quote Freshness & Strict Timestamps:** Quote age is measured from the quote packet's exchange timestamp, **independently of last-trade age**. Four distinct metrics are tracked: feed latency, quote age, last-trade age, and pipeline latency. A receipt-time fallback **never certifies that an exchange quote is fresh**; fallback quotes are marked `EXECUTION_INELIGIBLE_UNVERIFIED_TIMESTAMP`. Epoch timestamps are **never subtracted from monotonic values**. Future-skewed ticks ($>2.0\text{s}$) are rejected.
   - **Underlying Volume & VWAP Semantics:** Cash indices (`^NSEI`) have no traded volume; summing constituent volume does NOT produce an index VWAP. Traded volume and VWAP are strictly sourced from active near-month futures (`NIFTY-FUT`) or marked `None` with `vwap_source = "UNAVAILABLE"`.
   - **Phase 1 Quote Snapshot Persistence:** `fno_option_quote_snapshot` is explicitly assigned to Phase 1 with rolling 5-day retention. Realistic fills in Phase 4 are evaluated against captured quote snapshots, not from OHLCV candles alone.
   - **Separation of Market Exits from Expiry Settlement:** Continuous market exits cross the order book bid; official expiry settlement is an administrative cash settlement recorded as `fill_type = "SETTLEMENT"` with zero slippage. Settlement is never recorded as a bid-side fill.
   - **Protocol for Zero-Bid & Pending Settlement:** If an exit triggers but bids are 0.00 or missing during market hours, the system never fabricates a fill (`PENDING_LIQUIDITY`). Post-15:30 IST on expiry day, positions enter `PENDING_EXPIRY_SETTLEMENT` without fabricating prices until official exchange settlement values/fees are verified. Expired contracts are **strictly prevented from entering next-session exit retries**.
   - **Configurable Operational & Risk Policies:** Staging at 13:00 IST and square-off at 15:15 IST are labeled as configurable Nomad policies, not universal exchange rules.
   - **Sample Size Tier Resolution:** Resolves evaluation-gate ambiguities ($N < 20$ rejected, $20 \le N \le 29$ conditional with 2-week extension, $N \ge 30$ adequate).
   - **Pre-Implementation Fee Verification:** Statutory fees are marked as assumptions requiring pre-implementation verification against actual broker contract notes and circular schedules.
   - **Disentangled Acceptance Criteria:** Strictly separates unit-test acceptance criteria from live-market acceptance criteria.

---

## 2. Fact Classification: Verified vs. Inferred vs. Untested

| Category | Finding / Dimension | Status & Evidence |
| :--- | :--- | :--- |
| **Verified** | **NFO Master Snapshot** | Inspected `data/universe/kite_instruments_master.csv`. Confirmed snapshot contained 41,336 NFO instruments and 4,061 active NIFTY options across 18 expiries. This is a snapshot count; the master refreshes daily at ~08:00 IST. |
| **Verified** | **Equity Normalizer OI Loss** | Line-by-line inspection of `market/normalizers/kite.py:L210-L298` confirms `open_interest` is dropped and `exchange="NSE"` is hardcoded. The equity normalizer will remain untouched; an isolated `OptionNormalizer` will be authored. |
| **Verified** | **Equity State Contamination Risk** | `market/services/kite_ticker.py:L128-L132` passes all incoming ticks to `IntradayStateManager.on_tick()`. Pushing option symbols here corrupts equity breadth and sector momentum. |
| **Verified** | **Kite Historical Documentation Limit** | Official Kite Connect v3 documentation states that historical data is provided only for active instruments; derivatives data is limited to active contracts of the current expiry, near month, and far month. |
| **Verified** | **SEBI Empirical Studies (FY22–FY24 vs FY25–FY26)** | Official SEBI research reports: (1) September 2024 study of **1.13 crore unique individual traders** across FY22–FY24 established that **92.8%** incurred cumulative net losses; (2) August 20, 2026 study (*Study: Profitability of Individual Traders in the Equity Derivatives Segment [FY25-FY26]* [_103835.html](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html)) established net-loss rates of **90.9%** in FY25 and **87.7%** in FY26, with transaction costs compounding gross losses and turning profitable traders net negative. |
| **Inferred** | **System Resource Consumption** | Subscribing to 22–44 option tokens on the existing WebSocket connection consumes $<3.5\%$ of Kite's 3,000-instrument limit, inferring minimal CPU/memory overhead. |
| **Untested** | **Live NFO WebSocket Streaming on Nomad** | While equity streaming is operational, streaming live NFO option packets in `MODE_FULL` through a Nomad normalizer has **NOT yet been executed** (pending Phase 1 execution). |
| **Untested** | **Option Strategy Profitability** | Directional option buying strategies (15m ORB, VWAP Reclaim) are unproven hypotheses that have **NOT yet undergone prospective validation**. |

---

## 3. Confirmed Kite Connect Data Capabilities & Limitations

Primary Source: [Zerodha Kite Connect v3 Documentation](https://kite.trade/docs/connect/v3/) (Accessed October 2026).

1. **Active Option Metadata (`GET /instruments`):**  
   Daily CSV provides full instrument token, tradingsymbol, strike, expiry, lot size, and tick size for all active NFO options.
2. **WebSocket Streaming (`KiteTicker.MODE_FULL`):**  
   Provides a 184-byte binary packet structured per official Kite Connect specifications:
   - **Fixed Quote Fields (Bytes 0–64, 64 bytes total):** `instrument_token`, `last_price`, `last_quantity`, `average_price` (exchange session ATP, distinct from Nomad's candle VWAP), `volume_traded`, `buy_quantity`, `sell_quantity`, `open`, `high`, `low`, `close`, `last_trade_time`, `oi`, `oi_day_high`, `oi_day_low`, `exchange_timestamp`.
   - **Market Depth (Bytes 64–184, 120 bytes total):** 10 depth entries (5 Buy bids + 5 Sell asks) of 12 bytes each (`quantity` int32, `price` int32 / 100.0, `orders` int16, 2 bytes padding).
3. **Active Contract Historical API (`GET /historical/{token}/{timeframe}`):**  
   Returns timestamp, OHLC, volume, and OI for **currently trading** contracts. Rate limit: 3 requests/sec.
4. **Expired Contract Historical API:**  
   Official documentation limits historical data availability to active instruments. Historical candles for expired derivative contracts are not available from Kite Connect.

---

## 4. Relevant Existing Codebase Files & Integration Points

- [`market/services/kite_auth.py:L45-L80`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/kite_auth.py#L45-L80): `KiteCredentialService` manages Fernet-encrypted credentials and session tokens. **Shared across equity and F&O**.
- [`market/services/kite_registry.py:L100-L140`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/kite_registry.py#L100-L140): `KiteInstrumentRegistry` loads CSV but discards NFO options. **Phase 1 will build `OptionInstrumentRegistry` in `fno/`**.
- [`market/services/kite_ticker.py:L88-L140`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/kite_ticker.py#L88-L140): `KiteTickerManager` runs threaded WebSocket. **Phase 1 will route NFO tokens to an isolated dispatcher**.
- [`market/normalizers/kite.py:L210-L298`](file:///Users/shivamsingh/personal/nomad-analyst/market/normalizers/kite.py#L210-L298): `KiteNormalizer` drops OI. **Equity normalizer remains untouched; Phase 1 will build `OptionNormalizer` in `fno/`**.
- [`market/models.py:L220-L260`](file:///Users/shivamsingh/personal/nomad-analyst/market/models.py#L220-L260): `OHLCVBar` stores equity bars. **Phase 1 will create `OptionOHLCVBar` and `OptionQuoteSnapshot` in `fno/`**.

---

## 5. Corrected Quantitative Strategy Evidence & Epistemic Status

1. **Non-Equivalence Acknowledged:**  
   Underlying index momentum does NOT prove option-buying profitability. Directional moves are frequently neutralized by theta decay ($\Theta < 0$), volatility crush ($\mathcal{V} \cdot \Delta \sigma$), and crossing the bid-ask spread.
2. **Strategy Classification:**  
   - `FNO-HYP-01` (15m ORB + Volume): Unproven hypothesis to evaluate prospectively.
   - `FNO-HYP-02` (VWAP Reclaim): Unproven hypothesis to evaluate prospectively.
   - `FNO-HYP-03` (Volatility Squeeze): Excluded from scope due to theta burn risks and lack of historical IV baselines.
3. **Execution Reality & Realistic Fills:**  
   Simulated fills cannot be evaluated from OHLCV candles alone. Realistic taker fills execute against captured quote snapshots (`fno_option_quote_snapshot`) at `Best Ask + Slippage` on entry and `Best Bid - Slippage` on continuous market exits. Official expiry settlement is an administrative cash settlement that does not cross the book and is never recorded as a bid-side fill.
4. **Current Statutory & Exchange Charges (Assumptions Requiring Verification):**
   - **NSE Options Transaction Outflow (Effective 1 March 2026):** **₹3,553 per crore of premium traded** (**0.03553%** on premium turnover) under NSE Circular `NSE/FA/73061`, comprising **₹3,552.99** transaction charge + **₹0.01** IPFT contribution.
   - **STT on Option Sale (Effective 1 April 2026):** **0.15% of premium turnover** on the sell side under the Finance Act.
   - **STT on Exercised Options (Effective 1 April 2026):** **0.15% of intrinsic value** on in-the-money expired contracts.
   - **Brokerage:** ₹20 flat per executed order.
   - **Goods & Services Tax (GST):** **18% applied strictly to (Brokerage + Exchange/IPFT Charges + SEBI Fees)**.
   - **SEBI Charges:** ₹10 per crore (0.0001%).
   - **Stamp Duty:** 0.003% on buy-side premium turnover.

---

## 6. Authoritative Seven-Phase Implementation Sequence

```mermaid
graph LR
    P0["Phase 0: Architecture & Contracts (Current)"] --> P1["Phase 1: Isolated Data Foundation & Quotes"]
    P1 --> P2["Phase 2: Core Intelligence Engine"]
    P2 --> P3["Phase 3: Generic Strategy Interface"]
    P3 --> P4["Phase 4: Shared Paper Execution Lab"]
    P4 --> P5["Phase 5: 1-Month Parallel Experiment"]
    P5 --> P6["Phase 6: Evidence Review & Production Gate"]
```

| Phase ID | Phase Name | Execution Status | Core Deliverables & Disentangled Acceptance Standard |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Architecture, Empirical Research & Data-Contract Approval** | **CURRENT (Documentation-Only)** | Codebase audit, SEBI studies citation, 184-byte packet mapping, and canonical specification (`fno_core_engine_and_strategy_lab_spec.md`) ratified. Zero code/db mutations. |
| **Phase 1** | **Isolated Options Data Foundation, Bars & Quote Snapshots** | **PENDING AUTHORIZATION** | Dedicated `fno/` app, `OptionInstrumentRegistry`, stateful desired-universe reconciliation loop (ATM $\pm 5$), `OptionNormalizer` (184 bytes, sparse depth, valid 0 OI, quote classification, independent quote age), `OptionOHLCVBar`, and `OptionQuoteSnapshot` persistence engines. |
| **Phase 2** | **Core Intelligence Engine & Validated Feature Snapshots** | **PLANNED** | Standardized `OptionFeatureSnapshot` emitter with provenance, Black-Scholes Greeks with failure handling, verified underlying futures volume context, and quote freshness monitoring. |
| **Phase 3** | **Generic Strategy Interface & Signal Framework** | **PLANNED** | Abstract `BaseStrategy` lifecycle, dynamic strategy configuration and versioning, and standardized `OptionSignal` generation and validation. Zero concrete strategy rules implemented prior to this phase. |
| **Phase 4** | **Shared Paper Execution Lab & Independent Strategy Evaluation** | **PLANNED** | Taker execution against persisted quote snapshots (`Best Ask + Slippage`, `Best Bid - Slippage`), settlement separation (`SETTLEMENT` fill type), zero-bid exit protocol without fabrication, verified fee engine, and isolated `fno_paper_trade_ledger` tracking. |
| **Phase 5** | **Prospective One-Month Parallel Paper Experiment** | **PLANNED** | Multi-strategy parallel execution over 20–22 trading sessions, daily P&L and friction reconciliation, regime-decomposed performance analysis, and sample size tier resolution ($N < 20$ rejected, $20 \le N \le 29$ conditional, $N \ge 30$ adequate). |
| **Phase 6** | **Evidence-Based Review & Production Gate** | **PLANNED** | Comprehensive evaluation against falsification gates, strategy ranking using multi-metric matrix (not total P&L alone), and operator certification decision regarding live capital or further research. |

---

## 7. Next Immediate Step: Phase 1 Scope & Disentangled Acceptance Criteria

### Scope for Phase 1:
- Dedicated, isolated `fno/` Django application.
- Option instrument registry dynamically parsing daily master CSV with authoritative contract expiry dates and stale file detection.
- Stateful desired-universe reconciliation loop (ATM $\pm 5$ strikes, spot shift rebalancing, 60s periodic reconciliation, and configurable next-weekly staging policy).
- Option tick normalizer unpacking 184-byte `MODE_FULL` packets, defensively handling valid zero OI, unpopulated OI (`None`), sparse depth (120 bytes), locked quotes (`bid == ask`), crossed quotes (`bid > ask`), volume resets, and timestamp integrity (measuring quote age independently of last trade time, rejecting future skew $>2.0$s).
- Dedicated `OptionOHLCVBar` model and 1-minute candle rollup engine with compound unique constraints.
- Dedicated `OptionQuoteSnapshot` model and persistence engine with compound indexing and rolling 5-day retention.
- Reconnection and resubscription reconciliation.
- Dedicated unit-test suite in `fno/tests/`.

### Explicit Exclusions for Phase 1:
- No trading signals or strategy implementation.
- No paper-trading execution or simulated fills.
- No live broker orders.
- No stock options, Bank Nifty, option selling, or multi-leg spreads.

### Disentangled Acceptance Criteria:
- **AC-1-U01** `[Unit-Test Requirement]`: Dynamically resolves active weekly expiry date authoritatively from instrument master CSV and detects stale master files.
- **AC-1-U02** `[Unit-Test Requirement]`: Unpacks `MODE_FULL` packets with valid zero OI handling, sparse depth parsing (120 bytes), locked/crossed quote classification, and anomaly detection.
- **AC-1-U03** `[Unit-Test Requirement]`: Desired-universe reconciliation correctly calculates tokens to subscribe and unsubscribe on spot movements and expiry rolls.
- **AC-1-U04** `[Unit-Test Requirement]`: 1-minute `OptionOHLCVBar` persistence engine is idempotent and prevents duplicate rows under compound unique constraint.
- **AC-1-U05** `[Unit-Test Requirement]`: `OptionQuoteSnapshot` persists depth JSONB and bid/ask, rejects timestamps with future skew $>2.0$s, handles fallback timestamps without marking them fresh, and supports fast indexed queries.
- **AC-1-L01** `[Live Acceptance Test]`: Streaming live NFO option ticks concurrently produces zero errors or state mutations in `IntradayStateManager` and zero rows in `market_ohlcvbar`.
- **AC-1-L02** `[Live Acceptance Test]`: 1-minute `OptionOHLCVBar` records persist with strictly accurate `open_interest` and volume deltas across continuous trading.
- **AC-1-L03** `[Live Acceptance Test]`: Reconnection recovery resubscribes all active tokens in `MODE_FULL` within 5 seconds of WebSocket reconnect during market hours.
- **AC-1-L04** `[Live Acceptance Test]`: `OptionQuoteSnapshot` records persist with valid quote classifications and $\le 3.0$s quote ages during live trading.

---

## 8. Exact Paths to All Relevant Research Documents & Canonical Spec

All documents reside in the repository under `docs/research/fno/`:

1. [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md) — **Canonical Architectural Specification: Core Intelligence Engine, Feature Contracts, Strategy Interface, and Paper Evaluation Lab**.
2. [`docs/research/fno/fno_repository_audit.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_repository_audit.md) — Line-by-line codebase audit and reusability matrix.
3. [`docs/research/fno/fno_research_landscape.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_research_landscape.md) — Academic foundations, August 2026 SEBI studies, NSE Circular 73061, and tax microstructure.
4. [`docs/research/fno/fno_strategy_evidence_register.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_strategy_evidence_register.md) — Falsifiable hypothesis register and null hypotheses.
5. [`docs/research/fno/fno_data_feasibility_and_costs.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_data_feasibility_and_costs.md) — Kite Connect API matrix, 184-byte packet parsing, sparse depth validation, and cost analysis.
6. [`docs/research/fno/fno_target_architecture.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_target_architecture.md) — Decoupled third pillar blueprint, instrument master authority, defensive normalizer, and DDL.
7. [`docs/research/fno/fno_paper_trading_and_validation_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_paper_trading_and_validation_spec.md) — Conservative taker execution models, effective-dated tax engine, and NSE 73061 fees.
8. [`docs/research/fno/fno_phase_roadmap.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase_roadmap.md) — Authoritative 7-phase implementation plan with disentangled criteria.
9. [`docs/research/fno/fno_chatgpt_handoff.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_chatgpt_handoff.md) — This authoritative reconciled handoff document.
10. [`docs/research/fno/fno_phase0_audit_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase0_audit_report.md) — Formal Phase 0 revision audit report and acceptance matrix.
11. [`docs/research/fno/fno_phase0_1_contract_correction_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase0_1_contract_correction_report.md) — Standalone Phase 0.1 Contract Correction report.

---

## 9. Confirmation of Zero Implementation Changes

**Implementation of Phase 1 has NOT started.**  
- Application code changed: **0 lines.**
- Configuration / settings changed: **0 lines.**
- Test files modified: **0 files.**
- Migrations generated or applied: **0 migrations.**
- Dependencies modified: **0 packages.**
- Database records altered: **0 records.**
- Active running daemons modified: **0 processes.**
