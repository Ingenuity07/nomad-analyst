# Nomad Market Intelligence — Foundation Cleanup & Migration Plan: Phase 0 Audit

This document is a complete read-only repository audit detailing the current state of the codebase, inventorying modules, identifying obsolete career/prospecting domain logics, highlighting reusable components, evaluating migration risks, and defining the target architecture.

---

## 1. Current Architecture

Nomad is structured as a **Modular Monolith** applying Clean Architecture and Domain-Driven Design (DDD) concepts. 
*   **Web Layer**: Daphne ASGI server routes WebSockets and Django REST Framework API views.
*   **Task Layer**: Asynchronous Celery workers run heavy background processing tasks (scrapers, crawls, LLM evaluations).
*   **Caching & Coordination**: Redis is used for channel layers, caching, and distributed atomic task locking.
*   **Database Layer**:
    *   **PostgreSQL (`aios_db`)**: The default database, storing operational profiles, conversation state, LangGraph checkpoint blobs, and campaign structures.
    *   **SQLite (`llm_telemetry.sqlite3`)**: Managed via `LLMTelemetryRouter` in `llm/routers.py`, storing prompt templates, correlation IDs, tokens, latencies, and LLM provider calls.

---

## 2. Django Apps Inventory

Below is the inventory of all Django apps registered in the codebase:

### 1. `config/`
*   **Purpose**: Root Django project configuration.
*   **Models**: None.
*   **URLs**: Registers REST paths, ASGI channels, and Swagger APIs.
*   **Tasks**: None.
*   **External Dependencies**: `django`, `channels`, `daphne`.
*   **Tests**: None.
*   **Classification**: **KEEP**
*   **Reason**: Root settings and ASGI configuration are required core infrastructure.

### 2. `llm/`
*   **Purpose**: Mid-tier AI provider router, Prompt template registry, and Tool Executor platform.
*   **Models**: `LLMPrompt`, `PromptRun`, `AgentConfig`.
*   **URLs**: Telemetry monitoring views.
*   **Tasks**: None.
*   **External Dependencies**: `opentelemetry-api`, `opentelemetry-sdk`, `pydantic`, `jinja2`.
*   **Tests**: Unit tests for router logic, token calculations, and tool executor.
*   **Classification**: **KEEP**
*   **Reason**: Central reusable LLM gateway, prompts database, and tool execution infrastructure.

### 3. `chat/`
*   **Purpose**: Multi-agent interaction orchestrator, WebSockets streaming, and LangGraph runtime checkpoints.
*   **Models**: `Conversation`, `Message`, `AgentRun`, `ToolExecution`, `AgentCheckpoint`, `AgentCheckpointWrite`, `AgentMemory`.
*   **URLs**: Conversation endpoints.
*   **Tasks**: `run_agent_task` (runs agents asynchronously in Celery with Redis locks).
*   **External Dependencies**: `langgraph`, `langgraph-checkpoint`, `channels_redis`, `asgiref`.
*   **Tests**: Extensively tests WebSocket connections, LangGraph checkpoint persistence, and agent loop execution.
*   **Classification**: **REPURPOSE**
*   **Reason**: Retain WebSocket connections and LangGraph checkpointing infrastructure. Remove references to `JobReasoningAgent` and B2B career prompts, replacing them with financial/market research workflows.

### 4. `knowledge_base/`
*   **Purpose**: Resume ingestion, OCR extraction, and segmenting/saving candidate profiles.
*   **Models**: `UserProfile`, `ProfessionalKnowledgeBase`, `Experience`, `Project`, `Skill`, `JobPosting`, `SkillExperienceLink`, `SkillProjectLink`, `ProjectExperienceLink`.
*   **URLs**: OCR processing endpoints.
*   **Tasks**: None.
*   **External Dependencies**: `pypdf`, `python-docx` (`docx`).
*   **Tests**: Basic dummy tests.
*   **Classification**: **REMOVE** (Career Models) / **REPURPOSE** (Ingestion Concepts)
*   **Reason**: Career-centric profile models are obsolete. The ingestion concept (parsing text, segmenting, LLM extraction) will be repurposed into the new `research/` app to parse company filings (PDFs/HTML). Redefine/move a simplified `UserProfile` to resolve foreign keys in `chat` models.

