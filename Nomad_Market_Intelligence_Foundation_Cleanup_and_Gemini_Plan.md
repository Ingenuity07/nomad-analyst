# Nomad Market Intelligence — Foundation Cleanup & Migration Plan

> **Purpose:** This document is the technical execution plan for converting the existing Nomad Bot / Analyst Django project into the foundation of a personal Indian Stock Market Intelligence platform.
>
> **Important:** This phase is a **cleanup and foundation migration only**. We are not building the stock-analysis engine yet. We are removing obsolete career/prospecting functionality, preserving reusable platform infrastructure, and establishing the correct domain boundaries so the next modules can be built cleanly.

---

## 1. Product Direction

The eventual platform will provide:

1. Indian stock-market universe
2. Current and historical market data
3. Fundamental company analysis
4. Technical analysis
5. Company documents and filings
6. News and corporate-event intelligence
7. Sector analysis
8. Global/macro market cues
9. Future-demand/theme discovery
10. Small-cap/mid-cap/large-cap discovery
11. Hidden-gem research
12. Intraday buy/sell setups
13. Entry, stop-loss and target calculations
14. Delivery/positional ideas
15. Signal tracking and outcome measurement
16. Backtesting
17. Persistent market knowledge
18. LLM-assisted research and reasoning

The architecture must therefore separate:

```text
External Data
    ↓
Provider Adapters
    ↓
Canonical / Normalized Data
    ↓
Deterministic Analytics
    ↓
Evidence / Research
    ↓
LLM Reasoning
    ↓
Analysis / Thesis
    ↓
Signals
    ↓
Outcome Tracking
```

The LLM is an intelligence layer, **not the database or source of numerical truth**.

---

# 2. Current Architecture: What We Are Preserving

The existing project contains reusable platform infrastructure that should remain the foundation.

## Keep

### Django / DRF

Use Django as the application framework and DRF for APIs.

### PostgreSQL

Primary persistent application database.

### Redis

Retain Redis for:

- cache
- locks
- Celery broker/backend as currently configured
- Channels as currently configured

### Celery

Retain background task infrastructure.

### Django Channels / ASGI

Retain real-time communication capability.

This will become useful later for:

- live market state
- intraday signals
- scanner updates
- analysis progress

### LLM Router

Preserve the existing intelligent LLM routing architecture.

### Tool Registry

Preserve generic tool registration.

### Tool Executor

Preserve:

- schema validation
- execution lifecycle
- error handling
- telemetry
- logging
- authorization/security mechanisms where applicable

### LangGraph / Agent Runtime

Preserve the existing workflow/checkpoint architecture where it is generic.

### Telemetry

Preserve:

- PromptRun
- model/provider tracking
- latency
- token usage
- tool execution telemetry

### Provider Execution / Evidence Concepts

Preserve and repurpose these concepts for financial research.

---

# 3. What Must Be Removed

The current project was originally designed around career/prospecting functionality.

Remove domain-specific functionality around:

- prospecting campaigns
- ICP profiles
- lead companies
- contacts
- buying groups
- CRM
- sales guidance
- email sequences
- inbound sales replies
- resume generation
- ATS analysis
- resume versions
- job applications
- job postings
- career knowledge-base entities
- candidate/project/skill relationships

Do not delete generic infrastructure merely because it currently happens to be used by an obsolete module.

---

# 4. Target Architecture After Cleanup

Initial target:

```text
nomad-market/
│
├── config/
│
├── market/
│   ├── models.py
│   ├── services/
│   ├── providers/
│   ├── normalizers/
│   ├── api/
│   ├── tasks.py
│   └── tests/
│
├── research/
│   ├── models.py
│   ├── services/
│   ├── ingestion/
│   ├── evidence/
│   ├── api/
│   ├── tasks.py
│   └── tests/
│
├── intelligence/
│   ├── agents/
│   ├── workflows/
│   ├── services/
│   └── tests/
│
├── llm/
│   ├── router.py
│   ├── models.py
│   └── tools/
│       ├── base.py
│       ├── registry.py
│       ├── executor.py
│       ├── schemas/
│       └── implementations/
│
├── chat/
│
├── tests/
│
└── manage.py
```

Do not create every possible future submodule now.

For example, do **not** create:

```text
market/
    technical/
    fundamentals/
    options/
    signals/
    portfolio/
    macro/
    sectors/
```

until those capabilities actually exist.

---

# 5. Migration Philosophy

## 5.1 Inspect First

Before changing code, inspect:

