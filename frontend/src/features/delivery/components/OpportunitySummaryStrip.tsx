import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { StockOpportunitySnapshot } from '@/lib/api/types';

export interface OpportunitySummaryStripProps {
  candidates?: StockOpportunitySnapshot[];
  totalCount?: number;
  marketRegime?: string;
  horizon?: string;
}

export const OpportunitySummaryStrip: React.FC<OpportunitySummaryStripProps> = ({
  candidates = [],
  totalCount = 0,
  marketRegime = 'BULLISH',
  horizon = 'DELIVERY_SWING',
}) => {
  // Compute summary stats
  const topCandidate = candidates.length > 0 ? candidates[0] : null;
  const topScore = topCandidate
    ? typeof topCandidate.final_opportunity_score === 'number'
      ? topCandidate.final_opportunity_score
      : parseFloat(topCandidate.final_opportunity_score) || 0
    : null;

  // Find dominant sector
  const sectorCounts: Record<string, number> = {};
  candidates.forEach((c) => {
    if (c.sector) sectorCounts[c.sector] = (sectorCounts[c.sector] || 0) + 1;
  });
  const dominantSector = Object.entries(sectorCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || '—';

  return (
    <Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-6)' }}>
        <Metric
          label="Ranked Candidates"
          value={totalCount}
          subtext={`In ${horizon.replace('_', ' ').toLowerCase()}`}
        />
        <Metric
          label="Highest Score"
          value={topScore !== null ? `${topScore.toFixed(1)}/100` : '—'}
          subtext={topCandidate ? `${topCandidate.symbol} (${topCandidate.sector})` : 'No candidates'}
        />
        <Metric
          label="Concentrated Sector"
          value={dominantSector}
          subtext="Highest candidate density"
        />
        <Metric
          label="Macro Regime Gate"
          value={marketRegime.toUpperCase()}
          subtext="Benchmark alignment"
        />
      </div>
    </Card>
  );
};
