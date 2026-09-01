# FE-8 Research & Intelligence Workspace — Technical Inspection Report

## Executive Summary

This document presents a comprehensive, read-only technical inspection of the backend intelligence layer (Module 5) and frontend components in preparation for **FE-8: Research & Intelligence Workspace** (`/research`).

The inspection confirms that the core research pipeline — including `MarketResearchService`, `MarketResearchAgent`, `IntelligentRouter`, 24 domain market tools, and `POST /api/v1/research/` — is **IMPLEMENTED and fully functional**.

---

## 1. Research API Audit

| Endpoint | Method | Status | Service / View | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v1/research/` | `POST` | **IMPLEMENTED** | `StockResearchAPIView` / `MarketResearchService` | On-demand multi-tool equity research task returning structured JSON report. |
| `/api/chat/` | `POST` | **IMPLEMENTED** (Legacy) | `ChatAPIView` / `SingleAgentOrchestrator` | Multi-turn conversational endpoint with Celery async task execution support. |
| `/api/conversations/` | `GET` | **IMPLEMENTED** (Legacy) | `ConversationListAPIView` | Lists user conversation threads. |
| `/api/conversations/<id>/` | `GET` | **IMPLEMENTED** (Legacy) | `ConversationDetailAPIView` | Retrieves message history with token metrics for a thread. |
| `/api/chat/approve/` | `POST` | **IMPLEMENTED** (Legacy) | `ApproveAPIView` | Human-in-the-loop approval endpoint for LangGraph execution. |
| `/api/v1/research/reports/` | `GET` | **MISSING** | — | Persistence query for historical research reports. |
| `/api/v1/research/sector/` | `POST` | **MISSING** | — | Dedicated sector-level research endpoint (covered via generic query). |

### `POST /api/v1/research/` Specification:
- **Request Schema**:
  ```json
  {
    "symbol": "RELIANCE",
    "question": "Assess debt leverage, capital return efficiency, and recent breakout momentum.",
    "depth": "standard", // "quick" | "standard" | "deep"
    "as_of": "2026-08-20T10:00:00Z" // Optional ISO timestamp
  }
  ```
- **Response Schema**:
  ```json
  {
    "company": "Reliance Industries Limited",
    "instrument": "RELIANCE",
    "as_of": "2026-08-20T10:00:00Z",
    "summary": "Executive summary synthesizing technical trend, fundamentals, and catalysts...",
    "market_snapshot": { "price": 2975.5, "pe": 26.4, "market_cap_tier": "Large" },
    "technical_analysis": "Trading above 50-day and 200-day SMAs with RSI at 64.2...",
    "fundamental_analysis": "Operating cash flow expanded 14% YoY; debt-to-equity stands at 0.42...",
    "news_analysis": "Recent material developments indicate retail expansion...",
    "positive_factors": ["Bullish trend structure", "Expanding operating margins", "Low structural leverage"],
    "risks": ["Refining margin contraction", "Near-term resistance at ₹3,020"],
    "contradictions": ["Revenue increased 12% but net profit margin contracted by 40 bps"],
    "unknowns": ["Q2 foreign subsidiary tax reconciliation unconfirmed"],
    "evidence": [
      "Income statement 2024-Q4: Revenue ₹2,45,000 Cr",
      "Technical indicators 2026-08-20: SMA_50=2850, SMA_200=2710",
      "News item 2026-08-15: Retail segment adds 150 new locations"
    ],
    "generated_at": "2026-09-01T15:45:00Z"
  }
  ```
- **Execution**: Synchronous request-response.
- **Streaming**: Non-streaming (returns complete parsed JSON).

---

## 2. Module 5 Architecture & Orchestration

The equity research workflow is executed deterministically:
```
USER PROMPT + PARAMS (symbol, question, depth, as_of)
                       ↓
         POST /api/v1/research/
                       ↓
             StockResearchAPIView
                       ↓
           MarketResearchService
                       ↓
          MarketResearchAgent
     (Initializes ToolRegistry with 24 market tools)
                       ↓
               IntelligentRouter
     (Selects model tier, executes LLM generation)
                       ↓
            Agentic ReAct Tool Loop
   [Iteration 1..N: Tool Call → ToolExecutor → Tool Result]
   (Protected by ResearchLoopState stuck-loop detection)
                       ↓
            Structured Synthesis
     (Enforces strict ResearchReport JSON schema)
                       ↓
               Client Response
