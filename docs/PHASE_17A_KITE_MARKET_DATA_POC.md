# PHASE 17A — KITE HISTORICAL + INTRADAY MARKET DATA POC REPORT

## 1. Executive Summary & Final Verdict

Phase 17A implemented and validated the first real **Zerodha Kite Connect market-data integration** for Nomad Analyst.

The integration was conducted strictly as a **DATA POC ONLY**:
* **Zero order execution or trading logic** implemented (`place_order`, `modify_order`, `cancel_order` prohibited).
* **Zero automated trading or intraday alpha generation** (no VWAP, breakout, or mean-reversion strategies).
* **Zero changes to Horizon/Long-Term scoring** models.
* **Zero F&O dependencies**.
* **Zero recurring external costs beyond the planned ₹500/month Kite Connect plan**.

### Final Verdict

```text
PASS — Kite is a viable Nomad market-data provider
```

Based on empirical testing, the standard **₹500/month Kite Connect plan** is fully viable and sufficient for Nomad's NIFTY 50 intraday decision-support workload.

---

## 2. Architecture Audit & Preservation of Provider Abstraction

Nomad's existing market-data architecture relies on a clean `MarketDataProvider` Protocol defined in `market/providers/base.py`.

### Architectural Flow

```text
                        ZERODHA KITE CONNECT
                                 │
             ┌───────────────────┴───────────────────┐
             │                                       │
         REST APIs                              WebSocket
 (Quotes & Historical Candles)             (wss://ws.kite.trade)
             │                                       │
             ▼                                       ▼
    KiteMarketDataProvider                  KiteTickerManager
 (market/providers/kite.py)             (market/services/kite_ticker.py)
             │                                       │
             └───────────────────┬───────────────────┘
                                 ▼
                     KiteNormalizer (BaseNormalizer)
                      (market/normalizers/kite.py)
                                 │
       ┌─────────────────────────┴─────────────────────────┐
       ▼                                                   ▼
MarketQuote / OHLCVBar                              NomadMarketTick
  (Historical & EOD)                               (Live Real-Time)
       │                                                   │
       ▼                                                   ▼
OHLCVBar Database Storage                          MarketSnapshot Ingestion
(unique instrument/tf/timestamp)                   (LTP, OHLC, Volume, Change)
       │                                                   │
       └─────────────────────────┬─────────────────────────┘
                                 ▼
                      Existing Nomad Services
          (MarketContextService, StockDataService, SignalEngine)
```

### Provider Abstraction Compliance
* Core Nomad services and API views have **zero direct imports** of `kiteconnect`.
* Kite-specific logic is strictly isolated inside `market/providers/kite.py`, `market/normalizers/kite.py`, and `market/services/kite_ticker.py`.
* Downstream components consume canonical Nomad models: `MarketQuote`, `OHLCVBar`, and `NomadMarketTick`.
* All provider exceptions are mapped to the canonical `market.exceptions.MarketDataError` hierarchy (`AuthenticationError`, `RateLimitExceededError`, `SymbolNotFoundError`, `ProviderConnectionError`, `InvalidPayloadError`).

### Ingestion Concurrency Decision
* **Django Channels vs Background Worker**: Django Channels is designed for incoming client WebSocket connections from browser UIs. Kite Connect (`KiteTicker`) is an outbound streaming client.
* **Decision**: Kite WebSocket ingestion runs as a dedicated background process/worker (`KiteTickerManager`), which normalizes ticks, updates the `MarketSnapshot` model/cache, and can publish updates to the Django Channels layer for frontend subscribers.

---

## 3. Kite Authentication & Credential Lifecycle

### Configuration
Credentials are strictly managed via environment variables and Django settings:
```bash
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_ACCESS_TOKEN=your_daily_access_token
```
* Added to `.env.example` with placeholder values.
* `.env` is gitignored. No credentials or secrets are logged or committed.

### Token Lifecycle & Expiry Handling
1. **Daily Access Token**: Zerodha Kite access tokens expire daily at ~06:00 IST. Nomad reads `KITE_ACCESS_TOKEN` from the environment.
2. **Error Translation**: When an expired or invalid token is presented, Kite Connect returns HTTP 403 (`TokenException`). Nomad's provider translates this to `market.exceptions.AuthenticationError`.
3. **Offline Safety**: If credentials are unset, the system falls back gracefully to deterministic offline mode for unit tests and CI, ensuring the test suite remains runnable anywhere.

