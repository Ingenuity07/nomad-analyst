# Global Technology Stack & Open Source Registry

This document defines the authoritative, global source of truth for technology, library, and framework decisions in the **Nomad Analyst Platform**.

---

## 1. Core Architectural Principle

> [!IMPORTANT]
> **Nomad Analyst owns the domain architecture.**
> External open-source software (OSS) projects, libraries, and frameworks are integrated only where they provide strong, proven, and necessary capabilities. We do not introduce a production dependency merely because a library is popular.
>
> Every third-party library must be classified under one of the three integration tiers below:
> 1. **Direct Production Dependency**: Core runtime dependencies installed in `requirements.txt` and imported directly in production code.
> 2. **Selective Integration**: Isolated utilities or specific algorithms extracted/referenced from the library without importing its full infrastructure or database layers.
> 3. **Research/Reference Project**: External repositories used solely as reference designs, code patterns, or implementation guides. They are never imported or run in production.

---

## 2. Technology Stack Registry

### 1. Yahoo Finance (Chart API)
*   **Purpose**: Initial market-data provider for live stock quotes and historical daily price metrics.
*   **Architectural Layer**: Data Plane (`market` app).
*   **Intended Module**: Module 1.
*   **Status**: Confirmed & Implemented.
*   **Classification**: Direct Production Dependency (via standard `requests` HTTP client).
*   **Why Selected**: Provides free, keyless, and reliable access to NSE and BSE equities without heavy client libraries or API subscription costs.
*   **What it must NOT be used for**: High-frequency streaming, order execution, or tick-by-tick order-book updates.
*   **Current Implementation Status**: Implemented in [`market/providers/yfinance.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/providers/yfinance.py).

### 2. TA-Lib (Technical Analysis Library)
*   **Purpose**: High-performance, deterministic technical indicator calculations (RSI, MACD, Moving Averages, Bollinger Bands).
*   **Architectural Layer**: Quant/Technical Feature Calculations.
*   **Intended Module**: Module 2.
*   **Status**: Confirmed.
*   **Classification**: Direct Production Dependency (to be added to `requirements.txt` in Module 2).
*   **Why Selected**: Standard, industry-grade C-compiled mathematical engine ensuring high-speed, reliable calculations of standard trading indicators.
*   **What it must NOT be used for**: Custom AI reasoning, portfolio optimization, or strategy simulation.
*   **Current Implementation Status**: Planned for Module 2.

### 3. VectorBT (Vectorized Backtesting)
*   **Purpose**: Quantitative strategy evaluation, historical backtesting, and parameters optimization.
*   **Architectural Layer**: Decision Plane (Backtesting).
*   **Intended Module**: Module 9.
*   **Status**: Confirmed.
*   **Classification**: Selective Integration / Research-Reference.
*   **Why Selected**: Provides vectorized matrix-based backtesting tools that are extremely fast and efficient for checking historical strategy rules.
*   **What it must NOT be used for**: Real-time market data ingestion or live order tracking. It must not be forced into the production database ingestion pipelines.
*   **Current Implementation Status**: Planned for Future Modules.

### 4. NautilusTrader
*   **Purpose**: Event-driven market-data and trading execution engine patterns.
*   **Architectural Layer**: Decision & Ingestion Planes.
*   **Intended Module**: Future Live Trading Integration.
*   **Status**: Confirmed.
*   **Classification**: Selective Integration / Research-Reference.
*   **Why Selected**: Offers high-performance, asynchronous event-driven loop patterns suitable for live broker connections.
*   **What it must NOT be used for**: General Django database models or LLM agent planning loops. Do not force its complex container/runtime architecture into basic research components.
*   **Current Implementation Status**: Planned for Future Modules.

### 5. Qlib (Quantitative Investment Platform)
*   **Purpose**: Machine learning quantitative research, data processing, and predictive scoring reference structures.
*   **Architectural Layer**: Intelligence Plane.
*   **Intended Module**: Future ML Modeling.
*   **Status**: Confirmed.
*   **Classification**: Research/Reference Project.
*   **Why Selected**: Provides Microsoft's AI-oriented quant framework patterns for model training and feature preprocessing pipelines.
*   **What it must NOT be used for**: Core Django REST views, WebSockets, or live quote normalizations.
*   **Current Implementation Status**: Planned for Future Modules.

### 6. Indian Market Open-Source Projects (e.g. `nsetools`, `nsepy`)
*   **Purpose**: Reference implementation guidelines for accessing National Stock Exchange (NSE) web headers, security symbols, option chains, and corporate actions.
*   **Architectural Layer**: Ingestion & Reference Data.
*   **Intended Module**: Module 1 & Future Ingestion.
*   **Status**: Confirmed.
*   **Classification**: Research/Reference Project (extracting code patterns only).
*   **Why Selected**: Provides proven scrapers and session header structures for navigating Indian exchange websites.
*   **What it must NOT be used for**: We must not blindly import these external packages directly in production due to their lack of maintenance and frequent connection breakages. Instead, we extract their header/query mechanics and implement them natively in our provider layer.
*   **Current Implementation Status**: Referenced during Module 1 setup.
