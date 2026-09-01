# Nomad Analyst — Global Frontend Design System Specification

**Version:** 1.0.0 (Canonical Master Specification)  
**Date:** September 1, 2026  
**Status:** Permanent Source of Truth for Visual & Interaction Architecture  
**Philosophy:** Minimalist, Sober, Institutional Financial Terminal & Editorial Research Aesthetic

---

## 1. Core Principles & Philosophy

Nomad Analyst is an institutional-grade equity intelligence and quantitative research terminal designed for Indian equity markets. The visual identity balances high information density with visual calm, strict mathematical precision, and typographic elegance.

### Non-Negotiable Directives:
1. **Editorial Financial Restraint:** Neutral, low-fatigue dark surfaces. Prohibited: neon colors, glowing gradient borders, heavy glassmorphism, floating drop-shadow cards, and crypto/trading-game aesthetics.
2. **Tabular Monospace Numerical Precision:** All prices, volumes, percentages, ratios, R-multiples, and timestamps must use monospace tabular numerals (`font-feature-settings: 'tnum'`). Financial data never shifts or jitters during live updates.
3. **Restrained Semantic Color:** Color communicates directional delta and trade state only. Every color cue is accompanied by explicit text and icons—never relying on color alone.
4. **Information Architecture over Nested Cards:** Use structured sections, tables, subtle dividers, compact metric groups, and expandable detail drawers rather than wrapping every widget in a rounded box.
5. **Universal Component Reuse:** Every frontend module (FE-1 through FE-9) must strictly reuse these tokens and component primitives without introducing ad-hoc visual styles.

---

## 2. Complete Design Tokens (CSS Custom Properties)

All visual parameters are governed by canonical CSS custom properties:

