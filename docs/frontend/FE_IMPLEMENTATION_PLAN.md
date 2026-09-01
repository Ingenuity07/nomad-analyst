# Nomad Analyst — Frontend Implementation Roadmap & Phase Plan

**Version:** 1.0.0  
**Target:** React 19 + TypeScript + Vite Frontend Application  
**Execution Strategy:** Modular, phase-gated delivery with automated verification at every step.

---

## Phase Breakdown & Milestone Schedule

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             FRONTEND DELIVERY ROADMAP                            │
├──────────────────────┬───────────────────────────────────────────────────────────┤
│ PHASE                │ DELIVERABLE SCOPE                                         │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ FE-1: Foundation     │ Shell, Design System Tokens, Router, Nav, IST Session Clock│
│ FE-2: Market View    │ Macro Indices, Breadth Bar, Sector Momentum Grid, News    │
│ FE-3: Stock Detail   │ Lightweight Charts Canvas, Technicals, Audited Statements │
│ FE-4: Opportunities  │ Ranked 6D Opportunity Table, Archetype Badges, Pros/Risks │
│ FE-5: Intraday Grid  │ Live 5m Signals, Setup Cards, R:R Meters, Readiness Panel │
│ FE-6: AI Research    │ Prompt Studio, Live Tool Trace Stream, Report Cards       │
│ FE-7: Backtesting    │ Walk-Forward Console, Expectancy/R Metrics, Trade Log     │
│ FE-8: Watchlists     │ Custom Symbol Trackers, Multi-Watchlist Organizer         │
│ FE-9: Hardening      │ Cmd+K Quick Search, Responsive Polish, Dark-Theme Audit   │
└──────────────────────┴───────────────────────────────────────────────────────────┘
```

---

### FE-1: Application Shell, Router & Design System
- **Goals:**
  - Initialize Vite React + TypeScript application structure.
  - Establish CSS Custom Property design tokens (`--bg-primary`, `--border-subtle`, `--bullish`, `--bearish`, monospace numerical classes).
  - Configure React Router (v7) with root layout, responsive sidebar, top header, and IST Market Session status banner.
  - Build reusable UI atom library: `Card`, `Badge`, `Button`, `Table`, `Tabs`, `DataStatusTag`, `ShimmerSkeleton`.
- **Verification:**
  - Shell loads cleanly in under 200ms with dark terminal theme.
  - Route transitions across empty placeholder views function smoothly.

---

### FE-2: Market Overview Workspace (`/market`)
- **Goals:**
  - Implement top macro index ticker strip (`^NSEI`, `^NSEBANK`, `^GSPC`, `USDINR=X`, `CL=F`).
  - Implement Market Regime Card and Advance/Decline Breadth Bar with live percentages.
  - Implement Sector Momentum Matrix with tier categorization (Strongest, Improving, Weakening, Lagging).
  - Implement Macro & Market News headline stream with source attribution.
- **Verification:**
  - Connects to `GET /api/market/overview/`.
  - Re-evaluates breadth and index quotes on background interval polling (30s).

---

### FE-3: Stock Detail Workspace (`/stocks/:symbol`)
- **Goals:**
  - Integrate TradingView Lightweight Charts canvas with volume sub-pane and multi-timeframe controls (`5m`, `15m`, `1h`, `1d`, `1w`).
  - Add indicator overlay toggles (SMA 20/50/200, EMA 9/21, VWAP, Bollinger Bands) and oscillator sub-panes (RSI 14, MACD).
  - Render setup price level lines (Entry, Stop Loss, Target 1, Target 2).
  - Build Tabbed Workspace: Technical Indicators Matrix, Multi-Period Statements Table (Income, Balance Sheet, Cash Flow), Sector Relative Strength, Corporate News Timeline.
- **Verification:**
  - Smooth 60fps pan and zoom across 500+ candlestick bars.
  - Financial statements display correct Crore/Lakh formatting with clean column alignment.

---

### FE-4: Delivery & Swing Opportunity Discovery (`/delivery`)
- **Goals:**
  - Build Opportunity Discovery Table with Universe (`NIFTY50`, `NIFTY_MIDCAP_100`) and Horizon (`DELIVERY_SWING`, `LONG_TERM`) filters.
  - Implement 6-Dimension Score visual breakdown meters (Technical 25%, Fundamental 25%, Sector 15%, Market 15%, News 10%, Liquidity 10%).
  - Implement Opportunity Detail Drawer highlighting deterministic pros, risks, and entry/stop parameters.
- **Verification:**
  - Connects to `GET /api/opportunities/`.
  - Sorting by Final Score, Sector, or Opportunity Type works instantly.

---

### FE-5: Live Intraday Intelligence (`/intraday`)
- **Goals:**
  - Build Intraday Setup Cards for active `BUY`/`SELL` signals (ORB Breakout, VWAP Reclaim, Trend Continuation, Mean Reversion).
  - Display exact Entry, Stop, Target 1, Target 2, R:R Ratio, Confidence, and Expiry Countdown.
  - Display Intraday Data Quality & Readiness widget (Warmup candle status, gap checks).
  - Implement WebSocket listener for instant real-time signal generation and status updates (`ENTRY_TRIGGERED`, `TARGET_HIT`, `STOP_HIT`, `EXPIRED`).
- **Verification:**
  - Verified against simulated and live session candle updates.
  - Expired signals automatically transition to dimmed state.

---

### FE-6: AI Stock Research Studio (`/research`)
- **Goals:**
  - Implement Natural Language Research Query Console with Quick, Standard, and Deep depth toggles.
  - Add optional historical Point-in-Time (`as_of`) calendar selector.
  - Build live Tool Execution Stream timeline widget showing tool names and elapsed runtimes.
  - Render structured Research Report cards: Executive Summary, Market Snapshot, Technicals, Fundamentals, News, Positive Drivers, Risk Drivers, Contradictions, Unknowns, and Evidence Traces.
- **Verification:**
  - Connects to `POST /api/research/query/`.
  - Report renders in under 6 seconds with evidence citation chips.

---

### FE-7: Quantitative Backtesting Laboratory (`/backtesting`)
- **Goals:**
  - Build Backtest Configuration Form: Universe, Timeframe, Date Range, Cost Model (`NO_COST`, `REALISTIC_NSE_EQUITY`), Ambiguity Policy.
  - Build Executive Performance Dashboard: Win Rate %, Expectancy, Avg R-Multiple, Profit Factor, Max Drawdown (in R), Average Holding Duration.
  - Add Small-Sample Warnings banner when `n < 10` or `n < 30`.
  - Build Dimensional Breakdown Tabs (By Setup Type, By Timeframe, By Direction, By Regime, By Sector) and Simulated Trade Log Table.
- **Verification:**
  - Connects to `POST /api/backtests/run/` and `GET /api/backtests/{run_id}/`.
  - Visual verification that zero look-ahead bias and transaction costs are honestly reflected.

---

### FE-8: Watchlists & System Alerts (`/watchlist`, `/alerts`)
- **Goals:**
  - Implement custom symbol watchlist manager with local storage persistence.
  - Build real-time notification stream for signal activations and market regime changes.
- **Verification:**
  - Watchlist symbols maintain live price polling and one-click navigation to Stock Detail.

---

### FE-9: Polish, Performance & Accessibility
- **Goals:**
  - Implement global `Cmd+K` keyboard shortcut for instant stock symbol autocomplete.
  - Ensure 100% keyboard accessibility and non-color-dependent status indicators.
  - Bundle optimization and Lighthouse performance auditing (Target: >90 score across Performance, Accessibility, and Best Practices).
- **Verification:**
  - Zero console errors, clean TypeScript build (`tsc -b`), fast client loading.