- repository tree
- Django apps
- models
- migrations
- settings
- URLs
- Celery tasks
- Redis configuration
- Channels configuration
- LLM providers
- tool registry
- tool executor
- agents
- LangGraph graphs
- checkpointing
- telemetry
- dependencies
- tests
- admin
- management commands
- environment variables

The actual repository is the source of truth.

---

## 5.2 No Big-Bang Rewrite

Work in small phases.

Each phase must:

1. modify only relevant files
2. run tests
3. run Django checks
4. inspect git diff
5. verify imports
6. verify migrations
7. document changes
8. stop if a material discrepancy is found

---

## 5.3 No Premature Architecture

Do not introduce:

- microservices
- Kafka
- event buses
- Kubernetes
- vector databases
- complex data lakes
- service meshes
- generic factory factories
- unnecessary repository abstractions
- unnecessary domain events

The application is a personal project and should remain a **modular monolith**.

---

# 6. Phase 0 — Repository Audit

**No code changes.**

Create an audit containing:

### Application inventory

For every Django app:

```text
app
purpose
models
URLs
tasks
dependencies
tests
status:
    KEEP
    REMOVE
    REPURPOSE
```

### Model inventory

For every model:

```text
model
app
relationships
purpose
keep/remove/repurpose
reason
```

### Infrastructure inventory

Document:

```text
PostgreSQL
Redis
Celery
Channels
LLM providers
Tool Registry
Tool Executor
LangGraph
Checkpointing
Telemetry
```

### Dependency inventory

Identify packages used only by obsolete domains.

Do not remove a package solely because it looks related; verify imports/usages first.

### Migration inventory

Identify:

- active migrations
- obsolete migrations
- cross-app dependencies
- database routers
- telemetry DB usage
- migration risks

### Output

Create:

```text
docs/migration/phase-0-audit.md
```

The agent must stop after producing the audit.

---

# 7. Phase 1 — Remove Obsolete Domain

Remove career/prospecting functionality safely.

## Prospecting

Remove domain entities such as:

```text
Workspace
ProspectingCampaign
ICPProfile
ProblemSignal
LeadCompany
CompanySource
WebsiteAnalysis
Qualification
Person
ContactPoint
BuyingGroupMember
SalesGuidance
EmailSequence
EmailMessage
InboundReply
```

Before deleting each one, search:

```text
imports
foreign keys
serializers
views
URLs
admin
Celery tasks
signals
tests
management commands
```

Do not leave dangling imports.

---

# 8. Phase 2 — Remove Resume Domain

Remove:

- resume models
- resume versions
- LaTeX generation
- ATS analysis
- resume templates
- resume APIs
- resume tasks
- resume tests

Before removal, identify shared dependencies.

Do not remove a library if another active component still requires it.

---

# 9. Phase 3 — Remove Application Tracking

Remove job application models and functionality.

Clean:

- models
- migrations where appropriate
- serializers
- APIs
- URLs
- admin
- services
- tasks
- tests

---

# 10. Phase 4 — Remove Career Knowledge Base

Remove career-specific models such as:

```text
UserProfile
ProfessionalKnowledgeBase
Experience
Project
Skill
SkillExperienceLink
SkillProjectLink
ProjectExperienceLink
JobPosting
```

However, preserve the **concept of persistent knowledge**.

It will later become:

```text
Company Knowledge
Sector Knowledge
Theme Knowledge
Research Evidence
Historical Theses
Signal Outcomes
```

---

# 11. Phase 5 — Configuration Cleanup

Update:

```text
settings.py
urls.py
asgi.py
celery.py
routing.py
```

Remove references to deleted apps.

Verify:

```bash
python manage.py check
python manage.py showmigrations
```

Run the full existing test suite.

Verify:

- Django startup
- Celery startup
- Redis connectivity
- Channels configuration
- database routing
- telemetry database
- environment variable loading

Do not rewrite configuration unnecessarily.

---

# 12. Phase 6 — Preserve and Clean LLM Layer

The LLM layer is reusable and should remain.

Preserve:

```text
IntelligentRouter
AgentConfig
LLMPrompt
PromptRun
ToolRegistry
ToolExecutor
```

Remove only prompts/configurations tied to:

- prospecting
- sales
- resume
- job applications
- candidate matching

---

## LLM responsibility

The LLM can:

- reason
- summarize
- compare
- classify
- formulate research questions
- interpret evidence
- challenge a thesis
- synthesize findings

The LLM must not be responsible for authoritative:

