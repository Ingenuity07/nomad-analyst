import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export const PortfolioBoundaryCard: React.FC = () => {
  return (
    <Card header="Personal Decisions & Broker Portfolio Boundary" data-testid="portfolio-boundary-card">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Badge variant="neutral" size="sm">LOCAL BROWSER PERSISTENCE</Badge>
          <span>Watchlists and decision states (WATCHING / CONSIDERING / RESEARCHING / HOLDING) are stored locally in your browser.</span>
        </div>
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>
          Live multi-broker order execution, trade transaction journaling, and automated P&L portfolio accounting remain planned backend infrastructure (FUTURE).
        </p>
      </div>
    </Card>
  );
};
