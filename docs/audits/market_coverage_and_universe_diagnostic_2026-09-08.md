# NOMAD ANALYST — MARKET COVERAGE & SCANNER UNIVERSE DIAGNOSTIC INVESTIGATION

**Date of Investigation:** September 8, 2026 — 21:30 IST  
**Audit Mode:** READ-ONLY ARCHITECTURAL DIAGNOSTIC  
**Target Stocks Audited:** PC Jeweller, Hikal, IFCI, MV Electro, Hindustan Copper, Pudumjee Paper Products, Vodafone Idea, Lumino Industries  

---

## 1. Executive Summary

During the September 8, 2026 live market session, multiple high-momentum movers across the broader National Stock Exchange (NSE) were flagged externally, including:
- **PC Jeweller** (`PCJEWELLER`)
- **Hikal** (`HIKAL`)
- **IFCI** (`IFCI`)
- **MV Electro** (`MVELECTRO`)
- **Hindustan Copper** (`HINDCOPPER`)
- **Pudumjee Paper Products** (`PDMJEPAPER`)
- **Vodafone Idea** (`IDEA`)
- **Lumino Industries** (`LUMINO`)

However, none of these stocks appeared in Nomad Analyst's Intraday Scanner or Opportunities Feed.

### Key Finding:
This behavior is **not** a defect in signal detection, eligibility rules, score calculation, or API serialisation. 

Instead, the investigation identified that **the Nomad Analyst intraday pipeline is structurally and hardcoded to operate exclusively on the NIFTY 50 large-cap universe**:
1. **Universe Hardcoding:** The ticker daemon (`run_intraday_ticker`), state manager (`IntradayStateManager`), and opportunity engine (`IntradayOpportunityEngine`) strictly query `universe_memberships__universe__name="NIFTY50"`.
2. **Database Omission:** The local PostgreSQL database contains **only 52 instruments** (the 50 NIFTY 50 constituents plus `^NSEI` and `^NSEBANK` index benchmarks). None of the 8 audited stocks exist in the `Instrument` or `Company` tables.
3. **Zero WebSocket Subscription:** Because `run_intraday_ticker` only loads tokens for active NIFTY 50 database records, Zerodha Kite was never asked to stream ticks for these broader-market stocks.
4. **Zero Pipeline Ingestion:** With no incoming ticks, no 1-minute bars were formed, no intraday state was registered in Redis, and no evaluations were performed.

In summary, the stocks were excluded at **Step 0 (Universe Definition)**. The engine never evaluated and rejected them—they were never in the scanner's operational scope.

---

## 2. Current Scanner Universe

| Dimension | Value in Production | Reference / Evidence |
|:---|:---|:---|
| **Active Scanner Universe** | **`NIFTY50` exclusively** | `market/management/commands/run_intraday_ticker.py:69` |
| **Active Instruments Subscribed to Kite** | **52 instruments** (50 equities + 2 indices) | Subscribed via `ws.subscribe(tokens)` |
| **Total Instruments in Database** | **52 instruments** | `Instrument.objects.count() == 52` |
| **Total Companies in Database** | **52 companies** | `Company.objects.count() == 52` |
| **`NIFTY100` Active Members** | **0** | `Universe.objects.get(name="NIFTY100").memberships.count() == 0` |
| **`NIFTY500` Active Members** | **0** | `Universe.objects.get(name="NIFTY500").memberships.count() == 0` |
| **Total NSE Equities in Kite Master** | **10,262 instruments** | `data/universe/kite_instruments_master.csv` |
| **ETFs Included** | **No (0%)** | Filtered out; only common equity (`EQ`) |
| **Mid-Caps & Small-Caps Included** | **No (0%)** | Only top 50 large-caps in NIFTY 50 |

---

## 3. Stock-by-Stock Diagnostic Table

