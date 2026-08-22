# Database Schema Audit

This document presents the detailed baseline audit of all models, field specifications, indices, relationships, and multi-database configurations in the **Nomad Analyst Platform** as of the baseline.

---

## 1. App-by-App Model Audit

### 1. `llm` Application Models (Telemetry & Prompt Configuration)

#### Model: `LLMPrompt` (Operational Database: PostgreSQL)
*   **Purpose**: Stores Jinja2 prompt templates.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `key`: CharField (max_length=255, unique=True) — Identifies the prompt (e.g. `market.research_planner.system`).
    *   `system_prompt`: TextField — System instructions.
    *   `user_prompt`: TextField — User instructions.
    *   `variables`: JSONField (default=list) — Variable tokens required by the prompt templates.
    *   `version`: IntegerField (default=1) — Prompt template version.
    *   `is_active`: BooleanField (default=True).
    *   `created_at`: DateTimeField.
    *   `updated_at`: DateTimeField.

#### Model: `AgentConfig` (Operational Database: PostgreSQL)
*   **Purpose**: Associates prompts and models to specific agent roles.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `agent_name`: CharField (max_length=100, unique=True).
    *   `system_prompt`: ForeignKey to `LLMPrompt`.
    *   `temperature`: DecimalField.
    *   `max_tokens`: IntegerField.
    *   `model_tier`: CharField (choices: `simple`, `medium`, `critical`).

#### Model: `PromptRun` (Telemetry Database: SQLite)
*   **Purpose**: Log records tracking latency, cost, and usage metrics of individual LLM queries.
*   **Fields**:
    *   `id`: BigAutoField.
    *   `prompt_key`: CharField.
    *   `prompt_version`: IntegerField.
    *   `provider`: CharField.
    *   `model`: CharField.
    *   `prompt_tokens`: IntegerField.
    *   `completion_tokens`: IntegerField.
    *   `cost`: DecimalField (max_digits=10, decimal_places=6) — Total USD expenditure.
    *   `latency_ms`: IntegerField.
    *   `status`: CharField.
    *   `error`: TextField.
    *   `created_at`: DateTimeField.
*   **Indices**: Non-clustered indexes on `prompt_key`, `provider`, and `created_at` for telemetry queries.

---

### 2. `chat` Application Models (Agent State & Operations)

#### Model: `UserProfile` (Operational Database: PostgreSQL)
*   **Purpose**: Standard candidate and user profile.
*   **Fields**:
    *   `id`: BigAutoField.
    *   `username`: CharField (max_length=150, unique=True).
    *   `email`: EmailField.
    *   `full_name`: CharField.
    *   `phone`: CharField (blank/null).
    *   `linkedin_url`: URLField (blank/null).
    *   `github_url`: URLField (blank/null).
    *   `portfolio_url`: URLField (blank/null).

#### Model: `Conversation` (Operational Database: PostgreSQL)
*   **Purpose**: Thread wrapper linking messages.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `user_profile`: ForeignKey to `UserProfile`.
    *   `title`: CharField.
    *   `selected_provider`: CharField (max_length=50).
    *   `selected_model`: CharField (max_length=100).
    *   `created_at` & `updated_at`: DateTimeFields.

#### Model: `Message` (Operational Database: PostgreSQL)
*   **Purpose**: Chronological log of chat turns.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `conversation`: ForeignKey to `Conversation` (on_delete=CASCADE).
    *   `role`: CharField (choices: `user`, `assistant`, `system`, `tool`).
    *   `content`: TextField.
    *   `prompt_tokens`: IntegerField.
    *   `completion_tokens`: IntegerField.
    *   `total_tokens`: IntegerField.
    *   `provider` & `model`: CharFields.
    *   `created_at`: DateTimeField.

#### Model: `AgentRun` (Operational Database: PostgreSQL)
*   **Purpose**: Audits the execution of a LangGraph agent run.
*   **Fields**:
    *   `id`: BigAutoField.
    *   `conversation`: ForeignKey to `Conversation`.
    *   `agent_type`: CharField.
    *   `status`: CharField.
    *   `prompt_tokens` & `completion_tokens`: IntegerFields.
    *   `total_cost`: DecimalField.
    *   `started_at` & `completed_at`: DateTimeFields.

#### Model: `ToolExecution` (Operational Database: PostgreSQL)
*   **Purpose**: Logs details of tool invocations within an agent run.
*   **Fields**:
    *   `id`: BigAutoField.
    *   `agent_run`: ForeignKey to `AgentRun`.
    *   `tool_name`: CharField.
    *   `input_data`: JSONField.
    *   `output_data`: JSONField.
    *   `status`: CharField (choices: `success`, `error`).
    *   `executed_at`: DateTimeField.

