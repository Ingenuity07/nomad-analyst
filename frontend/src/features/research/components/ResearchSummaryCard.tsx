import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';

export interface ResearchSummaryCardProps {
  summary: string;
  marketSnapshot?: Record<string, any>;
}

export const ResearchSummaryCard: React.FC<ResearchSummaryCardProps> = ({
  summary,
  marketSnapshot = {},
}) => {
  const price = marketSnapshot.price || marketSnapshot.close || marketSnapshot.current_price;
  const pe = marketSnapshot.pe || marketSnapshot.pe_ratio;
  const sector = marketSnapshot.sector || marketSnapshot.industry;
  const capTier = marketSnapshot.market_cap_tier || marketSnapshot.market_cap;

  const hasSnapshotMetrics = price !== undefined || pe !== undefined || sector !== undefined || capTier !== undefined;

  return (
    <Card header="Executive Research Synthesis" data-testid="research-summary-card">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Synthesis Prose */}
        <div
          data-testid="research-summary-text"
          style={{
            fontSize: 'var(--text-sm)',
            lineHeight: 1.7,
            color: 'var(--text-primary)',
            whiteSpace: 'pre-wrap',
            fontFamily: 'inherit',
          }}
        >
          {summary || 'No executive summary provided for this research task.'}
        </div>

        {/* Snapshot Metrics Strip if present */}
        {hasSnapshotMetrics && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: 'var(--space-3)',
              backgroundColor: 'var(--bg-surface-sunken)',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {price !== undefined && (
              <Metric
                label="Asset Price"
                value={`₹${typeof price === 'number' ? price.toFixed(2) : price}`}
              />
            )}
            {pe !== undefined && (
              <Metric
                label="P/E Ratio"
                value={`${typeof pe === 'number' ? pe.toFixed(1) : pe}x`}
              />
            )}
            {sector && (
              <Metric
                label="Sector"
                value={String(sector)}
              />
            )}
            {capTier && (
              <Metric
                label="Market Cap"
                value={String(capTier)}
              />
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
