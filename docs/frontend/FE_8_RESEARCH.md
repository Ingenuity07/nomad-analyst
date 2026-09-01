# FE-8 Research & Intelligence Workspace Documentation

## Overview

The **Research & Intelligence Workspace** (`/research`) serves as the institutional research interface to Nomad Analyst's deterministic intelligence layer (Module 5).

It allows users to select an Indian stock, submit natural-language research questions or theses, configure research depth, set historical point-in-time (`as_of`) dates, and inspect a multi-dimensional synthesized intelligence dossier backed by verifiable factual evidence traces.

---

## Architecture & Integration

```
USER QUERY CONSOLE
  ├── Symbol: (e.g. RELIANCE, TCS, INFY)
  ├── Question: (e.g. "Assess capital structure & operating cash flow")
  ├── Depth: Quick (6 steps) | Standard (9 steps) | Deep (12 steps)
  └── As-Of: Live / Current vs Historical ISO Timestamp
            ↓
POST /api/v1/research/
            ↓
MarketResearchService (BE)
            ↓
MarketResearchAgent (ReAct loop with 24 market tools)
            ↓
Structured JSON Synthesis
            ↓
RESEARCH DOSSIER UI
  ├── ResearchReportHeader (Company, Symbol, PIT badge, As-Of vs Generated timestamps)
  ├── ResearchSummaryCard (Executive summary prose + Valuation & Price metrics strip)
  ├── FactorIntelligenceMatrix (Positive Drivers, Key Risks, Contradictions, Unknowns)
  ├── DeepAnalysisSections (Technicals, Financials & Margins, News & Corporate Events)
  ├── EvidenceDrawer (Slide-over listing of all cited factual traces)
  ├── SessionResearchHistory (In-memory recent inquiry cache)
  └── ResearchDisclaimer (Persistent non-advisory legal notice)
```

---

## API Contract

- **Endpoint**: `POST /api/v1/research/`
- **Method**: `POST`
- **Request Payload**:
  ```json
  {
    "symbol": "RELIANCE",
    "question": "Assess operating cash flows and margin trajectory.",
    "depth": "standard",
    "as_of": "2026-08-20T10:00:00Z"
  }
  ```
- **Response Structure**:
  ```json
  {
    "company": "Reliance Industries Limited",
    "instrument": "RELIANCE",
    "as_of": "2026-08-20T10:00:00Z",
    "summary": "...",
    "market_snapshot": { "price": 2975.5, "pe": 26.4 },
    "technical_analysis": "...",
    "fundamental_analysis": "...",
    "news_analysis": "...",
    "positive_factors": ["..."],
    "risks": ["..."],
    "contradictions": ["..."],
    "unknowns": ["..."],
    "evidence": ["..."],
    "generated_at": "..."
  }
  ```

---

## Key Features

1. **Research Console**:
   - Ticker selector with popular Indian stock presets (`RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, etc.).
   - Analytical thesis textarea with 4 prompt suggestions.
   - Depth selector (`quick`, `standard`, `deep`) mapping directly to backend tool iteration bounds.
   - Point-in-Time (`as_of`) toggle for historical research without lookahead bias.
2. **Executive Dossier**:
   - Executive summary with high-priority visual prominence.
   - Valuation snapshot metrics strip.
3. **Factor Intelligence Matrix**:
   - Color-coded cards: Positive Drivers (subtle green), Risks (subtle red), Contradictions (subtle yellow/amber), Unknowns (neutral info).
4. **Domain Analysis Tabs**:
   - Tabbed / stacked breakdown of Technical, Fundamental, and News impacts.
5. **Evidence & Citation Inspection**:
   - Slide-over drawer displaying verified source strings, statement periods, and indicator timestamps.
6. **Session In-Memory History**:
   - Automatically maintains the last 10 inquiries conducted in the active session for instant recall.
7. **Context Propagation**:
   - Navigating to `/research?symbol=TCS` automatically pre-populates the target stock symbol.
8. **Institutional Non-Advisory Notice**:
   - Persistent notice clarifying that synthesis is strictly research/analytical and does not constitute financial advice.

---

## Future & Non-Implemented Capabilities

- **PDF Annual Report RAG & Vector Embeddings**: Not implemented (backend lacks document chunking & vector DB).
- **Multi-turn conversational threads**: Not implemented in FE-8 (single-turn structured synthesis).
- **Token streaming via SSE/WebSockets**: Not implemented (synchronous structured JSON endpoint).
- **Persistent historical reports endpoint**: Not implemented (in-memory session history used).
