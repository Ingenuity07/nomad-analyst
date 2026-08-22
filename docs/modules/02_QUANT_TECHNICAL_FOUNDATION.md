# Module 2 — Quant & Technical Analysis Foundation

This document defines the architectural specifications, implementation details, and design decisions of the **Quant & Technical Analysis Foundation** module (Module 2).

---

## 1. Architecture
The system follows a strict, layered flow from raw data inputs to derived, trace-auditable technical indicators:

```text
OHLCV Data Ingestion
        ↓
    TA-Lib Adapter
        ↓
TechnicalFeatureEngine (Numpy/Pandas computations)
        ↓
Derived Technical Features (TechnicalFeature Model)
        ↓
Query Service (MarketService)
        ↓
Deterministic Agent Tools (get_historical_ohlcv, get_technical_features)
```

---

## 2. OHLCV Source
*   **Source**: Yahoo Finance Chart API (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`).
*   **Adjustments**: Stored price bars are **unadjusted** (representing raw transaction values traded at the time of the bar). Unadjusted values are standard for simple stock research.
*   **Persistence Model**: `OHLCVBar` stores open, high, low, close, volume, timeframe, and timezone-aware timestamps.

---

## 3. Feature Architecture
*   **DecoupledDerived Layer**: Indicators are never stored directly as columns on `OHLCVBar`. Instead, they are saved as records in the `TechnicalFeature` table.
*   **Schema Fields**:
    *   `instrument`: ForeignKey to `Instrument`.
    *   `timeframe`: Timeframe string (e.g. `1d`).
    *   `timestamp`: Corresponding bar timestamp.
    *   `name`: Indicator name (e.g. `RSI_14`, `SMA_20`).
    *   `parameters`: JSON dictionary.
    *   `param_key`: Sorted serialized parameter string for composite indexing (e.g. `period=14`, `fast=12;slow=26;signal=9`).
    *   `value`: Calculated numeric decimal value (max_digits=16, decimal_places=6).

---

## 4. TA-Lib Integration
TA-Lib is the official production technical-indicator calculation engine. It is wrapped behind the `TechnicalFeatureEngine` class inside `market/services/feature_engine.py`. The rest of the application never calls TA-Lib directly.

---

## 5. TA-Lib Version
*   **Python Wrapper Version**: `TA-Lib==0.7.1` (compiled against Homebrew C library `ta-lib 0.7.1`).

---

## 6. Indicators & Custom Calculations
The engine calculates:
*   **TREND**: Simple Moving Average (SMA 20, 50, 200), Exponential Moving Average (EMA 20, 50, 200).
*   **MOMENTUM**: Relative Strength Index (RSI 14), Moving Average Convergence Divergence (MACD 12/26/9 line, signal, and histogram).
*   **VOLATILITY**: Average True Range (ATR 14), rolling volatility (20-day standard deviation of daily returns).
*   **VOLUME**: Volume SMA 20, relative volume (current volume / volume SMA 20).
*   **PRICE**: Daily return (`(close - prev_close)/prev_close`), cumulative return (`(close - first_close)/first_close`), rolling 20-day high/low, and distance from rolling high/low.

---

## 7. Parameters Configuration
All periods are centralized in the `DEFAULT_INDICATOR_CONFIG` specification dictionary in [`market/services/feature_engine.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/feature_engine.py) to keep them clean and easily configurable.

---

## 8. Warmup Handling
*   Indicators require historical data to calculate. During the warmup period, values are set to `None` in the database.
*   No fabricated or extrapolated values are written.

---

## 9. Look-Ahead Prevention
*   Bars are sorted chronologically (`timestamp ASC`) before processing.
*   Calculations are strictly causal (only past data is accessed to resolve index `i`), ensuring look-ahead safety for future backtesting.

---

## 10. Persistence & Idempotency
*   **Database Writes**: Saved in bulk using `bulk_create` to avoid N+1 queries.
*   **Idempotency**: Deletes existing features for the target instrument and timeframe before saving new calculations, preventing constraint errors.

---

## 11. Incremental Calculation
*   Feature calculation runs chronologically. Future daily updates recalculate features for the target instrument using a 1-year historical bar history to satisfy warmup limits.

---

## 12. Testing
*   Tested fully offline using mocked requests (`market/tests.py`).
*   Covers validation checks, historical bar ingestion, TA-Lib calculations, look-ahead safety, and determinism.

---

## 13. Limitations
*   Requires a minimum of 200 bars for a valid 200-day moving average calculation.
*   Holidays/halts yield gaps which are skipped during validation.

---

## 14. Future Integrations
*   **VectorBT**: VectorBT will fetch these persisted `TechnicalFeature` tables to test and evaluate quant trading rules.
*   **NautilusTrader**: NautilusTrader will serve as the event-driven live trading loop execution container.
*   **Qlib**: Will ingest features to train quantitative machine learning prediction models.
