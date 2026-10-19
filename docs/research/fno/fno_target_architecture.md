# Nomad Analyst — F&O Target Architecture Blueprint (Reconciled)

**Document Reference:** `docs/research/fno/fno_target_architecture.md`  
**Revision Date:** 2026-10-17  
**Auditor:** Quantitative Researcher & Systems Architect  
**Status:** RATIFIED ARCHITECTURAL BLUEPRINT — RECONCILED WITH CANONICAL SPECIFICATION  

---

## 1. Architectural Philosophy: The Third Pillar Isolation Principle

Nomad Analyst maintains three distinct analytical pillars:
1. **Intraday Equity Momentum Engine:** Operates on the 50 NIFTY equities + 4 benchmarks, aggregating 1m/5m/15m bars, calculating sector breadth across 14 sectors, and generating intraday equity opportunities.
2. **Horizon Structural Engine:** Operates on daily bars and fundamental metrics, producing multi-week swing and value recommendations.
3. **F&O Options Pillar (Strategy Lab):** Operates on high-frequency derivative ticks, preserving Open Interest, market depth, Black-Scholes Greeks, and managing independent paper-trading ledgers.

### Canonical Specification Reference:
For exact Pydantic schemas, database DDL, strategy interfaces, and evaluation matrices, consult the canonical specification:  
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

### The Isolation Mandates:
- **No Shared State Mutation:** Option ticks must **never** be passed into `IntradayStateManager.on_tick()`. Pushing derivative symbols into the equity state manager would contaminate market breadth, advance/decline ratios, and sector momentum.
- **No Shared Table Bloat:** Option bars must be stored in a dedicated table (`fno_option_ohlcvbar`), preventing write amplification and indexing degradation in the primary `market_ohlcvbar` table (which holds 87,503 equity bars).
- **Dedicated Normalization:** Derivative ticks must be normalized by an isolated `OptionNormalizer` in `fno/`, handling Open Interest, sparse depth, and `exchange="NFO"`. The existing equity normalizer (`market/normalizers/kite.py`) must remain completely untouched.

---

## 2. Four Core Architectural Pillars

### A. Shared Core Intelligence Engine
A reusable source of validated, timestamped market features emitted as immutable `OptionFeatureSnapshot` contracts consumed by all strategy modules:
- Kite market-data ingestion and isolated NFO routing.
- Instrument metadata, daily master parsing, and authoritative expiry resolution.
- Dynamic subscription management (ATM $\pm 5$ strikes).
- Option ticks, 1-minute OHLCV bars, Open Interest, quotes, and market depth (120 bytes).
- Market regime, trend, momentum, volatility (India VIX), technical features, and market breadth.
- Options analytics (Black-Scholes IV, Delta, Gamma, Theta, Vega), quote freshness, and data-quality monitoring.
- Standardized, reproducible feature snapshots with explicit missing/stale data semantics.

### B. Extensible Instrument Universe
- **Initial Configuration Scope:** NIFTY index options, CE and PE, buying only.
- **Architectural Extensibility:** Instrument identity, strike resolvers, and subscription managers use generic parameters (`underlying_symbol`, `strike_step`, `lot_size`, `tick_size`). Additional indices (`BANKNIFTY`, `FINNIFTY`) or eligible option instruments can be introduced via configuration without altering core engine logic.
- **Capture Window Boundary:** ATM $\pm 5$ strikes is an **initial capture window**, not a complete option chain. Full-chain surface metrics (such as complete market skew or full PCR) are not claimed from this partial window.

### C. Independent Strategy Modules
- Each strategy is an isolated class inheriting from `BaseStrategy`.
- Strategies are independently configurable, versioned, and enabled or disabled.
- Every strategy consumes the exact same validated `OptionFeatureSnapshot` contract and produces standardized `OptionSignal` instances.
- Zero private market-data connections; zero shared state or position leakage between strategies.

### D. Shared Paper-Trading & Evaluation Framework
- Each strategy maintains an independent simulated trade ledger and performance history (`fno_paper_trade_ledger`).
- Realistic quote-based taker fills: `Best Ask + Slippage` on buy entries, `Best Bid - Slippage` on exits.
- Defensive microstructure rejection gates: stale quotes (>3.0s), crossed quotes (`Best Bid >= Best Ask`), and excessive spreads (>2.5%).
- Exact effective-dated transaction fees: NSE Circular `NSE/FA/73061` (effective 1 March 2026: ₹3,552.99 exchange fee + ₹0.01 IPFT = ₹3,553/crore), STT (effective 1 April 2026: 0.15% on sell premium), 18% GST on (Brokerage + Exchange/IPFT + SEBI).
- **One-Month Prospective Evaluation Lab:** Multi-strategy parallel execution over 20–22 trading sessions, evaluated across a 7-dimensional decision matrix (expectancy, friction drag ratio, net profit factor, win rate, drawdown, and statistical uncertainty). No winner selected on total P&L alone.

---

## 3. Decoupled Pipeline & Component Architecture

