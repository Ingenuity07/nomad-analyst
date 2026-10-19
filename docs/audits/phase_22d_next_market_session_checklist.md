# Phase 22D — Next Live Market Session Acceptance Checklist

**Target Session:** 09:08 IST to 09:45 IST on Next Active NSE Trading Day  
**Repository:** `Ingenuity07/nomad-analyst`  
**Verified Baseline Commit:** `7cf8fc1725951d8306248c4298f0558a70f3e1a5`  
**Scope:** Live-Market Acceptance Gate for `AC-1-L01` through `AC-1-L05` & Paper Execution Monitoring  
**Safety Protocol:** Simulated paper trading only. No live broker orders permitted or enabled.

---

## 1. Operating Rules & Guardrails

1. **Market-Closed Integrity:** When the market is closed, criteria `AC-1-L01` through `AC-1-L05` remain strictly **`NOT TESTED`**. Live evidence must never be fabricated, simulated, or assumed from offline unit tests or empty database states.
2. **Outcome Separation:** A query or script executing without errors verifies **`VALIDATION_LOGIC: PASS`**, but does NOT prove data quality. If evaluated database rows or ticks are 0, data evidence must be marked **`DATA_CHECK_INCONCLUSIVE`** or **`NOT TESTED`**, never `PASS`.
3. **No Artificial Fault Injection in Live Trading:** Do not sever WebSocket connections, drop network interfaces, or inject synthetic ticks into live broker feeds to force event triggers. If natural events (e.g. network disconnect or spot move across ATM boundary) do not occur during the observation window, mark the criterion **`NOT TESTED`** with the legitimate operational reason recorded.
4. **Zero Live Orders & No Equity Normalizer Edits:** All paper trading runs in simulated taker mode against `fno_paper_trade_ledger`. The equity normalizer (`market/normalizers/kite.py`) must remain completely untouched.

---

## 2. Required Services & Pre-Flight Health Checks

All background services must be verified running and healthy prior to 09:14:00 IST.

### Service 1 — PostgreSQL Database
- **Startup:** Managed via system service (`systemctl start postgresql` or local brew service)
- **Health Check Command:**
  ```bash
  venv/bin/python manage.py check --database default && venv/bin/python manage.py check --database telemetry
  ```
- **Expected Outcome:** `System check identified no issues (0 silenced).`

### Service 2 — Redis Server (Cache & Stream Buffer)
- **Startup:** Managed via system service (`redis-server` or brew service)
- **Health Check Command:**
  ```bash
  venv/bin/python -c '
  from django.core.cache import cache
  cache.set("health_ping", "PONG", 10)
  assert cache.get("health_ping") == "PONG", "Redis cache unreachable!"
  print("Redis health: PONG (operational)")
  '
  ```
- **Expected Outcome:** `Redis health: PONG (operational)`

### Service 3 — Django Web Server
- **Startup Command:**
  ```bash
  venv/bin/python manage.py runserver 127.0.0.1:8000
  ```
- **Health Check Command:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/
  ```
- **Expected Outcome:** HTTP `200` or `302` response.

### Service 4 — Celery Worker
- **Startup Command:**
  ```bash
  venv/bin/python -m celery -A config worker -l info
  ```
- **Health Check Command:**
  ```bash
  venv/bin/python -m celery -A config inspect ping
  ```
- **Expected Outcome:** `-> celery@<hostname>: OK`

### Service 5 — Celery Beat Scheduler
- **Startup Command:**
  ```bash
  venv/bin/python -m celery -A config beat -l info
  ```
- **Health Check Command:**
  Confirm active terminal output or process status (`pgrep -fl "celery -A config beat"`).

### Service 6 — Frontend Development Server (Optional for Ingestion, Required for UI)
- **Startup Command:**
  ```bash
  cd frontend && npm run dev
  ```
- **Health Check Command:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/
  ```
- **Expected Outcome:** HTTP `200` response.

### Service 7 — Live Ticker Ingestion Daemon (Launch at 09:14:45 IST)
- **Authoritative Command:**
  ```bash
  venv/bin/python manage.py run_intraday_ticker --enable-fno --snapshot-interval 60
  ```