### 5. `prospecting/`
*   **Purpose**: Outbound B2B lead generation, crawler searches, suitability scoring, buying groups, and CRM sync.
*   **Models**: `Workspace`, `ProspectingCampaign`, `ICPProfile`, `ProblemSignal`, `DiscoveryRun`, `LeadCompany`, `CompanySource`, `LeadContact`, `WebsiteAnalysis`, `Evidence`, `CompanySignal`, `Qualification`, `Person`, `ContactPoint`, `BuyingGroupMember`, `ResearchRun`, `ProviderExecution`, `CampaignEvent`, `TargetList`, `ListMembership`, `CampaignEnrollment`, `SalesGuidance`, `EmailSequence`, `EmailMessage`, `EmailBounce`, `EmailUnsubscribe`, `InboundReply`, `LeadFeedback`, `CRMIntegrationRecord`, `ProspectingRequest`, `ProspectingSpecificationVersion`, `Discovery`, `DiscoveryLead`.
*   **URLs**: Prospecting and Lead search APIs.
*   **Tasks**: `discover_campaign_async` (performs OSM lookup, crawls sites, extracts contacts, scores matches, syncs CRMs).
*   **External Dependencies**: `playwright`, `beautifulsoup4`.
*   **Tests**: Large test suite for crawling, scoring, and CRM integrations.
*   **Classification**: **REMOVE** (B2B Leads Logic) / **REPURPOSE** (Research/Evidence Models)
*   **Reason**: B2B campaigns and lead structures are completely obsolete. The models `Evidence`, `ResearchRun`, and `ProviderExecution` represent generic research concepts and will be recreated/repurposed within the new `research/` app.

### 6. `resume/`
*   **Purpose**: LaTeX template compiling and job-to-resume comparison.
*   **Models**: `ResumeTemplate`, `ResumeVersion`, `ATSReport`.
*   **URLs**: Resume compiling and download endpoints.
*   **Tasks**: None.
*   **External Dependencies**: `jinja2`.
*   **Tests**: LaTeX compilation mock tests.
*   **Classification**: **REMOVE**
*   **Reason**: Career-specific and LaTeX resume rendering is obsolete.

### 7. `applications/`
*   **Purpose**: Job application tracking.
*   **Models**: `ApplicationTracker`.
*   **URLs**: Tracker APIs.
*   **Tasks**: None.
*   **External Dependencies**: None.
*   **Tests**: None.
*   **Classification**: **REMOVE**
*   **Reason**: Job application tracking is obsolete.

---

## 3. Detailed Model Inventory

Below is an inventory of all database models in the project:

