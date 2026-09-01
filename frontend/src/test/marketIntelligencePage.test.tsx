import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { MarketIntelligencePage } from '../pages/MarketIntelligencePage';

const mockOverview = {
  as_of: '2026-09-01T10:00:00Z',
  universe: 'NIFTY50',
  market_session: {
    window: 'MORNING',
    minutes_elapsed: 75,
    minutes_remaining: 225,
    is_trading_hour: true,
    session_date: '2026-09-01',
  },
  breadth: {
    advancing: 35,
    declining: 12,
    unchanged: 3,
    advance_decline_ratio: 2.92,
    breadth_regime: 'STRONG',
    participation: {
      pct_above_sma20: 74.0,
      pct_above_sma50: 72.0,
      pct_above_sma200: 80.0,
    },
    new_highs_count: 8,
    new_lows_count: 0,
  },
  index_regimes: {
    '^NSEI': { name: 'Nifty 50', regime: 'BULLISH', trend_slope: 0.045, above_sma_200: true },
    '^NSEBANK': { name: 'Bank Nifty', regime: 'BULLISH', trend_slope: 0.038, above_sma_200: true },
    '^BSESN': { name: 'Sensex', regime: 'BULLISH', trend_slope: 0.041, above_sma_200: true },
  },
  sector_rankings: [
    {
      rank: 1,
      sector: 'Technology',
      average_return: 2.15,
      relative_return_vs_nifty: 1.45,
      average_rsi: 64.5,
      average_volatility: 0.0142,
      tier: 'strongest',
      momentum_state: 'improving',
    },
    {
      rank: 2,
      sector: 'Energy',
      average_return: 1.85,
      relative_return_vs_nifty: 1.15,
      average_rsi: 61.2,
      average_volatility: 0.0165,
      tier: 'strongest',
      momentum_state: 'stable',
    },
    {
      rank: 3,
      sector: 'Financial Services',
      average_return: -0.45,
      relative_return_vs_nifty: -1.15,
      average_rsi: 48.0,
      average_volatility: 0.018,
      tier: 'weakest',
      momentum_state: 'deteriorating',
    },
  ],
  cross_market_cues: {
    '^GSPC': { name: 'S&P 500', close: 5650.0, daily_change_percent: 0.85, stale: false },
    'USDINR=X': { name: 'USD/INR Rate', close: 83.95, daily_change_percent: -0.12, stale: false },
    'CL=F': { name: 'Crude Oil', close: 76.5, daily_change_percent: -1.45, stale: false },
  },
  recent_news: [
    {
      type: 'news',
      headline: 'RBI Maintains Repo Rate at 6.5%, Signals Resilient Growth',
      source: 'Reuters',
      published_at: '2026-09-01T08:00:00Z',
    },
  ],
  data_freshness: {
    status: 'LIVE',
    timestamp: '2026-09-01T10:00:00Z',
  },
};

const mockIndices = {
  indices: [
    { symbol: '^NSEI', name: 'Nifty 50', price: 25150.0, change: 180.5, change_percent: 0.72, regime: 'BULLISH', above_sma_200: true },
    { symbol: '^NSEBANK', name: 'Bank Nifty', price: 51200.0, change: 320.0, change_percent: 0.63, regime: 'BULLISH', above_sma_200: true },
  ],
  as_of: '2026-09-01T10:00:00Z',
};

const mockSectors = {
  sector_rankings: mockOverview.sector_rankings,
  as_of: '2026-09-01T10:00:00Z',
};

const mockConstituents = {
  count: 2,
  results: [
    { symbol: 'TCS', company_name: 'Tata Consultancy Services', exchange: 'NSE' },
    { symbol: 'INFY', company_name: 'Infosys Limited', exchange: 'NSE' },
  ],
};

const mockOpportunities = {
  count: 1,
  results: [
    {
      id: 'opp-1',
      symbol: 'TCS',
      company_name: 'Tata Consultancy Services',
      sector: 'Technology',
      opportunity_type: 'TRENDING',
      final_score: 88.5,
      reasons: ['Strong momentum breakout', 'Sector leader in Technology'],
    },
  ],
};

describe('MarketIntelligencePage (FE-10)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/market/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockOverview,
        });
      }
      if (url.includes('/api/v1/market/indices/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockIndices,
        });
      }
      if (url.includes('/api/v1/market/sectors/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockSectors,
        });
      }
      if (url.includes('/api/v1/market/breadth/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ breadth: mockOverview.breadth, as_of: mockOverview.as_of }),
        });
      }
      if (url.includes('/api/v1/market/global/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ global_cues: mockOverview.cross_market_cues, as_of: mockOverview.as_of }),
        });
      }
      if (url.includes('/api/v1/stocks/?sector=') || url.includes('/api/v1/stocks/?')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockConstituents,
        });
      }
      if (url.includes('/api/v1/opportunities/?sector=') || url.includes('/api/v1/opportunities/?')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockOpportunities,
        });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });
  });

  const renderComponent = (initialPath = '/market-intelligence') =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/market-intelligence" element={<MarketIntelligencePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders benchmark indices with live regime badges and session window', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('benchmark-regime-bar')).toBeInTheDocument();
      expect(screen.getByText('Nifty 50')).toBeInTheDocument();
      expect(screen.getByText('Bank Nifty')).toBeInTheDocument();
      expect(screen.getAllByText(/BULLISH TREND/i).length).toBeGreaterThan(0);
    });
  });

  it('renders market breadth participation cards and progress bar', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('market-breadth-card')).toBeInTheDocument();
      expect(screen.getByText(/35 Advances/i)).toBeInTheDocument();
      expect(screen.getByText(/12 Declines/i)).toBeInTheDocument();
      expect(screen.getByText('2.92x')).toBeInTheDocument(); // A/D Ratio
      expect(screen.getByText(/STRONG BREADTH/i)).toBeInTheDocument();
    });
  });

  it('renders sector momentum leaderboard with ranked sectors and tier badges', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('sector-momentum-leaderboard')).toBeInTheDocument();
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('+2.15%')).toBeInTheDocument();
      expect(screen.getByText('Energy')).toBeInTheDocument();
      expect(screen.getByText('Financial Services')).toBeInTheDocument();
      expect(screen.getByText(/IMPROVING/i)).toBeInTheDocument();
    });
  });

  it('renders selected sector detail with constituents, opportunities, and AI research action', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('selected-sector-detail')).toBeInTheDocument();
      expect(screen.getByText('Tata Consultancy Services')).toBeInTheDocument();
      expect(screen.getByText('Infosys Limited')).toBeInTheDocument();
      expect(screen.getByTestId('research-sector-button')).toBeInTheDocument();
    });
  });

  it('renders global cues and macro disclosures', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('global-cues-sensitivities')).toBeInTheDocument();
      expect(screen.getByText('S&P 500')).toBeInTheDocument();
      expect(screen.getByText('USD/INR Rate')).toBeInTheDocument();
      expect(screen.getByText(/RBI Maintains Repo Rate at 6.5%/i)).toBeInTheDocument();
    });
  });

  it('renders theme roadmap card denoting future capabilities boundary', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('theme-roadmap-card')).toBeInTheDocument();
      expect(screen.getByText(/FUTURE BACKEND CAPABILITY/i)).toBeInTheDocument();
    });
  });
});