```

---

## 3. LLM Provider Architecture & Routing

- **Provider Abstraction**: `IntelligentRouter` (`llm/router.py`) implementing `BaseLLMProvider`.
- **Supported Adapters**:
  - `GeminiAdapter` (`gemini-2.5-flash` / Google Gemini API).
  - `GroqAdapter` (`mixtral-8x7b-32768` / Groq Cloud).
  - `CerebrasAdapter` (`llama3.1-8b`).
  - `OpenRouterAdapter` (`meta-llama/llama-3-8b-instruct:free`).
  - `OllamaAdapter` (`qwen3:8b`).
- **Telemetry & Tracing**: All runs log tokens, latency, cost in USD, correlation IDs, and error categorizations to `PromptRun` in `llm_telemetry` database.
- **Frontend Isolation**: Provider and model configurations are encapsulated backend concerns.

---

## 4. Tool System Inventory (24 Domain Market Tools)

| Tool Name | Domain / Source | Input Parameters | Output Summary |
| :--- | :--- | :--- | :--- |
| `get_stock_snapshot` | Price / Metrics | `symbol`, `as_of` | Price, 52w high/low, PE, volume, sector |
| `get_historical_ohlcv` | Price Action | `symbol`, `timeframe`, `start_date`, `end_date`, `as_of` | Historical OHLCV candle bars |
| `get_technical_features` | Indicators | `symbol`, `as_of` | SMA50, SMA200, RSI, RelVol, ATR, Distance from High |
| `get_company_financials` | Statements | `symbol`, `statement_type`, `frequency`, `limit`, `as_of` | Income statement, balance sheet, cash flows |
| `get_financial_metrics` | Ratios | `symbol`, `as_of` | ROE, ROCE, Debt/Equity, Operating Margin, Growth |
| `get_company_news` | News Headlines | `symbol`, `limit`, `as_of` | Material news items with sentiment and summaries |
| `get_company_events` | Corporate Events | `symbol`, `limit`, `as_of` | Dividends, splits, earnings announcements |
| `get_market_news` | Macro News | `limit`, `as_of` | Broad market, macroeconomic and sector news |
| `get_market_context` | Market / Regime | `as_of` | Index levels, breadth ratio, sector ranking tiers |
| `get_stock_opportunities` | Delivery Discovery | `universe`, `horizon`, `opportunity_type`, `limit`, `as_of` | Ranked delivery candidates with scores & pros/risks |
| `get_stock_opportunity` | Candidate Detail | `symbol`, `horizon`, `as_of` | 6-factor breakdown for specific stock candidate |
| `get_sector_opportunities` | Sector Discovery | `sector`, `horizon`, `as_of` | Sector candidate aggregation |
| `get_recommendations` | Recommendations | `horizon`, `signal`, `symbol`, `confidence`, `limit`, `as_of` | Filtered deterministic trade recommendations |
| `get_recommendation` | Setup Detail | `recommendation_id` | Full recommendation setup (entry, stop, target, factors) |
| `get_active_recommendations` | Active Setups | `horizon`, `limit`, `as_of` | All currently open trade setups |
| `get_intraday_ohlcv` | Intraday Price | `symbol`, `interval`, `date` | 5m/15m intraday price bars |
| `get_intraday_data_quality` | Feed Health | `as_of` | Feed staleness, gap detection, tick anomaly status |
| `get_intraday_features` | Intraday Math | `symbol`, `timeframe`, `as_of` | VWAP, ORB, relative volume ratios |
| `get_intraday_recommendations` | Intraday Signals | `signal`, `setup_type`, `limit`, `as_of` | Real-time intraday momentum signals |
| `get_intraday_recommendation` | Intraday Detail | `recommendation_id` | Intraday recommendation parameters |
| `get_intraday_setups` | Setup Detector | `setup_type`, `limit`, `as_of` | Detected intraday patterns (VWAP cross, ORB) |
| `get_recommendation_outcome` | Outcome Tracking | `recommendation_id` | Trade lifecycle evaluation, MFE, MAE, R-multiple |
| `get_strategy_performance` | Strategy Lab | `strategy`, `horizon`, `timeframe`, `as_of` | Win rate, profit factor, sample count |
| `get_backtest_result` | Backtester | `run_id` | Historical simulation summary report |
| `search_web` | Discovery | `query`, `limit` | DuckDuckGo web search links & snippets |
| `crawl_website` | Scraping | `url` | Web page content extractor |

---

## 5. Company Documents & Filing Search Status

| Capability | Status | Notes |
| :--- | :--- | :--- |
| **Structured Statements** | **IMPLEMENTED** | `IncomeStatement`, `BalanceSheetStatement`, `CashFlowStatement` stored with `period_end` and `filing_date`. |
| **Corporate Disclosures** | **IMPLEMENTED** | `CorporateEvent` stores dividend, earnings, and regulatory disclosure dates & summaries. |
| **PDF Annual Reports** | **MISSING** | No PDF parsing engine in repository. |
| **Vector Search / Embeddings** | **MISSING** | No vector database (pgvector/Pinecone/Chroma) or text chunking pipeline installed. |
| **Transcript RAG** | **MISSING** | Earnings call audio/text transcripts not ingested. |

---

## 6. Point-in-Time (PIT) & Lookahead Protection

- `as_of` timestamp is passed from frontend request payload to `MarketResearchService.research_stock(..., as_of=as_of)`.
- `MarketResearchAgent` injects `as_of` into tool arguments: `tool_args["as_of"] = as_of`.
- Deterministic tools enforce database filtering with `<= as_of` across prices, financial statements, indicators, and news items.

---

## 7. Operational Constraints & Financial Disclaimers

- **Zero Invention Rule**: System prompt forbids fabricating prices, dates, or financial metrics. If data is unavailable, the agent outputs `"Insufficient data"`.
- **No Unsolicited Trade Advice**: The agent is prohibited from issuing BUY/SELL/HOLD advice or inventing entry/stop prices unless retrieving them directly from recommendation tools.
- **Frontend Disclaimer Requirement**: FE-8 must display: *"AI-generated synthesis for research and informational purposes only. Nomad Analyst does not provide personalized investment advice or guaranteed trade execution."*

---

## 8. Backend Gap Analysis for FE-8

- **P0 (Blocks FE-8)**: **NONE**. `POST /api/v1/research/` is ready and functional.
- **P1 (Important Enhancements)**:
  - Persist generated reports in database for history lookup (`GET /api/v1/research/reports/`).
- **P2 (Secondary Enhancements)**:
  - Multi-turn research conversation thread endpoint under `/api/v1/research/conversations/`.
- **FUTURE**:
  - Vector database RAG for PDF annual reports and earnings transcripts.
  - Streaming token responses via Server-Sent Events (SSE).
