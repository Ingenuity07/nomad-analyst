import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { FundamentalsPage } from '../pages/FundamentalsPage';

const mockStockDetail = {
  instrument: {
    id: 'inst-123',
    symbol: 'RELIANCE',
    exchange: 'NSE',
    company: {
      id: 'comp-123',
      name: 'Reliance Industries Limited',
      legal_name: 'Reliance Industries Ltd.',
      short_name: 'RELIANCE',
      isin: 'INE002A01018',
      sector: 'Energy',
      industry: 'Oil & Gas Refining',
      description: 'Reliance Industries Limited is an Indian multinational conglomerate headquartered in Mumbai.',
      website: 'https://www.ril.com',
    },
  },
  latest_snapshot: {
    close: 2975.5,
    change_percent: 1.45,
    timestamp: '2026-09-01T10:00:00Z',
  },
  active_recommendation: {
    id: 'rec-123',
    signal: 'BUY',
    horizon: 'DELIVERY_SWING',
  },
};

const mockFundamentals = {
  symbol: 'RELIANCE',
  company_name: 'Reliance Industries Limited',
  sector: 'Energy',
  industry: 'Oil & Gas Refining',
  statements: {
    income_statement: [
      {
        id: 'inc-1',
        fiscal_year: 2025,
        period_type: 'ANNUAL',
        period_string: 'Mar 2025',
        revenue: 250000.0,
        ebitda: 45000.0,
        ebit: 38000.0,
        pbt: 32000.0,
        tax: 7000.0,
        pat: 25000.0,
        eps: 95.5,
        filing_date: '2025-05-15',
      },
      {
        id: 'inc-2',
        fiscal_year: 2024,
        period_type: 'ANNUAL',
        period_string: 'Mar 2024',
        revenue: 220000.0,
        ebitda: 39000.0,
        ebit: 33000.0,
        pbt: 28000.0,
        tax: 6000.0,
        pat: 22000.0,
        eps: 84.0,
        filing_date: '2024-05-20',
      },
    ],
    balance_sheet: [
      {
        id: 'bal-1',
        fiscal_year: 2025,
        period_type: 'ANNUAL',
        period_string: 'Mar 2025',
        equity_capital: 6500.0,
        reserves: 140000.0,
        borrowings: 60000.0,
        total_assets: 235000.0,
        total_liabilities: 235000.0,
        fixed_assets: 150000.0,
        filing_date: '2025-05-15',
      },
    ],
    cash_flow: [
      {
        id: 'cf-1',
        fiscal_year: 2025,
        period_type: 'ANNUAL',
        period_string: 'Mar 2025',
        operating_cash_flow: 42000.0,
        investing_cash_flow: -28000.0,
        financing_cash_flow: -11000.0,
        free_cash_flow: 18000.0,
        filing_date: '2025-05-15',
      },
    ],
  },
  metrics: [
    { id: 'm-1', name: 'pe_ratio', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 26.4 },
    { id: 'm-2', name: 'return_on_equity', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.1706 },
    { id: 'm-3', name: 'return_on_capital_employed', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.184 },
    { id: 'm-4', name: 'debt_equity', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.4095 },
    { id: 'm-5', name: 'ebitda_margin', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.18 },
    { id: 'm-6', name: 'net_margin', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.10 },
    { id: 'm-7', name: 'revenue_growth_yoy', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.1363 },
    { id: 'm-8', name: 'pat_growth_yoy', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 0.1363 },
    { id: 'm-9', name: 'cfo_pat', period_type: 'ANNUAL', period_string: 'Mar 2025', value: 1.68 },
  ],
  data_quality: {
    source: 'screener.in',
    status: 'COMPLETE',
  },
};

const mockEvents = {
  count: 1,
  results: [
    {
      id: 'event-1',
      headline: 'Outcome of Board Meeting for Dividend Approval',
      category: 'Board Meeting',
      source: 'NSE',
      announcement_id: 'ANN-2026-08',
      url: 'https://www.nseindia.com/corporate-filings/ann-1',
      published_at: '2026-08-15T12:00:00Z',
      details: {},
    },
  ],
};

const mockNews = {
  count: 1,
  results: [
    {
      id: 'news-1',
      headline: 'Reliance Expands Retail Footprint with 150 New Stores',
      summary: 'Reliance Retail aggressive retail expansion continues across Tier 2 and Tier 3 cities.',
      source: 'Reuters',
      published_at: '2026-08-20T08:30:00Z',
    },
  ],
};

describe('FundamentalsPage (FE-9)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/fundamentals/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockFundamentals,
        });
      }
      if (url.includes('/events/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockEvents,
        });
      }
      if (url.includes('/news/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockNews,
        });
      }
      if (url.includes('/api/v1/stocks/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockStockDetail,
        });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });
  });

  const renderComponent = (initialPath = '/fundamentals?symbol=RELIANCE') =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/fundamentals" element={<FundamentalsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders company profile header, ISIN, sector, and navigation actions', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('company-profile-header')).toBeInTheDocument();
      expect(screen.getByText('Reliance Industries Limited')).toBeInTheDocument();
      expect(screen.getByText(/INE002A01018/)).toBeInTheDocument();
      expect(screen.getByText('Energy')).toBeInTheDocument();
      expect(screen.getByText(/Oil & Gas Refining/)).toBeInTheDocument();
      expect(screen.getByTestId('view-stock-terminal-button')).toBeInTheDocument();
      expect(screen.getByTestId('research-company-button')).toBeInTheDocument();
    });
  });

  it('renders fundamental snapshot metric cards with calculated ratios', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('fundamental-snapshot-cards')).toBeInTheDocument();
      expect(screen.getByText('26.4x')).toBeInTheDocument(); // P/E
      expect(screen.getByText('17.06%')).toBeInTheDocument(); // ROE
      expect(screen.getByText('18.40%')).toBeInTheDocument(); // ROCE
      expect(screen.getByText('0.41')).toBeInTheDocument(); // Debt/Equity
      expect(screen.getByText('18.00%')).toBeInTheDocument(); // EBITDA margin
    });
  });

  it('renders financial statement explorer and switches between table and trends', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('financial-statement-explorer')).toBeInTheDocument();
      expect(screen.getByText('₹250000.00')).toBeInTheDocument(); // Revenue
      expect(screen.getByText('₹45000.00')).toBeInTheDocument(); // EBITDA
    });

    // Switch to performance trends view
    const trendBtn = screen.getByText(/Performance Trends/i);
    fireEvent.click(trendBtn);

    await waitFor(() => {
      expect(screen.getByTestId('financial-trend-charts')).toBeInTheDocument();
    });
  });

  it('renders exchange regulatory disclosures with official filing link', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('exchange-disclosures-card')).toBeInTheDocument();
      expect(screen.getByText(/Outcome of Board Meeting for Dividend Approval/i)).toBeInTheDocument();
      expect(screen.getByText(/View Official Exchange Filing ↗/i)).toBeInTheDocument();
    });
  });

  it('renders recent news card with terminal handoff', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('recent-news-card')).toBeInTheDocument();
      expect(screen.getByText(/Reliance Expands Retail Footprint with 150 New Stores/i)).toBeInTheDocument();
      expect(screen.getByText(/View All in Terminal →/i)).toBeInTheDocument();
    });
  });
});
