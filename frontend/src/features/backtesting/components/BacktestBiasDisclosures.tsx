import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export interface BacktestBiasDisclosuresProps {
  dataQualityWarnings?: string[];
  statisticalWarnings?: string[];
}

export const BacktestBiasDisclosures: React.FC<BacktestBiasDisclosuresProps> = ({
  dataQualityWarnings = [],
  statisticalWarnings = [],
}) => {
  const allWarnings = [...(statisticalWarnings || []), ...(dataQualityWarnings || [])];

  if (allWarnings.length === 0) return null;

  return (
    <Card
      header="Methodological Assumptions & Bias Disclosures"
      action={<Badge variant="warning" size="sm">Point-In-Time Limitations</Badge>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          Historical backtests simulate strategy behavior using strict point-in-time price bars. The following structural data limitations should be considered when interpreting results:
        </div>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)', margin: 0, paddingLeft: 'var(--space-4)' }}>
          {allWarnings.map((w, idx) => (
            <li key={idx} style={{ color: 'var(--warning-text, var(--text-secondary))' }}>
              {w}
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
};