- **Health Check / Startup Anchor:**
  Verify startup logs in daemon terminal:
  - `F&O option ingestion enabled (--enable-fno). Initialized FnoTickerConsumer.`
  - `Connecting to Kite WebSocket (wss://ws.kite.trade)...`
  - `Universe reconciled: +22 subscribed, -0 unsubscribed. Active tokens: 22`
  - `[HEARTBEAT] Ticks Received: ... | Feed: FRESH ... | F&O Active: 22`

---

## 3. Pre-Market Verification Window (09:08 – 09:14 IST)

Execute these checks before market open:

```bash
# 1. Verify fresh Zerodha Kite master instruments (< 24h old)
venv/bin/python manage.py shell -c '
from pathlib import Path
from datetime import datetime, timezone
master = Path("data/universe/kite_instruments_master.csv")
assert master.exists(), "Master CSV missing!"
age_h = (datetime.now(timezone.utc) - datetime.fromtimestamp(master.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600.0
assert age_h < 24.0, f"Master is stale ({age_h:.1f}h)!"
print(f"Instrument Master Fresh: age={age_h:.1f}h")
'

# 2. Verify active Kite login credentials
venv/bin/python -c '
from market.services.kite_credentials import KiteCredentialService
assert KiteCredentialService.get_api_key() and KiteCredentialService.get_valid_access_token(), "Missing Kite credentials!"
print("Kite authentication: VALID")
'

# 3. Verify zero migrations pending
venv/bin/python manage.py makemigrations --check --dry-run
```

---

## 4. Live Acceptance Verification Checklist (`AC-1-L01` through `AC-1-L05`)

Execute the following verification queries in a separate terminal during the live market observation window (**09:15 – 09:45 IST**).

---

### `AC-1-L01` — Equity Isolation Guarantee

* **Target Window:** 09:15 – 09:45 IST  
* **Objective:** Ensure NFO option tokens do not contaminate equity database tables (`market_ohlcvbar` and `market_stockintradaycontext`) or equity state managers.
* **Exact Read-Only Query:**
  ```bash
  venv/bin/python manage.py shell -c '
  from market.models import OHLCVBar, StockIntradayContext
  from django.utils import timezone
  import datetime

  now = timezone.now()
  start_window = now - datetime.timedelta(minutes=30)

  contaminated_bars = OHLCVBar.objects.filter(
      instrument__symbol__startswith="NIFTY26",
      timestamp__gte=start_window
  ).count()

  contaminated_contexts = StockIntradayContext.objects.filter(
      instrument__symbol__startswith="NIFTY26",
      timestamp__gte=start_window
  ).count()

  print("=== AC-1-L01: EQUITY ISOLATION AUDIT ===")
  print(f"Contaminated equity bars (market_ohlcvbar): {contaminated_bars}")
  print(f"Contaminated stock contexts (market_stockintradaycontext): {contaminated_contexts}")

  assert contaminated_bars == 0, f"CONTAMINATION: {contaminated_bars} NFO bars in equity table!"
  assert contaminated_contexts == 0, f"CONTAMINATION: {contaminated_contexts} NFO contexts in equity table!"
  print("OUTCOME: PASS (0 contaminated records in equity storage)")
  '
  ```
* **Expected Result & Pass/Fail Condition:**
  - `contaminated_bars == 0` AND `contaminated_contexts == 0`.
  - **PASS:** Zero contaminated records while F&O ingestion is actively receiving ticks.
  - **FAIL:** Any count $> 0$.
* **Evidence to Save:** Record counts, query timestamp, and daemon tick count.
* **Distinguishing Missing Data vs. Legitimate Zero:**
  - If F&O ingestion has received 0 ticks (e.g. daemon not running or disconnected), an equity count of 0 is **`INCONCLUSIVE / NOT TESTED`**, not a pass.
  - To record `PASS`, daemon logs must confirm active F&O ticks received (`F&O Ticks: > 0`).

---

### `AC-1-L02` — Continuous Option-Bar Persistence & Interval Coverage