- price
- OHLC
- volume
- market cap
- PE
- EPS
- ROE
- technical indicators
- entry price
- stop-loss
- target price

Those must come from deterministic data/analytics services.

---

# 13. Phase 7 — Tool Architecture Cleanup

Preserve:

```text
Tool
ToolRegistry
ToolExecutor
```

The target flow is:

```text
LLM / Agent
     ↓
Tool Registry
     ↓
Tool Executor
     ↓
Domain Service
     ↓
Provider
     ↓
Canonical Data
```

Never:

```text
LLM
 ↓
direct HTTP request
```

The tool layer becomes the controlled gateway into external systems.

---

# 14. Phase 8 — Create `market` App

Create:

```text
market/
```

The first domain models are deliberately minimal.

---

## Company

Suggested fields:

```text
id
name
legal_name
short_name
isin
sector
industry
sub_industry
description
website
is_active
created_at
updated_at
```

Do not duplicate every financial metric here.

---

## Instrument

Suggested fields:

```text
id
company
symbol
exchange
isin
instrument_type
currency
lot_size
is_active
created_at
updated_at
```

Use choices/enums for:

```text
NSE
BSE
```

and:

```text
EQUITY
ETF
INDEX
FUTURE
OPTION
```

Even though V1 focuses on equities.

---

## MarketSnapshot

Represents a current/point-in-time observation:

```text
id
instrument
timestamp
open
high
low
close
volume
previous_close
change
change_percent
source
source_timestamp
created_at
```

Do not put calculated indicators into this model.

---

# 15. Company vs Instrument

This distinction is mandatory.

A company is not the same thing as a tradable instrument.

Future examples:

```text
Company
    ↓
NSE Equity
BSE Equity
Futures
Options
```

This prevents the entire system from becoming dependent on a symbol-only worldview.

---

# 16. Phase 9 — Market Provider Boundary

Create:

```text
market/providers/
market/normalizers/
market/services/
```

Provider responsibilities:

```text
external API
    ↓
provider-specific response
```

Normalizer responsibilities:

```text
provider response
    ↓
canonical internal schema
```

Domain services consume only canonical objects.

---

## Provider interface

Start with a small interface:

```python
class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> MarketQuote:
        ...
```

Do not build a provider factory until a second real provider exists.

---

# 17. Phase 10 — First Market Tool

Implement:

```text
get_stock_snapshot(symbol)
```

Input:

```json
{
  "symbol": "RELIANCE"
}
```

Output should be structured:

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "price": 1423.50,
  "change": 12.40,
  "change_percent": 0.88,
  "volume": 1234567,
  "timestamp": "..."
}
```

Use schema validation.

Route it through:

```text
ToolRegistry
→ ToolExecutor
→ MarketService
→ Provider
→ Normalizer
```

---

# 18. First End-to-End Vertical Slice

The first real success condition is:

```text
User
 ↓
Chat/API
 ↓
LLM Router
 ↓
Tool selection
 ↓
Tool Registry
 ↓
Tool Executor
 ↓
get_stock_snapshot
 ↓
Market Service
 ↓
Market Provider
 ↓
Normalizer
 ↓
Canonical MarketQuote
 ↓
MarketSnapshot
 ↓
LLM explanation
 ↓
User
```

Example:

> "What is the current price of RELIANCE?"

The answer must originate from the market tool.

The LLM should not guess.

---

# 19. Phase 11 — Create `research` App

Create:

```text
research/
```

Initial models:

## ResearchRun

```text
id
research_type
status
query
started_at
completed_at
created_at
```

## Evidence

```text
id
research_run
source_type
source_name
source_url/reference
title
content
published_at
retrieved_at
content_hash
metadata
```

## ResearchReport

```text
id
research_run
title
summary
analysis
created_at
updated_at
```

Keep the schema small.

---

# 20. Evidence Model Philosophy

Research must be reproducible.

A conclusion should eventually look conceptually like:

```text
Thesis
 ├── Annual Report
 ├── Quarterly Result
 ├── Investor Presentation
 ├── Corporate Announcement
 ├── News Article
 └── Historical Market Data
```

Every evidence item should capture:

```text
where it came from
when it was published
when we retrieved it
what content was used
which research run used it
```

This will later allow the system to answer:

> "Why did you reach this conclusion?"

---

# 21. Phase 12 — Intelligence Layer

Create/retain:

```text
intelligence/
    agents/
    workflows/
    services/
