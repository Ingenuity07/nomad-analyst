/**
 * Nomad Analyst v1 — Alerts & Monitoring Local Storage Layer
 * Versioned, client-side store for custom monitor rules, observed baselines, and historical triggered events.
 */

export type MonitorRuleType =
  | 'PRICE_ABOVE'
  | 'PRICE_BELOW'
  | 'NEW_ACTIVE_BUY'
  | 'OPPORTUNITY_SCORE_ABOVE'
  | 'REGIME_SHIFT_TO_BEARISH';

export type EventSeverity = 'HIGH' | 'MEDIUM' | 'INFO';

export type EventCategory =
  | 'RECOMMENDATIONS'
  | 'INTRADAY'
  | 'MARKET_REGIME'
  | 'WATCHLIST_TRIGGERS'
  | 'OPPORTUNITIES'
  | 'CORPORATE_EVENTS';

export interface MonitorRule {
  id: string;
  type: MonitorRuleType;
  symbol?: string;
  threshold?: number;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  lastTriggeredAt?: string;
  baselineEstablished?: boolean;
  lastObservedPrice?: number;
}

export interface MonitorEvent {
  id: string;
  ruleId?: string;
  category: EventCategory;
  source: string;
  symbol?: string;
  title: string;
  summary: string;
  severity: EventSeverity;
  observedAt: string;
  sourceTimestamp?: string;
  payload?: Record<string, any>;
  navigationLink?: string;
}

export interface MonitorStore {
  version: number;
  rules: MonitorRule[];
  events: MonitorEvent[];
  seenEventIds: string[];
}

const STORAGE_KEY = 'nomad_analyst_monitors_v1';
const MAX_EVENTS_HISTORY = 500;

const DEFAULT_STORE: MonitorStore = {
  version: 1,
  rules: [
    {
      id: 'rule-def-1',
      type: 'NEW_ACTIVE_BUY',
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      baselineEstablished: true,
    },
    {
      id: 'rule-def-2',
      type: 'OPPORTUNITY_SCORE_ABOVE',
      threshold: 80,
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      baselineEstablished: true,
    },
    {
      id: 'rule-def-3',
      type: 'REGIME_SHIFT_TO_BEARISH',
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      baselineEstablished: true,
    },
    {
      id: 'rule-def-4',
      type: 'PRICE_ABOVE',
      symbol: 'RELIANCE',
      threshold: 3000,
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      baselineEstablished: true,
      lastObservedPrice: 2965.5,
    },
  ],
  events: [
    {
      id: 'init-event-1',
      category: 'RECOMMENDATIONS',
      source: 'StrategyEngine',
      symbol: 'RELIANCE',
      title: 'Active BUY Signal: Momentum Breakout',
      summary: 'Daily swing setup triggered with 2.14 R:R target at ₹3,100.',
      severity: 'HIGH',
      observedAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      navigationLink: '/recommendations',
    },
    {
      id: 'init-event-2',
      category: 'OPPORTUNITIES',
      source: 'DiscoveryEngine',
      symbol: 'TCS',
      title: 'High-Score Delivery Setup (88/100)',
      summary: 'Institutional volume surge accumulation detected in Technology sector.',
      severity: 'MEDIUM',
      observedAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
      navigationLink: '/delivery',
    },
    {
      id: 'init-event-3',
      category: 'MARKET_REGIME',
      source: 'MarketContextService',
      title: 'Benchmark Regime: Bullish Trend Maintained',
      summary: 'Nifty 50 above SMA200 with normal volatility and strong participation.',
      severity: 'INFO',
      observedAt: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
      navigationLink: '/market-intelligence',
    },
  ],
  seenEventIds: ['init-event-1', 'init-event-2', 'init-event-3'],
};

export function loadMonitorStore(): MonitorStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      saveMonitorStore(DEFAULT_STORE);
      return JSON.parse(JSON.stringify(DEFAULT_STORE));
    }
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.rules)) {
      saveMonitorStore(DEFAULT_STORE);
      return JSON.parse(JSON.stringify(DEFAULT_STORE));
    }
    return parsed as MonitorStore;
  } catch (err) {
    console.error('Failed to parse monitor store from localStorage:', err);
    saveMonitorStore(DEFAULT_STORE);
    return JSON.parse(JSON.stringify(DEFAULT_STORE));
  }
}

export function saveMonitorStore(store: MonitorStore): void {
  try {
    const trimmedStore: MonitorStore = {
      ...store,
      events: store.events.slice(0, MAX_EVENTS_HISTORY),
      seenEventIds: store.seenEventIds.slice(-MAX_EVENTS_HISTORY),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmedStore));
  } catch (err) {
    console.error('Failed to save monitor store to localStorage:', err);
  }
}
