# Target Architecture Gap Analysis

This document details the comparison between the **current implementation** as of Module 0 and the **target systems** across all stock market analysis domains.

---

## 1. Domain-by-Domain Analysis

### 1. Market Data (Ingestion & Feed)
*   **Current State**: Ingestion is decoupled via `MarketService`. We use a simulated quote generator (`DummyMarketProvider`) returning mocked Indian stock payloads and normalizing them to a `MarketQuote` Pydantic model.
*   **Reusable Components**: `MarketService` pipeline, `MarketQuote` Pydantic schema.
*   **Missing Pieces**: Live integration with real market data vendors (e.g. YFinance API or NSE web scrapers). Support for historical daily price bars (historical charts) and order-book depth.
*   **Architectural Risk**: Rate limits on public APIs or script brittleness for HTML scrapers.
*   **Target Module**: *MODULE 1: Market Data Foundation*.

### 2. Instrument / Universe Configuration
*   **Current State**: We have `Company` and `Instrument` models representing equity stock listings on exchanges (`NSE`, `BSE`).
*   **Reusable Components**: Both models and their customized admin configurations.
*   **Missing Pieces**: Index components (e.g. NIFTY 50 constituents), derivatives (F&O options and futures contract universes), currency support, and corporate action adjusters.
*   **Architectural Risk**: Duplicate tickers across boards ifISIN matches are mismanaged.
*   **Target Module**: *MODULE 1: Market Data Foundation*.

### 3. Technical / Quant Features
*   **Current State**: None. No indicators exist in the repository.
*   **Reusable Components**: None.
*   **Missing Pieces**: Technical indicator calculation engine (RSI, MACD, Moving Averages, Bollinger Bands) and price pattern recognition scanners.
*   **Architectural Risk**: High-frequency processing blockages if computations are executed inside WebSockets or request threads.
*   **Target Module**: *MODULE 2: Quant & Technical Analysis*.

### 4. Fundamental Analysis
*   **Current State**: Basic sector metadata mapping exists in `MarketService`.
*   **Reusable Components**: Basic sector fields on the `Company` model.
*   **Missing Pieces**: Balance Sheet, Income Statement, Cash Flow data models, valuation ratios (P/E, P/B, Debt/Equity, ROE), and quarterly result scrapers.
*   **Architectural Risk**: Dirty or inconsistent data formats across corporate filings.
*   **Target Module**: *MODULE 3: Fundamental Analysis*.

### 5. Corporate Documents & Fillings
*   **Current State**: None.
*   **Reusable Components**: None.
*   **Missing Pieces**: PDF annual report parsing engine, text chunking, and Vector Search/embedding database support for QA.
*   **Architectural Risk**: Heavy resource overhead in PDF processing inside Celery.
*   **Target Module**: *MODULE 4: Document Intelligence*.

### 6. News & Event Intelligence
*   **Current State**: Generic `SearchWebTool` and `CrawlWebsiteTool` tools.
*   **Reusable Components**: Scraper tools.
*   **Missing Pieces**: Dynamic news ingestion tasks, News feed models, sentiment scoring models, and event-driven signals.
*   **Architectural Risk**: Noise and hallucinated sentiment interpretations.
*   **Target Module**: *MODULE 5: News & Event Intelligence*.

### 7. Sector & Thematic Scans
*   **Current State**: Basic sector/industry classification fields on the `Company` model.
*   **Reusable Components**: `Company` metadata catalog.
*   **Missing Pieces**: Sector weight monitors, sector rotation scanner, and thematic stock lists (e.g., Green Energy, EV plays).
*   **Target Module**: *MODULE 6: Sector & Thematic Scans*.

### 8. AI Research & Reasoning
*   **Current State**: LangGraph orchestration workflow (`chat/agents/v2_graph.py`) containing planner, executor ReAct loop, critic review, and report synthesis nodes. Bootstrapped financial prompts seeded in DB.
*   **Reusable Components**: Complete graph structure, prompt registry, checkpoint saver, and `ResearchAgent`.
*   **Missing Pieces**: Specialized multi-agent research personas (e.g., Fundamental analyst agent, Technical analyst agent, macro reviewer agent).
*   **Target Module**: *MODULE 7: Intelligence Orchestration*.

### 9. Signals & Strategies (Decision Plane)
*   **Current State**: None.
*   **Reusable Components**: None.
*   **Missing Pieces**: Database models for `Strategy` config, `Signal` triggers (BUY/SELL), and risk check parameters.
*   **Target Module**: *MODULE 8: Signal & Strategy Engine*.

### 10. Recommendations & Outcomes
*   **Current State**: None.
*   **Reusable Components**: None.
*   **Missing Pieces**: Recommendation logger, P&L tracker, trailing stop losses, and backtesting simulation modules.
*   **Target Module**: *MODULE 9: Recommendations & Outcomes*.
