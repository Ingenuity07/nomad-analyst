# Test Suite Audit

This document reviews the testing configuration, unit tests, integration tests, and test coverage of the **Nomad Analyst Platform** as of Module 0.

---

## 1. Existing Test Configurations

Tests are run using Django's standard test runner. When tests execute, the application:
1.  Creates an isolated PostgreSQL test database (`test_nomad_analyst`).
2.  Creates an isolated SQLite test telemetry database (`test_llm_telemetry.sqlite3`).
3.  Executes migrations to configure schema configurations.

---

## 2. Test Inventory

### 1. Market Integration Tests (`market/tests.py`)
*   **Test Cases**:
    *   `test_dummy_market_provider`: Verifies the mock stock provider returns simulated price dictionaries.
    *   `test_dummy_normalizer`: Verifies mock response dictionaries are correctly mapped and cast to Pydantic `MarketQuote` decimal fields.
    *   `test_market_service_persistence`: Verifies the orchestrator service creates Company, Instrument, and point-in-time MarketSnapshot records.
    *   `test_get_stock_snapshot_tool`: Verifies direct tool execution returns a successful `ToolResult` payload.
*   **Status**: **PASSING (100% SUCCESS)**.

### 2. Chat Agent Tests (`chat/tests.py`)
*   **Test Cases**: Checks WebSocket connection consumer handles, LangGraph checkpoint storage adapters, and agent plan executions.
*   **Status**: **LEGACY FAILURE / TIMEOUT**.
    *   *Reason*: Several legacy tests perform assertions verifying retired B2B career actions (e.g. asserting that the run status ends in `"Waiting Approval"`). Other tests perform live API calls via `IntelligentRouter` to external LLM providers, which hit rate limits (429) or connection timeouts inside the isolated test environment.
    *   *Recommendation*: Obsolete career assertions inside `chat/tests.py` must be retired, and mock registries should be introduced for all LLM calls to keep the test runner fully offline and hermetic.

---

## 3. Test Coverage & Gap Analysis

*   **Tested Coverage**: Excellent coverage of the core Data Plane components (`market` app).
*   **Critical Untested Areas**:
    *   *Celery Worker Pipelines*: Beat schedules are audited in the DB, but runtime Celery worker execution is not tested.
    *   *LLM Prompt Renderings*: The prompt rendering registry does not have assertions verifying variable interpolation errors.
    *   *Error Handovers*: Failure paths (e.g. what happens if the data provider returns empty pricing lists) are not yet tested.
