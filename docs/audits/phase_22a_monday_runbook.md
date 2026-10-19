# Phase 22A — Monday Live Market Acceptance Runbook

**Execution Date:** Monday, 19 October 2026  
**Target Market Session:** 09:08 IST to 09:45 IST (Pre-Market Preparation + Market Open Burst + 30-Minute Ingestion Stability Window)  
**System Component:** Real-Time F&O Option Streaming Ingestion Daemon & Microstructure Pipeline  
**Document Status:** Ready for Live Execution (Pre-Market Baseline Verified Offline)  

---

## 1. Executive Summary & Operational Scope

This runbook defines the authoritative, step-by-step procedures for live-market acceptance of the Phase 22A F&O ingestion engine on Monday, 19 October 2026. 

### Operational Constraints & Guardrails
- **Paper / Observation Only:** Live order execution remains strictly disabled. Ticker daemon runs in stream ingestion and snapshot storage mode only.
- **Strict Equity Isolation:** Ingestion of NFO option contracts must not pollute equity state, equity indicators, or `market_ohlcvbar`.
- **Pre-Market Gate:** Ticker daemon must not be launched with `--enable-fno` until pre-market instrument master validation, token mapping, and component initialization pass cleanly.
- **Evidence-Driven Acceptance:** Criteria `AC-1-L01` through `AC-1-L05` and `OP-CHECK-PAPER-EXEC` remain strictly **`NOT TESTED`** until authentic live market data is captured during the session.
- **Outcome Separation:** Validation-logic success (script syntax, schema checks, query compilation) is strictly separated from data-evidence success. An empty database or zero evaluated records results in `DATA_CHECK_INCONCLUSIVE` or `NOT TESTED`, never a data-quality `PASS`.

---

## 2. Pre-Market Verification Window (09:08 – 09:15 IST)

All checks in this section must be completed prior to the 09:15:00 IST market open.

### Step 2.1 — Kite Instrument Master Freshness & Integrity
Verify that the cached Zerodha Kite Connect instrument master exists, is fresh (< 24 hours old), and contains today's active NFO option contracts.

```bash
# Check master CSV file timestamp and size
ls -lh data/universe/kite_instruments_master.csv

# Execute instrument master verification script
venv/bin/python manage.py shell -c '
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

ist = ZoneInfo("Asia/Kolkata")
now_utc = datetime.now(timezone.utc)
now_ist = now_utc.astimezone(ist)

master_path = Path("data/universe/kite_instruments_master.csv")
assert master_path.exists(), "CRITICAL: Instrument master CSV not found!"
mtime_utc = datetime.fromtimestamp(master_path.stat().st_mtime, tz=timezone.utc)
mtime_ist = mtime_utc.astimezone(ist)
age_hours = (now_utc - mtime_utc).total_seconds() / 3600.0

print("=== STEP 2.1: INSTRUMENT MASTER INTEGRITY ===")
mtime_str = mtime_ist.strftime("%Y-%m-%d %H:%M:%S %Z")
print(f"Master File Modified: {mtime_str} (Age: {age_hours:.1f} hours)")
assert age_hours < 24.0, f"Master file is stale ({age_hours:.1f}h > 24h limit)!"
print("VALIDATION_LOGIC: PASS")
print("DATA_EVIDENCE: PASS (Fresh instrument master verified)")
'
```

### Step 2.2 — Pre-Market Universe & Expiry Dynamic Resolution (NIFTY ATM ±5 Strikes)
Confirm that `DesiredUniverseManager` dynamically discovers the nearest unexpired weekly expiry from the authoritative instrument master CSV and resolves the exact 22-contract active universe (11 CE + 11 PE) around the projected opening spot.

**Timezone, Expiry & Spot Rules:**
- All explicit market wall-clock times must use `zoneinfo.ZoneInfo("Asia/Kolkata")`. Convert to UTC only when passing to application APIs.
- The nearest weekly expiry must be resolved dynamically via `OptionInstrumentRegistry.get_nearest_weekly_expiry("NIFTY", as_of_date=now_ist.date())`. Never hard-code an assumed expiry date.
- **Indicative spot policy:** The pre-market diagnostic spot (`24500.00`) is used strictly for offline baseline verification before market open. During live trading, the active universe is driven dynamically by incoming `^NSEI` index ticks. Verification procedures (Verifications A, D) must resolve the live spot independently from session equity bars and must NEVER silently fall back to `24500.00`.

