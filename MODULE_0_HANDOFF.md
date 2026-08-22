# Module 0 Handoff — Architecture Audit & Baseline

*   **Module Name**: Module 0: Existing Architecture Audit & Baseline
*   **Date**: August 22, 2026
*   **Git Branch**: `main`
*   **Git Commit Hash**: `c5c9937a3cb70a6d249667bfa142d2a772cdceba`
*   **Module Status**: COMPLETED

---

## 1. Current System Summary

Nomad Analyst is a stock market intelligence platform built using Django. The platform is structured to support real-time conversational analysis, automated market updates, and stock research pipelines. It is designed around clean architecture principles with separate data, intelligence, and conversation layers.

---

## 2. Current Architecture

The application is structured as a **Modular Monolith**:
*   **Daphne ASGI Server**: Manages HTTP views and real-time WebSockets.
*   **Django REST Framework**: Implements REST endpoints.
*   **Celery Background Workers**: Processes tasks asynchronously (e.g. market updates, agent reasoning runs).
*   **Redis**: Celery broker and result store, WebSocket Channel Layer store, and cache backend.
*   **PostgreSQL**: Operational database storing conversations, messages, market catalogs, and research logs.
*   **SQLite**: Isolated telemetry database for high-volume token tracing and latency tracking.

---

## 3. Existing Django Apps

1.  **`config/`**: Root project configuration.
2.  **`llm/`**: AI providers router, versioned prompt template registry, and Pydantic tool execution platform.
3.  **`chat/`**: WebSocket messaging consumers, LangGraph state execution checkpointer, and user profiles.
4.  **`market/`**: Data plane catalog (`Company`, `Instrument`, `MarketSnapshot`) and quote ingestion tasks.
5.  **`research/`**: Intelligence plane logs (`ResearchRun`, `Evidence`, `ResearchReport`).

---

## 4. Existing AI Architecture

*   **Provider Router (`IntelligentRouter`)**: Waterfall routing supporting model complexity tiers (Groq, Gemini, Ollama, OpenRouter, Cerebras).
*   **Prompt Registry (`PromptRegistry`)**: Jinja2 prompt rendering database.
*   **Graph State Runtime**: LangGraph state-machine compiling planner, executor ReAct loop, critic review, and report synthesis nodes.

---

## 5. Existing Tool Architecture

*   `read_file`: Reads workspace files.
*   `search_web`: Performs web searches.
*   `crawl_website`: Webpage scraper with Playwright.
*   `get_stock_snapshot`: Fetches and persists market quotes via `MarketService`.
*   `analyze_screenshot`: Visually inspects screenshots using vision LLMs.

*Tool executions pass through a single `ToolExecutor` which redacts secrets and logs performance metadata.*

---

## 6. Database Summary

*   **PostgreSQL**: Handles operational database storage. Contains all Django models except telemetry.
*   **SQLite**: Handled via `LLMTelemetryRouter`. Stores the `PromptRun` table to prevent telemetry logs from locking transactional PostgreSQL tables.

---

## 7. Async / Background Architecture

*   `run_agent_task`: On-demand Celery worker task executing agent loops. Protected by Redis locks.
*   `update_instrument_quotes`: Periodic Celery Beat task running every 30 minutes to update prices.

---

## 8. API Summary

*   REST Endpoints: Chat APIs, approval checkpoints, conversation listings, and provider statuses.
*   WebSocket Endpoints: `/ws/chat/<uuid:conversation_id>/` for token streaming.

---

## 9. Infrastructure

*   Celery Worker & Celery Beat.
*   Redis DB 0 (broker) and DB 1 (cache/locks).
*   PostgreSQL and SQLite.

---

## 10. Components Kept

*   `llm` App, prompts registries, routers, and Pydantic tool executors.
*   `chat` App, channels consumers, checkpointers, and user profile structures.
*   `market` App, catalogs, dummy providers, normalizers, and service ingestion.
*   `research` App, runs, evidence logs, and report models.

---

## 11. Components Refactored

*   `chat/scheduler.py`: Replaced default `agent_type` from `JobReasoningAgent` to `ResearchAgent`.
*   `chat/agents/v2_graph.py`: Stripped out obsolete B2B resume tailoring and form filling nodes, keeping the graph clean and loopback research-focused.

---

## 12. Components Moved

*   `UserProfile` model moved from `knowledge_base` to `chat` app.

---

## 13. Components Deprecated / Removed

*   All legacy career-related applications (`prospecting`, `resume`, `applications`, `knowledge_base`) have been completely deleted.
*   Obsolete agents (`JobReasoningAgent`) and tools (`SearchCompaniesTool`, `ExtractContactDataTool`) have been removed.

---

## 14. Known Problems & Gaps

*   **Legacy Tests**: Legacy assertions inside `chat/tests.py` verify retired B2B status loops or fail on live rate limits (429).
*   **Real Data Feeds**: `MarketService` currently relies on simulated data. Live API connections to real exchanges (NSE/BSE) are planned.

---

## 15. Test Status

*   **`market` app tests**: **PASSING (100% SUCCESS)**. All 4 tests run and verify quote fetches and normalizations.
*   **`chat` app tests**: Legacy tests contain retired assertions and fail on rate limits in offline test environments.

---

## 16. Exact Changes Made

Module 0 was documentation-only. Created:
*   `CURRENT_ARCHITECTURE.md`
*   `TARGET_ARCHITECTURE_GAP.md`
*   `MODULE_BOUNDARIES.md`
*   `DATABASE_AUDIT.md`
*   `TOOL_AUDIT.md`
*   `DEPENDENCY_AUDIT.md`
*   `ASYNC_AUDIT.md`
*   `API_AUDIT.md`
*   `TESTING_AUDIT.md`
*   `SECURITY_OBSERVABILITY_AUDIT.md`
*   `MODULE_0_HANDOFF.md`

No production code was modified during this audit phase.

---

## 17. Next Recommended Module

*   **MODULE 1 — MARKET DATA FOUNDATION**: Replace the simulated provider with live Indian market data APIs (e.g. YFinance or scrapers), build bulk loaders, and implement index tickers.

---

## 18. Instructions for Next Agent

*   The data plane is already structured cleanly inside the `market` app.
*   Start Module 1 by replacing `market/providers/dummy.py` with real-world providers (such as `yfinance` or custom scrapers), maintaining the `MarketDataProvider` Protocol interface to prevent breaking `MarketService`.
*   Ensure that any live network requests are mocked or bypassed during unit tests to keep tests fast and offline-reliable.