```

Do not migrate every old agent immediately.

Keep generic:

- planner
- graph runtime
- checkpointing
- execution state

Initially support only the minimum research workflow.

Potential first role:

```text
MARKET_RESEARCH
```

Future roles:

```text
FUNDAMENTAL_ANALYST
TECHNICAL_ANALYST
SECTOR_ANALYST
MACRO_ANALYST
CRITIC
SYNTHESIS
```

Do not implement them yet.

---

# 22. Phase 13 — Chat Boundary

Keep chat.

But enforce:

```text
chat
 ↓
intelligence
 ↓
services/tools
 ↓
market/research
```

Never:

```text
chat/views.py
    calculate PE
    calculate RSI
    fetch NSE data
    build trading signals
```

Chat is an interface.

It is not the domain layer.

---

# 23. Phase 14 — Celery Foundation

Remove obsolete prospecting scheduled jobs.

Create:

```text
market/tasks.py
```

Initially one task is sufficient:

```text
refresh_stock_snapshot
```

Do not build the full market scheduler.

Future jobs can include:

```text
refresh_market_universe
refresh_daily_prices
refresh_historical_prices
refresh_news
refresh_company_documents
refresh_financials
calculate_features
run_daily_analysis
```

Those belong to later modules.

---

# 24. Phase 15 — Admin

Configure Django admin for:

```text
Company
Instrument
MarketSnapshot
ResearchRun
Evidence
ResearchReport
```

Provide:

- list display
- search
- filtering
- readonly timestamps
- useful foreign-key navigation

Django admin is the initial operational UI.

Do not build a large frontend dashboard during cleanup.

---

# 25. Phase 16 — Testing

Every new layer requires tests.

## Model tests

Test:

- constraints
- relationships
- choices
- timestamps
- uniqueness

## Provider tests

Test:

```text
provider response
→ normalizer
→ canonical schema
```

## Service tests

Test market-service behavior independently from the provider where possible.

## Tool tests

Test:

```text
schema validation
registry lookup
executor execution
error handling
```

## Integration tests

Test:

```text
ToolRegistry
→ ToolExecutor
→ MarketTool
→ Service
→ Provider
→ Normalizer
```

## LLM tests

Test:

- structured output
- tool invocation
- fallback behavior
- malformed model output
- prompt versioning

Do not write tests that depend on a model producing one exact natural-language answer.

---

# 26. Database and Migration Safety

Before modifying models:

1. inspect current database usage
2. inspect migration graph
3. identify data worth preserving
4. back up if necessary
5. determine whether this is a disposable development database

Never blindly:

```bash
rm db.sqlite3
```

or destroy PostgreSQL data merely to make migrations easy.

For a personal development environment, a clean rebuild can be acceptable **only after explicitly verifying that no valuable data is being lost**.

---

# 27. Dependency Cleanup

After deleting obsolete apps:

1. search imports
2. identify packages used exclusively by removed apps
3. remove only verified-unused dependencies
4. regenerate/update dependency lock information if the repository uses it
5. run the test suite

Do not aggressively upgrade unrelated packages during this migration.

---

# 28. Code Quality Standards

New code should:

- use type hints where practical
- use clear names
- keep functions focused
- avoid fat views
- avoid circular imports
- use timezone-aware datetimes
- validate external input
- avoid logging secrets
- use environment variables for credentials
- use transactions where appropriate
- avoid duplicated provider parsing
- have tests for important branches
- follow existing repository formatting/linting conventions

Do not introduce a new coding style if the repository already has one.

---

# 29. Explicit Non-Goals

Do NOT implement during cleanup:

- automated broker trading
- order placement
- portfolio management
- technical indicators
- RSI/MACD/ATR engine
- options chain analytics
- fundamental scoring
- hidden-gem scoring
- intraday signal engine
- entry/exit prediction
- backtesting
- vector DB
- Kafka
- Kubernetes
- microservices
- large React dashboard
- autonomous trading agent

These come later.

---

# 30. Commit Strategy

Prefer small logical commits:

```text
01 audit baseline
02 remove obsolete prospecting domain
03 remove resume/application domains
04 clean Django configuration
05 create market app
06 add market models
07 add market provider boundary
08 add first market provider
09 add get_stock_snapshot tool
10 create research app
11 integrate intelligence/chat
12 tests/admin/documentation
```

Do not combine unrelated changes into one huge commit.

---

# 31. Definition of Done

The cleanup/foundation phase is complete only when:

### Application

```text
python manage.py check
```

passes.

### Database

Migrations apply cleanly.

### Tests

Existing relevant tests pass and new tests pass.

### Infrastructure

- PostgreSQL works
- Redis works
- Celery remains valid
- Channels remains valid
- telemetry remains valid
- LLM router remains valid

### Domain

Obsolete career/prospecting functionality is removed.

### Market

The following exist:

```text
Company
Instrument
MarketSnapshot
```

### Tooling

This works:

```text
get_stock_snapshot("RELIANCE")
```

through the existing tool system.

### Research

The following exist:

```text
ResearchRun
Evidence
ResearchReport
```

### Architecture

No provider-specific data structure leaks into the domain.

No market business logic lives in chat.

No unnecessary infrastructure has been introduced.

---

# 32. After Cleanup: Module Roadmap

Once the foundation is stable, build one module at a time:

```text
01 Market Universe
        ↓