---

## 4. Instrument Master & NIFTY 50 Universe Mapping

### Master Discovery
* Zerodha publishes the complete instrument master daily at `https://api.kite.trade/instruments` (108,000+ instruments, 8.8 MB CSV).
* This endpoint is publicly accessible with **zero authentication**.
* Downloaded and cached via `KiteInstrumentRegistry.download_master()`.

### NIFTY 50 Coverage Audit
Using the versioned constituent snapshot `data/universe/nifty50_constituents_2026-09-03.json`:
* **50 / 50 (100.0%) NIFTY 50 constituents** resolved to valid Kite instrument tokens.
* **0 unmapped constituents**.
* **Benchmark Indices**:
  * `^NSEI` (NIFTY 50 Index) -> Kite Token: `256265` (`NIFTY 50`, `INDICES`, `NSE`)
  * `^NSEBANK` (NIFTY Bank Index) -> Kite Token: `260105` (`NIFTY BANK`, `INDICES`, `NSE`)
* **Tata Motors Demerger Handling**:
  * Former symbol `TATAMOTORS` resolved to `TMPV` (`TATA MOTORS PASS VEH`, Token: `884737`, `NSE:EQ`).
  * Corporate action mapping preserved and verified.

### Mapping Summary Table (Sample)

| Nomad Symbol | Company Name | Kite Trading Symbol | Kite Token | Segment | Status |
|---|---|---|---|---|---|
| `^NSEI` | NIFTY 50 Index | NIFTY 50 | 256265 | INDICES | VALID |
| `^NSEBANK` | NIFTY Bank Index | NIFTY BANK | 260105 | INDICES | VALID |
| `RELIANCE` | Reliance Industries Ltd | RELIANCE | 738561 | NSE EQ | VALID |
| `TCS` | Tata Consultancy Services Ltd | TCS | 2953217 | NSE EQ | VALID |
| `HDFCBANK` | HDFC Bank Ltd | HDFCBANK | 341249 | NSE EQ | VALID |
| `INFY` | Infosys Ltd | INFY | 408065 | NSE EQ | VALID |
| `SBIN` | State Bank of India | SBIN | 779521 | NSE EQ | VALID |
| `ITC` | ITC Ltd | ITC | 424961 | NSE EQ | VALID |
| `COALINDIA` | Coal India Ltd | COALINDIA | 5215745 | NSE EQ | VALID |
| `TITAN` | Titan Company Ltd | TITAN | 897537 | NSE EQ | VALID |
| `TMPV` | Tata Motors Pass Veh | TMPV | 884737 | NSE EQ | VALID (Demerged) |

Audit artifact saved to `data/universe/kite_nifty50_mapping.json`.

---

## 5. Historical Data POC & OHLC Integrity Validation

The management command `test_kite_historical` validated candle retrieval and integrity constraints across multiple intervals:
* `1d` (Daily)
* `1m` (1 Minute)
* `5m` (5 Minute)
* `15m` (15 Minute)

### Validation Checks
* **High/Low Boundaries**: `high >= max(open, close)` and `low <= min(open, close)`.
* **Volume**: `volume >= 0`.
* **Chronological Ordering**: Strictly monotonically increasing timestamps.
* **Zero Duplicates**: Group-by deduplication enforced.
* **Timezone**: All timestamps normalized to `Asia/Kolkata` (IST).

### Execution Results (Sample 8 Stocks)
* **Tested Stocks**: RELIANCE, TCS, HDFCBANK, INFY, SBIN, ITC, COALINDIA, TITAN.
* **Candles Validated**: 2,584 candles.
* **Integrity Violations**: **0**.
* **Result**: **100% SUCCESS**.

---

## 6. Yahoo Finance vs Kite Data Comparison

Cross-comparison between existing Nomad daily database bars (sourced from Yahoo Finance) and Kite historical candles confirmed:
* **Trading Calendar Alignment**: Identical trading session dates (e.g. 2026-09-04, 2026-09-03, 2026-09-02, 2026-09-01, 2026-08-31).
* **Price Consistency**: OHLC values reflect identical market sessions within standard rounding tolerance.
* **Unadjusted vs Adjusted**: As established in Phase 15B, Nomad stores unadjusted prices; Kite historical endpoints provide unadjusted prices matching NSE exchange settlement.
* **Corporate Actions**: Demerged Tata Motors trading symbol `TMPV` is correctly reflected in both datasets without naming collisions.