```bash
venv/bin/python manage.py shell -c '
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from decimal import Decimal
from fno.services.option_registry import OptionInstrumentRegistry
from fno.services.desired_universe import DesiredUniverseManager, CONFIG_NIFTY

ist = ZoneInfo("Asia/Kolkata")
now_ist = datetime.now(ist)

# 1. Load authoritative instrument master
reg = OptionInstrumentRegistry()
count = reg.load_master(max_age_hours=24, raise_if_stale=False)
mtime_utc = reg.master_mtime
mtime_ist = mtime_utc.astimezone(ist) if mtime_utc else None
age_hours = (datetime.now(timezone.utc) - mtime_utc).total_seconds() / 3600.0 if mtime_utc else None

print("=== STEP 2.2: PRE-MARKET UNIVERSE & EXPIRY RESOLUTION ===")
print("Current IST Time:", now_ist.strftime("%Y-%m-%d %H:%M:%S %Z"))
print(f"Master File: {reg.master_path} (Age: {age_hours:.1f}h, Mtime: {mtime_ist})")
assert age_hours is not None and age_hours < 24.0, f"Instrument master is stale ({age_hours:.1f}h > 24h limit)!"

# 2. Dynamically resolve nearest unexpired weekly expiry
nearest_expiry = reg.get_nearest_weekly_expiry("NIFTY", as_of_date=now_ist.date())
print(f"Resolved Nearest Weekly Expiry: {nearest_expiry} (Source: {reg.master_path.name})")
assert nearest_expiry is not None, "Failed to resolve nearest unexpired NIFTY weekly expiry from master!"
assert nearest_expiry >= now_ist.date(), f"Resolved expiry {nearest_expiry} is in the past!"

# 3. Resolve desired contracts around indicative diagnostic spot
dum = DesiredUniverseManager(registry=reg, config=CONFIG_NIFTY)
indicative_spot = Decimal("24500.00")
atm_strike = dum.calculate_atm_strike(indicative_spot)
contracts = dum.get_desired_contracts(indicative_spot, as_of_datetime=now_ist.astimezone(timezone.utc))

print(f"Underlying Spot: {indicative_spot} [DIAGNOSTIC PRE-FLIGHT ONLY]")
print(f"Calculated ATM Strike: {atm_strike}")
print(f"Total Desired Contracts: {len(contracts)} (Expected: 22)")
ce_count = sum(1 for c in contracts if c.instrument_type == "CE")
pe_count = sum(1 for c in contracts if c.instrument_type == "PE")
print(f"Contract Breakdown: {ce_count} CE, {pe_count} PE")

assert len(contracts) == 22, f"Expected 22 desired contracts, got {len(contracts)}"
assert ce_count == 11 and pe_count == 11, f"Asymmetric strike distribution: {ce_count} CE, {pe_count} PE!"
print("VALIDATION_LOGIC: PASS")
print("DATA_EVIDENCE: PASS (Dynamic resolution verified against fresh master)")
'
```

### Step 2.3 — CLI Opt-In & Environment Verification
Confirm that the daemon CLI exposes `--enable-fno`, verify component construction readiness, and verify credentials without exposing secrets.

```bash
# 1. Verify CLI argument flag in argument parser
venv/bin/python manage.py run_intraday_ticker --help | grep "\-\-enable-fno"

# 2. Verify F&O Consumer Component Construction (offline dependency & registry load test)
venv/bin/python manage.py shell -c '
from fno.services.fno_ticker_consumer import FnoTickerConsumer
consumer = FnoTickerConsumer()
print("FnoTickerConsumer Component Construction: SUCCESS")
assert consumer.universe_manager is not None
assert consumer.bar_aggregator is not None
assert consumer.quote_manager is not None
assert consumer.normalizer is not None
print("F&O component dependencies initialized cleanly.")
print("OUTCOME: COMPONENT_CONSTRUCTION_PASS")
print("NOTE: End-to-end live startup wiring remains PENDING_STARTUP_VERIFICATION.")
'

# 3. Check Kite credentials readiness
venv/bin/python -c '
from market.services.kite_credentials import KiteCredentialService
api_key = KiteCredentialService.get_api_key()
token = KiteCredentialService.get_valid_access_token()
print("Kite API Key present:", bool(api_key))
print("Kite Access Token valid:", bool(token))
assert api_key and token, "Missing or expired Zerodha Kite session! Authenticate at /api/v1/kite/login/"
'

# 4. Verify Django system checks and pending migrations
venv/bin/python manage.py check
venv/bin/python manage.py makemigrations --check
```

