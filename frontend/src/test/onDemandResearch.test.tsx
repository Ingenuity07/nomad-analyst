import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { IntradayOpportunityTable } from '@/features/intraday/components/IntradayOpportunityTable';
import { IntradayOpportunityDetailDrawer } from '@/features/intraday/components/IntradayOpportunityDetailDrawer';
import { IntradayResearchModal } from '@/features/research/components/IntradayResearchModal';
import { IntradayOpportunityItem } from '@/lib/api/types';

// Mock API Client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}));

const mockOpportunity: IntradayOpportunityItem = {
  symbol: 'TATASTEEL',
  opportunity_type: 'RELATIVE_STRENGTH',
  state: 'CONFIRMED',
  score: 84.0,
  confidence: 0.89,
  bias: 'BULLISH',
  component_scores: {
    momentum_score: 85.0,
    relative_strength_score: 90.0,
    volume_score: 82.0,
    vwap_score: 88.0,
    market_alignment_score: 80.0,
    sector_alignment_score: 95.0,
    orb_score: 85.0,
    data_quality_score: 90.0,
  },
  metrics: {
    last_price: 156.4,
    change_pct: 2.8,
    vwap: 154.2,
    vwap_diff_pct: 1.43,
    volume: 4500000,
    relative_volume: 2.4,
    momentum_5m: 0.45,
    momentum_15m: 1.20,
    relative_strength_vs_market: 1.95,
    relative_strength_vs_sector: 0.40,
    opening_range_state: 'ABOVE_ORB_HIGH',
    volume_confirmation: 'STRONG',
  },
  rank: 1,
  sector: { name: 'Metals', rank: 1, return_pct: 2.4 },
  market_alignment: 'STRONGLY_ALIGNED',
  sector_alignment: 'STRONGLY_ALIGNED',
  data_quality: 'HIGH',
  freshness: 'FRESH',
  timestamp: '2026-09-06T10:30:00Z',
  base_score: 84.0,
  penalties: [],
  supporting_factors: ['Above VWAP', 'Strong RS'],
  contradicting_factors: [],
  warnings: [],
  invalidation_condition: 'Close below VWAP 154.20',
};

const mockExamineResponse = {
  reused: true,
  llm_calls_made: 0,
  research: {
    id: 'run-uuid-1234',
    symbol: 'TATASTEEL',
    mode: 'INTRADAY',
    status: 'completed',
    started_at: '2026-09-06T10:30:00Z',
    completed_at: '2026-09-06T10:30:02Z',
    evidence_hash: 'abc123hash',
    output: {
      summary: 'Tata Steel demonstrates exceptional relative strength against weakening index breadth.',
      observed_facts: [
        'Opportunity score is 84.0 with confidence 0.89.',
        'Trading above VWAP with positive 5m/15m momentum.'
      ],
      analyst_interpretation: 'Institutional flow into metals protects the asset from broader market chop.',
      why_interesting: ['Leading sector rotation'],
      supporting_evidence: ['Volume confirmation 2.4x'],
      contradicting_evidence: ['Index breadth declining'],
      key_risks: ['Sharp reversal if NIFTY breaks 24,000'],
      unknowns: ['Block deal counterparties undisclosed'],
      market_context_interpretation: 'Market regime is TRENDING_UP.',
      sector_context_interpretation: 'Metals leading universe.',
      thesis: 'Constructive continuation supported by sector beta.',
      thesis_strength: 'HIGH',
      what_to_monitor: ['Sustained VWAP hold'],
      invalidating_developments: ['Break below VWAP 154.20'],
      research_confidence: 'HIGH'
    },
    basis: {
      score: 84.0,
      rank: 1,
      state: 'CONFIRMED',
      market_regime: 'TRENDING_UP',
      sector_name: 'Metals',
      sector_rank: 1,
      timestamp: '2026-09-06T10:30:00Z'
    },
    model_name: 'gemini-2.5-flash',
    provider: 'google',
    tokens_used: 1100,
    duration_ms: 1200
  },
  delta: {
    research_id: 'run-uuid-1234',
    symbol: 'TATASTEEL',
    mode: 'INTRADAY',
    research_timestamp: '2026-09-06T10:30:00Z',
    evaluated_at: '2026-09-06T10:35:00Z',
    age_minutes: 5.0,
    freshness: 'FRESH',
    staleness_reasons: [],
    has_material_changes: false,
    changes_summary: [],
    basis: { score: 84.0, rank: 1, state: 'CONFIRMED', market_regime: 'TRENDING_UP', sector_rank: 1 },
    current: { score: 84.0, rank: 1, state: 'CONFIRMED', market_regime: 'TRENDING_UP', sector_rank: 1 },
    deltas: {
      score_change: 0.0,
      rank_change: 0,
      state_changed: false,
      regime_changed: false,
      sector_rank_change: 0,
      momentum_change: 0.0,
      vwap_diff_change: 0.0,
      relative_strength_change: 0.0
    },
    zero_llm_call_verified: true
  }
};

