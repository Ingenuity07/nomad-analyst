import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';

import { useMarketOverview } from '@/hooks/useMarketOverview';
import { useMarketIndices } from '@/hooks/useMarketIndices';
import { useMarketBreadth } from '@/hooks/useMarketBreadth';
import { useMarketSectors } from '@/hooks/useMarketSectors';
import { useMarketGlobal } from '@/hooks/useMarketGlobal';

import { BenchmarkRegimeBar } from '@/features/marketIntelligence/components/BenchmarkRegimeBar';
import { MarketBreadthCard } from '@/features/marketIntelligence/components/MarketBreadthCard';
import { SectorMomentumLeaderboard } from '@/features/marketIntelligence/components/SectorMomentumLeaderboard';
import { SelectedSectorDetail } from '@/features/marketIntelligence/components/SelectedSectorDetail';
import { GlobalCuesSensitivities } from '@/features/marketIntelligence/components/GlobalCuesSensitivities';
import { ThemeRoadmapCard } from '@/features/marketIntelligence/components/ThemeRoadmapCard';

export const MarketIntelligencePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSector = searchParams.get('sector') || 'Technology';
  const [selectedSector, setSelectedSector] = useState<string>(initialSector);

  const { data: overview, isLoading: isOverviewLoading } = useMarketOverview();
  const { data: indicesData, isLoading: isIndicesLoading } = useMarketIndices();
  const { data: breadthData, isLoading: isBreadthLoading } = useMarketBreadth();
  const { data: sectorsData, isLoading: isSectorsLoading, error: sectorsError, refetch: refetchSectors } = useMarketSectors();
  const { data: globalData } = useMarketGlobal();

  const handleSelectSector = (sec: string) => {
    setSelectedSector(sec);
    setSearchParams({ sector: sec });
  };

  const sectors = sectorsData?.sector_rankings || overview?.sector_rankings || [];
  const indices = indicesData?.indices || [];
  const breadth = breadthData?.breadth || overview?.breadth;
  const cues = globalData?.global_cues || overview?.cross_market_cues;

  // If initial sector not selected and sectors exist, default to the top sector
  const activeSector = selectedSector || (sectors.length > 0 ? sectors[0].sector : 'Technology');

  return (
    <PageContainer
      title="Market Intelligence & Sector Analysis"
      subtitle="Institutional market regime classification, participation breadth, sector momentum leaderboards, and constituent intelligence."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* 1. Benchmark Indices & Market Regime Status */}
        <section aria-label="Benchmark Indices & Market Regime">
          {isIndicesLoading || isOverviewLoading ? (
            <Skeleton height="110px" />
          ) : (
            <BenchmarkRegimeBar
              indices={indices}
              session={overview?.market_session}
              freshness={overview?.data_freshness}
            />
          )}
        </section>

        {/* 2. Split Row: Market Breadth & Global Cues */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: 'var(--space-6)' }}>
          <section aria-label="Market Breadth">
            {isBreadthLoading ? (
              <Skeleton height="200px" />
            ) : (
              <MarketBreadthCard breadth={breadth} universe={overview?.universe || 'NIFTY50'} />
            )}
          </section>

          <section aria-label="Global Cues & Macro">
            <GlobalCuesSensitivities cues={cues} macroEvents={overview?.recent_news} />
          </section>
        </div>

        {/* 3. Sector Momentum Leaderboard */}
        <section aria-label="Sector Momentum Leaderboard">
          {isSectorsLoading ? (
            <Skeleton height="320px" />
          ) : sectorsError ? (
            <ErrorState
              title="Sector Rankings Unavailable"
              message={sectorsError.message || 'Failed to load sector momentum leaderboards.'}
              onRetry={() => refetchSectors()}
            />
          ) : (
            <SectorMomentumLeaderboard
              sectors={sectors}
              selectedSector={activeSector}
              onSelectSector={handleSelectSector}
            />
          )}
        </section>

        {/* 4. Interactive Selected Sector Drill-Down */}
        <section aria-label="Selected Sector Detail">
          <SelectedSectorDetail sector={activeSector} />
        </section>

        {/* 5. Theme Roadmap & Capabilities Note */}
        <section aria-label="Theme Capabilities Boundary">
          <ThemeRoadmapCard />
        </section>
      </div>
    </PageContainer>
  );
};