#### Models: `AgentCheckpoint` & `AgentCheckpointWrite` (Operational Database: PostgreSQL)
*   **Purpose**: Stores binary serialized states from LangGraph runtime.
*   **Fields**:
    *   Contain raw `bytes` binary fields mapping checkpoint thread hashes to preserve state across asynchronous Celery execution windows.

#### Model: `AgentMemory` (Operational Database: PostgreSQL)
*   **Purpose**: Stores long-term user preferences extracted from conversation logs.
*   **Fields**:
    *   `id`: BigAutoField.
    *   `user_profile`: ForeignKey to `UserProfile`.
    *   `category`: CharField (e.g., `preference`).
    *   `key`: CharField (e.g., `tech_stack`).
    *   `value`: JSONField.

---

### 3. `market` Application Models (Stock Market Universe)

#### Model: `Company` (Operational Database: PostgreSQL)
*   **Purpose**: Corporate catalog representing listed businesses.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `name`: CharField (e.g., *Reliance Industries Limited*).
    *   `legal_name`: CharField (blank/null).
    *   `short_name`: CharField (blank/null, unique/indexed).
    *   `isin`: CharField (max_length=12, unique=True).
    *   `sector` & `industry` & `sub_industry`: CharFields.
    *   `description`: TextField.
    *   `website`: URLField.
    *   `is_active`: BooleanField.

#### Model: `Instrument` (Operational Database: PostgreSQL)
*   **Purpose**: Specific tradeable asset listing linked to an exchange.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `company`: ForeignKey to `Company` (on_delete=CASCADE).
    *   `symbol`: CharField (max_length=50, unique=True) — e.g. `RELIANCE`.
    *   `exchange`: CharField (choices: `NSE`, `BSE`).
    *   `isin`: CharField (max_length=12).
    *   `instrument_type`: CharField (choices: `EQUITY`, `ETF`, `INDEX`, `FUTURE`, `OPTION`).
    *   `currency`: CharField (default `INR`).
    *   `lot_size`: IntegerField (default 1).
    *   `is_active`: BooleanField.

#### Model: `MarketSnapshot` (Operational Database: PostgreSQL)
*   **Purpose**: Records historical point-in-time pricing and volumes.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `instrument`: ForeignKey to `Instrument` (on_delete=CASCADE).
    *   `timestamp`: DateTimeField.
    *   `open` & `high` & `low` & `close`: DecimalFields (max_digits=12, decimal_places=2).
    *   `volume`: BigIntegerField.
    *   `previous_close` & `change`: DecimalFields.
    *   `change_percent`: DecimalField.
    *   `source`: CharField.
    *   `source_timestamp`: DateTimeField.

---

### 4. `research` Application Models (Evidence Logs & Synthesis)

#### Model: `ResearchRun` (Operational Database: PostgreSQL)
*   **Purpose**: Session tracker for investment research tasks.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `research_type`: CharField (e.g. `COMPANY_RESEARCH`).
    *   `status`: CharField (choices: `running`, `completed`, `failed`).
    *   `query`: TextField — Raw user query.
    *   `started_at` & `completed_at` & `created_at`: DateTimeFields.

#### Model: `Evidence` (Operational Database: PostgreSQL)
*   **Purpose**: Retained source excerpts, filings, and crawler dumps.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `research_run`: ForeignKey to `ResearchRun` (on_delete=CASCADE).
    *   `source_type` & `source_name`: CharFields.
    *   `source_url`: URLField.
    *   `title`: CharField.
    *   `content`: TextField — Raw scraped content.
    *   `published_at` & `retrieved_at`: DateTimeFields.
    *   `content_hash`: CharField (max_length=64) — SHA-256 hash of the content to enforce uniqueness and avoid duplicate ingestion.
    *   `metadata`: JSONField.

#### Model: `ResearchReport` (Operational Database: PostgreSQL)
*   **Purpose**: Houses the final synthesized investment markdown report.
*   **Fields**:
    *   `id`: UUID (Primary Key).
    *   `research_run`: ForeignKey to `ResearchRun` (on_delete=CASCADE).
    *   `title`: CharField.
    *   `summary`: TextField.
    *   `analysis`: TextField — Markdown analysis report.
    *   `created_at` & `updated_at`: DateTimeFields.