02 Current Market Data
        ↓
03 Historical OHLCV
        ↓
04 Fundamental Data
        ↓
05 Company Research
        ↓
06 News + Corporate Events
        ↓
07 Sector Intelligence
        ↓
08 Global/Macro Intelligence
        ↓
09 Technical Analysis
        ↓
10 Market Regime
        ↓
11 Hidden-Gem Discovery
        ↓
12 Intraday Scanner
        ↓
13 Signal Engine
        ↓
14 Backtesting
        ↓
15 Signal Outcome Tracking
        ↓
16 Portfolio Intelligence
```

Each module must be independently useful and tested before the next one begins.

---

# 33. Gemini Coding Agent Execution Prompt

Copy everything below into Gemini after attaching/providing this document.

---

## SYSTEM / ROLE

You are the senior backend engineer responsible for transforming this existing Django repository into the foundation of a personal Indian Stock Market Intelligence Platform.

You are working on an EXISTING CODEBASE.

Your priority is:

**correctness > preservation of working infrastructure > simplicity > speed.**

Do not redesign the entire system.

The attached migration plan is the target architecture and execution strategy.

The actual repository is the source of truth when determining current implementation details.

---

## CRITICAL RULES

1. **AUDIT FIRST.**
2. Do not modify code during Phase 0.
3. Stop after Phase 0 and report the audit.
4. Wait for approval before making migration changes.
5. Preserve reusable infrastructure.
6. Remove obsolete business-domain functionality.
7. Do not introduce unnecessary infrastructure.
8. Do not build future stock-analysis modules during cleanup.
9. Keep market numeric truth deterministic.
10. Keep provider-specific formats behind provider/normalizer boundaries.
11. Keep business logic out of chat views/consumers.
12. Do not silently resolve major architectural discrepancies; report them.
13. Do not delete valuable data without verification.
14. Avoid unrelated refactoring.
15. Work in small logical phases/commits.

---

# PHASE 0 — READ-ONLY AUDIT

Do NOT modify files.

Inspect:

- repository tree
- Django apps
- models
- migrations
- settings
- URLs
- serializers
- services
- Celery tasks
- Redis
- Channels
- LLM providers
- IntelligentRouter
- ToolRegistry
- ToolExecutor
- LangGraph graphs
- checkpointing
- telemetry
- admin
- management commands
- tests
- requirements/dependencies
- environment configuration

For every Django app report:

```text
APP
Purpose
Models
URLs
Tasks
External dependencies
Tests
Keep / Remove / Repurpose
Reason
```

For every important model report:

```text
Model
Purpose
Relationships
Consumers
Keep / Remove / Repurpose
Migration risk
```

Also identify:

- files that can be deleted
- files that must be modified
- files that should remain untouched
- dependencies that can potentially be removed
- migration risks
- data-loss risks
- circular-import risks
- infrastructure risks

Create:

```text
docs/migration/phase-0-audit.md
```

At the end of Phase 0 provide:

```text
AUDIT COMPLETE

Current architecture:
...

Reusable infrastructure:
...

Obsolete domain:
...

Proposed migration:
...

Risks:
...

Files expected to change:
...

Files expected to delete:
...

Tests currently passing:
...

