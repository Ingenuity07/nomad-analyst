import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { useOpportunities } from '@/hooks/useOpportunities';

export const DeliveryPageShell: React.FC = () => {
  const { data, isLoading } = useOpportunities({ universe: 'NIFTY50', horizon: 'DELIVERY_SWING' });

  return (
    <PageContainer
      title="Opportunity Discovery (Delivery)"
      subtitle="Cross-sectional multi-factor scoring (Technicals, Fundamentals, Sector Strength)"
    >
      <Card header="Opportunities Workspace Shell (FE-3 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Scored candidate ranking engine combining 50/200 SMA momentum, ROE/debt fundamentals, and leading sector leadership.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          API Endpoint: GET /api/v1/opportunities/?universe=NIFTY50 • Scored Candidates: {isLoading ? 'Loading...' : `${data?.count || 0} found`}
        </div>
      </Card>
    </PageContainer>
  );
};