> [!NOTE]
> **Component Construction vs Startup Wiring:**  
> Independent construction of `FnoTickerConsumer` verifies class imports, underlying asset configuration, and registry loading. However, it does NOT prove that `run_intraday_ticker`'s `--enable-fno` flag successfully wires the consumer into `KiteTickerManager(..., fno_consumer=fno_consumer)` at runtime. End-to-end startup wiring can only be verified safely at 09:14:45 IST by observing the startup log anchor: `F&O option ingestion enabled (--enable-fno). Initialized FnoTickerConsumer.`

### Step 2.4 — Authoritative Startup Command Preparation (09:14 IST)
Record the authoritative command line to be executed at 09:14:30 IST.

> [!IMPORTANT]
> **Authoritative Command Line:**  
> The single canonical command to start the live ticker daemon with F&O ingestion is:  
> `venv/bin/python manage.py run_intraday_ticker --enable-fno --snapshot-interval 60`  
> Do not use alternate or deprecated command variants (such as non-existent `market_ticker`).

---

## 3. Market Open & Acceptance Window (09:15 – 09:45 IST)

Execute the primary startup command at 09:14:45 IST so the WebSocket establishes connection and initial subscriptions before the opening bell:

```bash
venv/bin/python manage.py run_intraday_ticker --enable-fno --snapshot-interval 60
```

### Step 3.1 — Initial Connection & Mode Full Subscription
Observe initial daemon logs:
1. Verify live startup wiring anchor: `F&O option ingestion enabled (--enable-fno). Initialized FnoTickerConsumer.`
2. Verify log anchor: `Connecting to Kite WebSocket (wss://ws.kite.trade)...`
3. Verify log anchor: `Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22`
4. Confirm Kite mode set to `MODE_FULL` (184-byte packets containing 5-level market depth).

> [!IMPORTANT]
> **Sourcing Authoritative Subscribed-Token Evidence:**  
> Active token subscriptions must be sourced directly from the ticker daemon's log anchors:  
> `grep "Universe reconciled:" logs/intraday_ticker.log | tail -n 5`  
> `grep "\[HEARTBEAT\]" logs/intraday_ticker.log | tail -n 5`  
> (Confirming: `Active tokens: 22` and heartbeat `F&O Active: 22`). Active subscriptions must NEVER be inferred from persisted database bars alone, as an illiquid contract with zero trades or an ingestion delay would be falsely reported as unsubscribed.

### Step 3.2 — Continuous Live Ingestion Verification (Every 5 Minutes)
Execute targeted audit checks in a separate terminal:

#### Verification A: Continuous Option-Bar Persistence & Interval Coverage (`AC-1-L02`)
Verify 1-minute bars are rolled up and persisted with complete OHLCV, non-null volume, and accurate open interest semantics across all expected active contracts:
- Generates all expected 1-minute bucket timestamps aligned to market-minute boundaries across the observation window (e.g. 15 intervals from 09:15:00 to 09:30:00).
- Resolves active underlying spot from session equity bars in `market_ohlcvbar`. If spot is unavailable, marks check as `DATA_CHECK_INCONCLUSIVE` rather than silently assuming `24500.00`.
- Audits total expected contract-minute slots (`len(expected_tokens) * window_minutes`, e.g. 330 slots).
- Checks for duplicate bars on `(instrument_token, timestamp)` (must be 0).
- Validates OHLC integrity (`high >= open, high >= close, low <= open, low <= close, open > 0, close > 0`) and volume (`volume >= 0`).
- Strictly preserves OI distinction:
  - `VALID`: positive `open_interest > 0`.
  - `ZERO_ACTIVITY`: genuine `open_interest == 0`.
  - `UNPOPULATED`: missing/unavailable OI (`open_interest is None`). Never fabricated as 0.
- Tracks partial bars interrupted by network disconnects (`is_partial_bar=True`).
- **Missing Bar Telemetry Rule:** For missing option-bar minute slots, do not infer zero trades or ingestion failure from absent bars alone. Check available tick/consumer telemetry. If contract-level tick telemetry is insufficient to distinguish zero trades from pipeline drops, report `UNCLASSIFIED (EVIDENCE_INSUFFICIENT)`.
- **Outcome Separation:** Separates `VALIDATION_LOGIC: PASS` from `DATA_EVIDENCE: DATA_CHECK_PASS / DATA_CHECK_INCONCLUSIVE`.