| Model Name | App | Purpose | Keep / Remove / Repurpose |
| :--- | :--- | :--- | :--- |
| **`LLMPrompt`** | `llm` | Versioned system/user prompt templates. | **KEEP** |
| **`PromptRun`** | `llm` | Detailed LLM call metrics and tokens (telemetry DB). | **KEEP** |
| **`AgentConfig`** | `llm` | Agent system prompts and temperature configurations. | **KEEP** |
| **`UserProfile`** | `knowledge_base` | User profile data (name, email, portfolio URLs). | **REPURPOSE** (Move & Simplify to `chat` or common context to resolve foreign keys in `Conversation`/`AgentMemory`) |
| **`ProfessionalKnowledgeBase`**| `knowledge_base` | Candidate career summary. | **REMOVE** |
| **`Experience`** | `knowledge_base` | Employment history records. | **REMOVE** |
| **`Project`** | `knowledge_base` | Candidate projects. | **REMOVE** |
| **`Skill`** | `knowledge_base` | Categorized candidate skills. | **REMOVE** |
| **`JobPosting`** | `knowledge_base` | Scraped target job description meta. | **REMOVE** |
| **`SkillExperienceLink`** | `knowledge_base` | Experience skill link. | **REMOVE** |
| **`SkillProjectLink`** | `knowledge_base` | Project skill link. | **REMOVE** |
| **`ProjectExperienceLink`** | `knowledge_base`| Experience project link. | **REMOVE** |
| **`Workspace`** | `prospecting` | B2B multi-tenant boundary. | **REMOVE** (Obsolescent B2B tenant config) |
| **`ProspectingCampaign`** | `prospecting` | Outbound campaigns configuration. | **REMOVE** |
| **`ICPProfile`** | `prospecting` | Ideal Customer Profile search constraints. | **REMOVE** |
| **`ProblemSignal`** | `prospecting` | B2B pain point definition. | **REMOVE** |
| **`DiscoveryRun`** | `prospecting` | Scrape query session logs. | **REMOVE** |
| **`LeadCompany`** | `prospecting` | Discovered business prospect details. | **REMOVE** |
| **`CompanySource`** | `prospecting` | Lead references mapping to search engines. | **REMOVE** |
| **`LeadContact`** | `prospecting` | Scraped staff coordinates. | **REMOVE** |
| **`WebsiteAnalysis`** | `prospecting` | Scraped site fit scores. | **REMOVE** |
| **`Evidence`** | `prospecting` | Excerpts of text proving a problem signal exists. | **REPURPOSE** (Recreate under new `research` app for company research evidence) |
| **`CompanySignal`** | `prospecting` | Link mapping signals to companies. | **REMOVE** |
| **`Qualification`** | `prospecting` | B2B fit scores scorecard. | **REMOVE** |
| **`Person`** | `prospecting` | Contacts directory record. | **REMOVE** |
| **`ContactPoint`** | `prospecting` | Contact communications channel. | **REMOVE** |
| **`BuyingGroupMember`** | `prospecting` | Target outreach role mapping. | **REMOVE** |
| **`ResearchRun`** | `prospecting` | Logs research run stages. | **REPURPOSE** (Recreate under new `research` app for market research) |
| **`ProviderExecution`** | `prospecting` | Audits external provider calls. | **REPURPOSE** (Recreate under new `research` app for market quotes/data) |
| **`CampaignEvent`** | `prospecting` | Outbound event timeline logs. | **REMOVE** |
| **`TargetList`** | `prospecting` | Lists of target leads. | **REMOVE** |
| **`ListMembership`** | `prospecting` | Links companies to target lists. | **REMOVE** |
| **`CampaignEnrollment`** | `prospecting` | Outbound campaign tracking. | **REMOVE** |
| **`SalesGuidance`** | `prospecting` | Copywriting suggestions and CTA angles. | **REMOVE** |
| **`EmailSequence`** | `prospecting` | Multistage email templates. | **REMOVE** |
| **`EmailMessage`** | `prospecting` | Outbound outreach email copy. | **REMOVE** |
| **`EmailBounce`** | `prospecting` | Outbound clean list bounce logs. | **REMOVE** |
| **`EmailUnsubscribe`** | `prospecting` | Opt-out registers. | **REMOVE** |
| **`InboundReply`** | `prospecting` | Inbound sentiment classification logs. | **REMOVE** |
| **`LeadFeedback`** | `prospecting` | User feedback loops scorecard. | **REMOVE** |
| **`CRMIntegrationRecord`** | `prospecting` | CRM mappings. | **REMOVE** |
| **`ProspectingRequest`** | `prospecting` | User campaign prompt. | **REMOVE** |
| **`ProspectingSpecificationVersion`**| `prospecting` | Parsed target campaign spec versions. | **REMOVE** |
| **`Discovery`** | `prospecting` | Anchors campaign search targets. | **REMOVE** |
| **`DiscoveryLead`** | `prospecting` | Links companies to discovery runs. | **REMOVE** |
| **`ResumeTemplate`** | `resume` | LaTeX Jinja2 templates source. | **REMOVE** |
| **`ResumeVersion`** | `resume` | Tailored spec and generated LaTeX. | **REMOVE** |
| **`ATSReport`** | `resume` | ATS score breakdown report. | **REMOVE** |
| **`ApplicationTracker`** | `applications`| Tracks candidate application statuses. | **REMOVE** |
| **`Conversation`** | `chat` | Grouping for conversation threads. | **KEEP** (Has FK to `UserProfile`) |
| **`Message`** | `chat` | Individual messages in a thread. | **KEEP** |
| **`AgentRun`** | `chat` | Logs reasoning token metrics and costs. | **KEEP** |
| **`ToolExecution`** | `chat` | Execution trace for tools. | **KEEP** |
| **`AgentCheckpoint`** | `chat` | LangGraph thread checkpoint states. | **KEEP** |
| **`AgentCheckpointWrite`**| `chat` | LangGraph thread state write logs. | **KEEP** |
| **`AgentMemory`** | `chat` | Remembers user configuration settings. | **KEEP** (Has FK to `UserProfile`) |

