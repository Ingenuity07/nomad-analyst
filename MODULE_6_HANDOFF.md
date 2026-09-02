# MODULE 6 HANDOFF — MARKET REGIME & CROSS-MARKET INTELLIGENCE

## 1. Overview & Deliverables
Module 6 adds a deterministic market context layer explaining the broader environment in which Indian equities trade. This context is exposed to the LLM agent via tools and scheduled periodic snapshotting.

### Deliverables Completed
1.  **Database Model Layer**:
    *   Created `MarketContextSnapshot` in [`market/models.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/models.py) to save aggregated JSON snapshots.
    *   Added database migrations (`0007_marketcontextsnapshot`, `0008_alter_instrument_exchange`).
2.  **YFinance Ticker Normalization**:
    *   Updated `yfinance.py` provider to support index/global symbols (e.g. starting with `^` or containing `=`) without appending `.NS`.
    *   Expanded regex validation pattern in `yfinance.py` normalizer to accept index/currency ticker structures.
3.  **Context Service Engine**:
    *   Implemented `MarketContextService` in [`market/services/context_service.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/context_service.py).
    *   Calculates index trend regimes (bullish, bearish, sideways), daily breadth (AD ratios, SMA participation, new 52-week highs/lows), sector rankings (returns, relative performance, momentum shifts), global cues (latest closes, day percent changes, staleness checks), and cross-market Pearson correlations (20-day rolling correlation of Nifty vs S&P, USD/INR, Crude Oil).
4.  **Celery Scheduling**:
    *   Registered `refresh_market_context` task in [`market/tasks.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/tasks.py) to periodic fetch and update context assets.
    *   Bootstrapped database scheduler migration (`0009_bootstrap_market_context_periodic_task`).
5.  **Agent Tool Registration**:
    *   Added `GetMarketContextTool` to [`llm/tools/implementations/market_tool.py`](file:///Users/shivamsingh/personal/nomad-analyst/llm/tools/implementations/market_tool.py).
    *   Registered the tool in [`market/services/market_research_service.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/market_research_service.py) and [`chat/orchestrator/single_agent.py`](file:///Users/shivamsingh/personal/nomad-analyst/chat/orchestrator/single_agent.py).
6.  **Subsystem Verification**:
    *   Wrote and executed a full suite of subsystem tests verifying all calculations, timezone/staleness checks, and tool integrations in [`market/tests.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/tests.py).

---

## 2. Verification Results
Run the django test suite:
```bash
venv/bin/python manage.py test market
```
**Result**: 30/30 tests passed successfully.

---

## 3. How to Consume the Context
The LLM agent can call the `get_market_context` tool to retrieve the aggregated snapshot:
```json
{
  "as_of": "2026-08-20T10:00:00+00:00",
  "universe": "NIFTY50",
  "index_regimes": {
    "^NSEI": {
      "symbol": "^NSEI",
      "status": "active",
      "close": 12444.7,
      "trend": "bullish",
      "volatility": "normal",
      "momentum": "positive",
      "indicators": {"rsi14": 57.07, "sma50": 12035.89, "sma200": 11264.83, "vol20": 0.0148}
    }
  },
  "breadth": { ... },
  "sector_rankings": [ ... ],
  "global_cues": { ... },
  "cross_market_features": { ... }
}
```
This is fully PIT-safe and ensures look-ahead safety during research queries.