| Stock Name | In Instrument Master (Kite)? | In Scanner Universe? | Subscribed to Live Data? | Received Ticks Today? | Candles Generated? | Signal Generated? | Passed Eligibility? | Appeared in Opportunities? | Exact Reason for Exclusion |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **PC Jeweller** (`PCJEWELLER`) | **YES** (Token `7455745`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **Hikal** (`HIKAL`) | **YES** (Token `2475009`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **IFCI** (`IFCI`) | **YES** (Token `381697`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **MV Electro** (`MVELECTRO`) | **YES** (Token `195685633`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **Hindustan Copper** (`HINDCOPPER`) | **YES** (Token `4592385`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **Pudumjee Paper Products** (`PDMJEPAPER`) | **YES** (Token `3936513`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **Vodafone Idea** (`IDEA`) | **YES** (Token `3677697`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |
| **Lumino Industries** (`LUMINO`) | **YES** (Token `195974145`) | **NO** | **NO** | **NO** (0 ticks) | **NO** (0 bars) | **NO** | **NO** | **NO** | Excluded at universe selection (Not in NIFTY 50, not seeded in DB). |

---

## 4. Pipeline Flow & Exclusion Point

```
[1] Zerodha Kite Master (10,262 NSE Equities)
         │  (All 8 stocks exist here with active tokens)
         ▼
[2] Nomad Database Seeding (bootstrap_nifty50_universe)
         │  ❌ EXCLUSION POINT 1: Hardcoded to nifty50_constituents_2026-09-03.json
         │  ❌ The 8 stocks were never inserted into Instrument/Company tables
         ▼
[3] Ticker Daemon Startup (run_intraday_ticker)
         │  ❌ EXCLUSION POINT 2: Filter: universe_memberships__universe__name="NIFTY50"
         │  ❌ Only 50 equity tokens + 2 index tokens sent in ws.subscribe()
         ▼
[4] Live WebSocket Ingestion (KiteTickerManager)
         │  ❌ Zerodha never transmits ticks for unsubscribed symbols
         ▼
[5] In-Memory / Redis State (live_tick:<SYM>, stock_state:<SYM>)
         │  ❌ Zero keys exist in Redis for outside stocks
         ▼
[6] Bar Aggregation (IntradayBarAggregator)
         │  ❌ 0 ticks -> 0 OHLCV candles generated
         ▼
[7] State Manager Context Building (compute_current_context)
         │  ❌ Loads state only for symbols in _symbol_sector_map (NIFTY 50)
         ▼
[8] Signal & Eligibility Engine (IntradayOpportunityEngine)
         │  ❌ Evaluates constituent_contexts (0 to 50 items)
         │  ❌ Outside stocks never reach eligibility/signal check
         ▼
[9] API & Frontend Presentation (/api/v1/intraday/opportunities/)
         │  ❌ Returns ranked opportunities solely from NIFTY 50
         │  ❌ Single lookup GET /api/v1/intraday/opportunities/PCJEWELLER/ returns 404
```

---

## 5. Root Cause Analysis

The current behavior stems from three explicit architectural decisions made during the foundation phase:

1. **Bootstrap Script Designed for NIFTY 50 Sandbox:**  
   The initial bootstrapping command `market/management/commands/bootstrap_nifty50_universe.py` reads a static snapshot file (`data/universe/nifty50_constituents_2026-09-03.json`) containing exactly 50 companies. No broader market seeding command was implemented.

2. **Hardcoded Universe Queries across Runtime Services:**  
   Runtime code hardcodes the string `"NIFTY50"` in four critical locations:
   - `market/management/commands/run_intraday_ticker.py` (line 69):
     ```python
     instruments = Instrument.objects.filter(
         universe_memberships__universe__name="NIFTY50",
         universe_memberships__is_active=True,
         is_active=True,
     )
     ```
   - `market/services/intraday_state_manager.py` (line 82):
     ```python
     instruments = Instrument.objects.filter(
         universe_memberships__universe__name="NIFTY50",
         universe_memberships__is_active=True,
         is_active=True
     ).select_related("company")
     ```
   - `market/services/intraday_state_manager.py` (line 209):
     ```python
     instruments = Instrument.objects.filter(
         universe_memberships__universe__name="NIFTY50",
         universe_memberships__is_active=True
     )
     ```
   - `market/services/intraday_state_manager.py` (line 367):
     ```python
     instruments_map = {inst.symbol: inst for inst in Instrument.objects.filter(universe_memberships__universe__name="NIFTY50")}
     ```

3. **Unpopulated Broader Universes:**  
   `Universe` models exist in PostgreSQL for `NIFTY100` and `NIFTY500`, but both have zero active memberships.

---

## 6. Components Responsible for the Limitation

1. **`market/management/commands/run_intraday_ticker.py`:** Restricts WebSocket subscriptions to active NIFTY 50 members.
2. **`market/services/intraday_state_manager.py`:** Restricts sector loading, cache fallback reloading, and context assembly to NIFTY 50.
3. **`market/management/commands/bootstrap_nifty50_universe.py`:** Hardcoded constituent source: `CONSTITUENT_FILE = "data/universe/nifty50_constituents_2026-09-03.json"`.
4. **`data/universe/kite_nifty50_mapping.json`:** Holds mappings for only 50 stocks + 2 indices.
5. **`market/views.py` (`IntradayOpportunitiesAPIView`):** Bounded by the 50 stock contexts produced by `IntradayStateManager`.

---

## 7. Recommended Next Steps for Universe Expansion

When expanding coverage beyond NIFTY 50 (e.g. to NIFTY 500 or broader momentum universes):

1. **Broad Universe Ingestion Command:**  
   Implement a management command (e.g., `python manage.py bootstrap_universe --universe NIFTY500` or `sync_kite_instruments --universe NIFTY500`) to parse constituents from the cached master CSV (`data/universe/kite_instruments_master.csv`) and create corresponding `Company`, `Instrument`, and `UniverseMembership` records in PostgreSQL.
2. **Parametric Ticker Subscriptions:**  
   Update `run_intraday_ticker.py` to accept `--universe <NAME>` (e.g. `NIFTY500`), defaulting to `NIFTY50` if unspecified.  
   *(Zerodha Kite WebSocket allows up to 3,000 instrument subscriptions per connection, easily accommodating all 500 stocks).*
3. **Dynamic State Manager Sector Mapping:**  
   Modify `IntradayStateManager._load_universe_sectors()` to resolve sectors dynamically for the target active universe rather than hardcoding `"NIFTY50"`.
4. **Sector Metadata Enrichment:**  
   Ensure newly ingested mid-cap/small-cap stocks have assigned sector names (via Screener or NSE sector classifications) so relative strength, sector alignment, and sector-diversified ranking function accurately.
