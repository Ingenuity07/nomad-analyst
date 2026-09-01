import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from '@/App';
import * as apiClientModule from '@/lib/api/client';
import { PageLoadingFallback } from '@/components/common/PageLoadingFallback';

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}));

describe('FE-13 Final Application Integration & Route Code Splitting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    (apiClientModule.apiClient as any).mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/market/overview/')) {
        return Promise.resolve({
          as_of: '2026-09-01T15:30:00Z',
          universe: 'NIFTY50',
          market_session: { is_trading_hour: true, session_date: '2026-09-01' },
          indices: [
            { symbol: 'NIFTY 50', name: 'Nifty 50', price: 24500.0, change: 120.0, change_percent: 0.5 },
          ],
        });
      }
      if (url.startsWith('/api/v1/market/regime/')) {
        return Promise.resolve({
          as_of: '2026-09-01T15:30:00Z',
          universe: 'NIFTY50',
          trend_regime: { trend: 'BULLISH' },
          volatility_regime: { volatility: 'NORMAL' },
          momentum_regime: { momentum: 'POSITIVE' },
          breadth_regime: { breadth: 'STRONG' },
        });
      }
      if (url.startsWith('/api/v1/market/breadth/')) {
        return Promise.resolve({
          as_of: '2026-09-01T15:30:00Z',
          advances: 34,
          declines: 16,
          unchanged: 0,
          advance_decline_ratio: 2.125,
          breadth_regime: 'STRONG',
        });
      }
      if (url.startsWith('/api/v1/market/sectors/')) {
        return Promise.resolve({
          count: 1,
          results: [{ sector: 'Technology', momentum_state: 'LEADING', tier: 'TIER_1', stocks_count: 10, return_1m: 3.5 }],
        });
      }
      if (url.startsWith('/api/v1/recommendations/')) {
        return Promise.resolve({ count: 0, results: [] });
      }
      if (url.startsWith('/api/v1/opportunities/')) {
        return Promise.resolve({ count: 0, results: [] });
      }
      if (url.startsWith('/api/v1/stocks/')) {
        return Promise.resolve({
          instrument: { symbol: 'RELIANCE', company: { name: 'Reliance Industries Ltd.', sector: 'Energy' } },
          latest_snapshot: { close: 2980.0, change_percent: 1.2 },
        });
      }
      return Promise.resolve({ count: 0, results: [] });
    });
  });

  it('renders PageLoadingFallback component cleanly without layout shifts', () => {
    render(<PageLoadingFallback />);
    expect(screen.getByTestId('page-loading-fallback')).toBeInTheDocument();
  });

  it('renders App with AppShell and loads Market Overview by default', async () => {
    render(<App />);

    // Shell sidebar and header exist immediately
    expect(screen.getByText('NOMAD ANALYST')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Search symbol/i)).toBeInTheDocument();

    // Lazy-loaded Market Page resolves cleanly
    await waitFor(() => {
      expect(screen.getByText('Market Overview & Context')).toBeInTheDocument();
    });
  });
});