```mermaid
graph TD
    subgraph Market_Layer [Shared Broker Layer]
        KAUTH["KiteCredentialService (Shared 2FA Session)"]
        KWS["KiteTicker WebSocket Core"]
    end

    subgraph Dispatcher_Layer [Packet Router]
        ROUTER{"Token Segment Router"}
        KWS --> ROUTER
    end

    subgraph Equity_Pillar [Existing Intraday Equity Pipeline]
        ROUTER -->|Tokens: Equity & Benchmarks| ENORM["KiteNormalizer (market)"]
        ENORM --> ECACHE["Redis db=1 (live_tick:*)"]
        ENORM --> ESTAT["IntradayStateManager"]
        ESTAT --> EBARS["market_ohlcvbar (PostgreSQL)"]
        ESTAT --> EREC["StockRecommendation"]
    end

    subgraph FNO_Pillar [Isolated F&O Options Pillar (fno/)]
        ROUTER -->|Tokens: NFO Derivatives| ONORM["OptionNormalizer (fno)"]
        ONORM -->|184-byte Full Ticks, OI, Depth| OTICK["OptionMarketTick"]
        OTICK --> OCACHE["Redis db=1 (fno_tick:*)"]
        OTICK --> ODATA["OptionDataCaptureService"]
        ODATA --> OBARS["fno_option_ohlcvbar (PostgreSQL)"]
        
        REG["OptionInstrumentRegistry (fno)"] -->|Authoritative Expiry & Dynamic ATM ±5| ODATA
        REG -->|Subscribes / Unsubscribes| KWS
        
        ODATA --> SNAP["OptionFeatureEngine"]
        SNAP --> OFS["OptionFeatureSnapshot"]
        
        OFS ==> STRAT_A["Strategy A (Isolated)"]
        OFS ==> STRAT_B["Strategy B (Isolated)"]
        
        STRAT_A --> SIGS["Standardized OptionSignal"]
        STRAT_B --> SIGS
        
        SIGS --> EXEC["Shared Paper Execution Engine"]
        EXEC --> LEDGER_A["Independent Ledger (Strategy A)"]
        EXEC --> LEDGER_B["Independent Ledger (Strategy B)"]
    end
```

---

## 4. Detailed Component Specifications

### A. Dedicated Django App Structure (`fno/`)
```
fno/
├── __init__.py
├── apps.py                          # AppConfig: registers FNO signals and cleanup
├── models.py                        # OptionOHLCVBar, OptionFeatureSnapshotModel, PaperTradeLedger
├── services/
│   ├── __init__.py
│   ├── option_registry.py           # OptionInstrumentRegistry: authoritative master parsing
│   ├── strike_resolver.py           # OptionStrikeResolver: dynamic ATM ±K strike resolution
│   ├── option_normalizer.py         # OptionNormalizer: unpacks 184-byte packets (sparse depth, OI)
│   ├── option_data_capture.py       # OptionDataCaptureService: bar aggregation & persistence
│   ├── subscription_manager.py      # OptionSubscriptionManager: manages WebSocket subscriptions
│   ├── feature_engine.py            # OptionFeatureEngine: builds standardized OptionFeatureSnapshot
│   ├── greeks_calculator.py         # Black-Scholes Greeks and Implied Volatility
│   └── paper_execution_engine.py    # PaperExecutionEngine: fills, slippage, and fee deductions
├── strategies/
│   ├── __init__.py
│   ├── base.py                      # BaseStrategy abstract interface and lifecycle
│   └── registry.py                  # StrategyRegistry: registers, configures, and enables modules
├── tasks.py                         # Celery tasks: master reload, bar flush, paper reconciliation
├── tests/
│   ├── __init__.py
│   ├── test_registry.py             # Master authority, holiday roll, strike resolution
│   ├── test_normalizer.py           # Sparse depth (120 bytes), valid zero OI, crossed quotes
│   ├── test_feature_contracts.py    # Snapshot schema reproducibility and missing-data semantics
│   ├── test_strategy_isolation.py   # Strategy modularity, versioning, and zero state leakage
│   └── test_paper_execution.py      # Fill realism, fee schedules, and independent ledgers
```

