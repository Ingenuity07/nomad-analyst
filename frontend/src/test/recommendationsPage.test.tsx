import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RecommendationsPage } from '../pages/RecommendationsPage';

const mockStrategyPerformance = {
  strategy: 'DELIVERY_SWING',
  sample_size: 18,
  wins: 12,
  losses: 6,
  win_rate: 0.6667,
  avg_r_multiple: 1.45,
  is_small_sample: true,
  evaluated_at: '2026-09-01T10:00:00Z',
};

const mockRecommendations = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 'rec-1',
      symbol: 'RELIANCE',
      company_name: 'Reliance Industries Limited',
      sector: 'Energy',
      as_of: '2026-09-01T10:00:00Z',
      generated_at: '2026-09-01T10:00:00Z',
      horizon: 'DELIVERY_SWING',
      signal: 'BUY',
      setup_type: 'BREAKOUT',
      confidence: 'HIGH',
      status: 'ACTIVE',
      entry_type: 'BREAKOUT_CONFIRMATION',
      entry_price: 2980.0,
      entry_condition: 'Enter on daily close above 2980',
      stop_price: 2920.0,
      stop_method: 'STRUCTURAL',
      target_price: 3080.0,
      target_method: 'MEASURED_MOVE',
      risk_reward_ratio: 1.67,
      supporting_factors: ['Strong daily breakout above resistance', 'Volume expansion > 1.5x'],
      risk_factors: ['Earnings disclosure due next week'],
    },
  ],
};

const mockOutcomes = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 'out-1',
      recommendation: 'rec-old-1',
      symbol: 'TCS',
      signal: 'BUY',
      setup_type: 'PULLBACK',
      horizon: 'DELIVERY_SWING',
      evaluation_version: 1,
      evaluated_at: '2026-08-30T10:00:00Z',
      entry_triggered: true,
      entry_timestamp: '2026-08-25T09:30:00Z',
      actual_entry_price: 4150.0,
      exit_reason: 'TARGET_HIT',
      exit_timestamp: '2026-08-28T14:30:00Z',
      actual_exit_price: 4320.0,
      net_pnl_percent: 0.041,
      r_multiple: 1.85,
      target_hit: true,
      stop_hit: false,
      max_favorable_excursion: 0.045,
      max_adverse_excursion: 0.008,
      holding_duration_bars: 4,
    },
  ],
};

describe('RecommendationsPage (FE-6)', () => {
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
        <MemoryRouter initialEntries={['/recommendations']}>
          <Routes>
            <Route path="/recommendations" element={<RecommendationsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders Strategy Performance strip with Win Rate, Avg R, and Small Sample Warning', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/strategies/DELIVERY_SWING/performance/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStrategyPerformance });
      }
      if (url.includes('/api/v1/recommendations/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockRecommendations });
      }
      if (url.includes('/api/v1/outcomes/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOutcomes });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('66.7%')).toBeInTheDocument(); // Win rate
      expect(screen.getByText('+1.45 R')).toBeInTheDocument(); // Avg R
      expect(screen.getByText('18 Trades')).toBeInTheDocument(); // Sample size
      expect(screen.getByText(/SMALL SAMPLE \(< 30 TRADES\)/i)).toBeInTheDocument();
    });
  });

  it('renders Active Recommendations table and opens detail drawer on inspect', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/strategies/DELIVERY_SWING/performance/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStrategyPerformance });
      }
      if (url.includes('/api/v1/recommendations/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockRecommendations });
      }
      if (url.includes('/api/v1/outcomes/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOutcomes });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('₹2980.00')).toBeInTheDocument();
      expect(screen.getByText('₹2920.00')).toBeInTheDocument();
      expect(screen.getByText('₹3080.00')).toBeInTheDocument();
      expect(screen.getByText('1.67:1')).toBeInTheDocument();
    });

    const inspectBtn = screen.getByRole('button', { name: /Inspect →/i });
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      expect(screen.getByTestId('recommendation-detail-drawer')).toBeInTheDocument();
      expect(screen.getByText(/Strong daily breakout above resistance/i)).toBeInTheDocument();
      expect(screen.getByText(/Planned Trade Execution Parameters/i)).toBeInTheDocument();
    });
  });

  it('switches to Historical Outcomes tab and displays realized trades with P&L and R-multiple', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/strategies/DELIVERY_SWING/performance/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStrategyPerformance });
      }
      if (url.includes('/api/v1/recommendations/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockRecommendations });
      }
      if (url.includes('/api/v1/outcomes/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOutcomes });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const histTab = screen.getByText('Historical Evaluated Outcomes');
    fireEvent.click(histTab);

    await waitFor(() => {
      expect(screen.getByText('TCS')).toBeInTheDocument();
      expect(screen.getByText('TARGET_HIT')).toBeInTheDocument();
      expect(screen.getByText('+4.10%')).toBeInTheDocument();
      expect(screen.getByText('+1.85 R')).toBeInTheDocument();
      expect(screen.getByText('4b')).toBeInTheDocument();
    });
  });

  it('handles API error states gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: { code: 'SERVER_ERROR', message: 'Internal server error fetching recommendations.' },
      }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Unable to load recommendations/i)).toBeInTheDocument();
    });
  });
});
