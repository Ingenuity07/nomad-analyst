import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';

export interface WatchlistSummaryStripProps {
  totalCount: number;
  advancingCount: number;
  decliningCount: number;
  activeSignalsCount: number;
  avgOpportunityScore: number | null;
}

export const WatchlistSummaryStrip: React.FC<WatchlistSummaryStripProps> = ({
  totalCount,
  advancingCount,
  decliningCount,
  activeSignalsCount,
  avgOpportunityScore,
}) => {
  return (
    <Card data-testid="watchlist-summary-strip">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 'var(--space-3)',
        }}
      >
        <Metric
          label="Tracked Stocks"
          value={String(totalCount)}
          subtext="In active watchlist"
        />
        <Metric
          label="Day Breadth"
          value={`${advancingCount} ↑ / ${decliningCount} ↓`}
          subtext="Advancing / Declining"
        />
        <Metric
          label="Active Signals"
          value={String(activeSignalsCount)}
          subtext="Actionable setups"
        />
        <Metric
          label="Avg Opp Score"
          value={avgOpportunityScore !== null ? `${avgOpportunityScore.toFixed(0)}/100` : '—'}
          subtext="Basket quality"
        />
      </div>
    </Card>
  );
};
