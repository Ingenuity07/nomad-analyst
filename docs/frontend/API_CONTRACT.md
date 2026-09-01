# Nomad Analyst — Frontend API Contract Specification

**Version:** 1.0.0  
**Date:** September 1, 2026  
**Status:** Canonical Interface Specification  
**Format:** RESTful JSON over HTTP + WebSocket JSON Streams

---

## 1. Global API Conventions

### Base URL
All REST endpoints are served under `/api/`.

### Date & Time Format
All timestamps are serialized as ISO 8601 strings in UTC (`YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DDTHH:MM:SS+00:00`).

### Monospace Numbers & Decimals
All financial numbers (prices, percentages, ratios, shares) are serialized as standard JSON numbers (`float` / `int`) or `null` when missing. String-encoded numbers are avoided except for raw UUIDs.

### Standard Response Envelope
Successful responses return HTTP `200 OK` (or `201 Created`) with direct data payloads. Paginated list endpoints follow standard DRF format:

```json
{
  "count": 50,
  "next": "/api/opportunities/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Standard Error Envelope
Error responses return appropriate HTTP error codes (`400 Bad Request`, `404 Not Found`, `429 Too Many Requests`, `500 Server Error`) with a standardized error object:

```json
{
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "Stock instrument with symbol 'UNKNOWN' was not found in the universe.",
    "details": {},
    "timestamp": "2026-09-01T13:00:00Z"
  }
}
```

---

## 2. API Inventory: Existing vs Required

| Endpoint | Method | Backend Service Provider | Status | Frontend Consumer View |
|---|---|---|---|---|
| `/api/market/overview/` | `GET` | `MarketContextService` + `MarketService` | **REQUIRED** | `/market` Overview Workspace |
| `/api/market/indices/` | `GET` | `MarketService` | **REQUIRED** | Global Ticker Strip |
| `/api/market/regime/` | `GET` | `MarketContextService` | **REQUIRED** | Market Regime & Breadth Card |
| `/api/market/sectors/` | `GET` | `MarketContextService` | **REQUIRED** | Sector Momentum Matrix |
| `/api/stocks/search/` | `GET` | `Instrument.objects.filter` | **REQUIRED** | Global `Cmd+K` Quick Search |
| `/api/stocks/{symbol}/` | `GET` | `MarketService` + `Instrument` | **REQUIRED** | `/stocks/:symbol` Workspace Header |
| `/api/stocks/{symbol}/ohlcv/` | `GET` | `MarketService.get_historical_ohlcv` | **REQUIRED** | Candlestick Chart Canvas |
| `/api/stocks/{symbol}/technicals/` | `GET` | `MarketService.get_stored_features` | **REQUIRED** | Technical Indicators Matrix |
| `/api/stocks/{symbol}/fundamentals/` | `GET` | `FundamentalDataService` | **REQUIRED** | Financial Statement Tables |
| `/api/stocks/{symbol}/news/` | `GET` | `NewsIntelligenceService` | **REQUIRED** | News & Disclosures Timeline |
| `/api/opportunities/` | `GET` | `OpportunityDiscoveryService` | **REQUIRED** | `/delivery` Opportunity Discovery Grid |
| `/api/opportunities/{symbol}/` | `GET` | `OpportunityDiscoveryService` | **REQUIRED** | Opportunity Detail Drawer |
| `/api/recommendations/` | `GET` | `RecommendationService` | **REQUIRED** | Recommendations Grid & History |
| `/api/recommendations/{id}/` | `GET` | `RecommendationService` | **REQUIRED** | Recommendation Setup Detail |
| `/api/intraday/signals/` | `GET` | `IntradaySignalEngine` + `StockRecommendation` | **REQUIRED** | `/intraday` Live Signal Grid |
| `/api/intraday/{symbol}/readiness/` | `GET` | `IntradayReadinessService` | **REQUIRED** | Intraday Data Health Widget |
| `/api/backtests/` | `GET` | `BacktestRun.objects.all()` | **REQUIRED** | Backtest Run History Table |
| `/api/backtests/run/` | `POST` | `BacktestRunner.run` | **REQUIRED** | Trigger Historical Walk-Forward |
| `/api/backtests/{run_id}/` | `GET` | `BacktestRun.objects.get` | **REQUIRED** | `/backtesting` Performance Dashboard |
| `/api/strategy-performance/` | `GET` | `StrategyPerformanceService` | **REQUIRED** | Live Strategy Analytics Slices |
| `/api/research/query/` | `POST` | `MarketResearchService.research_stock` | **REQUIRED** | `/research` AI Research Studio |
| `/api/providers/` | `GET` | `IntelligentRouter` | **EXISTING** | System Health Monitor |
| `/api/conversations/` | `GET`/`POST`| `chat.views` | **EXISTING** | Legacy Chat Conversations |
| `/ws/market/` | `WS` | Django Channels (`market.consumers`) | **REQUIRED** | Live Signal & Quote Stream |

---

## 3. Comprehensive Endpoint Contracts

### 3.1 Market Overview (`GET /api/market/overview/`)
Aggregated endpoint supplying the complete dashboard payload in a single round-trip.

- **Request:** `GET /api/market/overview/?universe=NIFTY50`
- **Response Schema (`200 OK`):**

```json
{
  "as_of": "2026-09-01T09:45:00Z",
  "universe": "NIFTY50",
  "market_status": {
    "is_open": true,
    "session_phase": "REGULAR",
    "ist_time": "15:15:00",
    "closes_in_seconds": 900
  },
  "indices": [
    {
      "symbol": "^NSEI",
      "name": "NIFTY 50",
      "price": 24850.50,
      "change": 142.30,
      "change_percent": 0.58,
      "volume": 284501200,
      "high": 24910.00,
      "low": 24780.20,
      "prev_close": 24708.20,
      "trend_regime": "BULLISH_TRENDING"
    },
    {
      "symbol": "^NSEBANK",
      "name": "BANK NIFTY",
      "price": 51240.10,
      "change": -85.40,
      "change_percent": -0.17,
      "volume": 124500100,
      "high": 51450.00,
      "low": 51100.00,
      "prev_close": 51325.50,
      "trend_regime": "SIDEWAYS"
    }
  ],
  "global_cues": [
    { "symbol": "^GSPC", "name": "S&P 500", "price": 5648.40, "change_percent": 0.42 },
    { "symbol": "USDINR=X", "name": "USD / INR", "price": 83.92, "change_percent": 0.05 },
    { "symbol": "CL=F", "name": "Crude Oil", "price": 74.20, "change_percent": -1.15 },
    { "symbol": "GC=F", "name": "Gold", "price": 2515.60, "change_percent": 0.32 }
  ],
  "breadth": {
    "coverage_count": 50,
    "advancing": 32,
    "declining": 16,
    "unchanged": 2,
    "advance_decline_ratio": 2.0,
    "participation_score": 64.0,
    "breadth_regime": "STRONG_BULLISH",
    "new_52w_highs": 6,
    "new_52w_lows": 0
  },
  "sector_rankings": [
    { "sector": "Energy", "tier": "STRONGEST", "momentum_score": 88.5, "change_percent": 1.82 },
    { "sector": "Technology", "tier": "IMPROVING", "momentum_score": 74.2, "change_percent": 1.15 },
    { "sector": "Financial Services", "tier": "NEUTRAL", "momentum_score": 52.0, "change_percent": -0.10 },
    { "sector": "FMCG", "tier": "WEAKENING", "momentum_score": 38.4, "change_percent": -0.65 }
  ],
  "recent_market_news": [
    {
      "id": "news_101",
      "headline": "RBI Keeps Repo Rate Steady Amid Robust GDP Growth Outlook",
      "source": "Reuters",
      "published_at": "2026-09-01T08:30:00Z",
      "url": "https://...",
      "sentiment": "POSITIVE"
    }
  ],
  "data_freshness": {
    "status": "LIVE",
    "last_sync_timestamp": "2026-09-01T09:44:59Z"
  }
}
```

---

### 3.2 Stock Historical OHLCV (`GET /api/stocks/{symbol}/ohlcv/`)
Supplies raw candlestick sequences for the TradingView charting engine.

- **Request Parameters:**
  - `timeframe`: `5m` | `15m` | `1h` | `1d` | `1w` (default: `1d`)
  - `start_date`: ISO string e.g. `2026-01-01`
  - `end_date`: ISO string e.g. `2026-09-01`
  - `limit`: Integer (default: 500)
- **Response Schema (`200 OK`):**

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "timeframe": "1d",
  "bars_count": 252,
  "bars": [
    {
      "time": "2025-09-02",
      "open": 1280.00,
      "high": 1295.50,
      "low": 1275.20,
      "close": 1290.10,
      "volume": 8450120
    },
    {
      "time": "2026-09-01",
      "open": 1280.00,
      "high": 1311.80,
      "low": 1280.00,
      "close": 1309.00,
      "volume": 12613543
    }
  ],
  "data_quality": {
    "status": "COMPLETE",
    "gaps_detected": 0
  }
}
```

