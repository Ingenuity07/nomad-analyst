import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { DataStatus } from '@/components/ui/DataStatus';
import { useMarketOverview } from '@/hooks/useMarketOverview';

export const MarketPageShell: React.FC = () => {
  const { data, isLoading } = useMarketOverview('NIFTY50');

  return (
    <PageContainer
      title="Market Overview & Context"
      subtitle="Institutional NSE indices, market breadth, sector rankings, and regime intelligence"
      action={<DataStatus status={isLoading ? 'LOADING' : 'LIVE'} source="yfinance / NSE" />}
    >
      <Card header="Overview Workspace Shell (FE-2 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          This workspace will host the live Index Strip (NIFTY 50, SENSEX, BANK NIFTY), Advance/Decline Breadth Barometer, Sector Rotation Matrix, and Market Regime indicators.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          API Endpoint: GET /api/v1/market/overview/?universe=NIFTY50 • Status: {isLoading ? 'Fetching backend...' : `Connected (${data?.indices?.length || 0} indices)`}
        </div>
      </Card>
    </PageContainer>
  );
};
