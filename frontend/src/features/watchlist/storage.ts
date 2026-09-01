/**
 * Nomad Analyst v1 — Watchlist & Decision Local Storage Manager
 * Versioned, resilient client-side storage for custom watchlists, decision statuses, and personal thesis notes.
 */

export type DecisionStatus = 'WATCHING' | 'CONSIDERING' | 'RESEARCHING' | 'HOLDING';

export interface WatchlistItem {
  symbol: string;
  decisionStatus: DecisionStatus;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Watchlist {
  id: string;
  name: string;
  symbols: WatchlistItem[];
  createdAt: string;
  updatedAt: string;
}

export interface WatchlistStore {
  version: number;
  activeWatchlistId: string;
  watchlists: Watchlist[];
}

const STORAGE_KEY = 'nomad_analyst_watchlists_v1';

const DEFAULT_STORE: WatchlistStore = {
  version: 1,
  activeWatchlistId: 'default-core',
  watchlists: [
    {
      id: 'default-core',
      name: 'Core Watchlist',
      symbols: [
        {
          symbol: 'RELIANCE',
          decisionStatus: 'WATCHING',
          notes: 'Monitoring energy refiner and retail expansion setups.',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          symbol: 'TCS',
          decisionStatus: 'RESEARCHING',
          notes: 'Evaluating IT services demand recovery and margin trajectory.',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          symbol: 'INFY',
          decisionStatus: 'CONSIDERING',
          notes: 'Watching for breakout above structural resistance.',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          symbol: 'HDFCBANK',
          decisionStatus: 'WATCHING',
          notes: 'Tracking credit growth and deposit accretion.',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  ],
};

export function loadWatchlistStore(): WatchlistStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      saveWatchlistStore(DEFAULT_STORE);
      return DEFAULT_STORE;
    }
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.watchlists) || parsed.watchlists.length === 0) {
      saveWatchlistStore(DEFAULT_STORE);
      return DEFAULT_STORE;
    }
    return parsed as WatchlistStore;
  } catch (err) {
    console.error('Failed to parse watchlist storage, falling back to defaults:', err);
    saveWatchlistStore(DEFAULT_STORE);
    return DEFAULT_STORE;
  }
}

export function saveWatchlistStore(store: WatchlistStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch (err) {
    console.error('Failed to persist watchlist store to localStorage:', err);
  }
}
