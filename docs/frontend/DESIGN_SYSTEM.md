# Nomad Analyst — Global Frontend Design System Specification

**Version:** 1.0.0  
**Date:** September 1, 2026  
**Status:** Canonical Design Authority (Non-Negotiable)  
**Philosophy:** Minimalist, Sober, Institutional Financial Terminal & Editorial Research Aesthetic

---

## 1. Visual & Architectural Philosophy

Nomad Analyst is designed as an **institutional-grade equity intelligence and quantitative research terminal**. It must look and feel like a modern, premium financial workspace—prioritizing clarity, precision, structural hierarchy, and information density over decorative noise.

### Core Visual Principles:
1. **Sober & Restrained:** Neutral, low-fatigue dark surfaces. Zero neon glows, zero decorative glassmorphism, zero floating card clutter.
2. **Information-Dense but Uncluttered:** Clean tabular alignments, clear divider hierarchy, compact metric groups, expandable data drawers.
3. **Typography-First:** High-contrast sans-serif type paired with strict tabular numerals (`font-feature-settings: 'tnum'`) for all financial prices, percentages, and metrics.
4. **Purposeful Semantic Color:** Color is an indicator, not a decoration. Positive/negative hues are applied only to directional data (price delta, BUY/SELL signals, target hits), with accompanying explicit text and icons—never relying on color alone.
5. **Component Reusability:** Strict design-token consistency across all workspace modules (Market Overview, Intraday, Opportunities, Stock Detail, Research, Backtest).

---

## 2. Design Tokens & CSS Custom Properties

All styling is governed by canonical design tokens declared in `src/styles/tokens.css`:

```css
:root {
  /* ── Background & Surface Palette ─────────────────────────────────────── */
  --bg-app: #090D14;          /* Deep obsidian canvas */
  --bg-surface: #0E1420;      /* Primary container surface */
  --bg-surface-elevated: #141C2B; /* Hover states, dropdowns, active rows */
  --bg-surface-subtle: #111827;   /* Table headers, section headers */

  /* ── Border & Divider Hierarchy ────────────────────────────────────────── */
  --border-subtle: #1E293B;   /* Standard card & table dividers */
  --border-strong: #334155;   /* Active inputs, selected tabs, focused rows */
  --border-focus: #3B82F6;    /* Keyboard focus ring */

  /* ── Typography & Text Contrast ────────────────────────────────────────── */
  --text-primary: #F8FAFC;    /* Key headers, stock prices, primary values */
  --text-secondary: #94A3B8;  /* Field labels, column headers, descriptions */
  --text-muted: #64748B;      /* Timestamps, metadata, subtle disclaimers */
  --text-disabled: #475569;   /* Inactive tabs, disabled buttons */

  /* ── Brand & Accent ────────────────────────────────────────────────────── */
  --brand-primary: #3B82F6;   /* Controlled institutional sapphire */
  --brand-subtle: rgba(59, 130, 246, 0.10);
  --brand-border: rgba(59, 130, 246, 0.30);

  /* ── Semantic Directional Palette (Restrained) ────────────────────────── */
  /* Positive / Bullish / Target Hit */
  --positive: #10B981;        /* Emerald green */
  --positive-bg: rgba(16, 185, 129, 0.10);
  --positive-border: rgba(16, 185, 129, 0.25);

  /* Negative / Bearish / Stop Hit */
  --negative: #EF4444;        /* Crimson red */
  --negative-bg: rgba(239, 68, 68, 0.10);
  --negative-border: rgba(239, 68, 68, 0.25);

  /* Warning / Stale / Small Sample Alert */
  --warning: #F59E0B;         /* Amber */
  --warning-bg: rgba(245, 158, 11, 0.10);
  --warning-border: rgba(245, 158, 11, 0.25);

  /* Neutral / Inactive / Unavailable */
  --neutral-state: #64748B;   /* Slate */
  --neutral-bg: rgba(100, 116, 139, 0.10);
  --neutral-border: rgba(100, 116, 139, 0.25);

  /* ── Typography Families & Scales ──────────────────────────────────────── */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Roboto Mono', 'SF Mono', monospace;

  --text-xs: 0.6875rem;       /* 11px: Badges, tiny tags, metadata */
  --text-sm: 0.8125rem;       /* 13px: Table cells, field labels, body text */
  --text-base: 0.875rem;      /* 14px: Default body, standard controls */
  --text-md: 1.0rem;          /* 16px: Card titles, section headers */
  --text-lg: 1.25rem;         /* 20px: Sub-headers, large metrics */
  --text-xl: 1.5rem;          /* 24px: Primary stock price display */
  --text-2xl: 1.875rem;       /* 30px: Top-level workspace headers */

  /* ── Spacing Scale (4px Baseline) ──────────────────────────────────────── */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  /* ── Geometry & Layout ─────────────────────────────────────────────────── */
  --radius-sm: 3px;           /* Badges, tags, small inputs */
  --radius-md: 5px;           /* Buttons, standard inputs, cards */
  --radius-lg: 8px;           /* Large containers, modals */
  --shadow-subtle: 0 1px 3px rgba(0, 0, 0, 0.3);
  --shadow-overlay: 0 4px 16px rgba(0, 0, 0, 0.5);
}
```

