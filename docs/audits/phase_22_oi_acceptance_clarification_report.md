# Nomad Analyst — Phase 22 Open Interest (OI) Acceptance Clarification Report

**Document ID:** `PHASE-22-OI-ACCEPTANCE-CLARIFICATION`  
**Date:** 18 October 2026  
**Auditor / Engineering Role:** Antigravity AI Senior Django/QA Engineer  
**Workspace:** `/Users/shivamsingh/personal/nomad-analyst`  
**Target Live Session:** Monday, 19 October 2026 (NSE Trading Hours: 09:15–15:30 IST)

---

## 1. Executive Summary & Verdict

This documentation-only clarification resolves an ambiguity identified in the `AC-1-L02` acceptance rule regarding Open Interest (OI) data quality.

- **Inspection Finding:** Deep inspection of [`fno/models.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/models.py) (`OptionOHLCVBar`), [`fno/services/option_normalizer.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/services/option_normalizer.py), and [`fno/services/option_bar_aggregator.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/services/option_bar_aggregator.py) confirms that the implementation and database schema **already natively support** nullable OI and explicit status differentiation:
  - `open_interest = models.BigIntegerField(null=True, blank=True)`
  - `oi_status = models.CharField(max_length=20, default='VALID')` where status takes values `'VALID'`, `'ZERO_ACTIVITY'`, or `'UNPOPULATED'`.
  - Normalization logic in `OptionNormalizer` explicitly maps `raw_oi < 0` or missing packets to `open_interest = None, oi_status = "UNPOPULATED"`, `raw_oi == 0` to `open_interest = 0, oi_status = "ZERO_ACTIVITY"`, and `raw_oi > 0` to `open_interest = raw_oi, oi_status = "VALID"`.
- **Runbook Ambiguity:** The previous runbook verification script unconditionally asserted `assert bar.open_interest is not None`, creating a risk that unpopulated broker feeds would be rejected or incentivized to fabricate zero.
- **Remediation:** Updated [`docs/audits/phase_22a_monday_runbook.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22a_monday_runbook.md) Verification A script and the Evidence Matrix to verify that genuine `OI = 0` is strictly distinguished from missing/unpopulated OI, and that missing OI is never fabricated as zero.
- **Verdict:** **PASS (Documentation Clarified)**. Zero source code or migration modifications were required or made. Canonical criteria `AC-1-L01` through `AC-1-L05` remain **NOT TESTED** pending Monday live market evidence.

---

## 2. Previous vs. Updated `AC-1-L02` Wording

### In Operational Runbook Step 3.2 (Verification A)

#### Previous Wording
```text
Verify 1-minute bars are rolled up and persisted with complete OHLCV and open interest fields:
assert bar.volume is not None, "Volume is null!"
assert bar.open_interest is not None, "Open interest is null!"
```

#### Updated Wording
```text
Verify 1-minute bars are rolled up and persisted with complete OHLCV, volume, and accurate open interest semantics:
- Volume must be non-null and correctly accumulated across the 60-second window.
- Genuine OI = 0 must be explicitly distinguishable (oi_status="ZERO_ACTIVITY") from unpopulated/missing OI (open_interest=None, oi_status="UNPOPULATED").
- Missing OI must never be fabricated as zero merely to satisfy non-null checks.
- Any unpopulated OI bars must be logged with contracts, timestamps, and frequency for root-cause observation.

Invariant Checks:
- If oi_status == "UNPOPULATED": assert open_interest is None
- If oi_status == "ZERO_ACTIVITY": assert open_interest == 0
- If oi_status == "VALID": assert open_interest > 0
```

### In Evidence Matrix Table (`AC-1-L02`)

#### Previous Requirement & Expected Result
- **Requirement:** `Continuous Option-Bar Persistence`
- **Expected Result:** `Continuous 1m bars for all 22 active contracts; complete OHLCV and non-null volume/OI fields.`

#### Updated Requirement & Expected Result
- **Requirement:** `Continuous Option-Bar Persistence (including accurate Volume & OI handling)`
- **Expected Result:** `Continuous 1m bars for all 22 active contracts; complete OHLCV and non-null volume; open interest accurately populated; genuine OI = 0 distinguished (oi_status='ZERO_ACTIVITY') from unpopulated/missing OI (oi=null, oi_status='UNPOPULATED'); missing OI is never fabricated as zero and is reported with timestamps/contracts.`

---

## 3. Rationale for Distinguishing Zero OI from Missing OI

In options trading systems, conflating missing telemetry with zero market activity corrupts quantitative analysis and risk metrics:

1. **Analytical Risk (False Liquidity Signals):**
   - A genuine `OI = 0` indicates a newly listed contract or deep OTM/ITM strike where zero market participants hold overnight positions.
   - An unpopulated `OI = null` indicates that the broker tick packet omitted the 4-byte OI segment (or was transmitted during a feed mode transition or market pre-open state before the exchange disseminates cumulative contract positions).
   - If missing OI is fabricated as zero, quantitative algorithms (e.g. Max Pain, Put-Call Ratio, strike concentration, OI change analysis) interpret network transport omissions as sudden liquidations, triggering erroneous regime classifications.
2. **Acceptance Integrity:**
   - Forcing a rigid `open_interest is not None` assertion creates an unhealthy incentive for engineers or data ingestion daemons to replace nulls with `0` just to pass tests, hiding telemetry packet delivery defects.
3. **Auditability:**
   - Maintaining explicit `oi_status="UNPOPULATED"` allows operators to track broker packet quality, measure packet loss frequency, and inspect whether specific strikes suffer from feed degradation.