```css
:root {
  /* ═════════════════════════════════════════════════════════════════════════
     1. SURFACES & BACKGROUNDS
     ═════════════════════════════════════════════════════════════════════════ */
  --bg-app: #080B11;               /* Deep obsidian primary workspace canvas */
  --bg-surface: #0E131F;           /* Container surface, panels, workspaces */
  --bg-surface-elevated: #141B2B;  /* Hover rows, active controls, dropdown menus */
  --bg-surface-subtle: #101624;    /* Table header backgrounds, sidebar stripes */
  --bg-surface-sunken: #06080E;    /* Input fields, search bars, code blocks */

  /* ═════════════════════════════════════════════════════════════════════════
     2. BORDERS & STRUCTURAL DIVIDERS
     ═════════════════════════════════════════════════════════════════════════ */
  --border-subtle: #1B2436;        /* Structural cell dividers, panel outlines */
  --border-medium: #28354D;        /* Card headers, group separators */
  --border-strong: #3B4B69;        /* Active tabs, selected list items */
  --border-focus: #3B82F6;         /* High-visibility keyboard focus ring */

  /* ═════════════════════════════════════════════════════════════════════════
     3. TYPOGRAPHY & TEXT HIERARCHY
     ═════════════════════════════════════════════════════════════════════════ */
  --text-primary: #F8FAFC;         /* High-contrast headers, stock prices, primary values */
  --text-secondary: #94A3B8;       /* Field labels, column titles, narrative copy */
  --text-muted: #64748B;           /* Timestamps, source attributions, metadata */
  --text-disabled: #475569;        /* Inactive states, disabled controls */

  /* ═════════════════════════════════════════════════════════════════════════
     4. BRAND & ACCENT
     ═════════════════════════════════════════════════════════════════════════ */
  --brand-primary: #3B82F6;        /* Controlled institutional sapphire */
  --brand-hover: #2563EB;
  --brand-subtle: rgba(59, 130, 246, 0.08);
  --brand-border: rgba(59, 130, 246, 0.25);

  /* ═════════════════════════════════════════════════════════════════════════
     5. SEMANTIC FINANCIAL PALETTE (RESTRAINED)
     ═════════════════════════════════════════════════════════════════════════ */
  /* Positive / Bullish / Target Hit */
  --positive: #10B981;             /* Emerald */
  --positive-hover: #059669;
  --positive-bg: rgba(16, 185, 129, 0.08);
  --positive-border: rgba(16, 185, 129, 0.20);

  /* Negative / Bearish / Stop Hit */
  --negative: #EF4444;             /* Crimson */
  --negative-hover: #DC2626;
  --negative-bg: rgba(239, 68, 68, 0.08);
  --negative-border: rgba(239, 68, 68, 0.20);

  /* Warning / Stale Data / Small Sample Alert */
  --warning: #F59E0B;              /* Amber */
  --warning-hover: #D97706;
  --warning-bg: rgba(245, 158, 11, 0.08);
  --warning-border: rgba(245, 158, 11, 0.20);

  /* Neutral / Informational / Triggered Level */
  --neutral-state: #64748B;        /* Slate */
  --neutral-bg: rgba(100, 116, 139, 0.08);
  --neutral-border: rgba(100, 116, 139, 0.20);

  /* ═════════════════════════════════════════════════════════════════════════
     6. FONT FAMILIES, SIZES & WEIGHTS
     ═════════════════════════════════════════════════════════════════════════ */
  --font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Roboto Mono', 'SF Mono', 'Fira Code', monospace;

  --weight-regular: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  --text-2xs: 0.625rem;   /* 10px: Micro badge labels, chart tick labels */
  --text-xs: 0.6875rem;   /* 11px: Table column headers, small status tags */
  --text-sm: 0.8125rem;   /* 13px: Standard table cells, metadata, inputs */
  --text-base: 0.875rem;  /* 14px: Primary body text, button labels */
  --text-md: 1.0rem;      /* 16px: Card titles, panel sub-headers */
  --text-lg: 1.25rem;     /* 20px: Group headers, large metric values */
  --text-xl: 1.5rem;      /* 24px: Key stock price display */
  --text-2xl: 1.875rem;   /* 30px: Top-level workspace titles */

  --leading-tight: 1.2;
  --leading-normal: 1.45;
  --leading-relaxed: 1.6;

  /* ═════════════════════════════════════════════════════════════════════════
     7. SPACING SCALE (4px Baseline)
     ═════════════════════════════════════════════════════════════════════════ */
  --space-0-5: 2px;
  --space-1: 4px;
  --space-1-5: 6px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;

  /* ═════════════════════════════════════════════════════════════════════════
     8. GEOMETRY, RADII & SHADOWS
     ═════════════════════════════════════════════════════════════════════════ */
  --radius-xs: 2px;
  --radius-sm: 4px;       /* Badges, micro tags, small buttons */
  --radius-md: 6px;       /* Form inputs, buttons, standard panels */
  --radius-lg: 8px;       /* Modals, drawers, major containers */

  --shadow-subtle: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-medium: 0 4px 12px rgba(0, 0, 0, 0.5);
  --shadow-popover: 0 8px 24px rgba(0, 0, 0, 0.7);

  /* ═════════════════════════════════════════════════════════════════════════
     9. MOTION & TRANSITIONS
     ═════════════════════════════════════════════════════════════════════════ */
  --transition-fast: 100ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 180ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 3. Typographic Scale & Numeric Precision

### Numerical Formatting Standards
All financial values must use `--font-mono` with `font-variant-numeric: tabular-nums` or `font-feature-settings: 'tnum'` to prevent layout jumping when numbers change.

```
┌─────────────────────────┬───────────────────┬────────────────────────────────┐
│ VALUE TYPE              │ INPUT             │ DISPLAY FORMAT                 │
├─────────────────────────┼───────────────────┼────────────────────────────────┤
│ Indian Rupee (Price)    │ 1309.0            │ ₹1,309.00                      │
│ Indian Rupee (Large)    │ 1055780000000     │ ₹10,55,780 Cr                  │
│ Positive Delta          │ 0.0251            │ +2.51% (Green)                 │
│ Negative Delta          │ -0.0120           │ -1.20% (Red)                   │
│ R-Multiple              │ 1.7586            │ +1.76 R                        │
│ Risk / Reward Ratio     │ 2.0               │ 1 : 2.0                        │
│ Volume (Shares)         │ 12613543          │ 12.61 M                        │
│ Market Time (IST)       │ 2026-09-01T09:45Z │ 09:45:00 IST                   │
│ Date (IST)              │ 2026-09-01        │ 01 Sep 2026                    │
│ Missing Value           │ null / None       │ — (Em-dash)                    │
└─────────────────────────┴───────────────────┴────────────────────────────────┘
```

---

## 4. Component Design Language

### 4.1 Data Tables
- **Header:** Sticky top, `--bg-surface-subtle`, uppercase `--text-xs`, `--text-secondary`, subtle 1px border-bottom (`--border-subtle`).
- **Cells:** Vertical padding `--space-2` (8px), horizontal `--space-3` (12px).
- **Alignment:** Numbers are strictly right-aligned with `--font-mono`. Symbol, name, and text are left-aligned with `--font-sans`.
- **Row Interaction:** Subtle background transition on hover (`--bg-surface-elevated`), clickable rows maintain cursor pointer.

### 4.2 Status & Recommendation Badges
- **Shape:** Rectangular with `--radius-xs` or `--radius-sm`. Never fully rounded pills.
- **Palette:** Translucent fill (`--positive-bg`, `--negative-bg`, `--warning-bg`, `--neutral-bg`) with matching 1px solid border and high-contrast text.
- **Content:** Explicit symbol/icon + capitalized text string:
  - `▲ BUY` / `▼ SELL` / `● NO ACTION`
  - `⏱ ACTIVE` / `✓ TARGET HIT` / `✕ STOPPED` / `⌛ EXPIRED`
  - `🟢 LIVE` / `🟡 STALE (5m)` / `⚪ UNAVAILABLE`

### 4.3 Metric Tiles & Summary Cards
- Label: `--text-xs`, uppercase, `--text-secondary`, font-weight medium.
- Primary Value: `--text-lg` or `--text-xl`, `--font-mono`, `--text-primary`, tabular numbers.
- Secondary Delta: Inline or stacked below with semantic color + arrow indicator.

### 4.4 Form Controls & Filter Tabs
- **Search Bar:** Sunken background (`--bg-surface-sunken`), subtle border (`--border-subtle`), instant `Cmd+K` keyboard shortcut badge.
- **Segmented Tabs:** Horizontal tab bar with 1px bottom border. Active tab features high-contrast text (`--text-primary`) and a crisp 2px bottom indicator (`--brand-primary`).

---

## 5. Financial Charting Design Rules

1. **Chart Background:** Seamlessly matches container canvas (`#0E131F`).
2. **Gridlines:** Minimal dotted lines (`rgba(255, 255, 255, 0.03)`).
3. **Candlestick Aesthetics:**
   - Bullish Bar: `#10B981` (Solid Emerald body, matching wick)
   - Bearish Bar: `#EF4444` (Solid Crimson body, matching wick)
