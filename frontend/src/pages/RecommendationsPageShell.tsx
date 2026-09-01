import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { useRecommendations } from '@/hooks/useRecommendations';

export const RecommendationsPageShell: React.FC = () => {
  const { data, isLoading } = useRecommendations({ horizon: 'DELIVERY_SWING' });

  return (
    <PageContainer
      title="Recommendations & Outcome Tracking"
      subtitle="Point-in-time trade signals with immutable entry, stop loss, targets, and verified R-multiples"
    >
      <Card header="Recommendations Workspace Shell (FE-6 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Track active signals, win rate, average R-multiple, and real post-trade outcome lifecycle metrics.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          API Endpoint: GET /api/v1/recommendations/ • Active Signals: {isLoading ? 'Loading...' : `${data?.count || 0} registered`}
        </div>
      </Card>
    </PageContainer>
  );
};
