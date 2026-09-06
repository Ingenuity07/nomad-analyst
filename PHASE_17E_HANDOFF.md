# PHASE 17E HANDOFF: ON-DEMAND RESEARCH ENGINE

## 1. What Was Completed
Phase 17E successfully designed, implemented, and verified the **On-Demand Research Engine**, integrating the existing Nomad AI/LLM infrastructure (`llm.router.IntelligentRouter`) with the deterministic intelligence pipeline (Phase 17C Market Context & Phase 17D Opportunity Engine).

Key accomplishments:

1. **Zero LLM Calls for Default Nomad Operations**:
   - Market Context, Sector Analysis, Technical Analysis, Fundamental Analysis, News/Events, Intraday Opportunity Detection, Opportunity Scoring, Opportunity Ranking, and Horizon Scoring run 100% deterministically with **zero LLM calls**.
   - No automatic top-10 research, no background scanning, no cron jobs, and no LLM calls triggered on ticks or WebSocket updates.

2. **One-Call-Per-Examination Guarantee**:
   - Python/Django gathers and validates all facts beforehand into a single `ResearchEvidencePackage`.
   - Dispatches exactly ONE prompt to `IntelligentRouter.execute()`.
   - Receives and validates ONE structured JSON response matching the Pydantic schema `StructuredResearchOutput`.
   - Persists the snapshot and structured report.
   - Verified by automated tests: New Examination = exactly 1 LLM call.

3. **Research Caching & 0-Call Viewing**:
   - When a user views or reopens existing completed research, it is retrieved from the database with **0 LLM calls** (`reused: true`, `llm_calls_made: 0`).
   - Only an explicit click on **"Refresh Research"** executes 1 new LLM call.

4. **Deterministic Research Delta Service**:
   - `ResearchDeltaService` (`research/services/delta_service.py`):
   - Computes score changes, rank changes, opportunity state changes, momentum changes, VWAP diff changes, sector rank changes, and market regime changes with **zero LLM calls**.
   - Identifies freshness tiers (`FRESH`, `AGING`, `STALE`) and human-readable reasons (e.g., "Analysis was generated 35 minutes ago", "Opportunity score shifted by +12 pts", "Market regime changed from TRENDING_UP to RANGING").

5. **Concurrency Locking & Deduplication**:
   - Cache lock on `nomad:research_lock:{symbol}:{mode}` prevents duplicate concurrent LLM requests when a user double-clicks "Examine".

6. **Evidence Package Builder**:
   - `ResearchEvidencePackageBuilder` (`research/services/evidence_builder.py`):
   - Assembles Company, Instrument, Opportunity context, Stock context, Market context, Sector rotation, Fundamentals, Recent news, Corporate events, Data quality, and a pre-computed deterministic summary.
   - Preserves source attribution (`KITE_MARKET_FEED`, `FUNDAMENTAL_DATABASE`, `NEWS_SOURCE`, `CORPORATE_EVENT`, `DERIVED_CALCULATION`), timestamps, freshness, and computes SHA-256 `evidence_hash`.
   - Never converts missing data into 0; reports explicit `UNAVAILABLE` flags.

7. **Database Model & Migration**:
   - Extended `ResearchRun` in `research/models.py` with `symbol`, `research_mode`, `instrument`, `evidence_snapshot`, `evidence_hash`, `research_output`, `model_name`, `provider`, `tokens_used`, `duration_ms`, `opportunity_score_at_research`, `opportunity_state_at_research`, and indices.
   - Migration `0002_alter_researchrun_options_researchrun_duration_ms_and_more.py` applied.

8. **REST APIs (`market/urls.py` & `research/views.py`)**:
   - `POST /api/v1/research/examine/`
   - `GET /api/v1/research/{id}/`
   - `GET /api/v1/research/company/{symbol}/`
   - `POST /api/v1/research/{id}/refresh/`
   - `GET /api/v1/research/{id}/delta/`

9. **React 19 Frontend Integration**:
   - Hook: `useOnDemandResearch.ts` (`useExamineStock`, `useRefreshResearchRun`, `useResearchRun`, `useCompanyResearch`, `useResearchDelta`).
   - `IntradayOpportunityTable`: Added "Action" column with "EXAMINE" button in every row.
   - `IntradayOpportunityDetailDrawer`: Added "Examine with Deep AI Research (1 Call)" button.
   - `IntradayResearchModal`: High-aesthetic modal rendering:
     - Research Basis banner (time, score, rank, regime, sector rank).
     - Real-time Changes Since Analysis (Delta) with staleness indicators.
     - "[ Refresh Research (1 AI Call) ]" explicit button.
     - Structured findings (Executive Summary, Verified Facts vs Analyst Interpretation, Why Interesting, Supporting & Contradicting Evidence, Market & Sector Context, Key Risks, Unknowns, Thesis, What to Monitor, Invalidation Developments).
     - Telemetry strip (model, provider, tokens, latency, evidence hash).

10. **Test Coverage & Quality Assurance**:
    - Backend: 295/295 tests passing (100% green).
    - Frontend: 21 test files, 85/85 tests passing (100% green).
    - Production bundle compiled cleanly (`npm run build`).

---

## 2. Scope Boundaries & Explicit Safeguards
- **NO TRADE ORDERS / NO AUTONOMOUS EXECUTION**:
  - The AI model functions strictly as an analyst reasoning layer.
  - Zero BUY, SELL, ENTER, EXIT, STOP-LOSS, or TARGET price execution orders are produced.
  - LLM cannot overwrite deterministic metrics.
- **ZERO UNCONTROLLED TOOL-CALL CHAINS**:
  - All evidence is pre-fetched and validated deterministically; no recursive tool loops.
- **SECURITY**:
  - API keys and provider secrets are confined to backend environment variables and never exposed to the frontend.

---

## 3. Current State & Pending Market Verification
- **LIVE MARKET STREAM STATUS**: LIVE MARKET STREAM IMPLEMENTATION READY; REAL-MARKET VALIDATION PENDING NEXT NSE SESSION (09:15–15:30 IST).