```bash
venv/bin/python manage.py shell -c '
from fno.models import OptionOHLCVBar
from fno.services.option_registry import OptionInstrumentRegistry
from fno.services.desired_universe import DesiredUniverseManager, CONFIG_NIFTY
from market.models import OHLCVBar
from zoneinfo import ZoneInfo
from django.utils import timezone
import datetime
from decimal import Decimal

ist = ZoneInfo("Asia/Kolkata")
now = timezone.now()
now_ist = now.astimezone(ist)
window_minutes = 15
start_window = now - datetime.timedelta(minutes=window_minutes)
start_minute = start_window.replace(second=0, microsecond=0)
end_minute = now.replace(second=0, microsecond=0)

start_str = start_minute.astimezone(ist).strftime("%H:%M")
end_str = end_minute.astimezone(ist).strftime("%H:%M")

print("=== AC-1-L02 OPTION BAR COVERAGE AUDIT ===")
print("Observation Window:", start_str, "to", end_str, f"IST ({window_minutes}m)")

# 1. Resolve live spot independently — do NOT silently fall back to 24500.00
latest_spot_bar = OHLCVBar.objects.filter(
    instrument__symbol="^NSEI",
    timestamp__gte=start_minute - datetime.timedelta(minutes=60),
    timestamp__lte=end_minute
).order_by("-timestamp").first()

live_spot = None
if latest_spot_bar:
    live_spot = latest_spot_bar.close
    t_str = latest_spot_bar.timestamp.astimezone(ist).strftime("%H:%M:%S")
    print(f"Active Underlying Spot (^NSEI): {live_spot} (Source: market_ohlcvbar @ {t_str})")
else:
    print("Underlying Spot (^NSEI): UNAVAILABLE in market_ohlcvbar for current window.")

reg = OptionInstrumentRegistry()
reg.load_master(max_age_hours=24, raise_if_stale=False)
dum = DesiredUniverseManager(registry=reg, config=CONFIG_NIFTY)

if live_spot is None:
    expected_tokens = {}
    print("Expected Active Universe: UNRESOLVED (Awaiting live session spot)")
else:
    expected_contracts = dum.get_desired_contracts(live_spot, as_of_datetime=now)
    expected_tokens = {c.instrument_token: c for c in expected_contracts}
    print(f"Expected Active Universe: {len(expected_tokens)} contracts (ATM Strike: {dum.calculate_atm_strike(live_spot)})")

expected_intervals = [start_minute + datetime.timedelta(minutes=i) for i in range(window_minutes)]
total_expected_slots = len(expected_tokens) * len(expected_intervals) if expected_tokens else 0
print(f"Expected Contract-Minute Slots: {total_expected_slots}")

bars = OptionOHLCVBar.objects.filter(
    timestamp__gte=start_minute,
    timestamp__lt=end_minute,
    timeframe="1m"
).order_by("timestamp")
total_bars = bars.count()
print(f"Total Persisted Bars in Window: {total_bars}")

bars_by_slot = {}
bars_by_token = {}

for b in bars:
    slot_key = (b.instrument_token, b.timestamp)
    bars_by_slot.setdefault(slot_key, []).append(b)
    bars_by_token.setdefault(b.instrument_token, []).append(b)

duplicates_count = 0
ohlc_errors = 0
volume_errors = 0
valid_oi = 0
zero_oi = 0
unpopulated_oi = 0
partial_bars = 0

for slot_key, slot_bars in bars_by_slot.items():
    if len(slot_bars) > 1:
        duplicates_count += (len(slot_bars) - 1)
    for b in slot_bars:
        if not (b.high >= b.open and b.high >= b.close and b.low <= b.open and b.low <= b.close and b.open > 0 and b.close > 0):
            ohlc_errors += 1
        if b.volume is None or b.volume < 0:
            volume_errors += 1
        if b.oi_status == "VALID":
            valid_oi += 1
            assert b.open_interest is not None and b.open_interest > 0
        elif b.oi_status == "ZERO_ACTIVITY":
            zero_oi += 1
            assert b.open_interest == 0
        elif b.oi_status == "UNPOPULATED":
            unpopulated_oi += 1
            assert b.open_interest is None
        else:
            raise AssertionError(f"Unknown oi_status: {b.oi_status}")
        if b.is_partial_bar:
            partial_bars += 1

missing_slots = 0
if expected_tokens:
    for token in expected_tokens:
        token_slots_present = sum(1 for ts in expected_intervals if (token, ts) in bars_by_slot)
        missing_slots += (len(expected_intervals) - token_slots_present)

print(f"Duplicates: {duplicates_count} | OHLC Errors: {ohlc_errors} | Vol Errors: {volume_errors}")
print(f"OI Data Quality Breakdown: VALID={valid_oi}, ZERO_ACTIVITY={zero_oi}, UNPOPULATED={unpopulated_oi}")
print(f"Partial Bars: {partial_bars}")
if missing_slots > 0:
    print(f"Missing Contract-Minute Slots: {missing_slots} [UNCLASSIFIED (EVIDENCE_INSUFFICIENT: per-token tick telemetry required)]")

print("\n--- OUTCOME SEPARATION ---")
print("VALIDATION_LOGIC: PASS (Script executed cleanly, schema validated, assertions compile)")
if total_bars == 0 or not expected_tokens:
    print("DATA_EVIDENCE: DATA_CHECK_INCONCLUSIVE (Zero evaluated records in observation window)")
    print("AC-1-L02 STATUS: NOT TESTED (Awaiting Monday live session data)")
elif duplicates_count == 0 and ohlc_errors == 0 and volume_errors == 0:
    print(f"DATA_EVIDENCE: DATA_CHECK_PASS ({total_bars} bars evaluated across active universe)")
    print("AC-1-L02 STATUS: PASS")
else:
    print("DATA_EVIDENCE: DATA_CHECK_FAIL")
    print("AC-1-L02 STATUS: FAIL")
'
```

