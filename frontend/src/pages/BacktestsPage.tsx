import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Tabs } from '@/components/ui/Tabs';
import { ErrorState } from '@/components/ui/ErrorState';
import { Button } from '@/components/ui/Button';
import { useQueryClient } from '@tanstack/react-query';
import { useBacktests } from '@/hooks/useBacktests';
import { BacktestConfigForm } from '@/features/backtesting/components/BacktestConfigForm';
import { BacktestSummaryKPIs } from '@/features/backtesting/components/BacktestSummaryKPIs';
import { BacktestBiasDisclosures } from '@/features/backtesting/components/BacktestBiasDisclosures';
import { BacktestBreakdownTables } from '@/features/backtesting/components/BacktestBreakdownTables';
import { HistoricalBacktestsTable } from '@/features/backtesting/components/HistoricalBacktestsTable';
import { BacktestDetailDrawer } from '@/features/backtesting/components/BacktestDetailDrawer';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { BacktestRun, BacktestRunPayload } from '@/lib/api/types';

export const BacktestsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>('simulation');
  const [page, setPage] = useState<number>(1);
  const [activeRun, setActiveRun] = useState<BacktestRun | null>(null);
  const [selectedHistoricalRun, setSelectedHistoricalRun] = useState<BacktestRun | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Queries & Mutations
  const {
    data: historicalData,
    isLoading: isHistoryLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useBacktests(page);

  const handleRunBacktest = async (payload: BacktestRunPayload) => {
    setIsRunning(true);
    setSubmissionError(null);
    try {
      const res = await apiClient<BacktestRun>(ENDPOINTS.BACKTEST_RUN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setActiveRun(res);
      setSelectedHistoricalRun(null);
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
    } catch (err: any) {
      setSubmissionError(err?.message || 'Failed to complete backtest walk-forward simulation.');
    } finally {
      setIsRunning(false);
    }
  };

  const displayedRun = selectedHistoricalRun || activeRun;

  const tabs = [
    { key: 'simulation', label: 'Strategy Simulation & Results' },
    { key: 'history', label: 'Historical Backtest Runs', count: historicalData?.count },
  ];

  return (
    <PageContainer
      title="Backtesting Laboratory"
      subtitle="Deterministic walk-forward strategy simulation with explicit cost modeling and point-in-time enforcement."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* Navigation Tabs */}
        <section aria-label="Backtest Navigation">
          <Tabs
            tabs={tabs}
            activeKey={activeTab}
            onChange={(k) => { setActiveTab(k); }}
          />
        </section>

        {activeTab === 'simulation' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
            {/* 1. Configuration Form */}
            <section aria-label="Simulation Configuration">
              <BacktestConfigForm
                onSubmit={handleRunBacktest}
                isLoading={isRunning}
              />
            </section>

            {/* Error state on submission */}
            {submissionError && (
              <ErrorState
                title="Simulation Failed"
                message={submissionError}
                onRetry={() => setSubmissionError(null)}
              />
            )}

            {/* 2. Simulation Results (if any active or inspected run) */}
            {displayedRun && displayedRun.result && (
              <div data-testid="backtest-results-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                {/* Key Summary KPI Strip */}
                <section aria-label="Simulation Performance Summary">
                  <BacktestSummaryKPIs result={displayedRun.result} />
                </section>

                {/* Point-In-Time & Data Quality Disclosures */}
                <section aria-label="Bias & Data Disclosures">
                  <BacktestBiasDisclosures
                    dataQualityWarnings={displayedRun.data_quality_warnings}
                    statisticalWarnings={displayedRun.result?.statistical_warnings}
                  />
                </section>

                {/* Breakdown Tables */}
                <section aria-label="Dimensional Breakdowns">
                  <BacktestBreakdownTables
                    bySetupType={displayedRun.result?.by_setup_type}
                    byDirection={displayedRun.result?.by_direction}
                  />
                </section>
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
            {/* Drawer when a historical run is inspected */}
            {selectedHistoricalRun && (
              <section aria-label="Historical Run Details">
                <BacktestDetailDrawer
                  run={selectedHistoricalRun}
                  onClose={() => setSelectedHistoricalRun(null)}
                />
              </section>
            )}

            {/* Historical Runs Table */}
            <section aria-label="Historical Runs Table">
              {historyError ? (
                <ErrorState
                  title="Unable to load backtest history"
                  message={historyError.message}
                  onRetry={() => refetchHistory()}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <HistoricalBacktestsTable
                    runs={historicalData?.results || []}
                    selectedId={selectedHistoricalRun?.id}
                    onSelect={(run) => setSelectedHistoricalRun(run)}
                    isLoading={isHistoryLoading}
                  />

                  {/* Pagination */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) 0' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                      Total {historicalData?.count || 0} backtest runs
                    </span>
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!historicalData?.previous || page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                      >
                        ← Previous
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!historicalData?.next}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        Next →
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </PageContainer>
  );
};
export default BacktestsPage;
