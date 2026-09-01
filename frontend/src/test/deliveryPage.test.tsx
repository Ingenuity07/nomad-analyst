import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { DeliveryPage } from '../pages/DeliveryPage';

const mockOpportunityData = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 'opp-1',
      symbol: 'RELIANCE',
      company_name: 'Reliance Industries Limited',
      sector: 'Energy',
      as_of: '2026-09-01T13:45:00Z',
      universe: 'NIFTY50',
      horizon: 'DELIVERY_SWING',
      opportunity_type: 'MOMENTUM_BREAKOUT',
      final_opportunity_score: 87.5,
      component_scores: {
        technical: 92.0,
        fundamental: 78.0,
        sector: 100.0,
        market: 80.0,
        news: 70.0,
      },
      supporting_features: {
        close: 1309.0,
        pros: [
          'Price is trading above its 50-day SMA',
          'Safe leverage structure (Debt/Equity=0.45)',
          'Sector Energy is a top-performing market leader',
        ],
      },
      risks: [
        'Resistance level at ₹1,335.0',
        'Overhead 200-day moving average',
      ],
      data_quality: { status: 'COMPLETE' },
    },
    {
      id: 'opp-2',
      symbol: 'TCS',
      company_name: 'Tata Consultancy Services',
      sector: 'Technology',
      as_of: '2026-09-01T13:45:00Z',
      universe: 'NIFTY50',
      horizon: 'DELIVERY_SWING',
      opportunity_type: 'PULLBACK_SUPPORT',
      final_opportunity_score: 72.0,
      component_scores: {
        technical: 68.0,
        fundamental: 85.0,
        sector: 50.0,
        market: 80.0,
        news: 60.0,
      },
      supporting_features: {
        close: 4215.0,
        pros: [
          'High ROE (38.5%) capital efficiency',
          'Supported by 50-day EMA zone',
        ],
      },
      risks: [
        'Sector Technology is underperforming benchmark',
      ],
      data_quality: { status: 'COMPLETE' },
    },
  ],
};

describe('DeliveryPage (FE-3)', () => {
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
          <DeliveryPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders Delivery Opportunities workspace with candidate list', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/market/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            as_of: '2026-09-01T13:45:00Z',
            breadth: { breadth_regime: 'strong' },
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockOpportunityData,
      });
    });

    renderComponent();

    // Verify title and subtitle
    expect(screen.getByText(/Delivery Opportunities & Candidate Ranking/i)).toBeInTheDocument();

    // Await async candidate list resolution
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('TCS')).toBeInTheDocument();
    });

    // Check opportunity scores and badges
    expect(screen.getByText('★ 87.5')).toBeInTheDocument();
    expect(screen.getByText('★ 72.0')).toBeInTheDocument();

    // Check summary strip metrics
    expect(screen.getByText('Ranked Candidates')).toBeInTheDocument();
    expect(screen.getByText('Highest Score')).toBeInTheDocument();
  });

  it('opens Quick View drawer upon candidate row click', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/market/overview/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ as_of: '2026-09-01T13:45:00Z', breadth: { breadth_regime: 'strong' } }),
        });
      }
      if (url.includes('/recommendations/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ count: 0, results: [] }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockOpportunityData,
      });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const inspectBtn = screen.getAllByText(/inspect/i)[0];
    fireEvent.click(inspectBtn);

    // Verify Quick View Drawer opens with details
    await waitFor(() => {
      const drawer = screen.getByTestId('quick-view-drawer');
      expect(drawer).toBeInTheDocument();
      expect(drawer).toHaveTextContent('Why It Surfaced');
      expect(drawer).toHaveTextContent('Price is trading above its 50-day SMA');
      expect(drawer).toHaveTextContent('Structural Risks & Headwinds');
      expect(drawer).toHaveTextContent('Resistance level');
      expect(drawer).toHaveTextContent('Open Full Stock Terminal');
    });
  });

  it('filters candidates with search input', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockOpportunityData,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/filter symbol/i);
    fireEvent.change(searchInput, { target: { value: 'RELI' } });

    // RELIANCE should be visible, TCS should be filtered out
    expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    expect(screen.queryByText('TCS')).not.toBeInTheDocument();
  });

  it('renders ErrorState when API fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: {
          code: 'DISCOVERY_FAILURE',
          message: 'Multi-factor opportunity scoring failed.',
          details: {},
          timestamp: '2026-09-01T13:45:00Z',
        },
      }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Failed to Load Opportunity Candidates/i)).toBeInTheDocument();
    });
  });
});
