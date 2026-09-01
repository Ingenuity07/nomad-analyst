import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { IntradayPage } from '../pages/IntradayPage';

const mockOverviewData = {
  market_session: {
    window: 'MORNING',
    minutes_elapsed: 45,
    minutes_remaining: 330,
    is_trading_hour: true,
    session_date: '2026-09-01',
  },
  summary: {
    active_signals: 2,
    triggered_signals: 1,
    timeframes_supported: ['5m', '15m', '1h'],
  },
  as_of: '2026-09-01T10:00:00Z',
};

const mockRecsData = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 'intra-rec-1',
      symbol: 'RELIANCE',
      company_name: 'Reliance Industries Limited',
      sector: 'Energy',
      as_of: '2026-09-01T10:00:00Z',
      generated_at: '2026-09-01T10:00:00Z',
      horizon: 'INTRADAY',
      signal: 'BUY',
      setup_type: 'ORB_BREAKOUT',
      timeframe: '5m',
      confidence: 'HIGH',
      status: 'ACTIVE',
      entry_type: 'BREAKOUT_CONFIRMATION',
      entry_price: 1312.5,
      entry_condition: 'Enter above 1312.50 on volume expansion',
      stop_price: 1302.0,
      stop_method: 'STRUCTURAL',
      target_price: 1332.0,
      target_method: 'MEASURED_MOVE',
      risk_reward_ratio: 1.86,
    },
    {
      id: 'intra-rec-2',
      symbol: 'INFY',
      company_name: 'Infosys Limited',
      sector: 'Technology',
      as_of: '2026-09-01T10:00:00Z',
      generated_at: '2026-09-01T10:00:00Z',
      horizon: 'INTRADAY',
      signal: 'SELL',
      setup_type: 'VWAP_RECLAIM',
      timeframe: '15m',
      confidence: 'MEDIUM',
      status: 'TRIGGERED',
      entry_type: 'VWAP_REJECTION',
      entry_price: 1840.0,
      entry_condition: 'Short below VWAP 1840.0',
      stop_price: 1855.0,
      stop_method: 'VOLATILITY_ATR',
      target_price: 1810.0,
      target_method: 'PIVOT_SUPPORT',
      risk_reward_ratio: 2.0,
    },
  ],
};

const mockDataQuality = {
  symbol: 'RELIANCE',
  timeframe: '5m',
  is_ready: true,
  reason: 'All intraday indicator checks passed.',
  bar_count: 120,
  required_bars: 100,
  quality: {
    data_quality_grade: 'A',
    missing_bars_count: 0,
    gap_count: 0,
  },
  checks_passed: ['Timeframe 5m supported', 'Sufficient bars count (120/100)'],
  checks_failed: [],
  checked_at: '2026-09-01T10:00:00Z',
};

describe('IntradayPage (FE-4)', () => {
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
          <IntradayPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders Intraday Scanner workspace with live signal feed', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/intraday/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockOverviewData,
        });
      }
      if (url.includes('/intraday/recommendations/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockRecsData,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });
    });

    renderComponent();

    expect(screen.getByText(/Intraday Scanner & Real-Time Signals/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('INFY')).toBeInTheDocument();
    });

    // Verify directional signals and prices
    expect(screen.getAllByText('▲ BUY').length).toBeGreaterThan(0);
    expect(screen.getAllByText('▼ SELL').length).toBeGreaterThan(0);
    expect(screen.getByText(/1312\.50/)).toBeInTheDocument();
    expect(screen.getByText('1.86:1')).toBeInTheDocument();
  });

  it('opens Signal Detail Drawer upon inspect click', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/intraday/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockOverviewData,
        });
      }
      if (url.includes('/intraday/recommendations/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockRecsData,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const inspectBtn = screen.getAllByText(/inspect →/i)[0];
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      const drawer = screen.getByTestId('signal-detail-drawer');
      expect(drawer).toBeInTheDocument();
      expect(drawer).toHaveTextContent('Execution Parameters');
      expect(drawer).toHaveTextContent('Enter above 1312.50 on volume expansion');
      expect(drawer).toHaveTextContent('Open Stock Terminal');
    });
  });

  it('opens Data Quality Modal on DQ button click', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/intraday/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockOverviewData,
        });
      }
      if (url.includes('/intraday/recommendations/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockRecsData,
        });
      }
      if (url.includes('/intraday/data-quality/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockDataQuality,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const dqBtn = screen.getAllByText(/🔍 dq/i)[0];
    fireEvent.click(dqBtn);

    await waitFor(() => {
      expect(screen.getByText(/Intraday Data Quality Readiness/i)).toBeInTheDocument();
      expect(screen.getByText(/READY FOR STRATEGY EXECUTION/i)).toBeInTheDocument();
      expect(screen.getByText(/120 \/ 100/i)).toBeInTheDocument();
    });
  });

  it('renders ErrorState when intraday API fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: {
          code: 'INTRADAY_ENGINE_DOWN',
          message: 'Intraday signal engine is currently offline.',
          details: {},
          timestamp: '2026-09-01T10:00:00Z',
        },
      }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Failed to Load Live Intraday Signals/i)).toBeInTheDocument();
    });
  });
});