---

## 4. Observed Model & Schema Implementation Behavior

Inspection of the Nomad Analyst codebase revealed that the underlying architecture was built with this separation in mind:

### 1. Model Definition ([`fno/models.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/models.py#L22-L28))
```python
volume = models.BigIntegerField(default=0, help_text="Volume traded within this bar interval")
open_interest = models.BigIntegerField(null=True, blank=True, help_text="Reported OI at bar close (null if unpopulated)")
oi_status = models.CharField(
    max_length=20, 
    default='VALID', 
    help_text="VALID, ZERO_ACTIVITY (oi=0), or UNPOPULATED (oi=null)"
)
is_partial_bar = models.BooleanField(
    default=False, 
    help_text="True if bar interval overlapped a network disconnection gap"
)
```
- The database schema is fully nullable for `open_interest` (`null=True`).
- `oi_status` is an indexed, explicit enumeration capturing the exact semantic state.

### 2. Normalizer Decoding ([`fno/services/option_normalizer.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/services/option_normalizer.py#L147-L163))
```python
# Open Interest Semantics (Keep None distinct from 0)
if oi_unpopulated_override or raw_oi < 0:
    open_interest = None
    oi_day_high = None
    oi_day_low = None
    oi_status = "UNPOPULATED"
elif raw_oi == 0:
    open_interest = 0
    oi_day_high = raw_oi_high if raw_oi_high >= 0 else 0
    oi_day_low = raw_oi_low if raw_oi_low >= 0 else 0
    oi_status = "ZERO_ACTIVITY"
else:
    open_interest = raw_oi
    oi_day_high = raw_oi_high
    oi_day_low = raw_oi_low
    oi_status = "VALID"
```
The normalizer explicitly forbids promoting `None` to `0`.

### 3. Bar Aggregation ([`fno/services/option_bar_aggregator.py`](file:///Users/shivamsingh/personal/nomad-analyst/fno/services/option_bar_aggregator.py#L102-L106))
```python
# OI updates
if tick.open_interest is not None:
    active.open_interest = tick.open_interest
    active.oi_status = tick.oi_status
```
Completed bars persist `b.open_interest` and `b.oi_status` directly into the database.

**Conclusion:** There is **zero mismatch** between the intended rule and the codebase implementation. The defect was exclusively present in the documentation and runbook test assertions.

---

## 5. Exact Files Changed

Only documentation files were updated:

1. [`docs/audits/phase_22a_monday_runbook.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22a_monday_runbook.md):
   - Clarified Verification A procedure, updating script assertions to validate `oi_status` and enforce semantic consistency.
   - Updated Evidence Matrix `AC-1-L02` row to state explicit OI distinction and reporting requirements.
2. [`docs/audits/phase_22_final_safety_verification_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22_final_safety_verification_report.md):
   - Aligned Section 8 `AC-1-L02` table description.
3. [`docs/audits/phase_22_final_safety_corrections_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22_final_safety_corrections_report.md):
   - Synchronized Section 6 `AC-1-L02` summary table.
4. [`docs/audits/phase_22_final_safety_corrections_chatgpt_handoff.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22_final_safety_corrections_chatgpt_handoff.md):
   - Added OI acceptance clarification note and updated `AC-1-L02` description.
5. [`docs/audits/phase_22_oi_acceptance_clarification_report.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/audits/phase_22_oi_acceptance_clarification_report.md):
   - This authoritative clarification report.

---

## 6. Confirmation of Zero Code and Migration Changes

- **Python Source Files Changed:** **0**
- **Django Migration Files Created or Modified:** **0**
- **Unit/Regression Test Files Changed:** **0**
- **Configuration or Settings Changed:** **0**

All existing working-tree changes across `market/` and `config/settings.py` were strictly preserved.

---

## 7. Remaining Data-Quality Risks

1. **Pre-Open Broker OI Dissemination:** Between 09:00 and 09:15 IST, NSE index options do not trade; broker WebSocket feeds may transmit `raw_oi = 0` or omit the depth/OI payload until market open at 09:15 IST. Operators must observe the transition from pre-open unpopulated state to live open interest at 09:15 IST.
2. **Far OTM Strike Inactivity:** Newly dynamically subscribed strikes far from ATM may trade zero contracts for extended intervals. The aggregator must correctly maintain `volume = 0` with `oi_status="ZERO_ACTIVITY"` if OI is reported as 0, or `oi_status="VALID"` if static OI exists without volume.

---

## 8. Status of Canonical Live Criteria

All live-market criteria remain strictly **NOT TESTED**:

| Canonical ID | Canonical Requirement | Status |
|---|---|---|
| **`AC-1-L01`** | Equity Isolation: 0 NFO tokens in `market_ohlcvbar` or `IntradayStateManager` | **NOT TESTED** |
| **`AC-1-L02`** | Continuous Option-Bar Persistence (including Volume & OI distinction) | **NOT TESTED** |
| **`AC-1-L03`** | Reconnect / Resubscription Recovery within $\le 5.0\text{s}$ target | **NOT TESTED** |
| **`AC-1-L04`** | Live Quote Snapshots with valid classifications and quote age $\le 3.0\text{s}$ | **NOT TESTED** |
| **`AC-1-L05`** | Dynamic ATM Detection & Universe Reconciliation (22 active contracts) | **NOT TESTED** |
| **`OP-CHECK-PAPER-EXEC`** | Strategy Evaluation & Paper Ledger Execution | **NOT TESTED** |
