# Nomad Analyst — Phase 22 Independent Audit ChatGPT Handoff

**Handoff Reference:** `docs/audits/phase_22_independent_audit_chatgpt_handoff.md`  
**Date:** 2026-10-18  
**Time:** 06:06 IST  
**Author:** Quantitative Researcher & Systems Architect  
**Review Target:** Independent ChatGPT Architecture & Code Audit  
**Status:** PHASE 22 REMEDIATION & FINAL AUDIT CLOSURE COMPLETE — READY FOR INDEPENDENT AUDIT  

---

## 1. Executive Summary & Review Scope

Following the final audit closure pass, all remaining findings across the F&O Options Stack (Phases 22A through 22D) have been remediated and verified:

1. **Position Identity & Uniqueness Invariant (`fno/execution/paper_engine.py`):**
   - Verified that multiple unresolved ledger rows **cannot** share `strategy_id:tradingsymbol`.
   - In `_handle_buy_signal`, enforced the uniqueness invariant across both in-memory cache and the database ledger: any incoming entry order is strictly rejected (`REJECTED_POSITION_ALREADY_OPEN`) if an unresolved trade (`OPEN`, `PENDING_LIQUIDITY`, `UNEXECUTABLE_OVERNIGHT_CARRY`, `PENDING_EXPIRY_SETTLEMENT`) already exists.
   - In `sync_active_trades_from_db()`, prevented dictionary-key collisions by detecting duplicate unresolved rows in the DB and raising `ValueError` rather than silently overwriting state.

2. **Fee Date Policy & Boundary Enforcement (`fno/execution/fee_calculator.py`):**
   - Prevented `trade_date=None` from silently defaulting to the current statutory schedule.
   - Implemented an explicit policy: `calculate_round_trip` requires a valid `trade_date >= 2026-04-01` unless `allow_default_schedule=True` is explicitly passed; otherwise it raises `ValueError`.
   - Updated engine callers to pass explicit dates.

3. **Tick Parameter & Fill Validation (`fno/execution/paper_engine.py`):**
   - Defined `PERMITTED_ROUNDING_DIRECTIONS = frozenset({"UP", "CEILING", "DOWN", "FLOOR", "NEAREST"})`.
   - Validated that `tick_size` must be strictly positive (`tick_size > 0`) in `round_to_tick`, `calculate_taker_buy_fill`, and `calculate_taker_sell_fill`; non-positive values raise `ValueError`.
   - Validated permitted rounding directions and non-negative slippage rates (`rate >= 0`).

4. **Regression Verification:**
   - 385 tests passing across F&O and equity modules (87 in `fno.tests`, 298 in `market.tests`).
   - Django system checks and migrations checks are completely clean.

---

## 2. Test Verification Summary

```bash
venv/bin/python manage.py test fno.tests market.tests
```

```text
Ran 385 tests in 8.168s

OK
Destroying test database for alias 'default'...
Destroying test database for alias 'telemetry'...
```

- **F&O Test Suite:** **87 tests, 0 failures, 0 errors** (Phase 22A: 37, Phase 22B: 22, Phase 22C: 6, Phase 22D: 22).
- **Equity Test Suite:** **298 tests, 0 failures, 0 errors**.
- **Combined Test Suite:** **385 tests, 0 failures, 0 errors**.
- **Django System Check:** 0 silenced issues, migrations up to date (`No changes detected`).

---

## 3. Specific Code Snippets for Review

### 1. Position Uniqueness Invariant & Collision Prevention (`fno/execution/paper_engine.py`)
```python
def sync_active_trades_from_db(self) -> int:
    unresolved_trades = PaperTradeLedger.objects.filter(
        status__in=[
            "OPEN",
            "PENDING_LIQUIDITY",
            "UNEXECUTABLE_OVERNIGHT_CARRY",
            "PENDING_EXPIRY_SETTLEMENT",
        ]
    ).order_by("entry_timestamp")

    self.active_trades.clear()
    count = 0
    for trade in unresolved_trades:
        trade_key = f"{trade.strategy_id}:{trade.tradingsymbol}"
        if trade_key in self.active_trades:
            existing = self.active_trades[trade_key]
            raise ValueError(
                f"Uniqueness invariant violated: Multiple unresolved ledger rows found for "
                f"key '{trade_key}' (Trade #{existing.trade_id} with status '{existing.status}' "
                f"and Trade #{trade.trade_id} with status '{trade.status}'). Cannot silently collide."
            )
        self.active_trades[trade_key] = trade
        count += 1
    return count
```

