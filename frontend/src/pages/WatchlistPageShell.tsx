import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';

export const WatchlistPageShell: React.FC = () => {
  return (
    <PageContainer
      title="Watchlists & Custom Universes"
      subtitle="Organize portfolio baskets, monitor real-time deltas, and export research feeds"
    >
      <Card header="Watchlist Workspace Shell (FE-9 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Curate custom baskets across NIFTY 50, NIFTY Next 50, MidCap, and custom thematic sectors.
        </p>
      </Card>
    </PageContainer>
  );
};
