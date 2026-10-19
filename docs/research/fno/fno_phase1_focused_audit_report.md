# Nomad Analyst — Phase 1 Focused Implementation Audit Report

**Document Reference:** `docs/research/fno/fno_phase1_focused_audit_report.md`  
**Audit Date:** 2026-10-17  
**Auditor:** Quantitative Systems Architect  
**Scope:** Phase 1 Isolated F&O Data Foundation vs. Canonical Specification & Phase Roadmap  
**Verdict:** **REQUIRE TARGETED FIXES BEFORE LIVE ACCEPTANCE / PHASE 2**  

---

## 1. Executive Summary & Audit Recommendation

A comprehensive, line-by-line audit of the newly implemented F&O data foundation was conducted against:
1. The **Canonical Specification** ([`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)),
2. The **Phase 1 Roadmap** ([`docs/research/fno/fno_phase_roadmap.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase_roadmap.md)), and
3. The **Phase 1 Acceptance Report** ([`docs/research/fno/fno_phase_1_data_foundation_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_phase_1_data_foundation_report.md)).

### Core Audit Findings
- **Data Foundation Strengths:** All core unit-level services (`OptionInstrumentRegistry`, `OptionNormalizer`, `DesiredUniverseManager`, `OptionBarAggregator`, `OptionQuoteManager`) have been implemented with clean object-oriented architecture and pass 25 out of 25 unit tests. PostgreSQL migrations are applied, and existing equity test suites remain 100% green.
- **Critical Architectural Gaps & Defects Identified:**
  1. **Spot Threshold Blind Spot:** `DesiredUniverseManager.should_rebalance()` uses a raw spot drift threshold (`abs(spot - last_spot) >= 50.0`). Mathematical testing confirms this **can completely miss an ATM strike change** when spot moves across a strike boundary (e.g. 24,524.00 $\rightarrow$ 24,526.00 changes ATM from 24,500 to 24,550, but drift is only 2.0 pts, suppressing rebalancing).
  2. **Missing Live Ingestion Pipeline Glue:** While individual F&O services exist and are unit-tested, there is currently **no runtime router or pipeline glue** connecting live Kite WebSocket ticks to `OptionNormalizer`, `OptionQuoteManager`, and `OptionBarAggregator`. The existing `KiteTickerManager` and `run_intraday_ticker.py` only route to equity normalizers and equity state managers.
  3. **Acceptance Criteria Label Drift (AC-1-L04):** The Phase 1 acceptance report shifted criteria definitions, reassigning AC-1-L04 to "dynamic rebalancing" and omitting the canonical requirement for live `OptionQuoteSnapshot` persistence.
  4. **Unscheduled Retention Purge:** `OptionQuoteManager.purge_expired_quotes()` is a callable utility method tested in unit tests, but is not scheduled in Celery Beat or cron.
  5. **Zero-Bid vs. Empty-Book Classification:** When all bid levels in the 120-byte depth have zero price/quantity, `OptionNormalizer` classifies the quote as `EMPTY_BOOK` rather than `ZERO_BID` because zero-price entries are omitted prior to evaluation.

### Recommendation
**Require Targeted Fixes Before Live Acceptance / Phase 2.**  
Do not begin Phase 2. The four targeted defects must be resolved and unit-tested first, followed by live-market verification during Monday's continuous trading session.

---

## 2. Acceptance-Criteria Reconciliation

### 2.1 Side-by-Side Comparison Matrix

| Criteria ID | Canonical Specification (`spec.md:L643-L651`) | Phase 1 Roadmap (`roadmap.md:L72-L81`) | Phase 1 Report (`report.md:L133-L155`) | Audit Analysis & Discrepancies |
| :--- | :--- | :--- | :--- | :--- |
| **AC-1-U01** | `OptionInstrumentRegistry` parses daily CSV, treats master `expiry` date as authoritative, and detects stale master files. | Identical to Canonical Spec. | Evaluated via `test_option_registry.py`. Parsed 40,683 real NFO options. | **ALIGNED (PASS).** Unit tests verify parsing, expiry authority, and stale error. |
| **AC-1-U02** | `OptionNormalizer` unpacks 184-byte packets with valid zero OI, unpopulated OI (`None`), sparse depth (120 bytes), and locked/crossed quote classification. | Identical to Canonical Spec. | Evaluated via `test_option_normalizer.py`. Fixed fields, depth, valid 0 OI, quote classification. | **ALIGNED (PASS).** Unit tests verify 184-byte parsing, OI semantics, locked/crossed quotes. |
| **AC-1-U03** | Desired-universe reconciliation correctly calculates $\mathcal{U}_{\text{desired}} \setminus \mathcal{U}_{\text{active}}$ and $\mathcal{U}_{\text{active}} \setminus \mathcal{U}_{\text{desired}}$ on spot changes and expiry rolls. | Identical to Canonical Spec. | Evaluated via `test_desired_universe.py`. Spot shift $\ge 50$ pts diffs; 13:00 IST expiry staging. | **ALIGNED WITH DEFECT.** Unit tests pass under 50-pt drift, but logic misses boundary ATM shifts. |
| **AC-1-U04** | 1-minute `OptionOHLCVBar` persistence engine is idempotent and prevents duplicate rows under compound unique constraint. | Identical to Canonical Spec. | Evaluated via `test_option_bar_persistence.py`. Zero duplicates under unique constraint. | **ALIGNED (PASS).** Idempotent `bulk_create` verified on `unique_fno_ohlcv_token_tf_ts`. |
| **AC-1-U05** | `OptionQuoteSnapshot` persists depth JSONB and bid/ask, rejects timestamps with future skew $>2.0$s, handles fallback timestamps without marking them fresh, and supports fast indexed queries. | Identical to Canonical Spec. | Evaluated via `test_option_quote_snapshots.py`. Depth JSONB, fallback ineligible, 5-day purge. | **ALIGNED (PASS).** Point-in-time retrieval and timestamp eligibility gates verified. |
| **AC-1-L01** | Streaming live NFO option ticks concurrently produces zero errors or state mutations in `IntradayStateManager` and zero rows in `market_ohlcvbar`. | Identical to Canonical Spec. | Renamed to: *"Live WebSocket NFO streaming"*. Status: BLOCKED (Weekend). | **DISCREPANCY.** Report relabeled canonical equity-isolation criterion to generic streaming. |
| **AC-1-L02** | 1-minute `OptionOHLCVBar` records persist with strictly accurate `open_interest` and volume deltas across continuous trading. | Identical to Canonical Spec. | Renamed to: *"Real-time depth & OI ingestion"*. Status: BLOCKED (Weekend). | **DISCREPANCY.** Report relabeled continuous bar persistence to depth/OI ingestion. |
| **AC-1-L03** | Reconnection recovery resubscribes all active tokens in `MODE_FULL` within 5 seconds of WebSocket reconnect during market hours. | Identical to Canonical Spec. | Renamed to: *"Live 1-minute candle rollover verification"*. Status: BLOCKED (Weekend). | **DISCREPANCY.** Report replaced reconnection recovery resubscription with candle rollover. |
| **AC-1-L04** | `OptionQuoteSnapshot` records persist with valid quote classifications and $\le 3.0$s quote ages during live trading. | Identical to Canonical Spec. | Renamed to: *"Dynamic rebalancing under live spot movement"*. Status: BLOCKED (Weekend). | **MAJOR DISCREPANCY.** Earlier documentation assigned AC-1-L04 to live quote persistence; report assigned it to dynamic rebalancing. |

### 2.2 Resolution of the AC-1-L04 Discrepancy & Authoritative Mapping

The discrepancy occurred because the author of the Phase 1 acceptance report combined criteria from different drafts:
1. Canonical **AC-1-L04** specifically requires live verification of `OptionQuoteSnapshot` persistence with authentic bid/ask quotes and $\le 3.0$s quote ages.
2. The dynamic rebalancing requirement (verifying that moving spot shifts active option subscriptions during live trading) is a live verification of **AC-1-U03**.

To ensure **zero requirements are silently dropped**, the following **Authoritative Criterion Mapping** is established across all documentation:

```
=== AUTHORITATIVE F&O PHASE 1 CRITERIA MAPPING ===

Unit-Test Criteria:
  AC-1-U01: OptionInstrumentRegistry daily CSV parsing, expiry authority & staleness detection.
  AC-1-U02: OptionNormalizer 184-byte unpacking, valid 0 vs. None OI, sparse depth, locked/crossed quotes.
  AC-1-U03: DesiredUniverseManager reconciliation based on ATM strike change & token set diffs.
  AC-1-U04: OptionOHLCVBar 1-minute aggregation & idempotent compound unique constraint persistence.
  AC-1-U05: OptionQuoteSnapshot persistence, future skew rejection, point-in-time indexed queries.

Live-Market Criteria (Evaluated during Monday open market):
  AC-1-L01: Strict Equity Isolation — zero errors or state mutations in IntradayStateManager and zero rows in market_ohlcvbar.
  AC-1-L02: Continuous Bar Persistence — 1-minute OptionOHLCVBar records persist with accurate OI and volume deltas.
  AC-1-L03: Reconnection Recovery — resubscription of all active option tokens in MODE_FULL within 5s of reconnect.
  AC-1-L04: Live Quote Snapshots — OptionQuoteSnapshot records persist with valid classifications and quote age <= 3.0s.
  AC-1-L05: Live Dynamic Rebalancing — ATM shifts during live trading correctly trigger subscriptions of new strikes and unsubscriptions of distant strikes without dropped ticks.
```

---

## 3. Live-Feed Integration and Subscription Reconciliation

### 3.1 Trace of Runtime Path

An exhaustive inspection of the codebase was conducted to trace how WebSocket packets flow from Zerodha Kite to application models:

```
[Zerodha WebSocket: wss://ws.kite.trade]
                    │
                    ▼
         KiteTickerManager._on_ticks(ws, ticks)
         (in market/services/kite_ticker.py:L96-140)
                    │
                    ├──► KiteNormalizer.normalize_tick(raw_tick)  [EQUITY ONLY]
                    │    (Drops open_interest, hardcodes exchange="NSE")
                    │
                    ├──► cache.set(f"live_tick:{symbol}", ...)   [EQUITY ONLY]
                    │
                    ├──► self.update_market_snapshot(norm_tick)  [market_marketsnapshot]
                    │
                    └──► IntradayStateManager().on_tick(norm_tick) [EQUITY ONLY]
                         (Rolls up equity 1m bars into market_ohlcvbar)
```

**Key Finding:**  
`fno.services.option_normalizer.OptionNormalizer`, `fno.services.option_bar_aggregator.OptionBarAggregator`, `fno.services.option_quote_manager.OptionQuoteManager`, and `fno.services.desired_universe.DesiredUniverseManager` are **completely unreferenced** in `KiteTickerManager` and `run_intraday_ticker.py`.

There is currently **no runtime dispatcher or router** distinguishing NFO tokens from NSE equity tokens. If NFO option tokens were passed to `KiteTickerManager` today:
- `KiteNormalizer` would throw unmapped token errors or treat them as NSE equities,
- `open_interest` would be completely discarded,
- `IntradayStateManager` would attempt to process option contracts as equity symbols,
- Option ticks would either crash the worker or contaminate `market_ohlcvbar`.

### 3.2 Proof of ATM Strike Change Blind Spot in `DesiredUniverseManager`

In `fno/services/desired_universe.py:L163-L175`, the logic gating universe reconciliation was implemented as follows:

```python
def should_rebalance(self, spot_price: Decimal, as_of_datetime: Optional[datetime] = None) -> bool:
    if self._last_rebalance_spot is None:
        return True

    spot_drift = abs(spot_price - self._last_rebalance_spot)
    if spot_drift >= self.config.rebalance_threshold_pts:
        return True
    ...
    return False
```

#### Mathematical Proof of Failure:
- Let `strike_step = 50.0`.
- Let `rebalance_threshold_pts = 50.0`.
- Suppose at `T0`, spot price is `24,524.00`.
  $$\text{ATM}_0 = \text{round}(24,524.00 / 50.0) \times 50.0 = 490 \times 50.0 = \mathbf{24,500.00}$$
  The universe is initialized with ATM = 24,500 (strikes 24,250 to 24,750). `_last_rebalance_spot = 24,524.00`.
- At `T1`, spot price shifts by just **2.0 points** to `24,526.00`.
  $$\text{ATM}_1 = \text{round}(24,526.00 / 50.0) \times 50.0 = 491 \times 50.0 = \mathbf{24,550.00}$$
- **The true ATM strike has changed from 24,500 to 24,550!**
- However, evaluating `should_rebalance`:
  $$\text{spot\_drift} = |24,526.00 - 24,524.00| = \mathbf{2.00} < 50.0$$
  `should_rebalance()` returns **`False`**!
- `reconcile(spot_price=24526.00)` returns `(set(), set())`!

#### Runtime Test Verification:
A focused Python diagnostic was executed on the live codebase:
```python
# Initial: spot=24524.00, ATM=24500.0, active_tokens_count=22
# Step 2:  spot=24526.00, ATM=24550.0
#   Did ATM strike change? True (from 24500.0 to 24550.0)
#   Did should_rebalance(s2) detect it? False
#   Tokens to subscribe: 0, to unsubscribe: 0
```
**Conclusion:** Rebalancing **must not be gated solely on raw spot drift**. It must explicitly check whether `calculate_atm_strike(spot_price) != self._last_atm_strike`, or directly compare $\mathcal{U}_{\text{desired}} \neq \mathcal{U}_{\text{active}}$.

### 3.3 Reconnection, Periodic Heartbeat, and Expiry Rolls

1. **ATM Changes:** As proven above, currently missed near strike boundaries due to the 50-pt drift gate.
2. **Periodic Heartbeat:** No periodic background task or daemon loop currently invokes `DesiredUniverseManager.reconcile()`.
3. **Expiry Changes:** The 13:00 IST expiry staging policy is implemented in `DesiredUniverseManager.get_desired_contracts()`, but only triggers if `reconcile()` is called after 13:00 IST.
4. **Reconnect:** `KiteTickerManager._on_connect()` resubscribes the static `self.subscribed_tokens` list provided at startup; it does not query `DesiredUniverseManager` to refresh the token set upon reconnect.

---

## 4. Quote Storage, Integrity, and Retention

### 4.1 Implementation Status

| Feature | Implemented? | Tested? | File & Method |
| :--- | :---: | :---: | :--- |
| Depth JSONB Persistence | Yes | Yes | `fno/models.py:OptionQuoteSnapshot`, `fno/services/option_quote_manager.py:record_quote_snapshot` |
| Point-in-time Indexed Retrieval | Yes | Yes | `OptionQuoteManager.get_quote_at_timestamp(token, ts, lookback)` |
| Latest Quote Retrieval | Yes | Yes | `OptionQuoteManager.get_latest_quote(token)` |
| 5-Day Retention Purge | Yes | Yes | `OptionQuoteManager.purge_expired_quotes(days=5)` |
| Scheduled Cleanup Task | **No** | **No** | **Callable service only.** No entry in `market/tasks.py` or Celery Beat scheduler. |

### 4.2 Quote Semantics and Validation Review

1. **Timestamp Validity & Quote-Age Calculation:**
   - Evaluated strictly from `exchange_timestamp_utc`:
     $$\text{quote\_age\_seconds} = \max\left(0.0, \text{received\_wall\_clock\_utc} - \text{exchange\_timestamp\_utc}\right)$$
   - Last-trade age is computed independently from `last_trade_timestamp_utc`.
   - Timestamps with future skew $> +2.0$s are tagged `FUTURE_SKEW_REJECTED` and flagged `is_execution_eligible = False`.
   - Missing timestamps ($\le 0$) fall back to arrival time for queuing, tagged `FALLBACK_TO_RECEIVED`, and flagged `is_execution_eligible = False`. **Receipt time is never treated as proof of freshness.**
2. **Locked & Crossed Quotes:**
   - `best_bid == best_ask > 0`: Flagged `is_locked = True`, `quote_status = "LOCKED"`, `is_execution_eligible = False`.
   - `best_bid > best_ask > 0`: Flagged `is_crossed = True`, `quote_status = "CROSSED"`, `is_execution_eligible = False`.
3. **Zero-Bid vs. Empty-Book Nuance:**
   - In `fno/services/option_normalizer.py:L225`:
     ```python
     if qty > 0 and raw_p > 0:
         bids.append(...)
     ```
   - When an out-of-the-money option has zero buyers (raw bids have price=0), nothing is appended to `bids`.
   - Consequently, `best_bid` evaluates to `None`.
   - At line 271, `elif best_bid is None or best_ask is None:` classifies the quote as `EMPTY_BOOK`.
   - Line 258 (`elif best_bid is not None and best_bid == Decimal("0.0"): quote_status = "ZERO_BID"`) is therefore unreachable for empty bid books.
   - **Impact:** While both `EMPTY_BOOK` and `ZERO_BID` correctly result in `is_execution_eligible = False`, any downstream module or audit specifically looking for `quote_status == "ZERO_BID"` on illiquid options will find `EMPTY_BOOK`.

---

## 5. Evidence and Deliverables

### 5.1 Working Tree & Git Status

Inspection of `git status -s` confirms all pre-existing changes were preserved without destructive commands:
- **Modified existing files:** Exactly 1 file modified in Nomad Analyst configuration:
  - `config/settings.py` (added `'fno'` to `INSTALLED_APPS`).
- **Untracked new directory:** All new F&O code is strictly contained within `fno/`:
  - `fno/apps.py`, `fno/models.py`, `fno/migrations/0001_initial.py`
  - `fno/services/option_registry.py`
  - `fno/services/option_normalizer.py`
  - `fno/services/desired_universe.py`
  - `fno/services/option_bar_aggregator.py`
  - `fno/services/option_quote_manager.py`
  - `fno/tests/...` (5 test modules)
- Zero git stashes, commits, resets, or cleans were executed.

### 5.2 Unit Test Evidence

Execution command:
```bash
./venv/bin/python manage.py test fno.tests -v 2
```
Results:
- `test_contract_lookup_by_strike_and_type` (AC-1-U01): **PASS**
- `test_master_expiry_date_is_authoritative` (AC-1-U01): **PASS**
- `test_parse_csv_filters_strictly_for_nfo_options` (AC-1-U01): **PASS**
- `test_stale_master_file_detection` (AC-1-U01): **PASS**
- `test_unpack_valid_mode_full_packet` (AC-1-U02): **PASS**
- `test_valid_zero_open_interest_semantics` (AC-1-U02): **PASS**
- `test_unpopulated_open_interest_semantics` (AC-1-U02): **PASS**
- `test_sparse_depth_handling` (AC-1-U02): **PASS**
- `test_locked_quote_classification` (AC-1-U02): **PASS**
- `test_crossed_quote_classification` (AC-1-U02): **PASS**
- `test_future_skew_rejection` (AC-1-U02): **PASS**
- `test_fallback_timestamp_never_certifies_freshness` (AC-1-U02): **PASS**
- `test_session_volume_reset_detection` (AC-1-U02): **PASS**
- `test_calculate_atm_strike` (AC-1-U03): **PASS**
- `test_calculate_desired_universe_at_initial_spot` (AC-1-U03): **PASS**
- `test_rebalance_suppression_on_small_spot_drift` (AC-1-U03): **PASS**
- `test_rebalance_trigger_on_significant_spot_movement` (AC-1-U03): **PASS**
- `test_next_weekly_staging_policy_on_expiry_day` (AC-1-U03): **PASS**
- `test_single_minute_aggregation_and_flush` (AC-1-U04): **PASS**
- `test_idempotence_and_zero_duplicate_rows` (AC-1-U04): **PASS**
- `test_record_and_retrieve_valid_quote_snapshot` (AC-1-U05): **PASS**
- `test_fallback_timestamp_is_ineligible_for_execution` (AC-1-U05): **PASS**
- `test_future_skew_rejected_is_ineligible_for_execution` (AC-1-U05): **PASS**
- `test_point_in_time_quote_retrieval` (AC-1-U05): **PASS**
- `test_purge_expired_quotes_retention_policy` (AC-1-U05): **PASS**

**Summary:** 25 tests run, 25 passed (100% success), 0 failures, 0 errors.

---

## 6. Confirmed Defects vs. Live-Session Risks

### Confirmed Defects (Require Targeted Code Fixes)
1. **Defect 1 — ATM Strike Boundary Blind Spot in `DesiredUniverseManager`:**
   - *Location:* `fno/services/desired_universe.py:L163-L175`
   - *Issue:* Gating rebalance solely on `abs(spot - last_spot) >= threshold_pts` suppresses rebalancing when spot crosses a strike midpoint with $<50$ pt movement.
   - *Required Fix:* Trigger rebalancing whenever `calculate_atm_strike(spot_price) != self._last_atm_strike` or whenever $\mathcal{U}_{\text{desired}} \neq \mathcal{U}_{\text{active}}$.
2. **Defect 2 — Zero-Bid vs. Empty-Book Depth Classification:**
   - *Location:* `fno/services/option_normalizer.py:L225, L258, L271`
   - *Issue:* When buy orders have zero price, they are filtered out, causing `best_bid = None`. This classifies a zero-bid contract as `EMPTY_BOOK` rather than `ZERO_BID`.
   - *Required Fix:* If `best_ask is not None` and (`best_bid is None` or `best_bid == Decimal("0.0")`), classify as `ZERO_BID`.
3. **Defect 3 — Missing Runtime Ingestion Dispatcher:**
   - *Location:* `market/services/kite_ticker.py` & `fno/services/`
   - *Issue:* No mechanism currently dispatches incoming WebSocket ticks by segment/token between `KiteNormalizer` (equity) and `OptionNormalizer` (derivatives).
   - *Required Fix:* Implement an isolated `FnoTickerConsumer` or token router ensuring NFO option ticks route strictly to `OptionNormalizer`, `OptionQuoteManager`, and `OptionBarAggregator`.
4. **Defect 4 — Retention Purge Task Scheduling:**
   - *Location:* `fno/services/option_quote_manager.py`
   - *Issue:* `purge_expired_quotes()` is only a callable method without a scheduled Celery Beat task.
   - *Required Fix:* Register a Celery task (e.g. `purge_fno_quote_snapshots`) in Celery Beat scheduled post-market daily.

### Live-Session Risks (Require Open-Market Session to Verify)
1. **Risk 1 — WebSocket Throughput Under 22 Active Contracts:**
   - Concurrently streaming 22 option contracts in `MODE_FULL` (184 bytes per packet) plus 54 equity tokens produces ~100–300 ticks/sec during active market hours. Reconnection latency, buffer sizing, and database write throughput must be verified under real load.
2. **Risk 2 — Real-Time Reconnection Timing (AC-1-L03):**
   - The requirement to resubscribe all active tokens within 5 seconds of reconnect requires verification against the live Zerodha WebSocket endpoint.
3. **Risk 3 — Broker Quote Age Distribution (AC-1-L04):**
   - Confirm that Kite exchange timestamps on live NFO options remain within $\le 3.0$s under live trading conditions.

---

## 7. Action Plan & Next Steps

1. **Awaiting User Review:** In accordance with the prompt ("*This task is an audit first. Make no application-code changes until the findings are documented. Stop and await review*"), no code modifications have been made.
2. **Recommended Targeted Remediation (Upon Approval):**
   - **Fix 1:** Update `DesiredUniverseManager.should_rebalance()` to track `_last_atm_strike` and trigger rebalance whenever the ATM strike changes or token sets differ.
   - **Fix 2:** Update `OptionNormalizer` to classify `best_ask is not None and best_bid is None` as `ZERO_BID`.
   - **Fix 3:** Implement an isolated NFO ticker consumer/router to wire live WebSocket ticks to `OptionNormalizer` without touching equity logic.
   - **Fix 4:** Register a post-market Celery cleanup task for quote snapshots.
3. **Live Acceptance Execution:**
   - Execute live criteria **AC-1-L01** through **AC-1-L05** during Monday morning's open market session (2026-10-19 09:15 IST).
