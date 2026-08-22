# Security & Observability Audit

This document audits the telemetry logging, cost monitoring, authorization policies, and safety whitelists implemented in the **Nomad Analyst Platform** as of Module 0.

---

## 1. Observability & Telemetry

### 1. Token & Cost Logging
All LLM prompts and executions are monitored for consumption metrics. The `IntelligentRouter` extracts input/output token counts and logs them inside the `PromptRun` table in the SQLite telemetry database (`llm_telemetry.sqlite3`).
*   **Pricing Calculations**: Cost metrics are computed using baseline token pricing rules (e.g. Gemini 2.5 Flash pricing: $0.075 / 1M input tokens, $0.30 / 1M output tokens).
*   **Spans & Correlation IDs**: Logs associate correlation IDs (Conversation UUID, Run ID) with individual LLM calls to enable trace graphs.

### 2. Tool Execution Latencies
The `ToolExecutor` calculates high-resolution execution durations using `time.perf_counter()` before and after tool calls. Telemetry metrics are printed to logs and stored in the database.

---

## 2. Security & Agent Guards

### 1. Sensitive Data Redaction
The `ToolExecutor` executes recursive sanitization on all input argument dictionaries and returned tool result payloads.
*   **Redacted Keys**: Any keys containing sensitive terms (`password`, `key`, `token`, `secret`, `auth`, `cookie`, `passphrase`) are replaced with `"[REDACTED]"` to prevent private API keys, user passwords, or session identifiers from leaking into database logs or stdout streams.

### 2. Playwright SSRF Navigation Whitelists
The `CrawlWebsiteTool` parses URLs prior to spawning Playwright browser drivers:
*   **Blocked Protocols**: Navigations to local directories (`file://`) are blocked.
*   **Blocked Hosts**: Navigations targeting loopback addresses (`localhost`, `127.0.0.1`, `::1`) or cloud instance metadata endpoints (`169.254.169.254`) are blocked.
*   **SSRF Mitigation**: Prevents the LLM from requesting sensitive local files or accessing internal instance resources.

### 3. Database Isolation
*   Transactional database operations (conversations, market data, evidence logs) are executed inside PostgreSQL.
*   Prompts execution metrics and performance logs are routed strictly to SQLite (`llm_telemetry.sqlite3`), eliminating cross-database joins and reducing table lock dependencies.