### 2. Entry Signal Unresolved Position Check (`fno/execution/paper_engine.py`)
```python
existing_trade = self.active_trades.get(trade_key)
if not existing_trade:
    existing_trade = PaperTradeLedger.objects.filter(
        strategy_id=signal.strategy_id,
        tradingsymbol=signal.tradingsymbol,
        status__in=[
            "OPEN",
            "PENDING_LIQUIDITY",
            "UNEXECUTABLE_OVERNIGHT_CARRY",
            "PENDING_EXPIRY_SETTLEMENT",
        ],
    ).first()
    if existing_trade:
        self.active_trades[trade_key] = existing_trade

if existing_trade and existing_trade.status in (
    "OPEN",
    "PENDING_LIQUIDITY",
    "UNEXECUTABLE_OVERNIGHT_CARRY",
    "PENDING_EXPIRY_SETTLEMENT",
):
    rejection_code = "REJECTED_POSITION_ALREADY_OPEN"
    logger.warning("Rejecting signal %s: %s", signal.signal_id, rejection_code)
    return PaperTradeEvent(..., message=rejection_code)
```

### 3. Fee Date Explicit Policy (`fno/execution/fee_calculator.py`)
```python
@classmethod
def calculate_round_trip(
    cls,
    buy_price: Decimal,
    sell_price: Decimal,
    quantity: int,
    is_exercise_settlement: bool = False,
    custom_brokerage_per_order: Optional[Decimal] = None,
    trade_date: Optional[date] = None,
    allow_default_schedule: bool = False,
) -> StatutoryFeeBreakdown:
    if trade_date is None:
        if not allow_default_schedule:
            raise ValueError(
                "Missing trade_date: An explicit trade_date is required to evaluate statutory fee schedules. "
                "Silent default schedule selection is prohibited. Pass trade_date (>= 2026-04-01) or set "
                f"allow_default_schedule=True to explicitly use schedule {cls.EFFECTIVE_SCHEDULE_DATE}."
            )
    elif trade_date < cls.EARLIEST_SUPPORTED_DATE:
        raise ValueError(
            f"Historical trade date {trade_date} is unsupported. Statutory schedule is configured "
            f"for effective date {cls.EFFECTIVE_SCHEDULE_DATE} onwards (NSE Circular NSE/FA/73061 "
            f"& Finance Act 2026). Earlier dates used tiered exchange slabs and lower STT rates."
        )
    ...
```

### 4. Tick Size & Direction Validation (`fno/execution/paper_engine.py`)
```python
PERMITTED_ROUNDING_DIRECTIONS = frozenset({"UP", "CEILING", "DOWN", "FLOOR", "NEAREST"})

def round_to_tick(
    price: Optional[Decimal],
    tick_size: Decimal = Decimal("0.05"),
    direction: str = "NEAREST",
) -> Optional[Decimal]:
    if price is None:
        return None
    if tick_size is None or tick_size <= Decimal("0.00"):
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    dir_norm = direction.upper() if direction else ""
    if dir_norm not in PERMITTED_ROUNDING_DIRECTIONS:
        raise ValueError(
            f"Invalid rounding direction '{direction}'. Permitted directions: {sorted(PERMITTED_ROUNDING_DIRECTIONS)}"
        )
    ...
```

---

## 4. Phase 22E Live Acceptance Checklist (Monday Market Open)

All current evidence is strictly **offline source-code and deterministic test evidence**. No live-market pass, profitability, or third-party certification is claimed.

| Time Window | Target Component | Command / Verification Action | Pass Criterion |
| :--- | :--- | :--- | :--- |
| **09:08–09:15 IST** | Instrument Master | `ls -la data/universe/kite_instruments_master.csv` | File exists, $< 24$h age, contains NFO options. |
| **09:08–09:15 IST** | Universe Discovery | CLI startup check | Active ATM resolved; 22 NFO tokens identified. |
| **09:15–09:20 IST** | Live Ingestion | `python manage.py run_intraday_ticker --enable-fno` | WebSocket connected in `MODE_FULL`; live 184-byte ticks received. |
| **09:15–09:20 IST** | Equity Isolation | DB row count query | Zero rows written to `market_ohlcvbar` for NFO tokens; `IntradayStateManager` unaffected. |
| **09:15–09:45 IST** | Continuous Stability | 30-min continuous monitoring | 0 process exits/crashes; continuous 1m bars in `fno_option_ohlcvbar`; dynamic ATM rebalancing across $\pm 25$ spot moves. |