---

### 3.3 Stock Technical Features (`GET /api/stocks/{symbol}/technicals/`)
Provides computed mathematical indicators.

- **Request:** `GET /api/stocks/RELIANCE/technicals/?timeframe=1d`
- **Response Schema (`200 OK`):**

```json
{
  "symbol": "RELIANCE",
  "timeframe": "1d",
  "as_of": "2026-09-01T09:45:00Z",
  "indicators": {
    "moving_averages": {
      "SMA_20": 1285.40,
      "SMA_50": 1260.10,
      "SMA_200": 1210.50,
      "EMA_9": 1298.20,
      "EMA_21": 1287.60,
      "alignment": "STRONG_BULLISH",
      "above_sma_200": true
    },
    "momentum": {
      "RSI_14": 65.20,
      "RSI_condition": "BULLISH_MOMENTUM",
      "MACD": {
        "macd_line": 14.50,
        "signal_line": 10.20,
        "histogram": 4.30,
        "crossover": "BULLISH"
      },
      "stochastic_oscillator": { "k": 78.4, "d": 72.1 }
    },
    "volatility": {
      "ATR_14": 24.50,
      "ATR_percent": 1.87,
      "bollinger_bands": {
        "upper": 1330.00,
        "middle": 1285.40,
        "lower": 1240.80,
        "bandwidth_percent": 6.94
      }
    },
    "volume_flow": {
      "VWAP": 1298.40,
      "relative_volume_20": 1.45,
      "OBV": 148502000
    },
    "support_resistance": {
      "resistance_1": 1325.00,
      "support_1": 1280.00,
      "distance_from_52w_high_percent": -3.20,
      "distance_from_52w_low_percent": 24.80
    }
  }
}
```

