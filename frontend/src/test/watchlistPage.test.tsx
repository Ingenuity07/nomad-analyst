import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WatchlistPage } from '../pages/WatchlistPage';
import * as apiClientModule from '../lib/api/client';

vi.mock('../lib/api/client', () => ({
  apiClient: vi.fn(),
}));

describe('WatchlistPage (FE-11)', () => {
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
      if (url.startsWith('/api/v1/recommendations/')) {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'rec-rel',
              symbol: 'RELIANCE',
              company_name: 'Reliance Industries Ltd.',
              sector: 'Energy',
              as_of: '2026-09-01T10:00:00Z',
              horizon: 'DELIVERY_SWING',
              signal: 'BUY',
              setup_type: 'MOMENTUM_BREAKOUT',
              timeframe: 'DAILY',
              confidence: 'HIGH',
              status: 'ACTIVE',
              entry_type: 'LIMIT',
              entry_price: 2950.0,
              entry_condition: 'Breakout above 2940',
              stop_price: 2880.0,
              target_price: 3100.0,
              trailing_stop: null,
              risk_reward_ratio: 2.14,
              catalysts: ['Energy margin recovery'],
              risks: ['Crude price volatility'],
              market_regime_context: { trend: 'BULLISH' },
              created_at: '2026-09-01T10:00:00Z',
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
              id: 'opp-tcs',
              symbol: 'TCS',
              company_name: 'Tata Consultancy Services Ltd.',
              sector: 'Technology',
              as_of: '2026-09-01T10:00:00Z',
              universe: 'NIFTY50',
              horizon: 'DELIVERY_SWING',
              opportunity_type: 'VOLUME_SURGE',
              final_opportunity_score: 88,
              component_scores: {},
              supporting_features: {},
              reasons: ['Institutional accumulation'],
              risks: ['FX fluctuation'],
              data_quality: {},
            },
          ],
        });
      }
      if (url.includes('/stocks/search/')) {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              symbol: 'SBIN',
              name: 'State Bank of India',
              sector: 'Financial Services',
              industry: 'Banks',
              exchange: 'NSE',
            },
          ],
        });
      }
      if (url.includes('/stocks/RELIANCE/')) {
        return Promise.resolve({
          instrument: {
            id: 'inst-1',
            symbol: 'RELIANCE',
            exchange: 'NSE',
            instrument_type: 'EQUITY',
            is_active: true,
            company: {
              id: 'c-1',
              name: 'Reliance Industries Ltd.',
              short_name: 'Reliance',
              sector: 'Energy',
              industry: 'Oil & Gas',
            },
          },
          latest_snapshot: {
            id: 'snap-1',
            timestamp: '2026-09-01T15:30:00Z',
            open: 2920,
            high: 2980,
            low: 2910,
            close: 2965.5,
            volume: 4500000,
            previous_close: 2920,
            change: 45.5,
            change_percent: 1.56,
            source: 'NSE_EOD',
          },
          active_recommendation: null,
          latest_opportunity: null,
        });
      }
      if (url.includes('/stocks/TCS/')) {
        return Promise.resolve({
          instrument: {
            id: 'inst-2',
            symbol: 'TCS',
            exchange: 'NSE',
            instrument_type: 'EQUITY',
            is_active: true,
            company: {
              id: 'c-2',
              name: 'Tata Consultancy Services Ltd.',
              short_name: 'TCS',
              sector: 'Technology',
              industry: 'IT Services',
            },
          },
          latest_snapshot: {
            id: 'snap-2',
            timestamp: '2026-09-01T15:30:00Z',
            open: 4100,
            high: 4150,
            low: 4080,
            close: 4120.0,
            volume: 2100000,
            previous_close: 4100,
            change: 20.0,
            change_percent: 0.49,
            source: 'NSE_EOD',
          },
          active_recommendation: null,
          latest_opportunity: null,
        });
      }
      return Promise.resolve({
        instrument: {
          id: 'inst-gen',
          symbol: 'GENERIC',
          exchange: 'NSE',
          instrument_type: 'EQUITY',
          is_active: true,
          company: { id: 'c-g', name: 'Generic Ltd', short_name: 'Generic', sector: 'General', industry: 'General' },
        },
        latest_snapshot: {
          id: 'snap-g',
          timestamp: '2026-09-01T15:30:00Z',
          open: 100,
          high: 105,
          low: 99,
          close: 102.5,
          volume: 10000,
          previous_close: 100,
          change: 2.5,
          change_percent: 2.5,
          source: 'NSE_EOD',
        },
        active_recommendation: null,
        latest_opportunity: null,
      });
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/watchlist']}>
          <Routes>
            <Route path="/watchlist" element={<WatchlistPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders watchlist management strip and default core watchlist', async () => {
    renderComponent();

    expect(screen.getByText('Watchlist & Personal Decisions')).toBeInTheDocument();
    expect(screen.getByText('Core Watchlist')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-summary-strip')).toBeInTheDocument();
    expect(screen.getByTestId('monitored-decision-table')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-boundary-card')).toBeInTheDocument();
  });

  it('displays default tracked symbols with live quote and matched recommendation signal', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('TCS')).toBeInTheDocument();
    });

    // Check matched BUY signal for RELIANCE
    await waitFor(() => {
      expect(screen.getByText(/BUY \(MOMENTUM_BREAKOUT\)/i)).toBeInTheDocument();
    });

    // Check matched Opportunity score for TCS (88/100)
    await waitFor(() => {
      expect(screen.getAllByText('88/100').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('allows creating a new custom watchlist and switching between lists', async () => {
    renderComponent();

    const newBtn = screen.getByTestId('add-new-watchlist-btn');
    fireEvent.click(newBtn);

    const input = screen.getByPlaceholderText('Watchlist name...');
    fireEvent.change(input, { target: { value: 'High Growth IT' } });

    const createBtn = screen.getByText('Create');
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(screen.getByText('High Growth IT')).toBeInTheDocument();
    });
  });

  it('allows adding a new symbol and prevents adding duplicates', async () => {
    renderComponent();

    const searchInput = screen.getByPlaceholderText(/Add stock/i);
    fireEvent.change(searchInput, { target: { value: 'RELIANCE' } });

    const addBtn = screen.getByText('+ Add');
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(screen.getByText(/'RELIANCE' is already in this watchlist./i)).toBeInTheDocument();
    });

    // Add new symbol SBIN
    fireEvent.change(searchInput, { target: { value: 'SBIN' } });
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(screen.getByText(/Added 'SBIN' to watchlist./i)).toBeInTheDocument();
    });
  });

  it('opens detail drawer on row click and updates personal decision notes', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    // Click RELIANCE row to open drawer
    const relianceRow = screen.getByText('RELIANCE');
    fireEvent.click(relianceRow);

    await waitFor(() => {
      expect(screen.getByText(/Watched Decision Dossier/i)).toBeInTheDocument();
    });

    // Click Edit Notes
    const editBtn = screen.getByText(/Edit Notes/i);
    fireEvent.click(editBtn);

    const textArea = screen.getByPlaceholderText(/Enter personal investment thesis/i);
    fireEvent.change(textArea, { target: { value: 'Bullish breakout confirmed with high delivery volume.' } });

    const saveBtn = screen.getByText('Save Thesis');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText('Bullish breakout confirmed with high delivery volume.')).toBeInTheDocument();
    });
  });
});