* **Target Window:** 09:20 – 09:45 IST (after at least 5 completed 1m bars)  
* **Objective:** Verify 1-minute bars in `fno_option_ohlcvbar` roll up continuously across all active contracts with valid OHLC, non-null volume, and unambiguous open interest semantics.
* **Exact Read-Only Query:**
  ```bash
  venv/bin/python manage.py shell -c '
  from fno.models import OptionOHLCVBar
  from django.utils import timezone
  from zoneinfo import ZoneInfo
  import datetime

  ist = ZoneInfo("Asia/Kolkata")
  now = timezone.now()
  window_start = now - datetime.timedelta(minutes=15)

  bars = OptionOHLCVBar.objects.filter(
      timestamp__gte=window_start,
      timeframe="1m"
  ).order_by("timestamp")

  total_bars = bars.count()
  tokens = set(bars.values_list("instrument_token", flat=True))
  
  duplicates = 0
  seen_slots = set()
  ohlc_errors = 0
  vol_errors = 0
  valid_oi = 0
  zero_oi = 0
  unpopulated_oi = 0

  for b in bars:
      key = (b.instrument_token, b.timestamp)
      if key in seen_slots:
          duplicates += 1
      seen_slots.add(key)

      if not (b.high >= b.open and b.high >= b.close and b.low <= b.open and b.low <= b.close and b.open > 0 and b.close > 0):
          ohlc_errors += 1
      if b.volume is None or b.volume < 0:
          vol_errors += 1

      if b.oi_status == "VALID":
          valid_oi += 1
          assert b.open_interest is not None and b.open_interest > 0
      elif b.oi_status == "ZERO_ACTIVITY":
          zero_oi += 1
          assert b.open_interest == 0
      elif b.oi_status == "UNPOPULATED":
          unpopulated_oi += 1
          assert b.open_interest is None

  print("=== AC-1-L02: OPTION BAR PERSISTENCE AUDIT ===")
  print(f"Total Bars in 15m window: {total_bars} across {len(tokens)} contracts")
  print(f"Duplicates: {duplicates} | OHLC Errors: {ohlc_errors} | Vol Errors: {vol_errors}")
  print(f"OI Data Quality: VALID={valid_oi}, ZERO_ACTIVITY={zero_oi}, UNPOPULATED={unpopulated_oi}")

  if total_bars == 0:
      print("DATA_EVIDENCE: DATA_CHECK_INCONCLUSIVE (0 bars in window)")
      print("STATUS: NOT TESTED")
  elif duplicates == 0 and ohlc_errors == 0 and vol_errors == 0 and len(tokens) >= 20:
      print("DATA_EVIDENCE: DATA_CHECK_PASS")
      print("STATUS: PASS")
  else:
      print("DATA_EVIDENCE: DATA_CHECK_FAIL")
      print("STATUS: FAIL")
  '
  ```
* **Expected Result & Pass/Fail Condition:**
  - `duplicates == 0`, `ohlc_errors == 0`, `vol_errors == 0`, active tokens $\approx 22$.
  - **PASS:** Complete 1m bars persisted without duplicate slots or OHLC violations.
  - **FAIL:** Duplicate bars, missing volume, or OHLC hierarchy violations.
* **Evidence to Save:** Total bars count, distinct token count, OI breakdown (`VALID`, `ZERO_ACTIVITY`, `UNPOPULATED`), and timestamp boundaries.
* **Distinguishing Missing Data vs. Legitimate Zero:**
  - **Volume:** `volume == 0` is valid zero trading activity. `volume is None` is invalid.
  - **Open Interest:**
    - Genuine zero OI = `open_interest == 0` with `oi_status = "ZERO_ACTIVITY"`.
    - Missing/unpopulated OI = `open_interest is None` with `oi_status = "UNPOPULATED"`. Missing OI must NEVER be saved as 0.
    - Positive OI = `open_interest > 0` with `oi_status = "VALID"`.
  - **Missing Bar Slots:** If a minute has no bar for a token, check daemon tick count. If contract-level tick telemetry indicates zero trades in that minute, it is legitimate inactivity; otherwise if ticks were received but no bar was generated, it is a pipeline drop.

---

### `AC-1-L03` — Reconnect & Resubscription Recovery within $\le 5.0\text{s}$