4. **Setup Level Lines:**
   - Entry Price: Horizontal dashed line (`#3B82F6` Sapphire), text tag `ENTRY: ₹1,309.00`
   - Stop Loss: Horizontal dashed line (`#EF4444` Crimson), text tag `STOP: ₹1,280.00`
   - Target 1 / 2: Horizontal dashed line (`#10B981` Emerald), text tag `TARGET: ₹1,360.00`
5. **Volume Sub-Pane:** Lower 20% height, translucent bars matching candle direction (`0.4` opacity).

---

## 6. Accessibility & Contrast Standards

- **Contrast Ratio:** All body text (`--text-primary`, `--text-secondary`) guarantees minimum 4.5:1 contrast against surface backgrounds (WCAG AA standard).
- **Non-Color Dependence:** Color is never the sole indicator of direction or status. Directional values always feature `+`/`-` signs or arrows (`▲`/`▼`).
- **Focus Rings:** Interactive buttons, inputs, and links render a clear 2px outline in `--border-focus` when accessed via keyboard navigation.

---

## 7. Responsiveness & Viewport Targets

- **Primary Target:** Desktop (1440px+ and 1920px+ multi-column financial terminals).
- **Secondary Target:** Laptop & Tablet (1024px – 1366px with collapsible sidebars and responsive table scrolling).
- **Mobile Friendly:** Stacked single-column layouts for live signals and watchlist monitoring.

---

## 8. Quality Gate Audit Checklist

Before any FE implementation is approved:
- [ ] Uses exclusively declared CSS tokens (no hardcoded ad-hoc hex colors).
- [ ] All prices, percentages, and metrics use tabular numerals (`--font-mono`).
- [ ] No crypto/neon aesthetics, no decorative gradients, no unnecessary glassmorphism.
- [ ] Missing values render as `—` (em-dash), not `0` or `false`.
- [ ] All interactive components have explicit `:hover`, `:active`, and `:focus-visible` states.
