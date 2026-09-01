import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Tabs } from '@/components/ui/Tabs';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';

import { useRecommendations } from '@/hooks/useRecommendations';
import { useOutcomes } from '@/hooks/useOutcomes';
import { StrategyPerformanceStrip } from '@/features/recommendations/components/StrategyPerformanceStrip';
import { RecommendationFilterToolbar } from '@/features/recommendations/components/RecommendationFilterToolbar';
import { ActiveSignalsTable } from '@/features/recommendations/components/ActiveSignalsTable';
import { HistoricalOutcomesTable } from '@/features/recommendations/components/HistoricalOutcomesTable';
import { RecommendationDetailDrawer } from '@/features/recommendations/components/RecommendationDetailDrawer';
import { StockRecommendation, RecommendationOutcome } from '@/lib/api/types';

export const RecommendationsPage: React.FC = () => {
  // Strategy performance selector
  const [selectedStrategy, setSelectedStrategy] = useState<string>('DELIVERY_SWING');

  // Filter state
  const [horizon, setHorizon] = useState<string>('');
  const [signal, setSignal] = useState<string>('');
  const [setupType, setSetupType] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [confidence, setConfidence] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Active view tab
  const [activeTab, setActiveTab] = useState<string>('active');
  const [page, setPage] = useState<number>(1);

  // Selected item for drawer
  const [selectedRec, setSelectedRec] = useState<StockRecommendation | null>(null);
  const [selectedOutcome, setSelectedOutcome] = useState<RecommendationOutcome | null>(null);

  const resetFilters = () => {
    setHorizon('');
    setSignal('');
    setSetupType('');
    setStatus('');
    setConfidence('');
    setSearchQuery('');
    setPage(1);
  };

  // Queries
  const {
    data: recsData,
    isLoading: isRecsLoading,
    error: recsError,
    refetch: refetchRecs,
  } = useRecommendations({
    horizon: horizon || undefined,
    signal: signal || undefined,
    setup_type: setupType || undefined,
    status: status || undefined,
    confidence: confidence || undefined,
    page,
  });

  const {
    data: outcomesData,
    isLoading: isOutcomesLoading,
    error: outcomesError,
    refetch: refetchOutcomes,
  } = useOutcomes({
    signal: signal || undefined,
    setup_type: setupType || undefined,
    page,
  });

  // Client-side symbol search filter if provided
  const filteredActiveRecs = (recsData?.results || []).filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toUpperCase();
    return r.symbol.toUpperCase().includes(q) || r.company_name.toUpperCase().includes(q);
  });

  const filteredOutcomes = (outcomesData?.results || []).filter((o) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toUpperCase();
    const sym = o.symbol || '';
    return sym.toUpperCase().includes(q);
  });

  const tabs = [
    { key: 'active', label: 'Active Signals & Recommendations', count: recsData?.count },
    { key: 'historical', label: 'Historical Evaluated Outcomes', count: outcomesData?.count },
  ];

  return (
    <PageContainer
      title="Trade Recommendations & Outcome Attribution"
      subtitle="Audited rule-based signals, execution parameters, and statistical track record."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* 1. Strategy Performance Metric Strip */}
        <section aria-label="Strategy Performance Summary">
          <StrategyPerformanceStrip
            strategy={selectedStrategy}
            onStrategyChange={setSelectedStrategy}
          />
        </section>

        {/* 2. Filter Toolbar */}
        <section aria-label="Recommendation Filters">
          <RecommendationFilterToolbar
            horizon={horizon}
            onHorizonChange={(val) => { setHorizon(val); setPage(1); }}
            signal={signal}
            onSignalChange={(val) => { setSignal(val); setPage(1); }}
            setupType={setupType}
            onSetupTypeChange={(val) => { setSetupType(val); setPage(1); }}
            status={status}
            onStatusChange={(val) => { setStatus(val); setPage(1); }}
            confidence={confidence}
            onConfidenceChange={(val) => { setConfidence(val); setPage(1); }}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onReset={resetFilters}
          />
        </section>

        {/* 3. Detail Drawer (when item selected) */}
        {(selectedRec || selectedOutcome) && (
          <section aria-label="Recommendation Detail">
            <RecommendationDetailDrawer
              recommendation={selectedRec}
              attachedOutcome={selectedOutcome}
              onClose={() => { setSelectedRec(null); setSelectedOutcome(null); }}
            />
          </section>
        )}

        {/* 4. Tab Navigation */}
        <section aria-label="Workspace Views">
          <Tabs
            tabs={tabs}
            activeKey={activeTab}
            onChange={(k) => { setActiveTab(k); setPage(1); }}
          />
        </section>

        {/* 5. Main Tab Data Tables */}
        <section aria-label="Signals Table">
          {activeTab === 'active' && (
            <div>
              {recsError ? (
                <ErrorState
                  title="Unable to load recommendations"
                  message={recsError.message}
                  onRetry={() => refetchRecs()}
                />
              ) : isRecsLoading ? (
                <Skeleton height="300px" />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <ActiveSignalsTable
                    recommendations={filteredActiveRecs}
                    selectedId={selectedRec?.id}
                    onSelect={(rec) => { setSelectedRec(rec); setSelectedOutcome(null); }}
                  />

                  {/* Pagination */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) 0' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                      Total {recsData?.count || 0} recommendations
                    </span>
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!recsData?.previous || page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                      >
                        ← Previous
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!recsData?.next}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        Next →
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'historical' && (
            <div>
              {outcomesError ? (
                <ErrorState
                  title="Unable to load historical outcomes"
                  message={outcomesError.message}
                  onRetry={() => refetchOutcomes()}
                />
              ) : isOutcomesLoading ? (
                <Skeleton height="300px" />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <HistoricalOutcomesTable
                    outcomes={filteredOutcomes}
                    selectedId={selectedOutcome?.id}
                    onSelect={(out) => { setSelectedOutcome(out); setSelectedRec(null); }}
                  />

                  {/* Pagination */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) 0' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                      Total {outcomesData?.count || 0} evaluated outcomes
                    </span>
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!outcomesData?.previous || page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                      >
                        ← Previous
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!outcomesData?.next}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        Next →
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  );
};
export default RecommendationsPage;