describe('Phase 17E — On-Demand Research Engine Frontend', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('renders EXAMINE button in opportunity table and calls onExamine when clicked', () => {
    const handleExamine = vi.fn();
    const handleSelect = vi.fn();

    render(
      <IntradayOpportunityTable
        opportunities={[mockOpportunity]}
        selectedSymbol={null}
        onSelectOpportunity={handleSelect}
        onExamine={handleExamine}
      />
    );

    const examineBtn = screen.getByTestId('examine-btn-TATASTEEL');
    expect(examineBtn).toBeDefined();
    expect(examineBtn.textContent).toBe('EXAMINE');

    fireEvent.click(examineBtn);
    expect(handleExamine).toHaveBeenCalledWith('TATASTEEL');
    expect(handleSelect).not.toHaveBeenCalled();
  });

  it('renders Examine with AI button in opportunity drawer and triggers callback', () => {
    const handleExamine = vi.fn();
    const handleClose = vi.fn();

    render(
      <IntradayOpportunityDetailDrawer
        opportunity={mockOpportunity}
        onClose={handleClose}
        onExamine={handleExamine}
      />
    );

    const drawerAiBtn = screen.getByTestId('drawer-examine-ai-btn');
    expect(drawerAiBtn).toBeDefined();
    expect(drawerAiBtn.textContent).toContain('Examine with Deep AI Research (1 Call)');

    fireEvent.click(drawerAiBtn);
    expect(handleExamine).toHaveBeenCalledWith('TATASTEEL');
  });

  it('renders IntradayResearchModal with structured findings, basis, delta, and zero-call verification', async () => {
    const { apiClient } = await import('@/lib/api/client');
    (apiClient as any).mockImplementation((url: string) => {
      if (url.includes('/delta/')) {
        return Promise.resolve(mockExamineResponse.delta);
      }
      return Promise.resolve(mockExamineResponse);
    });

    render(
      <QueryClientProvider client={queryClient}>
        <IntradayResearchModal
          isOpen={true}
          onClose={vi.fn()}
          symbol="TATASTEEL"
          mode="INTRADAY"
        />
      </QueryClientProvider>
    );

    // Await response render
    await waitFor(() => {
      expect(screen.getByText(/Tata Steel demonstrates exceptional relative strength/i)).toBeDefined();
    });

    // Verify basis and delta cards
    expect(screen.getByText(/Research Basis \(Snapshot\)/i)).toBeDefined();
    expect(screen.getByText(/Changes Since Analysis \(Delta\)/i)).toBeDefined();
    expect(screen.getByText(/Cached \(0 AI Calls\)/i)).toBeDefined();

    // Verify empirical facts and analyst reasoning
    expect(screen.getByText(/Opportunity score is 84.0 with confidence 0.89./i)).toBeDefined();
    expect(screen.getByText(/Institutional flow into metals protects the asset/i)).toBeDefined();

    // Verify Refresh Research button exists
    const refreshBtn = screen.getByText(/Refresh Research \(1 AI Call\)/i);
    expect(refreshBtn).toBeDefined();
  });

  it('triggers explicit refresh when Refresh Research is clicked', async () => {
    const { apiClient } = await import('@/lib/api/client');
    (apiClient as any).mockImplementation((url: string) => {
      if (url.includes('/delta/')) {
        return Promise.resolve(mockExamineResponse.delta);
      }
      if (url.includes('/refresh/')) {
        return Promise.resolve({
          ...mockExamineResponse,
          reused: false,
          llm_calls_made: 1,
          research: {
            ...mockExamineResponse.research,
            output: {
              ...mockExamineResponse.research.output,
              summary: 'Refreshed research report with newly verified catalyst.'
            }
          }
        });
      }
      return Promise.resolve(mockExamineResponse);
    });

    render(
      <QueryClientProvider client={queryClient}>
        <IntradayResearchModal
          isOpen={true}
          onClose={vi.fn()}
          symbol="TATASTEEL"
          mode="INTRADAY"
        />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Tata Steel demonstrates exceptional relative strength/i)).toBeDefined();
    });

    const refreshBtn = screen.getByText(/Refresh Research \(1 AI Call\)/i);
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(screen.getByText(/Refreshed research report with newly verified catalyst./i)).toBeDefined();
    });
  });
});
