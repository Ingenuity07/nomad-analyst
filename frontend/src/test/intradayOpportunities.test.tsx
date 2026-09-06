import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { IntradayOpportunityTable } from '@/features/intraday/components/IntradayOpportunityTable';
import { IntradayOpportunityDetailDrawer } from '@/features/intraday/components/IntradayOpportunityDetailDrawer';
import { IntradayOpportunityItem } from '@/lib/api/types';

const mockOpportunity: IntradayOpportunityItem = {
  symbol: 'TATASTEEL',
  company_name: 'Tata Steel Limited',
  timestamp: '2026-09-05T10:30:00+05:30',
  opportunity_type: 'RELATIVE_STRENGTH',
  state: 'CONFIRMED',
  score: 84.5,
  base_score: 84.5,
  confidence: 0.88,
  bias: 'BULLISH',
  score_change: 2.5,
  component_scores: {
    momentum_score: 85.0,
    relative_strength_score: 92.0,
    volume_score: 80.0,
    vwap_score: 95.0,
    market_alignment_score: 80.0,
    sector_alignment_score: 85.0,
    orb_score: 60.0,
    data_quality_score: 100.0,
  },
  penalties: [],
  supporting_factors: [
    'Trading +0.75% above session VWAP',
    'Outperforming NIFTY 50 by +1.40%',
    'Confirmed volume participation (RVOL 1.4x)',
    'Positive momentum across 5m (+0.40%) and 15m (+0.95%)',
  ],
  contradicting_factors: [],
  warnings: ['Approaching day resistance'],
  invalidation_condition: 'Loss of session VWAP on high volume or fall below 15m ORB range',
  metrics: {
    last_price: 154.20,
    change_pct: 2.10,
    vwap: 153.05,
    vwap_diff_pct: 0.75,
    volume: 12500000,
    relative_volume: 1.4,
    momentum_5m: 0.40,
    momentum_15m: 0.95,
    relative_strength_vs_market: 1.40,
    relative_strength_vs_sector: 0.85,
    opening_range_state: 'INSIDE_ORB',
    volume_confirmation: 'CONFIRMED_UP',
  },
  rank: 1,
  sector: {
    name: 'Metals',
    rank: 1,
    return_pct: 1.25,
  },
  market_alignment: 'STRONGLY_ALIGNED',
  sector_alignment: 'STRONGLY_ALIGNED',
  data_quality: 'HIGH',
  freshness: 'FRESH',
};

describe('Phase 17D — Intraday Opportunity UI Components', () => {
  it('renders opportunity table with scores, badges, and zero buy/sell execution labels', () => {
    const handleSelect = vi.fn();
    const { container } = render(
      <IntradayOpportunityTable
        opportunities={[mockOpportunity]}
        selectedSymbol={null}
        onSelectOpportunity={handleSelect}
      />
    );

    expect(screen.getByText('TATASTEEL')).toBeInTheDocument();
    expect(screen.getByText('REL STRENGTH')).toBeInTheDocument();
    expect(screen.getByText('CONFIRMED')).toBeInTheDocument();
    expect(screen.getByText('84.5')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByText('STRONGLY_ALIGNED')).toBeInTheDocument();

    // Verify STRICTLY zero BUY/SELL action instructions
    const text = container.textContent || '';
    expect(text).not.toMatch(/\bBUY NOW\b/i);
    expect(text).not.toMatch(/\bSELL NOW\b/i);
    expect(text).not.toMatch(/\bEXECUTE\b/i);
  });

  it('triggers selection callback when table row is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <IntradayOpportunityTable
        opportunities={[mockOpportunity]}
        selectedSymbol={null}
        onSelectOpportunity={handleSelect}
      />
    );

    fireEvent.click(screen.getByText('TATASTEEL'));
    expect(handleSelect).toHaveBeenCalledWith(mockOpportunity);
  });

  it('renders detail drawer with dimensional score decomposition and structured evidence', () => {
    const handleClose = vi.fn();
    render(
      <IntradayOpportunityDetailDrawer
        opportunity={mockOpportunity}
        onClose={handleClose}
      />
    );

    expect(screen.getByText('Dimensional Score Decomposition')).toBeInTheDocument();
    expect(screen.getByText(/Momentum \(20%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Relative Strength \(20%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Volume Confirmation \(15%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/VWAP Positioning \(10%\)/i)).toBeInTheDocument();

    expect(screen.getByText('✓ Supporting Factors')).toBeInTheDocument();
    expect(screen.getByText('Trading +0.75% above session VWAP')).toBeInTheDocument();
    expect(screen.getByText('Outperforming NIFTY 50 by +1.40%')).toBeInTheDocument();

    expect(screen.getByText('⚠ Warnings & Contextual Risks')).toBeInTheDocument();
    expect(screen.getByText('Approaching day resistance')).toBeInTheDocument();

    expect(screen.getByText('Invalidation Threshold')).toBeInTheDocument();
    expect(screen.getByText(mockOpportunity.invalidation_condition)).toBeInTheDocument();

    // Close button
    fireEvent.click(screen.getByText('✕'));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('displays penalties applied when present in opportunity item', () => {
    const oppWithPenalties: IntradayOpportunityItem = {
      ...mockOpportunity,
      score: 64.5,
      penalties: [
        { reason: 'LOW_VOLUME_CONFIRMATION', points: 10.0 },
        { reason: 'SECTOR_RETURN_NEGATIVE', points: 15.0 },
      ],
    };

    render(
      <IntradayOpportunityDetailDrawer
        opportunity={oppWithPenalties}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Penalties Applied')).toBeInTheDocument();
    expect(screen.getByText('LOW_VOLUME_CONFIRMATION')).toBeInTheDocument();
    expect(screen.getByText('-10 pts')).toBeInTheDocument();
    expect(screen.getByText('-15 pts')).toBeInTheDocument();
  });
});
