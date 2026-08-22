# Module 1 — Market Data Foundation

This document defines the implementation specifications, design decisions, and data boundaries of the **Market Data Foundation** module (Module 1).

---

## 1. Objective
Establish a reliable, production-ready, deterministic Market Data Plane that interfaces with a real market data provider to fetch, normalize, and store Indian stock market equities quotes and historical snapshots.

---

## 2. Scope
*   **Real Market Data Integration**: Integrate with Yahoo Finance Chart API.
*   **Decoupled Normalization**: Translate raw provider JSON outputs into canonical Pydantic model representation (`MarketQuote`).
*   **Operational Database Catalogs**: Maintain `Company`, `Instrument`, and `MarketSnapshot` tables.
*   **Idempotency & Data Quality**: Block duplicate entries at identical timestamps and enforce quality bounds (negative prices, invalid high/low bounds, stale observations, future timestamps).
*   **Error wrapping**: Map HTTP and connection timeouts to custom, descriptive exceptions (`exceptions.py`).
*   **Tool execution**: Bind the `get_stock_snapshot` tool to the new service layer.

---

## 3. Non-Goals
*   No technical indicator calculations (RSI, MACD, Moving Averages).
*   No buy/sell signals or recommendation rules.
*   No options, futures, or derivatives data structures.
*   No microservices, TimescaleDB migrations, or frontend work.

---

## 4. Existing Architecture Reused
*   **`market` App boundary**: Maintained the Django app, its admin pages, and database tables.
*   **`MarketDataProvider` Protocol**: Kept the base interface definition.
*   **`MarketQuote` Schema**: Kept the canonical Pydantic parameters.
*   **`ToolExecutor` & `ToolRegistry`**: Reused the LLM execution boundary.

---

## 5. Provider Selected & Why
*   **Selected Provider**: Yahoo Finance Chart API (`query1.finance.yahoo.com/v8/finance/chart/`).
*   **Rationale**: 
    1. Supports all major Indian equities and indices on the National Stock Exchange (NSE, `.NS` suffix) and Bombay Stock Exchange (BSE, `.BO` suffix).
    2. Accessible deterministically via standard HTTP `GET` requests without authentication keys, keeping deployment simple.
    3. Returns pricing, daily highs/lows, volumes, previous close values, and timestamp parameters.

---

## 6. Provider Capabilities
*   Fetches current regular market prices, day highs, day lows, opening prices, trading volumes, and close values.
*   Supports multiple historical ranges (`1d`, `5d`, `1y`, `max`) and resolutions (`1m`, `1d`).

---

## 7. Provider Limitations
*   Rate limiting: Public endpoints are subject to throttling (HTTP 429).
*   Structure: Suffix mapping (`.NS`/`.BO`) is mandatory to fetch Indian equities.

---

## 8. Canonical Schemas
Standardized via `market.providers.base.MarketQuote` Pydantic model:
*   `symbol` (clean uppercase string)
*   `exchange` (`NSE` or `BSE`)
*   `price` (Decimal LTP)
*   `open_price`, `high`, `low`, `close` (Decimals)
*   `volume` (Integer)
*   `previous_close` (Decimal)
*   `change` & `change_percent` (Decimals)
*   `timestamp` (timezone-aware datetime)

---

## 9. Data Flow
```text
LLM/User request
  ↓
get_stock_snapshot(symbol) [Tool]
  ↓
ToolExecutor (redacts secrets / audits latency)
  ↓
MarketService
  ↓
YFinanceMarketProvider (GET request) ──► Raw JSON response
  ↓
YFinanceNormalizer (maps variables, runs quality filters) ──► MarketQuote
  ↓
MarketService Persistence (checks duplicates, creates snapshot)
```

---

## 10. Company vs Instrument Model
*   **Company**: Represents the business entity (e.g. *Infosys Limited*). Sector, industry, and description belong here.
*   **Instrument**: Represents the listed tradeable contract. Symbol and exchange define uniqueness (e.g. `INFY:NSE`).

---

## 11. MarketSnapshot Semantics
A `MarketSnapshot` represents a point-in-time pricing and volume observation for an `Instrument`. It is designed to act as a historical log for charts and signal valuations.

---

## 12. Persistence
*   Upserts `Company` using `short_name`.
*   Upserts `Instrument` using symbol and exchange.
*   Appends a new point-in-time `MarketSnapshot` referenced to the `Instrument`.

---

## 13. Idempotency
To prevent the creation of duplicate snapshots if the same quote is retrieved multiple times in the same minute:
*   `MarketService` queries PostgreSQL: `MarketSnapshot.objects.filter(instrument=instrument, timestamp=canonical_quote.timestamp).exists()`.
*   If a record matches, database write is skipped.

---

## 14. Error Handling
Mapped inside `market/exceptions.py` to decouple provider exceptions from Django:
*   Connection Timeout/Refused ──► `ProviderConnectionError`
*   HTTP 401 / 403 / Credentials ──► `AuthenticationError`
*   HTTP 429 / Throttling ──► `RateLimitExceededError`
*   HTTP 404 / Empty Results ──► `SymbolNotFoundError`
*   Corrupt JSON / Parse Errors ──► `InvalidPayloadError`

---

## 15. Stale Data Handling
*   Observations with a quote timestamp older than 7 days are considered stale and blocked during normalization.
*   Prevents outdated closed-market records from polluting active trading logic.

---

## 16. Celery Behavior
*   `update_instrument_quotes`: Celery Beat cron task running every 30 minutes to query active Instruments, update prices, and append snapshots.

---

## 17. Tool Integration
*   The `GetStockSnapshotTool` validates input symbol syntax, queries the service, and formats a structured JSON response.

---

## 18. Testing
*   Tested fully offline using mocked requests (`market/tests.py`).
*   Covers provider responses, normalization validation gates, service idempotency, and tool executions.

---

## 19. Known Limitations
*   Public Yahoo Finance endpoints can rate limit during heavy bulk downloads.
*   Tickers must be correctly formatted to prevent mapping failures.

---

## 20. Future Extensions
*   Adding bulk historical bar loaders (loading 10 years of daily data).
*   Integrating secondary backup APIs (such as NSE Scrapers or AlphaVantage) to fallback on rate limits.
