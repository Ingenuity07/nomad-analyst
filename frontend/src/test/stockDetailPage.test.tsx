import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { StockDetailPage } from '../pages/StockDetailPage';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    addHistogramSeries: vi.fn(() => ({
      setData: vi.fn(),
      priceScale: vi.fn(() => ({
        applyOptions: vi.fn(),
      })),
    })),
    subscribeCrosshairMove: vi.fn(),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
    })),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  })),
}));

const mockStockDetail = {
  instrument: {
    id: 'inst-1',
    symbol: 'RELIANCE',
    exchange: 'NSE',
    instrument_type: 'EQUITY',
    currency: 'INR',
    company: {
      id: 'comp-1',
      name: 'Reliance Industries Limited',
      legal_name: 'Reliance Industries Limited',
      short_name: 'RELIANCE',
      sector: 'Energy',
      industry: 'Oil & Gas Refining & Marketing',
    },
  },
  latest_snapshot: {
    id: 'snap-1',
    symbol: 'RELIANCE',
    timestamp: '2026-09-01T10:00:00Z',
    open: '2950.00',
    high: '2985.00',
    low: '2940.00',
    close: '2975.50',
    volume: 4520100,
    previous_close: '2950.00',
    change: '25.50',
    change_percent: '0.86',
    source: 'NSE',
  },
  active_recommendation: {
    id: 'rec-1',
    symbol: 'RELIANCE',
    signal: 'BUY',
    setup_type: 'BREAKOUT',
    confidence: 'HIGH',
    status: 'ACTIVE',
    entry_price: 2980.0,
    stop_price: 2920.0,
    target_price: 3080.0,
    risk_reward_ratio: 1.67,
    entry_condition: 'Enter on daily close above 2980',
  },
  latest_opportunity: {
    symbol: 'RELIANCE',
    opportunity_type: 'TRENDING',
    final_opportunity_score: 87.5,
    component_scores: {
      technical: 95.0,
      fundamental: 80.0,
      sector: 90.0,
      news: 85.0,
    },
    reasons: ['Strong momentum support', 'Solid balance sheet leverage'],
  },
  data_freshness: {
    status: 'LIVE',
    timestamp: '2026-09-01T10:00:00Z',
  },
};

const mockOHLCV = {
  symbol: 'RELIANCE',
  exchange: 'NSE',
  timeframe: '1d',
  bars_count: 3,
  bars: [
    { timeframe: '1d', timestamp: '2026-08-28T00:00:00Z', open: '2920.0', high: '2950.0', low: '2910.0', close: '2945.0', volume: 3000000, source: 'yfinance' },
    { timeframe: '1d', timestamp: '2026-08-29T00:00:00Z', open: '2945.0', high: '2960.0', low: '2930.0', close: '2950.0', volume: 3200000, source: 'yfinance' },
    { timeframe: '1d', timestamp: '2026-09-01T00:00:00Z', open: '2950.0', high: '2985.0', low: '2940.0', close: '2975.5', volume: 4520100, source: 'yfinance' },
  ],
};

const mockTechnicals = {
  symbol: 'RELIANCE',
  timeframe: '1d',
  as_of: '2026-09-01T10:00:00Z',
  indicators_count: 7,
  indicators: {
    RSI_14: { value: 65.4, parameters: { period: 14 } },
    SMA_20: { value: 2930.0, parameters: { period: 20 } },
    SMA_50: { value: 2880.0, parameters: { period: 50 } },
    SMA_200: { value: 2750.0, parameters: { period: 200 } },
    EMA_20: { value: 2940.0, parameters: { period: 20 } },
    EMA_50: { value: 2895.0, parameters: { period: 50 } },
    EMA_200: { value: 2765.0, parameters: { period: 200 } },
    MACD_line: { value: 18.5, parameters: {} },
    MACD_signal: { value: 14.2, parameters: {} },
    MACD_hist: { value: 4.3, parameters: {} },
    ATR_14: { value: 38.5, parameters: { period: 14 } },
    volume_sma_20: { value: 3800000, parameters: { period: 20 } },
  },
  status: 'HEALTHY',
};

const mockFundamentals = {
  symbol: 'RELIANCE',
  company_name: 'Reliance Industries Limited',
  sector: 'Energy',
  industry: 'Oil & Gas',
  statements: {
    income_statement: [
      { id: 'inc-1', fiscal_year: 2024, period_type: 'ANNUAL', revenue: 900000, ebitda: 178000, ebit: 125000, pat: 79000, eps: 116.5 },
    ],
    balance_sheet: [
      { id: 'bal-1', fiscal_year: 2024, period_type: 'ANNUAL', equity_capital: 6765, reserves: 790000, borrowings: 310000, total_assets: 1700000 },
    ],
    cash_flow: [
      { id: 'cf-1', fiscal_year: 2024, period_type: 'ANNUAL', operating_cash_flow: 145000, investing_cash_flow: -110000, financing_cash_flow: -30000, free_cash_flow: 35000 },
    ],
  },
  metrics: [
    { id: 'm-1', name: 'return_on_equity', value: 0.178 },
    { id: 'm-2', name: 'return_on_capital_employed', value: 0.145 },
    { id: 'm-3', name: 'debt_equity', value: 0.39 },
    { id: 'm-4', name: 'net_margin', value: 0.088 },
    { id: 'm-5', name: 'revenue_growth_yoy', value: 0.125 },
    { id: 'm-6', name: 'pe_ratio', value: 25.5 },
  ],
  data_quality: { source: 'screener.in', status: 'COMPLETE' },
};