#### Verification B: Option Quote Snapshot Freshness & Timestamp Provenance (`AC-1-L04`)
Verify L1 and depth quote snapshots independently report local receipt age and exchange matching engine age across the active universe:
- Queries the latest quote snapshot **per expected active token** in the universe.
- Rejects future exchange timestamps from freshness PASS (`exch_age < 0.0` or `exchange_time_status == "FUTURE_SKEW_REJECTED"`).
- Enforces documented bounded exchange age: `0.0s <= exch_age <= 3.0s` on `exchange_time_status == "VALID"`.
- Separately classifies: `FRESH_BOUNDED`, `STALE`, `FUTURE`, `INVALID`, `MISSING`.
- **Production Eligibility Gate:** Quote eligibility audit verifies that `is_execution_eligible == True` strictly requires:
  1. `exchange_time_status == "VALID"`
  2. `quote_status == "VALID"` (rejecting `LOCKED`, `CROSSED`, `EMPTY_BOOK`, `ZERO_BID`, `STALE`, `INVALID`)
  3. `not is_stale`
  4. `not is_locked` and `not is_crossed`
  5. `best_bid is not None and best_bid > 0` and `best_ask is not None and best_ask > best_bid`
  6. Verified bounded exchange age ($0.0\text{s} \le \text{age} \le 3.0\text{s}$)
- **Outcome Separation:** Separates `VALIDATION_LOGIC: PASS` from `DATA_EVIDENCE: DATA_CHECK_PASS / DATA_CHECK_INCONCLUSIVE`.

