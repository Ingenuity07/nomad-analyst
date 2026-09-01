import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { useBacktests } from '@/hooks/useBacktests';

export const BacktestsPageShell: React.FC = () => {
  const { data, isLoading } = useBacktests();

  return (
    <PageContainer
      title="Quantitative Backtesting Lab"
      subtitle="Point-in-time walk-forward simulation with realistic STT, brokerage, and slippage cost models"
    >
      <Card header="Backtesting Lab Shell (FE-7 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Configure historical simulation windows, evaluate strategy version performance, and analyze trade execution distributions.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          Historical Runs Recorded: {isLoading ? 'Loading...' : `${data?.count || 0} runs`} • Endpoint: /api/v1/backtests/
        </div>
      </Card>
    </PageContainer>
  );
};
