# Nomad Analyst — F&O Market Data Feasibility, API Specs & Economic Costs (Reconciled)

**Document Reference:** `docs/research/fno/fno_data_feasibility_and_costs.md`  
**Revision Date:** 2026-10-17  
**Auditor:** Quantitative Researcher & Systems Architect  
**Status:** RATIFIED FEASIBILITY ANALYSIS — RECONCILED WITH CANONICAL SPECIFICATION  

---

## 1. Executive Summary & Core Feasibility Verdict

This document provides the technical and financial audit of data sources for Nomad Analyst's **F&O Options Pillar**.

### Canonical Specification Reference:
The full data contracts, feature schemas, strategy interfaces, execution models, and evaluation matrix are authoritatively specified in:  
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

### Key Verified Findings:
1. **Live Options Streaming (Verified Feasible):**  
   Kite WebSocket streaming natively supports NFO derivative contracts in `MODE_FULL` (184 bytes), delivering real-time LTP, market depth (120 bytes: 10 levels of 12 bytes each), and Open Interest (`oi`).
2. **Expired Options Historical Data (Documentation Limitation):**  
   Official Zerodha Kite Connect documentation explicitly limits historical data API access to active (currently traded) contracts. Expired derivative contracts are not documented as available via the historical candle endpoint once settlement concludes.
3. **No Incremental Data Cost (Verified):**  
   Prospective live tick capture, 1-minute bar aggregation, and forward paper trading can be operated within the existing authenticated Kite Connect subscription (~₹500/month) at **₹0 incremental data cost**.
4. **Configurable Dynamic Subscription Scope:**  
   The initial scope of ATM $\pm 5$ strikes (22 contracts) is a **configurable initial capture parameter** centered on dynamic spot price movements, not an immutable design constraint.
5. **Partial Chain Boundary Disclaimer:**  
   The ATM $\pm 5$ window is an **initial capture window**, not a complete option chain. The system does not claim or compute full-chain surface metrics (such as complete market skew or full PCR) from this partial window.
6. **Contract Expiry Authority:**  
   The contract `expiry` field in the daily instrument master CSV is the **authoritative source of truth**. Under current standard schedules, NIFTY weekly options expire on Tuesday (or **the previous trading day if Tuesday is a holiday**), but weekday rules are never the sole determinant.

---

## 2. Kite Connect API Specifications & Capability Matrix

| Data Stream / Endpoint | Official Kite Documentation URL & Section | Available Fields | Update Frequency / Format | Verified Status & Nomad Applicability |
| :--- | :--- | :--- | :--- | :--- |
| **Instruments Master CSV** | `https://kite.trade/docs/connect/v3/instruments/` (`GET /instruments`) | `instrument_token`, `exchange_token`, `tradingsymbol`, `name`, `last_price`, `expiry`, `strike`, `tick_size`, `lot_size`, `instrument_type`, `segment`, `exchange` | Daily update at ~08:00 IST (~9 MB CSV) | **VERIFIED AVAILABLE:** In the inspected local snapshot of `data/universe/kite_instruments_master.csv`, 116,536 total instruments were recorded, including 41,336 NFO instruments and 4,061 active NIFTY options across 18 expiries. This count reflects that specific snapshot; the master must be refreshed daily at runtime. |
| **Live WebSocket Stream (KiteTicker)** | `https://kite.trade/docs/connect/v3/websocket/` (`KiteTicker.MODE_FULL`) | 184-byte binary packet containing fixed quote fields (bytes 0–64: `instrument_token`, `last_price`, `last_quantity`, `average_price` [ATP], `volume_traded`, `buy_quantity`, `sell_quantity`, `ohlc`, `last_trade_time`, `oi`, `oi_day_high`, `oi_day_low`, `exchange_timestamp`) and market depth (bytes 64–184: 120 bytes total, 10 depth entries of 12 bytes each [quantity, price, orders, 2-byte padding]) | Binary WebSocket frames over TLS | **VERIFIED AVAILABLE:** Native WebSocket `MODE_FULL` delivers market depth and Open Interest. Max 3,000 instruments per connection. Existing equity setup subscribes to only 54 tokens. |
| **Active Options Historical REST** | `https://kite.trade/docs/connect/v3/historical/` (`GET /instruments/historical/{token}/{timeframe}`) | `[timestamp, open, high, low, close, volume, oi]` | 1-minute, 5-minute, daily bars for **active (unexpired)** contracts only | **VERIFIED AVAILABLE (Active Only):** Rate limit: 3 requests per second. Returns OHLCV+OI for currently trading contracts. |
| **Expired Options Historical REST** | `https://kite.trade/docs/connect/v3/historical/` (Documentation Note on Derivatives) | *Not documented as available for expired contracts* | N/A | **DOCUMENTED LIMITATION:** Official documentation confirms historical data is available only for active instruments. Historical candles for expired derivative contracts are not available from Kite Connect. |

