import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { DataStatus } from '@/components/ui/DataStatus';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';

import { useOpportunities } from '@/hooks/useOpportunities';
import { useRecommendations } from '@/hooks/useRecommendations';
import { useMarketOverview } from '@/hooks/useMarketOverview';
import { StockOpportunitySnapshot } from '@/lib/api/types';

import { DeliveryFilterToolbar } from '@/features/delivery/components/DeliveryFilterToolbar';
import { OpportunitySummaryStrip } from '@/features/delivery/components/OpportunitySummaryStrip';
import { OpportunityCandidateTable } from '@/features/delivery/components/OpportunityCandidateTable';
import { OpportunityQuickViewDrawer } from '@/features/delivery/components/OpportunityQuickViewDrawer';

export const DeliveryPage: React.FC = () => {
  const [universe, setUniverse] = useState<string>('NIFTY50');
  const [horizon, setHorizon] = useState<string>('DELIVERY_SWING');
  const [sector, setSector] = useState<string>('');
  const [minScore, setMinScore] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [selectedCandidate, setSelectedCandidate] = useState<StockOpportunitySnapshot | null>(null);

  // 1. Fetch ranked opportunities
  const {
    data: oppData,
    isLoading: isOppLoading,
    error: oppError,
    refetch: refetchOpp,
  } = useOpportunities({
    universe,
    horizon,
    sector: sector || undefined,
    min_score: minScore > 0 ? minScore : undefined,
    page,
  });

  // 2. Fetch market regime context
  const { data: marketOverview } = useMarketOverview(universe);

  // 3. Fetch active recommendations for linkage
  const { data: recData } = useRecommendations({ horizon, status: 'ACTIVE' });

  const handleResetFilters = () => {
    setUniverse('NIFTY50');
    setHorizon('DELIVERY_SWING');
    setSector('');
    setMinScore(0);
    setSearchQuery('');
    setPage(1);
    setSelectedCandidate(null);
  };

  // Filter candidates locally by search query if present
  const allResults = oppData?.results || [];
  const filteredCandidates = searchQuery
    ? allResults.filter(
        (c) =>
          c.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
          c.company_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : allResults;

  // Extract distinct sectors for filter dropdown
  const availableSectors = Array.from(
    new Set(allResults.map((c) => c.sector).filter(Boolean))
  );

  // Find linked recommendation for selected candidate
  const linkedRec = selectedCandidate
    ? recData?.results?.find((r) => r.symbol === selectedCandidate.symbol)
    : null;

  const totalPages = oppData ? Math.ceil(oppData.count / 20) : 1;

  return (
    <PageContainer
      title="Delivery Opportunities & Candidate Ranking"
      subtitle="Multi-factor cross-sectional scoring (Technicals, Fundamentals, Sector Leadership) for positional and swing trades"
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <DataStatus
            status={isOppLoading ? 'LOADING' : 'LIVE'}
            source="Module 7 Engine"
            lastUpdated={filteredCandidates[0]?.as_of ? new Date(filteredCandidates[0].as_of).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST' : undefined}
          />
          <Button variant="outline" size="sm" onClick={() => refetchOpp()} isLoading={isOppLoading}>
            ↻ Recalculate
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* 1. Filter Toolbar */}
        <section aria-label="Opportunity Filters">
          <DeliveryFilterToolbar
            universe={universe}
            onUniverseChange={(u) => { setUniverse(u); setPage(1); }}
            horizon={horizon}
            onHorizonChange={(h) => { setHorizon(h); setPage(1); }}
            sector={sector}
            onSectorChange={(s) => { setSector(s); setPage(1); }}
            minScore={minScore}
            onMinScoreChange={(ms) => { setMinScore(ms); setPage(1); }}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            availableSectors={availableSectors}
            onReset={handleResetFilters}
          />
        </section>

        {/* 2. Top Summary Metric Strip */}
        <section aria-label="Opportunity Summary">
          <OpportunitySummaryStrip
            candidates={filteredCandidates}
            totalCount={oppData?.count || filteredCandidates.length}
            marketRegime={marketOverview?.breadth?.breadth_regime || 'STRONG'}
            horizon={horizon}
          />
        </section>

        {/* 3. Error State Fallback */}
        {oppError && (
          <ErrorState
            title="Failed to Load Opportunity Candidates"
            message={oppError.message || 'Unable to communicate with discovery scoring engine.'}
            onRetry={() => refetchOpp()}
          />
        )}

        {/* 4. Main Ranked Candidate Table & Quick View Grid */}
        <section aria-label="Candidate Table and Quick View">
          <div style={{ display: 'grid', gridTemplateColumns: selectedCandidate ? '1fr 380px' : '1fr', gap: 'var(--space-6)', alignItems: 'start' }}>
            {/* Table Container */}
            <Card header={`Ranked Opportunities (${filteredCandidates.length} Candidates Displayed)`}>
              {isOppLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                </div>
              ) : filteredCandidates.length === 0 ? (
                <EmptyState
                  icon="🎯"
                  title="No Candidates Found"
                  description="No stock candidates matched the selected filters and score thresholds."
                  action={
                    <Button variant="secondary" size="sm" onClick={handleResetFilters}>
                      Reset All Filters
                    </Button>
                  }
                />
              ) : (
                <OpportunityCandidateTable
                  candidates={filteredCandidates}
                  selectedId={selectedCandidate?.id}
                  onSelectCandidate={(item) => setSelectedCandidate(item)}
                  isLoading={isOppLoading}
                />
              )}

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-3) var(--space-4)',
                    borderTop: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface-subtle)',
                  }}
                >
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(p - 1, 1))}
                  >
                    ← Previous
                  </Button>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next →
                  </Button>
                </div>
              )}
            </Card>

            {/* Side Drawer Quick View */}
            {selectedCandidate && (
              <OpportunityQuickViewDrawer
                candidate={selectedCandidate}
                recommendation={linkedRec}
                onClose={() => setSelectedCandidate(null)}
              />
            )}
          </div>
        </section>
      </div>
    </PageContainer>
  );
};
export default DeliveryPage;
