import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { DataStatus } from '@/components/ui/DataStatus';
import { useIntradayOverview } from '@/hooks/useIntradayOverview';

export const IntradayPageShell: React.FC = () => {
  const { data, isLoading } = useIntradayOverview();

  return (
    <PageContainer
      title="Intraday Scanner & Signals"
      subtitle="Multi-timeframe intraday setups (5m, 15m, 1h) with strict session window gates"
      action={<DataStatus status={isLoading ? 'LOADING' : 'LIVE'} source="Yahoo Intraday" />}
    >
      <Card header="Intraday Workspace Shell (FE-4 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Live scanner for VWAP pullbacks, Opening Range Breakouts (ORB), and multi-timeframe momentum with strict data quality verification.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          Session: {data?.market_session.window || 'CONNECTING'} • Active Intraday Signals: {data?.summary.active_signals ?? '—'}
        </div>
      </Card>
    </PageContainer>
  );
};