---

## 3. Typography & Numerical Precision Standards

### Rule: Tabular Monospace for All Numerical Data
All prices, percentages, shares, ratios, R-multiples, and timestamps **must** use `--font-mono` with `font-variant-numeric: tabular-nums` or `font-feature-settings: 'tnum'` to prevent layout shifting during real-time streaming updates.

### Formatting Conventions:
| Data Type | Example Input | Standard Output Format | Class / Helper |
|---|---|---|---|
| **Indian Rupee (INR)** | `1309.0` | `₹1,309.00` | `formatCurrency(val)` |
| **Large INR (Crores)** | `1055780.0` | `₹10,55,780 Cr` | `formatCrores(val)` |
| **Percentage Delta** | `0.0251` | `+2.51%` (Green) or `-1.20%` (Red) | `formatPercent(val, showSign=true)` |
| **R-Multiple** | `1.7586` | `+1.76 R` | `formatR(val)` |
| **Risk / Reward Ratio**| `2.0` | `1 : 2.0` | `formatRR(val)` |
| **Volume (Shares)** | `12613543` | `12.61 M` or `1.26 Cr` | `formatVolume(val)` |
| **Timestamp (IST)** | `2026-09-01T09:45:00Z` | `09:45:00 IST` | `formatISTTime(val)` |
| **Date (IST)** | `2026-09-01` | `01 Sep 2026` | `formatDate(val)` |
| **Missing Metric** | `null` / `None` | `—` (Em-dash) | `formatFallback()` |

---

## 4. Component Design Language

### 4.1 Data Tables
- Header: Sticky, subtle background (`--bg-surface-subtle`), uppercase text (`--text-xs`, `--text-secondary`), border-bottom (`--border-subtle`).
- Rows: Clean horizontal border (`--border-subtle`), subtle hover highlighting (`--bg-surface-elevated`).
- Numerical Columns: Right-aligned with `--font-mono`.
- Text Columns: Left-aligned with `--font-sans`.

### 4.2 Signal & Status Badges
- Non-pill, rectangular with subtle radius (`--radius-sm`).
- Low-saturation background (`--positive-bg` / `--negative-bg` / `--warning-bg` / `--neutral-bg`) with crisp border (`1px solid`) and clear text.
- Must include text label + icon (e.g. `▲ BUY`, `▼ SELL`, `⏱ ACTIVE`, `⚠ STALE`).

### 4.3 Metric Groups
- Label above value: `--text-xs`, uppercase, `--text-secondary`.
- Value below: `--text-lg` or `--text-xl`, `--font-mono`, `--text-primary`.
- Delta tag inline or below.

### 4.4 Financial Charts
- Background: Matches `--bg-surface` (`#0E1420`).
- Gridlines: Very subtle dotted lines (`rgba(255, 255, 255, 0.04)`).
- Up Candle: `#10B981` (Solid Emerald), Down Candle: `#EF4444` (Solid Crimson).
- Price Levels: Horizontal dashed lines with crisp label tags (Entry: Blue, Stop: Red, Target: Green).

---

## 5. Visual Quality Gate Checklist

Before marking any frontend workspace or component complete, verify:
- [ ] **Visual Restraint:** Does it look like a professional research terminal rather than a colorful crypto dashboard?
- [ ] **Alignment & Grid:** Are all numbers in tables strictly right-aligned with monospace font?
- [ ] **Contrast & Accessibility:** Does all text meet WCAG AA contrast against `--bg-surface`?
- [ ] **Semantic Honesty:** Are missing values rendered as `—` rather than `0.0` or `false`?
- [ ] **State Representation:** Are `LOADING` (shimmer skeletons), `EMPTY`, `STALE`, and `ERROR` states explicitly designed?
- [ ] **Keyboard & Focus:** Are interactive elements navigable via Tab with a visible focus ring (`--border-focus`)?