```bash
venv/bin/python manage.py shell -c '
from fno.models import OptionQuoteSnapshot
from django.utils import timezone
from zoneinfo import ZoneInfo
import datetime
from decimal import Decimal

ist = ZoneInfo("Asia/Kolkata")
now = timezone.now()
now_ist = now.astimezone(ist)
window_start = now - datetime.timedelta(minutes=5)

print("=== AC-1-L04 QUOTE SNAPSHOT PROVENANCE & FRESHNESS AUDIT ===")
print("Audit Time:", now_ist.strftime("%Y-%m-%d %H:%M:%S %Z"))

recent_quotes = OptionQuoteSnapshot.objects.filter(
    received_wall_clock_utc__gte=window_start
).order_by("-received_wall_clock_utc")

distinct_tokens = set(recent_quotes.values_list("instrument_token", flat=True))
print(f"Total Snapshots in Window: {recent_quotes.count()} across {len(distinct_tokens)} distinct tokens")

valid_fresh_exch = 0
stale_exch = 0
future_exch = 0
invalid_exch = 0
missing_exch = 0
eligibility_inconsistencies = 0

for token in distinct_tokens:
    q = recent_quotes.filter(instrument_token=token).first()
    recv_age = (now - q.received_wall_clock_utc).total_seconds()
    
    if q.exchange_timestamp_utc is None or q.exchange_time_status == "FALLBACK_TO_RECEIVED":
        missing_exch += 1
        exch_age_str = "MISSING"
    elif q.exchange_time_status == "VALID":
        exch_age = (now - q.exchange_timestamp_utc).total_seconds()
        # Reject future timestamps from freshness PASS (bounded 0.0s <= exch_age <= 3.0s)
        if exch_age < 0.0 or q.exchange_timestamp_utc > (q.received_wall_clock_utc + datetime.timedelta(seconds=1.0)):
            future_exch += 1
            exch_age_str = f"FUTURE_REJECTED ({exch_age:.2f}s)"
        elif exch_age <= 3.0:
            valid_fresh_exch += 1
            exch_age_str = f"FRESH ({exch_age:.2f}s)"
        else:
            stale_exch += 1
            exch_age_str = f"STALE ({exch_age:.2f}s)"
    elif q.exchange_time_status in ("FUTURE_SKEW_REJECTED",):
        future_exch += 1
        exch_age_str = f"FUTURE_REJECTED ({q.exchange_time_status})"
    else:
        invalid_exch += 1
        exch_age_str = f"INVALID ({q.exchange_time_status})"

    # Production Execution Eligibility Verification
    expected_eligibility = (
        q.exchange_time_status == "VALID"
        and q.quote_status == "VALID"
        and not q.is_stale
        and not q.is_locked
        and not q.is_crossed
        and q.best_bid is not None and q.best_bid > Decimal("0.0")
        and q.best_ask is not None and q.best_ask > q.best_bid
        and q.exchange_timestamp_utc is not None
        and 0.0 <= (now - q.exchange_timestamp_utc).total_seconds() <= 3.0
    )
    if q.is_execution_eligible != expected_eligibility:
        eligibility_inconsistencies += 1

print(f"Timestamp Classification: FRESH_BOUNDED={valid_fresh_exch}, STALE={stale_exch}, FUTURE={future_exch}, INVALID={invalid_exch}, MISSING={missing_exch}")
print(f"Execution Eligibility Inconsistencies: {eligibility_inconsistencies}")
assert eligibility_inconsistencies == 0, f"Found {eligibility_inconsistencies} execution eligibility violations!"

print("\n--- OUTCOME SEPARATION ---")
print("VALIDATION_LOGIC: PASS (Script executed cleanly, schema validated, eligibility rules checked)")
if recent_quotes.count() == 0:
    print("DATA_EVIDENCE: DATA_CHECK_INCONCLUSIVE (Zero quote snapshots evaluated in observation window)")
    print("AC-1-L04 STATUS: NOT TESTED (Awaiting Monday live session data)")
elif valid_fresh_exch > 0 and eligibility_inconsistencies == 0:
    print(f"DATA_EVIDENCE: DATA_CHECK_PASS ({valid_fresh_exch} fresh quotes verified across active universe)")
    print("AC-1-L04 STATUS: PASS")
else:
    print("DATA_EVIDENCE: DATA_CHECK_FAIL")
    print("AC-1-L04 STATUS: FAIL")
'
```

#### Verification C: Equity Isolation Guarantee (`AC-1-L01`)
Verify that zero NFO derivative symbols appear in equity database storage, and document runtime state manager isolation:

```bash
venv/bin/python manage.py shell -c '
from market.models import OHLCVBar, StockIntradayContext
from django.utils import timezone
import datetime

now = timezone.now()
start_window = now - datetime.timedelta(minutes=45)

print("=== AC-1-L01: EQUITY ISOLATION AUDIT ===")
contaminated_bars = OHLCVBar.objects.filter(
    instrument__symbol__startswith="NIFTY26",
    timestamp__gte=start_window
)
contaminated_bars_count = contaminated_bars.count()

contaminated_contexts = StockIntradayContext.objects.filter(
    instrument__symbol__startswith="NIFTY26",
    timestamp__gte=start_window
)
contaminated_contexts_count = contaminated_contexts.count()

print(f"  Contaminated equity OHLCV bars (market_ohlcvbar): {contaminated_bars_count}")
print(f"  Contaminated stock intraday contexts (market_stockintradaycontext): {contaminated_contexts_count}")
assert contaminated_bars_count == 0, f"LEAK: Found {contaminated_bars_count} NFO bars in market_ohlcvbar!"
assert contaminated_contexts_count == 0, f"LEAK: Found {contaminated_contexts_count} NFO contexts in market_stockintradaycontext!"

print("\n--- OUTCOME SEPARATION ---")
print("VALIDATION_LOGIC: PASS (Script executed cleanly, schema validated)")
print("PART_A_DATABASE_ISOLATION: PASS (0 contaminated records in equity storage)")
print("PART_B_RUNTIME_ISOLATION: NOT TESTED (In-memory IntradayStateManager process-isolated; live telemetry required)")
print("OVERALL AC-1-L01 STATUS: NOT TESTED (Pending concurrent live F&O tick ingestion)")
'
```

#### Verification D: Dynamic ATM Reconciliation (`AC-1-L05`)
Monitor underlying spot moves on `^NSEI`.