---

### 3.4 Stock Fundamentals (`GET /api/stocks/{symbol}/fundamentals/`)
Returns audited multi-period statements and derived metric ratios.

- **Request:** `GET /api/stocks/RELIANCE/fundamentals/`
- **Response Schema (`200 OK`):**

```json
{
  "symbol": "RELIANCE",
  "company_name": "Reliance Industries Limited",
  "sector": "Energy",
  "industry": "Oil & Gas Refining & Marketing",
  "currency": "INR (Crores)",
  "annual_statements": {
    "periods": ["Mar 2024", "Mar 2025", "Mar 2026"],
    "income_statement": [
      { "metric": "Revenue", "values": [898020.0, 975400.0, 1055780.0] },
      { "metric": "Operating Expenses", "values": [720100.0, 799800.0, 876715.0] },
      { "metric": "EBITDA", "values": [177920.0, 175600.0, 179065.0] },
      { "metric": "Depreciation", "values": [46700.0, 50200.0, 54100.0] },
      { "metric": "Interest / Financing", "values": [21500.0, 23400.0, 24800.0] },
      { "metric": "Profit Before Tax (PBT)", "values": [109720.0, 102000.0, 100165.0] },
      { "metric": "Net Profit (PAT)", "values": [79020.0, 82400.0, 95754.0] },
      { "metric": "EPS in Rs", "values": [58.42, 60.92, 59.69] }
    ]
  },
  "derived_metrics": {
    "profitability": {
      "return_on_equity_percent": 18.2,
      "return_on_capital_employed_percent": 16.4,
      "operating_margin_percent": 16.96,
      "net_profit_margin_percent": 9.07
    },
    "leverage_solvency": {
      "debt_to_equity": 0.42,
      "interest_coverage_ratio": 5.04,
      "current_ratio": 1.25
    },
    "growth_trends": {
      "revenue_growth_yoy_percent": 8.24,
      "pat_growth_yoy_percent": 16.20,
      "eps_growth_3y_cagr_percent": 12.40
    }
  },
  "data_quality": {
    "source": "screener.in",
    "reporting_type": "CONSOLIDATED",
    "last_audited_fiscal_year": 2026
  }
}
```