* **Target Window:** 09:15 – 09:45 IST  
* **Objective:** Observe daemon resilience during transient network disconnects or broker resets; verify reconnection and resubscription of all 22 active contracts completes within $\le 5.0\text{s}$.
* **Exact Command / Read-Only Log Check:**
  ```bash
  # Check daemon log or stdout for watchdog reconnect events
  grep -E "\[WATCHDOG\] Reconnected successfully" logs/intraday_ticker.log | tail -n 5
  ```
* **Expected Result & Pass/Fail Condition:**
  - If a natural disconnect occurs:
    - Log anchor: `[WATCHDOG] Reconnected successfully on attempt #1. Restored 22 instrument subscriptions.`
    - Elapsed reconnect duration $\le 5.0\text{s}$.
    - Bars spanning the gap are flagged `is_partial_bar = True`.
    - **PASS:** Successful recovery within 5.0s target.
  - If NO natural disconnect occurs:
    - **NOT TESTED (NO_NATURAL_DISCONNECT).** Do NOT artificially kill connections or inject network faults in live market.
* **Evidence to Save:** Log snippet with timestamps of disconnect detection and reconnect completion, count of restored subscriptions.
* **Distinguishing Missing Data vs. Legitimate Zero:**
  - 0 reconnect events is a **legitimate zero** (stable network). It must be reported as `NOT TESTED (NO_NATURAL_DISCONNECT)`, NOT a failure.

---

### `AC-1-L04` — Live Quote Snapshots with Valid Classifications & Age $\le 3.0\text{s}$

* **Target Window:** 09:15 – 09:45 IST  
* **Objective:** Verify quote snapshots in `fno_option_quote_snapshot` report authentic exchange matching engine timestamps, dynamic age $\le 3.0\text{s}$, and tamper-proof execution eligibility.
* **Exact Read-Only Query:**
  ```bash
  venv/bin/python manage.py shell -c '
  from fno.models import OptionQuoteSnapshot
  from django.utils import timezone
  import datetime
  from decimal import Decimal

  now = timezone.now()
  window_start = now - datetime.timedelta(minutes=5)

  recent_quotes = OptionQuoteSnapshot.objects.filter(
      received_wall_clock_utc__gte=window_start
  ).order_by("-received_wall_clock_utc")

  distinct_tokens = set(recent_quotes.values_list("instrument_token", flat=True))
  print(f"=== AC-1-L04: QUOTE SNAPSHOT AUDIT ===")
  print(f"Evaluating {recent_quotes.count()} snapshots across {len(distinct_tokens)} tokens")

  valid_fresh = 0
  stale_count = 0
  future_skew = 0
  invalid_status = 0
  eligibility_mismatches = 0

  for token in distinct_tokens:
      q = recent_quotes.filter(instrument_token=token).first()
      if q.exchange_time_status != "VALID" or q.exchange_timestamp_utc is None:
          invalid_status += 1
          continue

      age = (now - q.exchange_timestamp_utc).total_seconds()
      if age < 0.0:
          future_skew += 1
      elif age <= 3.0:
          valid_fresh += 1
      else:
          stale_count += 1

      expected_eligible = (
          q.exchange_time_status == "VALID"
          and q.quote_status == "VALID"
          and not q.is_stale
          and not q.is_locked
          and not q.is_crossed
          and q.best_bid is not None and q.best_bid > Decimal("0.0")
          and q.best_ask is not None and q.best_ask > q.best_bid
          and 0.0 <= age <= 3.0
      )
      if q.is_execution_eligible != expected_eligible:
          eligibility_mismatches += 1

  print(f"Fresh (<=3.0s): {valid_fresh} | Stale (>3.0s): {stale_count} | Future: {future_skew} | Invalid: {invalid_status}")
  print(f"Eligibility Inconsistencies: {eligibility_mismatches}")

  if recent_quotes.count() == 0:
      print("STATUS: NOT TESTED (Zero quote snapshots in window)")
  elif valid_fresh > 0 and future_skew == 0 and eligibility_mismatches == 0:
      print("STATUS: PASS")
  else:
      print("STATUS: FAIL")
  '
  ```
* **Expected Result & Pass/Fail Condition:**
  - `valid_fresh > 0`, `future_skew == 0`, `eligibility_mismatches == 0`.
  - **PASS:** Fresh quotes with verified exchange timestamps $\le 3.0\text{s}$ and strictly consistent `is_execution_eligible`.
  - **FAIL:** Any quote with negative exchange age, unverified timestamp marked eligible, or age $> 3.0\text{s}$ marked eligible.
