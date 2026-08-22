# Architecture Alignment Handoff

*   **Handoff Type**: Technology Stack & Architectural Alignment
*   **Date**: August 22, 2026
*   **Branch**: `main`
*   **Git Commit Hash**: `3ec6a24c9713fd80b46ef5a92166a53b836dbb47`

---

## 1. Context & Rationale

### What Was Wrong/Missing
Module 1 established the initial deterministic market data plane but did not catalog the target Open-Source Software (OSS) frameworks (TA-Lib, VectorBT, NautilusTrader, Qlib, etc.) and Indian-market integration designs that had been researched during previous exploration phases. Without a registry, there was a risk that subsequent modules might duplicate research or make conflicting architectural selections.

### Why the Issue Occurred
The scope of Module 1 focused exclusively on constructing the live data model (Yahoo Finance REST client) and verification test suites. A dedicated, unified global registry document was missing in the documentation tree.

---

## 2. Key Architectural Decisions

We established the fundamental principle: **Nomad Analyst owns the domain architecture.**
Third-party libraries are grouped into one of three classifications:
1.  **Direct Production Dependency**: Installed in `requirements.txt` and utilized directly in runtime execution.
2.  **Selective Integration**: Sub-components or specific formulas are extracted/reused without adopting the full project framework.
3.  **Research/Reference Project**: Used solely for reference patterns and logic layouts. Never imported or executed in production.

---

## 3. Global Technology Registry

| OSS Project / Library | Layer | Classification | Purpose in Nomad Analyst | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Yahoo Finance** | Data Plane | Direct Production | Initial NSE/BSE stock quote and daily chart provider. | Confirmed & Implemented |
| **TA-Lib** | Technical Features | Direct Production | Fast, C-compiled technical indicator calculations (RSI, MACD). | Confirmed (Planned for Module 2) |
| **VectorBT** | Backtesting | Selective Integration | Vectorized strategy backtesting and parameter reviews. | Confirmed (Planned for Future Modules) |
| **NautilusTrader** | Decision/Ingestion | Selective Integration | High-performance event-driven loop patterns for live trading. | Confirmed (Planned for Future Modules) |
| **Qlib** | Intelligence Plane | Research/Reference | Microsoft quantitative machine learning research layout guide. | Confirmed (Planned for Future Modules) |
| **Indian Market Scrapers** | Ingestion Plane | Research/Reference | Query header parameters and scrapers for NSE option charts. | Confirmed & Referenced |

---

## 4. Impact & Implications

*   **Module 1 Impact**: None. The Yahoo Finance Provider (`YFinanceMarketProvider`) and Normalizer (`YFinanceNormalizer`) remain intact and continue to drive quote updates.
*   **Module 2 Implications**: Establishes that **TA-Lib** will be the core technical indicator calculation engine. We must not write manual Python formulas for MACD or RSI, nor import heavy, unconfirmed dependencies.
*   **Unresolved Decisions**: None. All core library roles are fully defined.

---

## 5. File Changes Inventory

*   **Created**: [`docs/architecture/TECHNOLOGY_STACK.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/architecture/TECHNOLOGY_STACK.md)
*   **Modified**: [`MODULE_1_HANDOFF.md`](file:///Users/shivamsingh/personal/nomad-analyst/MODULE_1_HANDOFF.md) (appended reference to technology registry)
*   **Deleted**: None.

---

## 6. Current Architecture after Alignment
The platform runs as a modular monoline with a clean separation of concerns:
*   **Data Plane (`market`)**: Fetches raw data, filters out dirty metrics (quality gates), and writes to DB.
*   **Intelligence Plane (`research`)**: Manages AI graph executors and evidence logs.
*   **Decision Plane (Planned)**: Will leverage TA-Lib for indicator generation and VectorBT for quantitative backtesting.

---

## 7. Recommended Next Step
*   **Proceed to Module 2 (Quant & Technical Analysis)**: Install TA-Lib, create database schema configurations for calculated features, and develop technical indicator updates.
