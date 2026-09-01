import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { BacktestsPage } from '../pages/BacktestsPage';

const mockBacktestRun = {
  id: 'bt-1',
  run_id: 'NIFTY50_1d_DELIVERY_SWING_2026-03-01_2026-09-01_test123',
  status: 'COMPLETE',
  universe_name: 'NIFTY50',
  timeframe: '1d',
  horizon: 'DELIVERY_SWING',
  start_date: '2026-03-01',
  end_date: '2026-09-01',
  strategy_version: '1.0',
  config: {
    universe_name: 'NIFTY50',
    timeframe: '1d',
    horizon: 'DELIVERY_SWING',
    start_date: '2026-03-01',
    end_date: '2026-09-01',
    cost_mode: 'REALISTIC',
    ambiguity_policy: 'CONSERVATIVE',
  },
  result: {
    total_signals: 45,
    triggered: 32,
    untriggered: 13,
    wins: 20,
    losses: 12,
    ambiguous: 0,
    win_rate: 0.625,
    trigger_rate: 0.711,
    avg_return_pct: 0.038,
    avg_r: 1.35,
    expectancy: 1.35,
    profit_factor: 1.82,
    max_drawdown_r: -2.45,
    avg_holding_bars: 6.2,
    sample_count: 32,
    statistical_warnings: [],
    by_setup_type: {
      BREAKOUT: {
        dimension_key: 'setup_type',
        dimension_value: 'BREAKOUT',
        total: 25,
        triggered: 20,
        untriggered: 5,
        wins: 14,
        losses: 6,
        win_rate: 0.70,
        avg_r: 1.60,
        expectancy: 1.60,
        profit_factor: 2.10,
        avg_holding_bars: 5.5,
        warnings: [],
      },
    },
    by_direction: {
      BUY: {
        dimension_key: 'direction',
        dimension_value: 'BUY',
        total: 45,
        triggered: 32,
        untriggered: 13,
        wins: 20,
        losses: 12,
        win_rate: 0.625,
        avg_r: 1.35,
        expectancy: 1.35,
        profit_factor: 1.82,
        avg_holding_bars: 6.2,
        warnings: [],
      },
    },
  },
  data_quality_warnings: [
    'SURVIVORSHIP_BIAS: Universe membership is evaluated as of current active membership.',
    'HISTORICAL_FUNDAMENTALS: Financial statements are not fully backfilled for all past quarters.',
  ],
  started_at: '2026-09-01T10:00:00Z',
  completed_at: '2026-09-01T10:00:05Z',
};

const mockHistoryList = {
  count: 1,
  next: null,
  previous: null,
  results: [mockBacktestRun],
};

describe('BacktestsPage (FE-7)', () => {
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
        <MemoryRouter initialEntries={['/backtests']}>
          <Routes>
            <Route path="/backtests" element={<BacktestsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders simulation configuration form and historical runs count', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/backtests/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockHistoryList });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    expect(screen.getByText('Historical Simulation Configuration')).toBeInTheDocument();
    expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run Backtest Simulation/i })).toBeInTheDocument();
  });

  it('submits a backtest run and displays performance KPIs, biases, and breakdowns', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/backtests/run/')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockBacktestRun,
        });
      }
      if (url.includes('/api/v1/backtests/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockHistoryList });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const runBtn = screen.getByTestId('run-backtest-button');
    await act(async () => {
      fireEvent.click(runBtn);
    });

    await waitFor(() => {
      expect(screen.getByTestId('backtest-results-container')).toBeInTheDocument();
      expect(screen.getAllByText('+1.35 R').length).toBeGreaterThan(0); // Expectancy
      expect(screen.getAllByText('1.82').length).toBeGreaterThan(0); // Profit Factor
      expect(screen.getByText('-2.45 R')).toBeInTheDocument(); // Max Drawdown

      // Methodological bias disclosures
      expect(screen.getByText(/Methodological Assumptions & Bias Disclosures/i)).toBeInTheDocument();
      expect(screen.getByText(/SURVIVORSHIP_BIAS/i)).toBeInTheDocument();

      // Breakdown tables
      expect(screen.getByText('BREAKOUT')).toBeInTheDocument();
      expect(screen.getByText('70.0%')).toBeInTheDocument();
    });
  });

  it('switches to historical runs tab and inspects past run in detail drawer', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/backtests/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockHistoryList });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const historyTab = screen.getByText('Historical Backtest Runs');
    fireEvent.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText(/NIFTY50_1d_DELIVERY_SWING/i)).toBeInTheDocument();
    });

    const viewBtn = screen.getByRole('button', { name: /View Run →/i });
    fireEvent.click(viewBtn);

    await waitFor(() => {
      expect(screen.getByTestId('backtest-detail-drawer')).toBeInTheDocument();
      expect(screen.getByText('Simulation Parameters')).toBeInTheDocument();
    });
  });

  it('handles simulation submission failure gracefully', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/backtests/run/')) {
        return Promise.resolve({
          ok: false,
          status: 400,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            error: { code: 'VALIDATION_ERROR', message: 'Universe NIFTY50 has no active members for the requested date window.' },
          }),
        });
      }
      if (url.includes('/api/v1/backtests/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockHistoryList });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const runBtn = screen.getByTestId('run-backtest-button');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/Simulation Failed/i)).toBeInTheDocument();
      expect(screen.getByText(/Universe NIFTY50 has no active members/i)).toBeInTheDocument();
    });
  });
});
