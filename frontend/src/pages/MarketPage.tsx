import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { DataStatus } from '@/components/ui/DataStatus';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';

import { useMarketOverview } from '@/hooks/useMarketOverview';
import { useMarketIndices } from '@/hooks/useMarketIndices';
import { IndexStrip } from '@/features/market/components/IndexStrip';
import { MarketRegimeCard } from '@/features/market/components/MarketRegimeCard';
import { MarketBreadthBarometer } from '@/features/market/components/MarketBreadthBarometer';
import { SectorRotationMatrix } from '@/features/market/components/SectorRotationMatrix';
import { GlobalCuesPanel } from '@/features/market/components/GlobalCuesPanel';
import { MarketNewsFeed } from '@/features/market/components/MarketNewsFeed';

export const MarketPage: React.FC = () => {
  const [universe, setUniverse] = useState<string>('NIFTY50');

  // Primary market context query
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useMarketOverview(universe);

  // Dedicated indices query for highest freshness
  const { data: indicesData, isLoading: isIndicesLoading } = useMarketIndices();

  const handleRefresh = () => {
    refetchOverview();
  };

  // Combine indices from dedicated endpoint or overview payload
  const activeIndices = indicesData?.indices?.length ? indicesData.indices : overviewData?.indices || [];

  return (
    <PageContainer
      title="Market Overview & Context"
      subtitle="NSE Indian benchmark indices, market breadth, regime intelligence, and sector leadership"
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <Select
            value={universe}
            onChange={(e) => setUniverse(e.target.value)}
            options={[
              { value: 'NIFTY50', label: 'NIFTY 50 Universe' },
              { value: 'NIFTYNEXT50', label: 'NIFTY Next 50' },
              { value: 'NIFTYMIDCAP50', label: 'NIFTY MidCap 50' },
            ]}
          />
          <DataStatus
            status={isOverviewLoading ? 'LOADING' : (overviewData?.data_freshness?.status as any) || 'LIVE'}
            source="NSE / yfinance"
            lastUpdated={overviewData?.as_of ? new Date(overviewData.as_of).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST' : undefined}
          />
          <Button variant="outline" size="sm" onClick={handleRefresh} isLoading={isOverviewLoading}>
            ↻ Refresh
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* 1. Top Index Snapshot Strip */}
        <section aria-label="Index Quotes">
          <IndexStrip indices={activeIndices} isLoading={isIndicesLoading && isOverviewLoading} />
        </section>

        {/* 2. Error Fallback (if entire overview fails) */}
        {overviewError && (
          <ErrorState
            title="Failed to Load Complete Market Context"
            message={overviewError.message || 'Unable to establish connection with market intelligence service.'}
            onRetry={handleRefresh}
          />
        )}

        {/* 3. Market Regime & Breadth Dual Panel */}
        <section aria-label="Market Regime and Breadth" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-6)' }}>
          {isOverviewLoading ? (
            <>
              <Skeleton height="220px" borderRadius="var(--radius-md)" />
              <Skeleton height="220px" borderRadius="var(--radius-md)" />
            </>
          ) : (
            <>
              <MarketRegimeCard
                regimeData={overviewData?.index_regimes}
                breadthRegime={overviewData?.breadth?.breadth_regime}
                asOf={overviewData?.as_of}
              />
              <MarketBreadthBarometer breadth={overviewData?.breadth} />
            </>
          )}
        </section>

        {/* 4. Sector Rotation & Relative Strength Table */}
        <section aria-label="Sector Rotation Matrix">
          {isOverviewLoading ? (
            <Skeleton height="280px" borderRadius="var(--radius-md)" />
          ) : (
            <SectorRotationMatrix
              sectors={overviewData?.sector_rankings}
              isLoading={isOverviewLoading}
            />
          )}
        </section>

        {/* 5. Global Cues & Recent Market News Grid */}
        <section aria-label="Global Context and News" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-6)' }}>
          {isOverviewLoading ? (
            <>
              <Skeleton height="240px" borderRadius="var(--radius-md)" />
              <Skeleton height="240px" borderRadius="var(--radius-md)" />
            </>
          ) : (
            <>
              <GlobalCuesPanel
                cues={overviewData?.cross_market_cues || overviewData?.global_cues}
              />
              <MarketNewsFeed news={overviewData?.recent_news} />
            </>
          )}
        </section>
      </div>
    </PageContainer>
  );
};
export default MarketPage;