const mockNews = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 'news-1',
      headline: 'Reliance announces major new green energy project',
      summary: 'Expansion into solar gigafactories underway in Gujarat.',
      source: 'Reuters',
      published_at: '2026-09-01T08:30:00Z',
      url: 'https://example.com/news-1',
    },
  ],
};

const mockEvents = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 'ev-1',
      headline: 'Q1 Financial Results Disclosure',
      category: 'Financial Results',
      source: 'NSE',
      published_at: '2026-08-15T12:00:00Z',
      details: 'Unaudited financial results for the quarter ended June 30, 2026.',
    },
  ],
};

describe('StockDetailPage (FE-5)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });
  });

  const renderComponent = (symbol = 'RELIANCE') =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/stocks/${symbol}`]}>
          <Routes>
            <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders Stock Detail header, chart container, and overview metrics', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/stocks/RELIANCE/ohlcv/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOHLCV });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/technicals/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockTechnicals });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/fundamentals/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockFundamentals });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/news/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockNews });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/events/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockEvents });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStockDetail });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('Reliance Industries Limited • Oil & Gas Refining & Marketing')).toBeInTheDocument();
      expect(screen.getByText('₹2,975.50')).toBeInTheDocument();
      expect(screen.getByText(/\+₹25\.50/)).toBeInTheDocument();
    });

    // Verify Overview Tab content
    expect(screen.getByText(/Key Market & Pricing Metrics/i)).toBeInTheDocument();
    expect(screen.getByText('Active Strategy Recommendation')).toBeInTheDocument();
    expect(screen.getByText('★ 87.5 / 100')).toBeInTheDocument();
  });

  it('switches to Technical Indicators tab and displays indicators', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/stocks/RELIANCE/technicals/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockTechnicals });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/ohlcv/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOHLCV });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStockDetail });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const techTab = screen.getByText('Technical Indicators');
    fireEvent.click(techTab);

    await waitFor(() => {
      expect(screen.getByText(/Moving Averages & Trend Alignment/i)).toBeInTheDocument();
      expect(screen.getByText('₹2930.00')).toBeInTheDocument();
      expect(screen.getByText('65.4')).toBeInTheDocument();
      expect(screen.getByText('₹38.50')).toBeInTheDocument();
    });
  });

  it('switches to Fundamentals tab and renders statements and derived ratios', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/stocks/RELIANCE/fundamentals/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockFundamentals });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/ohlcv/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOHLCV });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStockDetail });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const fundTab = screen.getByText('Audited Statements & Ratios');
    fireEvent.click(fundTab);

    await waitFor(() => {
      expect(screen.getByText(/Derived Financial Ratios & Profitability/i)).toBeInTheDocument();
      expect(screen.getByText('17.80%')).toBeInTheDocument(); // ROE
      expect(screen.getByText('0.39')).toBeInTheDocument(); // Debt/Equity
      expect(screen.getByText('25.50')).toBeInTheDocument(); // P/E
      expect(screen.getByText('₹900000.00')).toBeInTheDocument(); // Revenue
    });
  });

  it('submits AI research question and renders report', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/chat/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            response: 'Reliance exhibits a robust operational cash flow profile driven by refining margins and retail expansion.',
            as_of: '2026-09-01T10:00:00Z',
          }),
        });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/ohlcv/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockOHLCV });
      }
      if (url.includes('/api/v1/stocks/RELIANCE/')) {
        return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => mockStockDetail });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const aiTab = screen.getByText('AI Research Synthesis');
    fireEvent.click(aiTab);

    await waitFor(() => {
      expect(screen.getByText(/Nomad Analyst AI Research — RELIANCE/i)).toBeInTheDocument();
    });

    const submitBtn = screen.getByRole('button', { name: /Generate Research Report/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      const output = screen.getByTestId('ai-research-output');
      expect(output).toBeInTheDocument();
      expect(output).toHaveTextContent('Reliance exhibits a robust operational cash flow profile');
    });
  });

  it('renders ErrorState when unknown symbol is queried', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: { code: 'NOT_FOUND', message: "Stock symbol 'UNKNOWN' not found." },
      }),
    });

    renderComponent('UNKNOWN');

    await waitFor(() => {
      expect(screen.getAllByText(/Symbol 'UNKNOWN' Not Found/i).length).toBeGreaterThan(0);
    });
  });
});
