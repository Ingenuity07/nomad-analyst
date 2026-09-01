import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ResearchPage } from '../pages/ResearchPage';

const mockResearchReport = {
  company: 'Reliance Industries Limited',
  instrument: 'RELIANCE',
  as_of: '2026-08-20T10:00:00Z',
  summary: 'Reliance Industries demonstrates robust operational cash flows supported by petrochemical and retail expansion. Capital structure exhibits low leverage with debt-to-equity at 0.42.',
  market_snapshot: {
    price: 2975.5,
    pe: 26.4,
    sector: 'Energy',
    market_cap_tier: 'Large Cap',
  },
  technical_analysis: 'Trading above 50-day and 200-day SMAs with daily RSI at 64.5 indicating sustained trend continuation.',
  fundamental_analysis: 'Operating cash flows expanded 14% YoY with steady Return on Equity of 18.2%. Working capital cycle remains tight.',
  news_analysis: 'Recent corporate disclosures highlight 150 new retail store additions and strategic green energy investments.',
  positive_factors: [
    'Strong structural momentum above 200-day SMA',
    'Robust operating cash flow conversion (18% ROE)',
    'Dominant retail market footprint',
  ],
  risks: [
    'Refining margin pressure from volatile crude benchmarks',
    'Near-term technical overhead resistance at ₹3,020',
  ],
  contradictions: [
    'Revenue expanded 12% YoY while net profit margin contracted by 40 bps',
  ],
  unknowns: [
    'Overseas exploration subsidiary capital allocation timeline unconfirmed',
  ],
  evidence: [
    'Income Statement 2024-Q4: Revenue ₹2,45,000 Cr, EBITDA ₹42,500 Cr',
    'Technical Indicators 2026-08-20: SMA_50=2850, SMA_200=2710, RSI_14=64.5',
    'News Disclosures 2026-08-15: Retail segment adds 150 new locations',
  ],
  generated_at: '2026-09-01T15:45:00Z',
};

describe('ResearchPage (FE-8)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });
  });

  const renderComponent = (initialPath = '/research') =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/research" element={<ResearchPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('renders initial research console, prompt suggestions, and empty state', () => {
    renderComponent();

    // Verify Title and Subtitle
    expect(screen.getByText('Equity Intelligence & Research Laboratory')).toBeInTheDocument();
    expect(screen.getByText('AI Equity Intelligence & Synthesis Console')).toBeInTheDocument();

    // Verify Inputs
    expect(screen.getByPlaceholderText('e.g. RELIANCE, TCS, INFY')).toBeInTheDocument();
    expect(screen.getByTestId('research-question-input')).toBeInTheDocument();
    expect(screen.getByTestId('run-research-button')).toBeInTheDocument();

    // Verify Empty State
    expect(screen.getByText('No Research Synthesis Generated Yet')).toBeInTheDocument();

    // Verify Disclaimer
    expect(screen.getByTestId('research-disclaimer')).toBeInTheDocument();
  });

  it('submits a research request and renders the full synthesized research dossier', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/research/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockResearchReport,
        });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const runBtn = screen.getByTestId('run-research-button');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByTestId('research-report-container')).toBeInTheDocument();
      expect(screen.getByTestId('research-report-header')).toBeInTheDocument();
      expect(screen.getAllByText(/Reliance Industries Limited/i).length).toBeGreaterThanOrEqual(1);

      // Executive summary
      expect(screen.getByTestId('research-summary-card')).toBeInTheDocument();
      expect(screen.getByText(/demonstrates robust operational cash flows/i)).toBeInTheDocument();

      // Factor Intelligence Matrix
      expect(screen.getByTestId('factor-intelligence-matrix')).toBeInTheDocument();
      expect(screen.getByText(/Strong structural momentum above 200-day SMA/i)).toBeInTheDocument();
      expect(screen.getByText(/Refining margin pressure from volatile crude benchmarks/i)).toBeInTheDocument();
      expect(screen.getByText(/Revenue expanded 12% YoY while net profit margin contracted by 40 bps/i)).toBeInTheDocument();
      expect(screen.getByText(/Overseas exploration subsidiary capital allocation timeline unconfirmed/i)).toBeInTheDocument();

      // Domain Analysis
      expect(screen.getByTestId('deep-analysis-sections')).toBeInTheDocument();
      expect(screen.getByText(/Trading above 50-day and 200-day SMAs/i)).toBeInTheDocument();

      // Session History
      expect(screen.getByTestId('session-research-history')).toBeInTheDocument();
    });
  });

  it('opens and inspects evidence traces in slide-over drawer', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/research/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockResearchReport,
        });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const runBtn = screen.getByTestId('run-research-button');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByTestId('open-evidence-button')).toBeInTheDocument();
    });

    // Open evidence drawer
    const evidenceBtn = screen.getByTestId('open-evidence-button');
    fireEvent.click(evidenceBtn);

    await waitFor(() => {
      expect(screen.getByTestId('evidence-drawer-content')).toBeInTheDocument();
      expect(screen.getByText(/Income Statement 2024-Q4: Revenue ₹2,45,000 Cr/i)).toBeInTheDocument();
      expect(screen.getByText(/Technical Indicators 2026-08-20: SMA_50=2850/i)).toBeInTheDocument();
    });
  });

  it('pre-populates symbol when navigating with ?symbol= query parameter', () => {
    renderComponent('/research?symbol=TCS');

    const symbolInput = screen.getByPlaceholderText('e.g. RELIANCE, TCS, INFY') as HTMLInputElement;
    expect(symbolInput.value).toBe('TCS');
  });

  it('handles research execution errors gracefully', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/research/')) {
        return Promise.resolve({
          ok: false,
          status: 500,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            error: {
              code: 'RESEARCH_EXECUTION_FAILED',
              message: 'Stock symbol UNKNOWN not found in registry.',
            },
          }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) });
    });

    renderComponent();

    const runBtn = screen.getByTestId('run-research-button');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/Research Execution Failed/i)).toBeInTheDocument();
      expect(screen.getByText(/Stock symbol UNKNOWN not found in registry/i)).toBeInTheDocument();
    });
  });
});
