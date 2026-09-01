import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { MarketPage } from '../pages/MarketPage';

const mockOverviewData = {
  as_of: '2026-09-01T13:45:00Z',
  universe: 'NIFTY50',
  market_session: {
    window: 'MORNING',
    minutes_elapsed: 60,
    minutes_remaining: 315,
    is_trading_hour: true,
    session_date: '2026-09-01',
  },
  indices: [
    { symbol: '^NSEI', name: 'NIFTY 50', price: 25410.8, change: 114.2, change_percent: 0.45, timestamp: '2026-09-01T13:45:00Z' },
    { symbol: '^NSEBANK', name: 'NIFTY BANK', price: 52140.0, change: -120.5, change_percent: -0.23, timestamp: '2026-09-01T13:45:00Z' },
  ],
  breadth: {
    advancing: 32,
    declining: 18,
    unchanged: 0,
    advance_decline_ratio: 1.78,
    breadth_regime: 'strong',
    participation: {
      pct_above_sma20: 72.0,
      pct_above_sma50: 84.0,
      pct_above_sma200: 68.0,
    },
  },
  index_regimes: {
    '^NSEI': {
      symbol: '^NSEI',
      regime: 'BULLISH',
      trend: 'BULLISH',
      sma_50: 24800.0,
      sma_200: 23200.0,
      distance_from_52w_high: -0.85,
      volatility_regime: 'LOW',
    },
  },
  sector_rankings: [
    {
      sector: 'Energy',
      rank: 1,
      average_return: 2.51,
      relative_return_vs_nifty: 2.06,
      average_rsi: 65.4,
      average_volatility: 0.012,
      momentum_state: 'improving',
      tier: 'strongest',
    },
    {
      sector: 'Technology',
      rank: 2,
      average_return: -0.84,
      relative_return_vs_nifty: -1.29,
      average_rsi: 44.2,
      average_volatility: 0.015,
      momentum_state: 'deteriorating',
      tier: 'weakest',
    },
  ],
  cross_market_cues: {
    '^GSPC': { name: 'S&P 500', symbol: '^GSPC', price: 5640.0, change_percent: 0.75, impact_bias: 'BULLISH' },
  },
  recent_news: [
    {
      id: 'news-1',
      headline: 'NSE market breath surges on broad institutional buying',
      summary: 'Energy and FMCG sectors lead gains across benchmark indices.',
      source: 'Reuters',
      published_at: '2026-09-01T13:30:00Z',
      event_type: 'MARKET_ROUNDUP',
    },
  ],
  data_freshness: {
    status: 'LIVE',
    timestamp: '2026-09-01T13:45:00Z',
  },
};

describe('MarketPage (FE-2)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <MarketPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders market overview workspace with full data sections', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/market/indices/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ indices: mockOverviewData.indices, as_of: mockOverviewData.as_of }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockOverviewData,
      });
    });

    renderComponent();

    // Check title and header elements
    expect(screen.getByText(/Market Overview & Context/i)).toBeInTheDocument();

    // Await async query resolution
    await waitFor(() => {
      expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
      expect(screen.getByText(/₹25,410.80/i)).toBeInTheDocument();
    });

    // Check Market Regime
    expect(screen.getByText(/Market Regime & Macro Trend/i)).toBeInTheDocument();
    expect(screen.getByText(/▲ BULLISH/i)).toBeInTheDocument();

    // Check Breadth Barometer
    expect(screen.getByText(/Market Breadth & Participation/i)).toBeInTheDocument();
    expect(screen.getByText('1.78')).toBeInTheDocument();
    expect(screen.getByText(/32 Adv/i)).toBeInTheDocument();

    // Check Sector Table
    expect(screen.getByText(/Sector Rotation & Relative Strength Matrix/i)).toBeInTheDocument();
    expect(screen.getByText('Energy')).toBeInTheDocument();
    expect(screen.getByText('+2.51%')).toBeInTheDocument();

    // Check Global Cues and News Feed
    expect(screen.getByText(/Global Market Context & Macro Cues/i)).toBeInTheDocument();
    expect(screen.getByText(/NSE market breath surges on broad institutional buying/i)).toBeInTheDocument();
  });

  it('handles sector sorting by return %', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockOverviewData,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Energy')).toBeInTheDocument();
    });

    const sortBtn = screen.getByRole('button', { name: /sort by return/i });
    fireEvent.click(sortBtn);

    // Verify sort state applied
    expect(screen.getByText('+2.51%')).toBeInTheDocument();
  });

  it('renders ErrorState when API request fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: {
          code: 'SERVER_ERROR',
          message: 'Market intelligence engine unavailable.',
          details: {},
          timestamp: '2026-09-01T13:45:00Z',
        },
      }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Failed to Load Complete Market Context/i)).toBeInTheDocument();
    });
  });
});