---

### 3.5 Delivery Opportunities (`GET /api/opportunities/`)
Returns ranked stock opportunities across universes.

- **Request:** `GET /api/opportunities/?universe=NIFTY50&horizon=DELIVERY_SWING`
- **Response Schema (`200 OK`):**

```json
{
  "count": 50,
  "results": [
    {
      "id": "opp_981a",
      "symbol": "RELIANCE",
      "company_name": "Reliance Industries Limited",
      "sector": "Energy",
      "opportunity_type": "MOMENTUM_BREAKOUT",
      "final_opportunity_score": 87.0,
      "component_scores": {
        "technical_score": 97.0,
        "fundamental_score": 56.0,
        "sector_score": 100.0,
        "market_score": 100.0,
        "news_score": 70.0,
        "liquidity_score": 95.0
      },
      "recommendation_signal": "BUY",
      "pros": [
        "Price is trading above 50-day SMA and 200-day SMA",
        "Strong momentum support (RSI=65.2)",
        "Sector 'Energy' is top-performing market leader",
        "Safe leverage structure (Debt/Equity=0.42)"
      ],
      "risks": [
        "Trading near upper resistance boundary (₹1,325.0)"
      ],
      "as_of": "2026-09-01T09:45:00Z"
    }
  ]
}
```

---

### 3.6 Intraday Signals (`GET /api/intraday/signals/`)
Supplies live session intraday recommendations.

- **Request:** `GET /api/intraday/signals/?timeframe=5m&status=ACTIVE`
- **Response Schema (`200 OK`):**

```json
{
  "as_of": "2026-09-01T09:45:00Z",
  "market_session": {
    "is_open": true,
    "session_window": "MID_SESSION"
  },
  "count": 4,
  "results": [
    {
      "id": "rec_0912",
      "symbol": "TCS",
      "company_name": "Tata Consultancy Services",
      "signal": "BUY",
      "setup_type": "VWAP_RECLAIM",
      "timeframe": "5m",
      "confidence": "HIGH",
      "status": "ACTIVE",
      "entry_price": 4150.00,
      "stop_price": 4120.00,
      "target_price": 4210.00,
      "target_2_price": 4250.00,
      "risk_reward_ratio": 2.00,
      "risk_amount_per_share": 30.00,
      "session_window": "MORNING_EXPANSION",
      "expires_at": "2026-09-01T09:45:00Z",
      "created_at": "2026-09-01T04:30:00Z",
      "supporting_reasons": [
        "Clean 5m candle close above intraday VWAP (₹4,142.0)",
        "RSI momentum expanding above 60.0",
        "Volume 1.8x above 20-period average"
      ],
      "invalidation_criteria": "5m candle close below stop level ₹4,120.0"
    }
  ]
}
```

---

### 3.7 Backtest Runner & Results (`POST /api/backtests/run/` & `GET /api/backtests/{run_id}/`)
Executes and inspects deterministic historical walk-forward simulations.

- **Trigger Request (`POST /api/backtests/run/`):**

```json
{
  "universe_name": "NIFTY50",
  "timeframe": "1d",
  "horizon": "DELIVERY_SWING",
  "start_date": "2026-03-01",
  "end_date": "2026-09-01",
  "cost_config": {
    "mode": "REALISTIC",
    "brokerage_percent": 0.03,
    "STT_percent": 0.1,
    "slippage_bps": 5.0
  },
  "ambiguity_policy": "CONSERVATIVE"
}
```

