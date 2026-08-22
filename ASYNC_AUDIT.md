# Asynchronous & Scheduler Tasks Audit

This document details the background execution architecture, queues, and database interactions of the **Nomad Analyst Platform** as of Module 0.

---

## 1. Asynchronous Tasks Inventory

### Task: `chat.tasks.run_agent_task`
*   **Trigger**: Triggered via `.delay()` inside `ChatAPIView` (REST API) when `async_execution=True` is provided, or during active WebSocket connection runs.
*   **Queue**: default Celery worker queue.
*   **Frequency**: On-demand (user-triggered).
*   **Locks & Synchronization**: Acquires a Redis cache key lock (`lock:run_agent_task:{username}:{conversation_id}`) with a 10-minute timeout using `cache.add()` (atomic `SETNX`). If the task is already active, duplicate invocations are immediately skipped.
*   **Database Interaction**:
    *   Reads `UserProfile`, `Conversation`, and `Message` tables.
    *   Creates a running `AgentRun` entry.
    *   Appends new `Message` objects to the database.
    *   Invokes the LangGraph checkpoints saver to serialize state in `AgentCheckpoint`.
*   **External API Interaction**: Calls external LLM provider endpoints to resolve planner, executor, and synthesis nodes.

### Task: `market.tasks.update_instrument_quotes`
*   **Trigger**: Automatically dispatched by Celery Beat scheduler.
*   **Queue**: default Celery worker queue.
*   **Frequency**: Every 30 minutes (defined via the `Update stock quotes every 30 minutes` database schedule in `django_celery_beat.models.PeriodicTask`).
*   **Locks & Synchronization**: Handled by the Celery Beat interval scheduler.
*   **Database Interaction**:
    *   Queries all active `Instrument` records (`is_active=True`).
    *   For each symbol, fetches quotes and upserts `Company` and `Instrument` metadata.
    *   Creates a new `MarketSnapshot` entry in the Postgres operational database.
*   **External API Interaction**: Queries simulated or live data providers (`DummyMarketProvider`).

---

## 2. Ingestion Design Patterns

*   **Normal Background Tasks**: Use standard Celery shared tasks. Decoupled from the HTTP request thread, protected by Redis locks.
*   **Market Data Ingestion**:
    *   The `update_instrument_quotes` task represents a pull-based ingestion model. It iterates over a curated universe of symbols and saves pricing snapshots.
    *   *Future stream architecture*: When real-time streaming is introduced (e.g. WebSockets connections to broker terminals), data will be pushed directly to Daphne channel layers and written in batches to PostgreSQL to prevent locking the main database connection pool.