Recommended execution order:
...
```

STOP.

Do not continue until explicitly approved.

---

# PHASE 1 — CLEAN OBSOLETE DOMAIN

After approval:

Remove:

- prospecting
- lead generation
- CRM
- sales guidance
- buying groups
- outbound email sequences
- inbound sales replies
- resume generation
- ATS analysis
- resume versions
- job applications
- career knowledge-base models
- job postings

Before deleting anything:

Search all references.

Check:

- imports
- foreign keys
- serializers
- views
- URLs
- admin
- Celery tasks
- signals
- tests
- management commands
- settings
- migrations

Preserve generic infrastructure.

After changes:

```bash
python manage.py check
python manage.py test
```

If the repository uses configured lint/type checks, run them.

Inspect git diff.

Report:

```text
Files deleted
Files modified
Models removed
Routes removed
Tasks removed
Dependencies removed
Tests updated
Potential risks
```

---

# PHASE 2 — CONFIGURATION CLEANUP

Update only what is necessary in:

```text
settings
urls
asgi
celery
routing
```

Remove obsolete app references.

Verify:

- PostgreSQL
- Redis
- Celery
- Channels
- telemetry DB
- environment variables
- LLM configuration

Do not redesign configuration.

---

# PHASE 3 — MARKET APP

Create:

```text
market/
```

Implement:

### Company

```text
id
name
legal_name
short_name
isin
sector
industry
sub_industry
description
website
is_active
created_at
updated_at
```

### Instrument

```text
id
company
symbol
exchange
isin
instrument_type
currency
lot_size
is_active
created_at
updated_at
```

### MarketSnapshot

```text
id
instrument
timestamp
open
high
low
close
volume
previous_close
change
change_percent
source
source_timestamp
created_at
```

Do not add future analytical fields.

Create migrations.

Create admin.

Create tests.

---

# PHASE 4 — MARKET PROVIDER

Create:

```text
market/providers/
market/normalizers/
market/services/
```

Implement a minimal provider interface.

Use one concrete provider.

Do not create unnecessary factories.

Ensure:

```text
Provider
→ Normalizer
→ Canonical Schema
→ Service
```

Provider-specific response formats must never leak into Django domain models.

Add tests.

---

# PHASE 5 — FIRST TOOL

Implement:

```text
get_stock_snapshot(symbol)
```

The call path must be:

```text
ToolRegistry
→ ToolExecutor
→ Market Service
→ Provider
→ Normalizer
→ Canonical MarketQuote
```

Use structured validation.

Test:

- valid symbol
- invalid input
- provider failure
- timeout/error
- malformed provider response
- successful result

---

# PHASE 6 — RESEARCH

Create:

```text
research/
```

Implement:

```text
ResearchRun
Evidence
ResearchReport
```

Evidence must preserve source metadata and timestamps.

Reuse generic existing research/evidence concepts where appropriate instead of duplicating functionality.

---

# PHASE 7 — INTELLIGENCE

Preserve the existing:

- LLM Router
- Tool Registry
- Tool Executor
- LangGraph runtime
- checkpointing
- telemetry

Connect the minimum market research capability.

Do not build:

- technical analyst
- fundamental analyst
- macro analyst
- signal agent

yet.

---

# PHASE 8 — CHAT

Keep chat.

Ensure:

```text
chat
→ intelligence
→ tools/services
→ market/research
```

Chat must not contain market calculations or provider-specific API code.

---

# PHASE 9 — CELERY

Remove obsolete jobs.

Add only the minimum market task infrastructure required for the current foundation.

A simple initial task such as:

```text
refresh_stock_snapshot
```

is sufficient.

Do not build the full market scheduler.

---

# PHASE 10 — FINAL VERIFICATION

Run:

```bash
python manage.py check
python manage.py test
python manage.py showmigrations
```

and any existing:

```text
lint
type-check
format-check
```

Verify:

- application startup
- database connection
- migrations
- Redis
- Celery
- Channels
- LLM router
- ToolRegistry
- ToolExecutor
- first market tool
- admin
- research models
- no obsolete imports
- no dangling URLs
- no dangling tasks

---

# FINAL REPORT FORMAT

Return:

## 1. Executive Summary

## 2. Architecture After Migration

## 3. Deleted Components

## 4. Modified Components

## 5. New Components

## 6. Database Changes

## 7. Tooling Changes

## 8. LLM Changes

## 9. Tests Added

## 10. Commands Executed

## 11. Test Results

## 12. Remaining Technical Debt

## 13. Risks

## 14. Recommended Next Module

Do not recommend implementing multiple future modules at once.

Recommend only the **next single module**.

---

# Final Principle

This is not a rewrite.

It is:

```text
Existing Nomad Platform
        ↓
Remove obsolete business domain
        ↓
Preserve strong infrastructure
        ↓
Introduce market domain
        ↓
Build one working vertical slice
        ↓
Verify
        ↓
Next module
```

Build the foundation cleanly enough that future modules can be added without repeatedly restructuring the entire project.
