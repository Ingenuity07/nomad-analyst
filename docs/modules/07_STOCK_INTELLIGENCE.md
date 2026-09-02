# Module 7: Stock Intelligence & Opportunity Discovery

## Objective
The Stock Intelligence and Opportunity Discovery layer fuses deterministic data (Quotes, Technical Indicators, Fundamentals, News Events, and Sector Context) to score, classify, and rank stocks within a given Universe for distinct investment horizons without look-ahead bias.

---

## 1. Database Model Design

### `Universe`
Defines stock lists (e.g. `NIFTY50`, `NIFTY100`, `NIFTY500`).
*   `name`: Unique string identifier.
*   `description`: Descriptive text.
*   `is_active`: Boolean status flag.

### `UniverseMembership`
Resolves temporal instrument mappings.
*   `universe`: ForeignKey to `Universe`.
*   `instrument`: ForeignKey to `Instrument`.
*   `added_at`: DateTime of membership addition.
*   `removed_at`: Nullable DateTime of membership removal.
*   `is_active`: Boolean flag indicating active membership.

### `StockOpportunitySnapshot`
Factual representation of scored and classified opportunities at a Point-In-Time.
*   `instrument`: ForeignKey to `Instrument`.
*   `as_of`: Target Point-In-Time timestamp.
*   `universe`: Scanned universe label.
*   `horizon`: Targeted investment horizon (`DELIVERY_SWING` or `LONG_TERM`).
*   `opportunity_type`: Classified type (e.g. `TRENDING`, `MOMENTUM`, etc.).
*   `component_scores`: Breakdowns of technical, fundamental, sector, market, and news metrics.
*   `final_opportunity_score`: Decimal score (0 to 100).
*   `supporting_features`: JSON map containing underlying close price, technical parameters, and lists of pros.
*   `risks`: JSON list containing risks (cons).
*   `data_quality`: JSON map detailing availability (e.g. `COMPLETE`, `STALE`, `PARTIAL`).

---

## 2. Investment Horizons & Scoring Configuration

### Horizons
*   **`DELIVERY_SWING`**: Focuses on mid-term trends (1-4 weeks). Heavily weighted on technical analysis and sector trends.
*   **`LONG_TERM`**: Focuses on structural quality (6-12 months). Heavily weighted on fundamental health.
*   **`INTRADAY`**: Currently flagged as `NOT READY`.

### Default Configuration Weights
| Component | `DELIVERY_SWING` Weight | `LONG_TERM` Weight |
|---|---|---|
| Technical | 40% | 10% |
| Fundamental | 20% | 50% |
| Sector | 20% | 20% |
| Market Alignment | 10% | 10% |
| News & Events | 10% | 10% |

---

## 3. Point-in-Time (PIT) & Look-Ahead Safety
All feature retrievals filter strictly with date inequalities:
1.  **OHLCV / Technicals**: Timestamp `timestamp <= as_of`.
2.  **Fundamentals**: Date `period_end <= as_of.date()`. Derived metrics are matched with visible income statements to prevent future statement leakage.
3.  **News & Events**: Published date `published_at <= as_of`.

---

## 4. Batch Query Optimization
To prevent N+1 performance degradation:
1.  **Select Related**: Pre-fetches `Company` models using `select_related('company')` on instruments.
2.  **Window Aggregations**: Finds the maximum timestamps using Django `.values().annotate(Max())` grouped by instrument, then loads record sets in a single multi-in query.
3.  **Batch Write**: Employs `transaction.atomic()`, running a single `delete` and `bulk_create` for calculated opportunity snapshots.

---

## 5. Celery Periodic Tasks
A daily runner `run_daily_opportunity_scan` periodically scans all active universes and horizons, populating `StockOpportunitySnapshot` records in the database.