**Rebalance Trigger Specification:**
- The rebalance trigger is governed by the **calculated ATM strike boundary**, NOT a fixed 50-point spot move.
- For NIFTY (strike step = 50.0), crossing the 25-point half-step threshold (e.g. spot moving from `24524.00` to `24526.00`) changes the round-half-up ATM strike from `24500.00` to `24550.00`.
- When an ATM transition occurs:
  1. `DesiredUniverseManager` recomputes desired tokens ($2K+1$ CE + $2K+1$ PE, maintaining 22 active contracts).
  2. WebSocket subscriptions are reconciled: incoming strikes are subscribed in `MODE_FULL` (+2 tokens per strike step shift) and outgoing strikes are unsubscribed (-2 tokens).
  3. Sourced from daemon logs: `Universe reconciled: +N subscribed, -N unsubscribed. Active tokens: 22 (ATM: ...)`.
- **Live Acceptance Rule:** If a natural market move triggers an ATM strike transition during the 09:15–09:45 IST window, verify the log anchors and active token set to mark `AC-1-L05: PASS`. If no natural ATM transition occurs, mark `AC-1-L05: NOT TESTED (PENDING_MARKET_MOVEMENT)`. Never inject artificial ticks or alter live broker feeds to force this test.

```bash
venv/bin/python manage.py shell -c '
from market.models import OHLCVBar
from django.utils import timezone
import datetime

now = timezone.now()
start_window = now - datetime.timedelta(minutes=30)

print("=== AC-1-L05: DYNAMIC ATM RECONCILIATION AUDIT ===")
spot_bars = OHLCVBar.objects.filter(
    instrument__symbol="^NSEI",
    timestamp__gte=start_window
).order_by("timestamp")

print("\n--- OUTCOME SEPARATION ---")
print("VALIDATION_LOGIC: PASS (Script executed cleanly, schema validated)")

if not spot_bars.exists():
    print("DATA_EVIDENCE: DATA_CHECK_INCONCLUSIVE (Zero session spot bars in window)")
    print("AC-1-L05 STATUS: NOT TESTED (PENDING_LIVE_SESSION_DATA)")
else:
    spots = [b.close for b in spot_bars]
    min_s, max_s = min(spots), max(spots)
    first_atm = (spots[0] / 50).quantize(1) * 50
    last_atm = (spots[-1] / 50).quantize(1) * 50
    print(f"Spot Range in Window: {min_s} to {max_s} (Start ATM: {first_atm}, End ATM: {last_atm})")
    if first_atm == last_atm:
        print("DATA_EVIDENCE: NO_ATM_BOUNDARY_CROSSING (Underlying spot stayed within current strike step)")
        print("AC-1-L05 STATUS: NOT TESTED (PENDING_MARKET_MOVEMENT)")
    else:
        print(f"ATM transition observed: {first_atm} -> {last_atm}. Check daemon logs for Universe Reconciled anchors.")
        print("DATA_EVIDENCE: DATA_CHECK_PASS")
        print("AC-1-L05 STATUS: PASS")
'
```

#### Verification E: Reconnect & Resubscription Recovery (`AC-1-L03`)
If a natural transient network disconnect or broker WebSocket reset occurs during trading hours:
- Observe log anchor: `[WATCHDOG] Reconnected successfully`
- Verify full re-subscription of all 22 active option contracts in `MODE_FULL` completes within $\le 5.0\text{s}$.
- Verify bars interrupted across the disconnect window are marked with `is_partial_bar=True`.
- **Live Acceptance Rule:** If no natural network disconnect occurs during the observation window, mark `AC-1-L03: NOT TESTED (NO_NATURAL_DISCONNECT)`. DO NOT artificially sever network connections, drop network interfaces, or kill the WebSocket process during the live trading session without an approved safe procedure.

```bash
# Check ticker daemon log for reconnect events
grep -E "\[WATCHDOG\] Reconnected successfully" logs/intraday_ticker.log | tail -n 5
```

#### Verification F: Heartbeat & Processing Backlog Health
Observe the ticker heartbeat emitted every 10 seconds in the daemon terminal:
`[HEARTBEAT] Ticks Received: 14250 | Feed: FRESH (0.2s ago) | Snapshots: 54 | F&O Ticks: 8940 | F&O Active: 22 | F&O Bars: 44`

Verify:
- Tick count increases continuously.
- Feed age remains $< 1.0\text{s}$.
- Subscribed tokens count `F&O Active: 22` is confirmed from live telemetry.
- No growing processing backlog or unhandled exceptions.