### B. Option Normalizer Specification (`fno/services/option_normalizer.py`)
Unpacks the 184-byte `MODE_FULL` packet and maps it to a canonical model:
- **Bytes 0–64 (Fixed Quote Fields, 64 bytes):** `instrument_token`, `last_price`, `last_quantity`, `average_price` (exchange session ATP, distinct from Nomad's candle VWAP), `volume_traded`, `buy_quantity`, `sell_quantity`, `open`, `high`, `low`, `close`, `last_trade_time`, `oi`, `oi_day_high`, `oi_day_low`, `exchange_timestamp`.
- **Bytes 64–184 (Market Depth, 120 bytes total):** 10 depth entries of 12 bytes each (5 Buy levels followed by 5 Sell levels), each containing `quantity` (int32, 4b), `price` (int32 / 100.0, 4b, INR), `orders` (int16, 2b, order count), and `padding` (2 bytes protocol alignment).

### C. Market Data Validation & Defensive Normalization Rules
1. **Valid Zero Values:** Out-of-the-money strikes legitimately report `open_interest = 0`, `volume = 0`, or empty bids. The normalizer accepts 0 as a valid numeric state.
2. **Missing / Unpopulated OI:** During pre-open or initial frames, OI may be null. The parser assigns `oi_status = "UNPOPULATED"` without dropping price ticks.
3. **Sparse Depth Handling:** Dynamically handles sparse depth arrays (0 to 5 levels) without index errors.
4. **Stale and Crossed Quotes:** Flag `is_crossed = True` when $\text{Best Bid} \ge \text{Best Ask}$. Flag `is_stale = True` when timestamps remain unchanged for $>3.0$ seconds during trading hours.
5. **Cumulative-Volume Resets:** When `volume_traded < previous_volume`, log a session reset event and recalculate 1-minute volume deltas.
6. **Timestamp Integrity:** Reject ticks with future timestamps ($>2.0$s ahead of system clock) or non-monotonic sequence corruption.

### D. Authoritative Contract Expiry Resolution & Dynamic Strike Management
1. **Instrument Master Authority:** The contract `expiry` field in `kite_instruments_master.csv` is the single source of truth. Weekly contracts follow a Tuesday schedule (shifting to **the previous trading day if Tuesday is a holiday**), but weekday rules never override the broker master.
2. **Dynamic Strike Window:** Fixed 50 index points for NIFTY. Default window $K=5$, providing 11 CE + 11 PE = 22 contracts ($[\text{ATM} - 5 \times 50, \text{ATM} + 5 \times 50]$).
3. **Dynamic Rebalancing:** Rebalancing evaluates every 60 seconds. When $|S_{\text{spot}} - S_{\text{last\_rebalance}}| \ge 50.0$ points, the subscription list updates. Newly entered strikes subscribe in `MODE_FULL`; distant strikes outside the active window unsubscribe (unless held in an active open paper position).
4. **Expiry Rollover:** From 13:00 IST on expiry day, stream Next-Weekly ATM contracts ($K=3$, 14 contracts) concurrently. At 15:30 IST, promote Next-Weekly to Primary Active.

---

## 5. Database Schema: Isolated F&O Tables

```sql
-- Dedicated 1-minute OHLCV + Open Interest Table
CREATE TABLE fno_option_ohlcvbar (
    id BIGSERIAL PRIMARY KEY,
    instrument_token INTEGER NOT NULL,
    tradingsymbol VARCHAR(50) NOT NULL,
    underlying_symbol VARCHAR(20) NOT NULL DEFAULT '^NSEI',
    option_type VARCHAR(2) NOT NULL, -- 'CE' or 'PE'
    strike_price NUMERIC(10, 2) NOT NULL,
    expiry_date DATE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(10, 2) NOT NULL,
    high NUMERIC(10, 2) NOT NULL,
    low NUMERIC(10, 2) NOT NULL,
    close NUMERIC(10, 2) NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    open_interest BIGINT, -- NULL if unpopulated, >= 0 if reported
    vwap NUMERIC(10, 2),
    source VARCHAR(20) NOT NULL DEFAULT 'Kite',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_fno_ohlcv_token_ts ON fno_option_ohlcvbar (instrument_token, timestamp);
CREATE INDEX idx_fno_ohlcv_sym_ts ON fno_option_ohlcvbar (tradingsymbol, timestamp DESC);
CREATE INDEX idx_fno_ohlcv_expiry ON fno_option_ohlcvbar (expiry_date, strike_price);

-- Independent Paper Trade Ledger Table
CREATE TABLE fno_paper_trade_ledger (
    trade_id BIGSERIAL PRIMARY KEY,
    strategy_id VARCHAR(50) NOT NULL,
    strategy_version VARCHAR(20) NOT NULL,
    signal_id UUID NOT NULL,
    instrument_token INTEGER NOT NULL,
    tradingsymbol VARCHAR(50) NOT NULL,
    option_type VARCHAR(2) NOT NULL,
    strike_price NUMERIC(10, 2) NOT NULL,
    expiry_date DATE NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    entry_fill_price NUMERIC(10, 2) NOT NULL,
    entry_slippage NUMERIC(10, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    exit_timestamp TIMESTAMPTZ,
    exit_trigger_reason VARCHAR(30),
    exit_fill_price NUMERIC(10, 2),
    exit_slippage NUMERIC(10, 2),
    gross_pnl NUMERIC(12, 2),
    total_frictions NUMERIC(12, 2),
    net_pnl NUMERIC(12, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fno_ledger_strat ON fno_paper_trade_ledger (strategy_id, status);
CREATE INDEX idx_fno_ledger_ts ON fno_paper_trade_ledger (entry_timestamp DESC);
```

---

## 6. Architectural Verification: Complete Pipeline Isolation

By routing option derivative tokens exclusively through `OptionNormalizer` and `OptionDataCaptureService`:
- `IntradayStateManager` continues processing equity symbols undisturbed.
- `market_ohlcvbar` table is protected from derivative row explosion.
- The existing equity normalizer (`market/normalizers/kite.py`) remains unmodified.
- The F&O pillar can be paused, restarted, or modified without risking equity streaming stability.
- All strategies consume standardized feature contracts and write to independent paper ledgers.