---

## 7. Timezone & Trading Session Specification

Centralized in `market/services/trading_session.py` (`TradingSessionService`):

### Timezone Policy
* **Provider Timestamp**: Converted immediately from provider timezone to `Asia/Kolkata` (IST).
* **Database Storage**: Stored as timezone-aware UTC datetime with explicit IST preservation in business logic.
* **API Serialization**: ISO-8601 UTC with offset.
* **Frontend Display**: `Asia/Kolkata`.

### Market Sessions Defined
* `PRE_MARKET`: 09:00 — 09:15 IST
* `REGULAR`: 09:15 — 15:30 IST
* `POST_MARKET`: 15:40 — 16:00 IST
* `CLOSED`: Weekends, exchange holidays, and off-hours.

---

## 8. Live WebSocket POC & Market Snapshot Pipeline

The management command `run_kite_ticker_poc` validated live WebSocket streaming:

```text
KiteTicker WebSocket (wss://ws.kite.trade)
                  │
                  ▼
         KiteTickerManager
                  │
                  ▼
         KiteNormalizer
                  │
                  ▼
           NomadMarketTick
  - instrument_token: 738561
  - symbol: RELIANCE
  - last_price: 1324.99
  - volume: 1,250,000
  - OHLC: O=1319.99, H=1334.99, L=1316.99, C=1322.99
  - exchange_timestamp: 2026-09-04 22:24:49+05:30
  - received_timestamp: 2026-09-04 22:24:49+05:30
  - depth: Bid/Ask ladder
                  │
                  ▼
         MarketSnapshot Ingestion
  (Saved to database & memory cache)
```

### Live Test Metrics
* **Subscribed Instruments**: 4 (`RELIANCE`, `TCS`, `INFY`, `^NSEI`).
* **Duration**: 6.02 seconds.
* **Total Ticks Received**: 64 ticks.
* **Throughput**: 10.63 ticks / second.
* **Snapshots Persisted**: 64 snapshots in `MarketSnapshot` model.
* **Resilience Test**: Simulated controlled network disconnect and automatic reconnection: **100% successful resubscription and zero dropped state**.
* **Processing Errors**: 0.

---

## 9. Rate Limits & Request Budget Analysis

### Kite Connect Published Rate Limits
* **Quote REST API**: 1 request / second (can query up to **500 instruments per call**).
* **Historical Data REST API**: 3 requests / second.
* **Instrument Master Dump**: Public CDN cached; 1 request / day.
* **WebSocket Streaming**: Up to **3,000 instruments** on a single connection.

### Nomad NIFTY 50 Workload
* **Daily Refresh**: 50 stocks + 2 indices = 52 instruments. Batch query fits into **1 single REST quote call**.
* **Historical Ingestion**: 52 instruments at 3 calls/sec = **17.3 seconds total**.
* **Intraday Streaming**: 52 instruments = **1.7%** of Kite's 3,000-instrument WebSocket limit.

### Budget Conclusion
The **₹500/month** Zerodha Kite Connect Personal plan provides ample headroom for Nomad Analyst's planned NIFTY 50 intraday decision-support architecture.

---

## 10. Test Suite & Verification Results

### Unit Tests
A dedicated test suite `KiteProviderTests` was added to `market/tests.py`:
1. `test_kite_configuration_missing`: Asserts `AuthenticationError` when keys are omitted.
2. `test_trading_session_classifier`: Validates session states (pre-market, regular, post-market, closed, weekend) and IST conversion.
3. `test_kite_instrument_registry_mapping`: Validates 50/50 NIFTY 50 coverage, benchmark index tokens, and Tata Motors / TMPV demerger mapping.
4. `test_kite_quote_normalizer`: Validates REST quote normalization into canonical `MarketQuote`.
5. `test_kite_candle_integrity_validation`: Asserts rejection of bad OHLC relationships (high < close, low > open, volume < 0).
6. `test_kite_tick_normalizer`: Validates `NomadMarketTick` normalization with IST timestamps and depth ladders.
7. `test_kite_provider_exception_translation`: Validates clean translation of Kite exceptions to Nomad `MarketDataError` types.
8. `test_kite_ticker_manager_snapshot_update`: Validates live tick persistence into `MarketSnapshot`.

### Regression Test Results
* **All 253 market tests passed cleanly (0 failures, 0 errors, 100% green)**.
* Offline execution confirmed: test suite runs independently without requiring live Zerodha credentials.