* **Evidence to Save:** Fresh/stale/future breakdown, evaluated token count, eligibility mismatch count.
* **Distinguishing Missing Data vs. Legitimate Zero:**
  - If snapshot count is 0, the result is **`DATA_CHECK_INCONCLUSIVE / NOT TESTED`**.
  - A zero bid (`best_bid == 0.00`) is a valid microstructure state classified as `quote_status="ZERO_BID"` with `is_execution_eligible=False`. Missing book is `EMPTY_BOOK`.

---

### `AC-1-L05` — Dynamic ATM Detection & Desired-Universe Reconciliation

* **Target Window:** 09:15 – 09:45 IST  
* **Objective:** Verify seamless universe rebalancing maintaining exactly 22 active contracts (11 CE + 11 PE) when the underlying spot crosses the ATM strike boundary ($\pm 25.0$ pts on NIFTY).
* **Exact Command / Read-Only Check:**
  ```bash
  # 1. Check spot movement range during session
  venv/bin/python manage.py shell -c '
  from market.models import OHLCVBar
  from django.utils import timezone
  import datetime

  now = timezone.now()
  bars = OHLCVBar.objects.filter(
      instrument__symbol="^NSEI",
      timestamp__gte=now - datetime.timedelta(minutes=30)
  ).order_by("timestamp")

  if not bars.exists():
      print("Spot bars: NONE (Inconclusive)")
  else:
      closes = [b.close for b in bars]
      start_atm = round(float(closes[0]) / 50.0) * 50
      end_atm = round(float(closes[-1]) / 50.0) * 50
      print(f"Spot range: {min(closes)} to {max(closes)}")
      print(f"Start ATM: {start_atm} -> Current ATM: {end_atm}")
      if start_atm != end_atm:
          print("ATM boundary crossing detected! Check daemon logs for reconciliation anchors.")
      else:
          print("No ATM boundary crossing. Spot remained within strike step.")
  '

  # 2. Check daemon logs for reconciliation anchors
  grep -E "Universe reconciled:" logs/intraday_ticker.log | tail -n 10
  ```
* **Expected Result & Pass/Fail Condition:**
  - If natural spot move crosses an ATM strike boundary:
    - Log anchor: `Universe reconciled: +2 subscribed, -2 unsubscribed. Active tokens: 22 (ATM: ...)`
    - Total active tokens remains exactly 22 at all times.
    - **PASS:** Seamless handover without drop in contract count.
  - If spot does NOT cross the ATM strike boundary:
    - **NOT TESTED (PENDING_MARKET_MOVEMENT).** Do NOT simulate or inject fake spot ticks.
* **Evidence to Save:** Spot high/low/range, ATM strike start/end, daemon reconciliation log lines with tokens added/removed.
* **Distinguishing Missing Data vs. Legitimate Zero:**
  - 0 reconciliation events when spot has not moved $> 25$ points is a **legitimate zero**. It must be documented as `NOT TESTED (PENDING_MARKET_MOVEMENT)`, not a failure.

---

## 5. Post-Session Verification & Shutdown (09:45 IST)

1. Send `SIGINT` (Ctrl+C) to `run_intraday_ticker`.
2. Verify clean shutdown log anchors:
   - `Shutdown signal received. Stopping live ticker...`
   - `Flushed N remaining F&O option bars on shutdown.`
   - `SESSION SUMMARY: Elapsed: ...s | Equity Ticks: ... | F&O Ticks: ... | F&O Bars: ... | F&O Quotes: ...`
3. Verify PID lock file removed:
   ```bash
   test ! -f /tmp/nomad_intraday_ticker.pid && echo "PID lock cleared successfully."
   ```
4. Collect all executed query outputs and log snippets into the live acceptance evidence report.

---

## 6. Pre-Execution Verification Sign-Off

- [x] All 5 checks use read-only queries and log inspections.
- [x] Zero schema modifications or pending migrations required.
- [x] Zero live broker orders enabled or permitted.
- [x] Equity normalizer (`market/normalizers/kite.py`) completely unmodified.
- [x] Exact command syntax and expected outputs verified against baseline code.