---

## 3. Kite WebSocket `MODE_FULL` Binary Packet Mapping & Validation Rules

In Zerodha Kite Connect v3, `MODE_FULL` transmits binary packets. For NSE and NFO instruments (derivative contracts), the binary frame unpacks into a 184-byte structure with specific byte offsets, types, scaling factors, and engineering units:

| Byte Offset | Field Name | Data Type | Scaling Factor | Units / Semantic Representation |
| :--- | :--- | :--- | :--- | :--- |
| **0 – 3** | `instrument_token` | `uint32` (4 bytes, Big Endian) | None | Broker instrument identifier |
| **4 – 7** | `last_price` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR (Indian Rupees) |
| **8 – 11** | `last_quantity` | `int32` (4 bytes, Big Endian) | None | Number of shares / option units traded in last trade |
| **12 – 15** | `average_price` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR — **Exchange Session Average Traded Price (ATP)** across all market participants from 09:15 IST. *(Distinct from Nomad's internally calculated bar-level or rolling VWAP)* |
| **16 – 19** | `volume_traded` | `int32` (4 bytes, Big Endian) | None | Cumulative day volume (contracts/units) |
| **20 – 23** | `buy_quantity` | `int32` (4 bytes, Big Endian) | None | Total cumulative quantity across buy book |
| **24 – 27** | `sell_quantity` | `int32` (4 bytes, Big Endian) | None | Total cumulative quantity across sell book |
| **28 – 31** | `open` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR (Day Open Price) |
| **32 – 35** | `high` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR (Day High Price) |
| **36 – 39** | `low` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR (Day Low Price) |
| **40 – 43** | `close` | `int32` (4 bytes, Big Endian) | `/ 100.0` | INR (Previous Session Close) |
| **44 – 47** | `last_trade_time` | `int32` (4 bytes, Big Endian) | None | Unix timestamp in seconds |
| **48 – 51** | `oi` | `int32` (4 bytes, Big Endian) | None | **Open Interest (number of outstanding contracts)** |
| **52 – 55** | `oi_day_high` | `int32` (4 bytes, Big Endian) | None | Session High Open Interest |
| **56 – 59** | `oi_day_low` | `int32` (4 bytes, Big Endian) | None | Session Low Open Interest |
| **60 – 63** | `exchange_timestamp` | `int32` (4 bytes, Big Endian) | None | Unix timestamp in seconds (exchange feed time) |
| **64 – 183** (Total 184 bytes) | `depth` (Market Depth) | `120 bytes` (Bytes 64–184) | Structured | 10 depth entries of 12 bytes each: 5 Buy levels followed by 5 Sell levels. Each entry contains: `quantity` (`int32`, 4b), `price` (`int32` / 100.0, 4b, INR), `orders` (`int16`, 2b, order count), and `padding` (2 bytes protocol alignment). Total depth = $10 \times 12 = 120$ bytes. |

### Robust Market Data Validation & Normalization Rules:
The option parser must NOT assume ideal market states. It must implement defensive data validation:
1. **Valid Zero Values:** Deep OTM strikes or inactive contracts legitimately report `oi = 0`, `volume_traded = 0`, or `quantity = 0` across order levels. Zero is a valid numeric value and must not be treated as an error.
2. **Missing or Null OI:** During pre-open (09:00–09:15 IST) or on newly listed strikes, OI may be null or unpopulated. The normalizer must accept null/zero without rejecting price ticks, assigning `oi_status = "UNPOPULATED"`.
3. **Sparse Depth Handling:** Illiquid contracts frequently report fewer than 5 active bid or ask levels (e.g., 1 bid and 0 asks). The normalizer dynamically handles sparse depth arrays (0 to 5 levels) without raising index out-of-range errors.
4. **Stale Quotes & Crossed Books:**  
   - Flag as an anomaly if $\text{Best Bid} \ge \text{Best Ask}$ (`CROSSED_BOOK`).
   - Flag as stale if the quote timestamp does not advance for $>3.0$ seconds during continuous market hours (`STALE_QUOTE`).
5. **Cumulative-Volume Resets:**  
   - At 09:15:00 IST session start, exchange volume resets to 0.
   - If a tick reports `volume_traded < previous_volume`, log a session reset event and reset 1-minute delta calculations.
6. **Timestamp Integrity & Sequence Checks:**  
   - Reject packets where `exchange_timestamp` is in the future ($>2.0$ seconds ahead of host clock).
   - Reject duplicate ticks where both sequence number/timestamp and price remain unchanged.

---

## 4. Contract Subscription Scope & Extensible Management

### A. Dynamic ATM Resolution
- **Strike Step:** Fixed at 50 index points for NIFTY 50.
- **ATM Formula:**
  $$\text{ATM} = \text{round}\left(\frac{S_{\text{spot}}}{50}\right) \times 50$$
- **Configurable Window ($K$):** Initial default $K=5$, providing $\text{ATM} \pm 5$ strikes (11 CE + 11 PE = 22 contracts).
- **Configurability:** $K$ is set via `FNO_STRIKE_WINDOW` (range 3 to 10).
- **Extensible Architecture:** The subscription manager uses generic asset configuration (`underlying_symbol`, `strike_step`, `lot_size`, `tick_size`). Supporting additional indices (`BANKNIFTY`, `FINNIFTY`) requires only configuration updates, not core engine redesigns.

### B. Dynamic Rebalancing Rationale & Thresholds
- **Rebalancing Trigger Threshold:** `FNO_REBALANCE_SPOT_DELTA = 50.0` points.
- **Technical Rationale for 50-Point Default:** NIFTY 50 option strikes are spaced exactly 50 points apart. A 50-point spot shift represents an exact one-strike migration. Using a threshold smaller than 50 points causes churn from intraday noise; using a larger threshold allows the ATM contract to drift away from the true center.
- **Evaluation Cadence:** Rebalancing logic evaluates every 60 seconds during market hours.

### C. NIFTY Expiry Authority & Calendar Rollover
1. **Instrument Master as Single Source of Truth:**
   - The contract `expiry` date published in the broker instrument master CSV is the definitive legal expiry date.
   - While weekly contracts currently follow a Tuesday schedule (shifting to **the previous trading day if Tuesday is a holiday**), weekday rules are never the sole source of truth.
2. **Rollover Execution:**
   - On the afternoon of the active weekly expiry date (starting at 13:00 IST), the system begins streaming the **Next Weekly Contract** ($K=3$, 14 contracts) concurrently.
   - At 15:30 IST on the expiry date, expired contracts are decommissioned and the Next Weekly becomes the primary active series.

---

## 5. Rate Limits, Connection Management & Reconnection Recovery

### A. Rate Limits & Connection Budget
- **WebSocket Capacity:** Up to 3,000 instruments per connection.
- **Nomad Load:** Equity stream = 54 tokens; Option stream = 22 to 44 tokens; Total $<100$ tokens ($<3.5\%$ of budget).
- **REST Rate Limits:** Historical data API: 3 req/sec; Quote API: 1 req/sec.

### B. Reconnection Resilience
- Automatic reconnection via `KiteTicker` exponential backoff.
- On `on_reconnect`, the active token subscription list is restored in `MODE_FULL` within 5 seconds.
- Stale tick detection flags any active contract lacking updates for $>3.0$ seconds during continuous market hours.

---

## 6. Financial Economics & Cost Comparison

| Data Vendor / Strategy | Setup / Hardware Cost | Monthly Recurring Data Cost | Historical Expired Data Available? | Live 5-Depth & OI Available? | Feasibility Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Zerodha Kite Connect (Current)** | **₹0** (Local Hardware) | **₹0 Incremental** (~₹500/mo existing Kite API fee) | **NO** (Active contracts only) | **YES** (Native WebSocket `MODE_FULL`) | **RECOMMENDED FOR PHASE 1:** Best for prospective live capture and forward paper trading at zero incremental expense. |
| **TrueData (NSE Real-Time + History)** | ₹0 | ~₹3,500 – ₹5,500 / month | **YES** (Multi-year tick/1m history) | **YES** | **DEFERRED:** Not required during data-capture foundation. |
| **GlobalDataFeeds (GDFL)** | ₹0 | ~₹3,000 – ₹4,500 / month | **YES** (Historical expired options) | **YES** | **DEFERRED:** Commercial cost not justified prior to strategy validation. |

---

## 7. Conclusions & Phase 1 Data Scope

1. Live options data capture via Kite Connect is verified feasible at zero incremental cost.
2. Because historical expired option candles are not available, strategy validation relies entirely on forward paper trading with captured data in Phase 5.
3. The instrument master is authoritative for contract expiry dates; sparse depth (120 bytes), valid zero OI, and crossed books are handled defensively.
4. ATM $\pm 5$ strikes is an initial capture window; full-chain surface metrics are not claimed from this partial window.