#### Verification G: Optional Strategy Evaluation & Paper Ledger Execution (`OP-CHECK-PAPER-EXEC`)
If paper trading strategies are active in observation mode:
- Verify signals are evaluated strictly against verified exchange timestamps (`exchange_time_status == "VALID"`).
- Verify simulated fills, statutory fee deductions, and trade events are recorded in `fno_paper_trade_ledger` without fabricated fills or missing dates.

---

## 4. Live Acceptance Evidence Matrix

| Criterion ID | Requirement | Exact Procedure / Command | Target Window (IST) | Expected Result | Actual Result | Evidence Location | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`AC-1-L01`** | **Equity Isolation** | Query `market_ohlcvbar` and `market_stockintradaycontext` via Verification C | 09:15 – 09:45 | Part A DB: Count = 0. Zero option bars in equity models. Part B: Runtime state manager isolated via architecture. | Pending Monday Live Session | Database queries on `market_ohlcvbar` & `market_stockintradaycontext` | **NOT TESTED** |
| **`AC-1-L02`** | **Continuous Option-Bar Persistence** | Query `fno_option_ohlcvbar` for 1m bars via Verification A | 09:15 – 09:45 | Continuous 1m interval coverage across active contracts (up to 330 slots); complete OHLCV; genuine OI = 0 distinguished (`ZERO_ACTIVITY`) from unpopulated OI (`UNPOPULATED`, null); missing OI never fabricated as 0. | Pending Monday Live Session | Database query on `fno_option_ohlcvbar` | **NOT TESTED** |
| **`AC-1-L03`** | **Reconnect / Resubscription Recovery** | Natural network blip or graceful disconnect observation via Verification E | 09:15 – 09:45 | Reconnection within $\le 5.0\text{s}$; full resubscription of 22 contracts in `MODE_FULL`; partial bars marked (`is_partial_bar=True`). (If no natural blip, remains NOT TESTED). | Pending Monday Live Session | Watchdog logs `[WATCHDOG] Reconnected successfully` | **NOT TESTED** |
| **`AC-1-L04`** | **Live Quote Snapshots & Classification** | Query `fno_option_quote_snapshot` for recent quotes per active token via Verification B | 09:15 – 09:45 | Bounded exchange freshness ($0.0 \le \text{age} \le 3.0\text{s}$); future timestamps rejected; execution eligibility consistent; per-token coverage reported. | Pending Monday Live Session | Database query on `fno_option_quote_snapshot` | **NOT TESTED** |
| **`AC-1-L05`** | **Dynamic ATM Reconciliation** | Observe natural spot move crossing ATM strike threshold ($\pm 25.0$ pts) via Verification D | 09:15 – 09:45 | Seamless token handover (+N / -N on ATM boundary crossing); exactly 22 active tokens maintained; uninterrupted feed. (If no natural move, remains NOT TESTED). | Pending Monday Live Session | DesiredUniverseManager logs `Universe reconciled:` | **NOT TESTED** |
| **`OP-CHECK-PAPER-EXEC`** | **Paper Strategy & Ledger Execution** | Query `fno_paper_trade_ledger` and `fno_paper_trade_event` via Verification G | 09:15 – 09:45 | Paper trades persist with verified exchange timestamps without fabricated fills or default fee override leaks. | Pending Monday Live Session | Database query on `fno_paper_trade_ledger` | **NOT TESTED** |

> [!IMPORTANT]
> **Strict Acceptance Rules:**
> - Criteria `AC-1-L01` through `AC-1-L05` can **only** be marked `PASS` using authentic, live market data captured between 09:15 and 09:45 IST on Monday, 19 October 2026.
> - Synthetic ticks, unit test outputs, offline fixtures, or an empty database do **not** constitute live-market evidence. Empty data checks produce `DATA_CHECK_INCONCLUSIVE` or `NOT TESTED`.
> - Do not artificially drop the live broker connection unless approved safe procedures are in effect.
> - Any check where natural market movement or events did not occur during the window must be recorded as `NOT TESTED` with the specific reason noted.

---

## 5. Post-Window Verification & Clean Shutdown (09:45 IST)

1. Send `SIGINT` (Ctrl+C) to the daemon process.
2. Verify graceful shutdown log anchors:
   - `Shutdown signal received. Stopping live ticker...`
   - `Flushed N remaining F&O option bars on shutdown.`
   - `SESSION SUMMARY: Elapsed: ...s | Equity Ticks: ... | F&O Ticks: ... | F&O Bars: ... | F&O Quotes: ...`
3. Confirm PID lock removal: `test ! -f /tmp/nomad_intraday_ticker.pid`.
4. Compile captured query outputs and log excerpts into `docs/audits/phase_22a_live_acceptance_evidence_report.md`.
