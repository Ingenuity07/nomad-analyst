import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AlertsPage } from '../pages/AlertsPage';
import * as apiClientModule from '../lib/api/client';

vi.mock('../lib/api/client', () => ({
  apiClient: vi.fn(),
}));

describe('AlertsPage (FE-12)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
    localStorage.clear();

    (apiClientModule.apiClient as any).mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/market/overview/')) {
        return Promise.resolve({
          as_of: '2026-09-01T15:30:00Z',
          universe: 'NIFTY50',
          market_session: {
            is_trading_hour: true,
            phase: 'REGULAR',
            session_date: '2026-09-01',
          },
          indices: [],
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
      if (url.startsWith('/api/v1/recommendations/')) {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'rec-live-1',
              symbol: 'RELIANCE',
              company_name: 'Reliance Industries Ltd.',
              sector: 'Energy',
              as_of: '2026-09-01T11:00:00Z',
              horizon: 'DELIVERY_SWING',
              signal: 'BUY',
              setup_type: 'MOMENTUM_BREAKOUT',
              timeframe: 'DAILY',
              confidence: 'HIGH',
              status: 'ACTIVE',
              entry_type: 'LIMIT',
              entry_price: 2950.0,
              stop_price: 2880.0,
              target_price: 3100.0,
              created_at: '2026-09-01T11:00:00Z',
            },
          ],
        });
      }
      if (url.startsWith('/api/v1/opportunities/')) {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'opp-live-1',
              symbol: 'TCS',
              company_name: 'Tata Consultancy Services Ltd.',
              sector: 'Technology',
              as_of: '2026-09-01T11:00:00Z',
              opportunity_type: 'VOLUME_SURGE',
              final_opportunity_score: 92,
              reasons: ['Strong FII inflow'],
              risks: [],
            },
          ],
        });
      }
      if (url.includes('/stocks/RELIANCE/')) {
        return Promise.resolve({
          instrument: { symbol: 'RELIANCE', company: { name: 'Reliance Industries Ltd.', sector: 'Energy' } },
          latest_snapshot: { close: 2980.0, change_percent: 1.2 },
        });
      }
      return Promise.resolve({
        count: 0,
        results: [],
      });
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/alerts']}>
          <Routes>
            <Route path="/alerts" element={<AlertsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders command center status strip, monitor rules, and active event feed', async () => {
    renderComponent();

    expect(screen.getByText('Alerts & Monitoring Command Center')).toBeInTheDocument();
    expect(screen.getByTestId('command-center-status-strip')).toBeInTheDocument();
    expect(screen.getByTestId('custom-monitor-manager')).toBeInTheDocument();
    expect(screen.getByTestId('active-event-feed')).toBeInTheDocument();
    expect(screen.getByTestId('server-notification-boundary-card')).toBeInTheDocument();
  });

  it('displays initial event feed and allows filtering by category', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Active BUY Signal: Momentum Breakout/i)).toBeInTheDocument();
    });

    // Click Category filter Recommendations
    const recCategoryBtn = screen.getByRole('button', { name: 'Recommendations' });
    fireEvent.click(recCategoryBtn);

    await waitFor(() => {
      expect(screen.getByText(/Active BUY Signal: Momentum Breakout/i)).toBeInTheDocument();
    });
  });

  it('allows adding a new price monitor rule and toggling active state', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('add-monitor-rule-btn')).toBeInTheDocument();
    });

    const addBtn = screen.getByTestId('add-monitor-rule-btn');
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(screen.getByTestId('rule-threshold-input')).toBeInTheDocument();
    });

    const thresholdInput = screen.getByTestId('rule-threshold-input');
    fireEvent.change(thresholdInput, { target: { value: '3150' } });

    const form = screen.getByTestId('add-monitor-rule-form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/3150/)).toBeInTheDocument();
    });

    // Toggle pause on the rule
    const toggleBtn = screen.getByTestId('toggle-rule-rule-def-1');
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByTestId('toggle-rule-rule-def-1')).toHaveTextContent(/Resume/i);
    });
  });

  it('opens alert detail drawer on event click and displays contextual links', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Active BUY Signal: Momentum Breakout/i)).toBeInTheDocument();
    });

    // Click event card
    const eventCard = screen.getByText(/Active BUY Signal: Momentum Breakout/i);
    fireEvent.click(eventCard);

    await waitFor(() => {
      expect(screen.getByTestId('alert-detail-drawer')).toBeInTheDocument();
      expect(screen.getByText('📈 Stock Terminal')).toBeInTheDocument();
      expect(screen.getByText('🤖 AI Research')).toBeInTheDocument();
    });
  });

  it('clears event history when clear feed button is clicked', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Active BUY Signal: Momentum Breakout/i)).toBeInTheDocument();
    });

    const clearBtn = await screen.findByRole('button', { name: /Clear Feed/i });
    fireEvent.click(clearBtn);

    await waitFor(() => {
      expect(screen.getByText(/No monitoring events recorded in this category yet./i)).toBeInTheDocument();
    });
  });
});