- **Execution Response (`200 OK` from `GET /api/backtests/{run_id}/`):**

```json
{
  "run_id": "NIFTY50_1d_DELIVERY_SWING_2026-03-01_2026-09-01_fa8912",
  "status": "COMPLETE",
  "started_at": "2026-09-01T13:00:00Z",
  "completed_at": "2026-09-01T13:00:01Z",
  "config": { ... },
  "performance_report": {
    "total_signals": 42,
    "triggered": 38,
    "untriggered": 4,
    "wins": 24,
    "losses": 14,
    "ambiguous": 0,
    "win_rate": 0.6316,
    "avg_return_pct": 3.84,
    "median_return_pct": 3.10,
    "avg_r": 1.42,
    "expectancy": 1.42,
    "profit_factor": 2.18,
    "max_drawdown_r": -2.40,
    "avg_holding_bars": 7.2,
    "statistical_warnings": [],
    "by_setup_type": {
      "MOMENTUM_BREAKOUT": { "total": 24, "triggered": 22, "wins": 15, "losses": 7, "win_rate": 0.6818, "avg_r": 1.65 },
      "PULLBACK_SUPPORT": { "total": 18, "triggered": 16, "wins": 9, "losses": 7, "win_rate": 0.5625, "avg_r": 1.12 }
    },
    "by_direction": {
      "BUY": { "total": 42, "triggered": 38, "wins": 24, "losses": 14, "win_rate": 0.6316, "avg_r": 1.42 }
    },
    "data_quality_warnings": [
      "UNAVAILABLE_HISTORICAL: Fundamental data cannot be reconstructed point-in-time.",
      "UNAVAILABLE_HISTORICAL: News/event data cannot be reconstructed point-in-time."
    ]
  }
}
```

---

### 3.8 AI Research Query (`POST /api/research/query/`)
Executes an on-demand multi-step equity research task.

- **Request (`POST /api/research/query/`):**

```json
{
  "symbol": "RELIANCE",
  "question": "Evaluate RELIANCE valuation, earnings momentum, and near-term technical support levels.",
  "depth": "STANDARD",
  "as_of": null
}
```

- **Response (`200 OK`):**

```json
{
  "company": "Reliance Industries Limited",
  "instrument": "RELIANCE",
  "as_of": "2026-09-01T09:44:59Z",
  "summary": "Reliance Industries Limited (RELIANCE) is currently trading at ₹1,309.0, up 2.51% on robust volume of 12.61M shares. Financial fundamentals demonstrate sustained double-digit PAT growth (+16.2% YoY) with low solvency risk (Debt/Equity 0.42). Technicals reflect a strong bullish trend above the 200-day SMA with primary resistance at ₹1,325.0.",
  "market_snapshot": {
    "price": 1309.0,
    "change": 32.0,
    "change_percent": 2.51,
    "volume": 12613543,
    "high": 1311.8,
    "low": 1280.0
  },
  "technical_analysis": "Price is in an established upward channel above both 50-day (₹1,260.1) and 200-day (₹1,210.5) moving averages. RSI at 65.2 confirms positive momentum without reaching extreme overbought thresholds.",
  "fundamental_analysis": "Annual revenue reached ₹1,055,780 Cr in FY26. ROE stands at 18.2% and Interest Coverage ratio is strong at 5.04x.",
  "news_analysis": "No high-impact negative regulatory or governance events detected in current disclosure cycles.",
  "positive_factors": [
    "Consistent revenue & EBITDA expansion across retail and energy verticals",
    "Conservative leverage (Debt/Equity = 0.42)",
    "Strong technical moving average alignment"
  ],
  "risks": [
    "Approaching major overhead resistance at ₹1,325.0 - ₹1,330.0",
    "Global crude refining margin fluctuations"
  ],
  "contradictions": [],
  "unknowns": [
    "Near-term CAPEX guidance for green energy subsidiary"
  ],
  "evidence": [
    "Screener.in Consolidated Statement FY2026",
    "NSE Market Snapshot 2026-09-01 09:44:59 UTC",
    "Technical Feature Engine Timeframe 1D"
  ],
  "generated_at": "2026-09-01T13:02:15Z"
}
```