---

## 4. Reusable Infrastructure

The following core components represent highly stable, generic infrastructure that should remain untouched or repurposed:

1.  **AI Provider Gateway (`llm.router`)**: Handles failover, complexity scoring, and vendor API adapters (Gemini, Groq, Cerebras, OpenRouter, Ollama).
2.  **Tool Executor (`llm.tools.executor`)**: Handles generic input validation (Pydantic), exception mapping, latency telemetry, and credentials redaction.
3.  **State Checkpoint Saver (`chat.agents.checkpoint_saver.DjangoCheckpointSaver`)**: Custom LangGraph checkpointer storing execution graph state in Postgres.
4.  **Telemetry Logger (`llm.routers.LLMTelemetryRouter`)**: Routes query logs to SQLite and core application states to Postgres.
5.  **ASGI Daphne WebSockets Consumer (`chat.consumers.ChatConsumer`)**: Streams token responses back to the UI in real-time.
6.  **Celery background worker queue & locking**: Redis cache backend locking for tasks.

---

## 5. Obsolete Domain

All career-seeking and outbound sales prospecting domains are obsolete. These include:
*   B2B lead generation crawls, CRM sync adapters (Salesforce, HubSpot), and buying group scrapers.
*   Candidate profiles, experience list trackers, resume latex compilers, and job application trackers.

---

## 6. Models To Remove

All models in the `resume` and `applications` apps, and career-specific models in `knowledge_base` and prospecting campaigns in `prospecting` will be removed.
*(Refer to the detailed Model Inventory table above)*

---

## 7. Models To Repurpose

1.  **`UserProfile`**: Move this model into the `chat` app. Strip the career-specific fields (e.g. portfolio link) to simplify it down to basic user identification (`username`, `email`, `full_name`). This resolves foreign keys in `Conversation` and `AgentMemory` without breaking migrations.
2.  **`ResearchRun`**: Recreate under the new `research` app to represent financial and stock market analysis runs.
3.  **`Evidence`**: Recreate under the new `research` app to track source documentation, filings, and news text excerpts matching financial hypotheses.
4.  **`ProviderExecution`**: Recreate under the new `research` app to audit market API data downloads (e.g., download costs, limits).

---

## 8. Dependencies Audit

Review of `requirements.txt` relative to obsolete modules:

