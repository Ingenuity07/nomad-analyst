# Nomad Analyst — FE-2 Market Overview & Context Documentation

**Version:** 1.0.0 (FE-2 Complete)  
**Date:** September 1, 2026  
**Status:** Implemented & Verified (15/15 Vitest Tests + 229/229 Django Tests)  
**Route:** `/market`

---

## 1. Executive Summary

FE-2 delivers the first complete financial product workspace: **Market Overview & Market Context** (`/market`). It answers at a single glance:
- What is happening across Indian equity benchmark indices (NIFTY 50, SENSEX, BANK NIFTY, NIFTY IT)?
- What macro regime currently governs the market (BULLISH, BEARISH, SIDEWAYS, HIGH VOLATILITY) with technical moving average evidence?
- How broad is participation across the market universe (Advance/Decline ratio, % above 50/200 SMA)?
- Which sectors are leading or deteriorating (Relative Strength Alpha vs NIFTY, Average RSI, Volatility)?
- What global macro cues and material market disclosures are active?

---

## 2. Component Architecture

```
frontend/src/
├── features/market/components/
│   ├── IndexStrip.tsx                # Compact 4-up index quote strip (LTP, delta %, badge)
│   ├── MarketRegimeCard.tsx          # Macro trend regime, volatility state, 50/200 SMA evidence
│   ├── MarketBreadthBarometer.tsx    # Visual proportion bar, A/D ratio, % above 50/200 SMA
│   ├── SectorRotationMatrix.tsx      # Sortable sector ranking table with Alpha vs NIFTY & RSI
│   ├── GlobalCuesPanel.tsx           # Cross-market macro cues & directional bias badges
│   └── MarketNewsFeed.tsx            # Material market announcements & timestamps
├── pages/
│   └── MarketPage.tsx                # Root workspace orchestrator with universe selector & retry boundaries
└── test/
    └── marketPage.test.tsx           # Comprehensive Vitest unit & component test suite
```

---

## 3. Consumed REST APIs

| Endpoint | Method | Response Mapping | Purpose |
|---|---|---|---|
| `GET /api/v1/market/overview/?universe={universe}` | `GET` | `MarketOverviewResponse` | Complete market context, session phase, breadth, sector rankings, global cues, and news |
| `GET /api/v1/market/indices/` | `GET` | `{ indices: MarketIndexItem[], as_of: string }` | Dedicated high-freshness index quotes strip |

---

## 4. Design System Compliance

- **Tabular Numerals:** All LTPs, deltas, percentages, and moving averages use `--font-mono` with `font-variant-numeric: tabular-nums`.
- **Restrained Semantic Colors:** Emerald (`#10B981`) and Crimson (`#EF4444`) applied strictly to deltas and status tags with explicit directional glyphs (`▲`/`▼`).
- **Resilient Fallbacks:** Missing or non-traded instruments render explicit `—` and `UNAVAILABLE` states without crashing or rendering zero.
- **Section-Level Error Isolation:** If a sub-query fails, an `ErrorState` allows retrying that section without unmounting the rest of the workspace.
