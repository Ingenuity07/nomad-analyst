# Module Boundaries & Classifications

This document outlines the boundaries of all modules in the **Nomad Analyst Platform**, classifying them as KEEP, REFACTOR, MOVE, WRAP, DEPRECATE, REMOVE, or BUILD.

---

## 1. Module Inventories & Classifications

| Component / App | Type | Current Classification | Description & Rationale |
| :--- | :--- | :--- | :--- |
| **`config`** | Django App | **KEEP** | Core Django configuration, settings, root URL mappings, and ASGI routing. Critical core infrastructure. |
| **`llm`** | Django App | **KEEP** | AI Provider Routing (`IntelligentRouter`), versioned Jinja2 `LLMPrompt` registries, and `ToolExecutor` gateway. Highly generic and reusable. |
| **`chat`** | Django App | **REFACTOR** | WebSockets consumer (`ChatConsumer`), message list logging, and `DjangoCheckpointSaver` state serialization. Obsolete career agents and application prompts have been removed; nodes now route strictly to financial stock research graphs. |
| **`market`** | Django App | **KEEP** | The core Data Plane. Hosts Company, Instrument, and point-in-time MarketSnapshot records. Uses dummy providers/normalizers which will be replaced in future updates with real API integrations. |
| **`research`** | Django App | **KEEP** | The core Intelligence Plane audit store. Tracks `ResearchRun` parameters, detailed tool-retrieved files and text snippets as `Evidence`, and final LLM-synthesized `ResearchReport` markdown outputs. |
| **`intelligence`** | Python Pack | **BUILD** | Target Intelligence Plane. Will host specialized agent personas (FundamentalAnalyst, TechnicalAnalyst, NewsAnalyst) and advanced domain research graphs. |
| **`decision`** | Django App | **BUILD** | Target Decision Plane. Will contain models for `Strategy` configs, `Signal` emissions (BUY/SELL recommendations), position sizing parameters, and output portfolio tracking. |

---

## 2. Invalidation & Data Flow Rules

To preserve clean boundaries, the following rules must be enforced across subsequent modules:

1.  **Strict Data-Intelligence Decoupling**:
    *   Models in `market` (data plane) represent raw/historical market facts. They never store research conclusions, agent states, or LLM tokens.
    *   Models in `research` (intelligence plane) link back to `market.Instrument` or `market.Company` via Foreign Keys but do not modify market price snapshots.
2.  **State Isolation**:
    *   LLM router latency and call traces are kept inside the `telemetry` SQLite DB to prevent transactional DB locking on PostgreSQL.
    *   Agent checkpoints are serialized in `chat.AgentCheckpoint` using binary bytes to keep LangGraph independent of custom PostgreSQL table schemas.
3.  **Tool Execution Flow**:
    *   All tools must inherit from `llm.tools.base.BaseTool`.
    *   All execution passes through `ToolExecutor` to enforce input checks (via Pydantic), exception formatting, token tracing, and secret key redaction.