*   **`playwright`** (crawling): **KEEP**. Necessary for future fundamental research, news ingestion, and web crawling.
*   **`beautifulsoup4`, `soupsieve`, `lxml`** (HTML parsing): **KEEP**. Used for cleaning scraped documents.
*   **`pypdf`** (PDF parser): **KEEP**. Necessary for parsing corporate annual filings and PDF reports.
*   **`python-docx`** (`docx`): **REMOVE**. Used only for generating tailored CVs in Word format.
*   **`Jinja2`**: **KEEP**. Used in `llm` prompt template rendering.
*   **`langgraph`, `langgraph-checkpoint`**: **KEEP**. Powers the agentic workflow and state checkpointer.
*   **`opentelemetry-api`, `opentelemetry-sdk`**: **KEEP**. Powers LLM tracing and latency monitoring.

---

## 9. Database & Migration Risks

### 1. The `UserProfile` Foreign Key Dependency
*   `chat.Conversation` and `chat.AgentMemory` have foreign key references to `knowledge_base.UserProfile`.
*   Simply deleting the `knowledge_base` app will cause import failures and database constraint errors.
*   **Mitigation**: We must migrate `UserProfile` to `chat.models.py`.
    *   Create a migration in the `chat` app to declare a simplified `UserProfile` table.
    *   Point foreign keys in `Conversation` and `AgentMemory` to `chat.UserProfile`.
    *   Write a data migration to move any existing default user profiles over, or perform a clean DB reset since this is a development database.

### 2. Telemetry Multi-DB Split
*   `LLMTelemetryRouter` routes `PromptRun` database operations to `telemetry`.
*   We must ensure that during deletions/creations, `PromptRun` operations do not leak into the default Postgres database.

---

## 10. LLM Architecture

*   The LLM is kept as a reasoning layer, not as a numeric database.
*   Prompts are bootstrapped dynamically via migrations (e.g., `llm.0005_bootstrap_prompts`).
*   Obsolete prompts matching prospecting and resume tailoring will be removed via a database cleanup migration, and new financial research prompts will be introduced.

---

## 11. Tool Architecture

The execution flow enforces validation at every level:
```text
LLM / Agent ──► Tool Registry ──► Tool Executor ──► Domain Service ──► Provider ──► Canonical Data Schema
```
*   The Tool Executor automatically redacts credentials (`key`, `token`, `secret`, `password`, `auth`, `cookie`).
*   Direct HTTP calls from the LLM are disallowed.

---

## 12. Celery / Redis / Channels

*   **Redis**: Port 6379, channel layers on DB 0, locks on DB 1.
*   **Celery**: Background loops run on Celery. Tasks in `prospecting/tasks.py` are obsolete and will be removed, and a new `market/tasks.py` will host cron schedules like `refresh_stock_snapshot`.

---

## 13. Proposed Target Architecture

The repository will be restructured as a clean modular monolith:
```text
nomad-market/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── celery.py
│
├── market/                  # NSE/BSE Instruments & Snapshot Cache
│   ├── models.py            # Company, Instrument, MarketSnapshot
│   ├── services/            # Market data business operations
│   ├── providers/           # API connections (e.g., NSE/BSE wrappers)
│   ├── normalizers/         # Maps response to canonical schemas
│   ├── api/                 # DRF Views
│   ├── tasks.py             # refresh_stock_snapshot Celery task
│   └── tests/
│
├── research/                # Financial reports & evidence registry
│   ├── models.py            # ResearchRun, Evidence, ResearchReport
│   ├── services/
│   ├── Ingestion/           # Parses PDF filings/annual reports
│   └── tests/
│
├── intelligence/            # LangGraph state machine runtime
│   ├── agents/              # Planner, Critic, MarketResearchAgent
│   └── workflows/
│
├── llm/                     # Telemetry router & prompts registry
│   ├── router.py
│   ├── models.py
│   └── tools/
│       ├── base.py
│       ├── registry.py
│       └── executor.py
│
└── chat/                    # WS connections & thread checkpoints
    ├── models.py            # UserProfile, Conversation, Message, Checkpoints
    └── consumers.py
```

---

## 14. Files to Delete

*   `Dockerfile` (already deleted)
*   `docker-compose.yml` (already deleted)
*   The entire `applications/` app directory.
*   The entire `resume/` app directory.
*   The entire `prospecting/` app directory.
*   The `knowledge_base/` app directory.

---

## 15. Files to Modify

*   `config/settings.py`: Remove obsolete apps from `INSTALLED_APPS` and logger configurations.
*   `config/urls.py`: Remove obsolete URLs.
*   `chat/models.py`: Redefine/migrate `UserProfile` here and update foreign key targets.
*   `chat/views.py`: Change `UserProfile` imports from `knowledge_base` to `chat.models` and adapt default user retrieval.
*   `chat/tasks.py`: Change `UserProfile` imports.
*   `chat/orchestrator/single_agent.py`: Remove B2B prospecting tools and job reasoning agents.
*   `chat/agents/v2_graph.py`: Simplify node graph, removing B2B resume customization nodes.

---

## 16. Files to Create

*   `market/models.py`: Declares `Company`, `Instrument`, and `MarketSnapshot` models.
*   `market/providers/base.py`: Defines the `MarketDataProvider` protocol.
*   `market/normalizers/`: Standard mapping protocols.
*   `market/services/`: Services for handling quotes.
*   `market/tasks.py`: Implements `refresh_stock_snapshot`.
*   `research/models.py`: Declares `ResearchRun`, `Evidence`, and `ResearchReport`.
*   `docs/migration/phase-0-audit.md`: (This document).

---

## 17. Migration Sequence

1.  **Phase 1**: Move/redefine `UserProfile` to `chat.models` and perform cleanup migrations to safely isolate and remove career/prospecting models.
2.  **Phase 2**: Delete directories `applications/`, `resume/`, `prospecting/`, and `knowledge_base/`.
3.  **Phase 3**: Configuration updates in `config/` (settings, urls).
4.  **Phase 4**: Initialize `market/` Django app and write models (`Company`, `Instrument`, `MarketSnapshot`).
5.  **Phase 5**: Create provider boundary and canonical schema mapping layers in `market/providers/` and `market/normalizers/`.
6.  **Phase 6**: Implement `get_stock_snapshot` tool and register it in `ToolRegistry`.
7.  **Phase 7**: Initialize `research/` app and create `ResearchRun`, `Evidence`, `ResearchReport` models.
8.  **Phase 8**: Integrate intelligence runtime graph nodes, removing resume planning and matching agents.
9.  **Phase 9**: Implement Celery tasks and scheduling configurations.
10. **Phase 10**: Verify final end-to-end integration and run migrations checks.

---

## 18. Verification Commands

The following commands will verify state progress:
*   `python manage.py check`: Checks for configuration and relational model errors.
*   `python manage.py showmigrations`: Verifies migration tree state.
*   `venv/bin/python manage.py test`: Executes tests.

---

## 19. Risks

1.  **Migration Dependency Failures**: Deleting `UserProfile` while `chat` models still reference it will result in broken migration dependencies. Re-routing the relation to `chat.UserProfile` first is required.
2.  **Data Deletion**: Since this is a local development database, schema resets are acceptable, but any manual credentials stored in the DB (like `AgentConfig`) will be reset unless backed up.
3.  **Third-Party API Outages**: Providers must be mocked during unit tests to avoid flakiness.

---

## 20. Questions / Ambiguities

*   Do we want to maintain the `django-celery-beat` database configurations for our new scheduler, or can we clean up historical periodic tasks?
*   Should the local user profile name default to `'default_user'` as previously established, or should it use standard Django Auth user models for authentication?
    *   *Recommendation*: Keep it simple using the simplified `UserProfile` table with default value queries to preserve compatibility with existing token and memory checks.

---

## Recommended First Migration Step:
**Define and migrate `UserProfile` to the `chat` application, re-routing foreign keys in `Conversation` and `AgentMemory` to point to `chat.UserProfile` before deleting the `knowledge_base` app.**
