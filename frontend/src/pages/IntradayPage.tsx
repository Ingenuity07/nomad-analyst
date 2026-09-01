import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { DataStatus } from '@/components/ui/DataStatus';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';

import { useIntradayOverview } from '@/hooks/useIntradayOverview';
import { useIntradayRecommendations } from '@/hooks/useIntradayRecommendations';
import { StockRecommendation } from '@/lib/api/types';

import { IntradayFilterToolbar } from '@/features/intraday/components/IntradayFilterToolbar';
import { IntradaySummaryStrip } from '@/features/intraday/components/IntradaySummaryStrip';
import { IntradaySignalTable } from '@/features/intraday/components/IntradaySignalTable';
import { SignalDetailDrawer } from '@/features/intraday/components/SignalDetailDrawer';
import { IntradayDataQualityModal } from '@/features/intraday/components/IntradayDataQualityModal';

export const IntradayPage: React.FC = () => {
  const [timeframe, setTimeframe] = useState<string>('');
  const [setupType, setSetupType] = useState<string>('');
  const [signal, setSignal] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSignal, setSelectedSignal] = useState<StockRecommendation | null>(null);

  // Data Quality modal state
  const [dqModalSymbol, setDqModalSymbol] = useState<string | null>(null);
  const [dqModalTimeframe, setDqModalTimeframe] = useState<string>('5m');

  // 1. Fetch live market session & signal summary overview
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useIntradayOverview();

  // 2. Fetch live intraday recommendations
  const {
    data: recsData,
    isLoading: isRecsLoading,
    error: recsError,
    refetch: refetchRecs,
  } = useIntradayRecommendations({
    timeframe: timeframe || undefined,
    setup_type: setupType || undefined,
    signal: signal || undefined,
    status: status || undefined,
  });

  const handleRefresh = () => {
    refetchOverview();
    refetchRecs();
  };

  const handleResetFilters = () => {
    setTimeframe('');
    setSetupType('');
    setSignal('');
    setStatus('');
    setSearchQuery('');
    setSelectedSignal(null);
  };

  const handleOpenDataQuality = (sym: string, tf: string) => {
    setDqModalSymbol(sym);
    setDqModalTimeframe(tf);
  };

  const allResults = recsData?.results || [];
  const filteredSignals = searchQuery
    ? allResults.filter(
        (s) =>
          s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (s.company_name && s.company_name.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : allResults;

  const isTrading = overviewData?.market_session?.is_trading_hour ?? false;

  return (
    <PageContainer
      title="Intraday Scanner & Real-Time Signals"
      subtitle="Deterministic strategy signal detectors (ORB Breakout, VWAP Reclaim, Trend Continuation, Mean Reversion) on 5m, 15m, and 1h intervals"
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <DataStatus
            status={isOverviewLoading ? 'LOADING' : isTrading ? 'LIVE' : 'UNAVAILABLE'}
            source="NSE 5m Ingestion"
            lastUpdated={overviewData?.as_of ? new Date(overviewData.as_of).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST' : undefined}
          />
          <Button variant="outline" size="sm" onClick={handleRefresh} isLoading={isRecsLoading}>
            ↻ Scan Now
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* 1. Filter Toolbar */}
        <section aria-label="Intraday Filters">
          <IntradayFilterToolbar
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            setupType={setupType}
            onSetupTypeChange={setSetupType}
            signal={signal}
            onSignalChange={setSignal}
            status={status}
            onStatusChange={setStatus}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onReset={handleResetFilters}
          />
        </section>

        {/* 2. Top Summary Metric Strip */}
        <section aria-label="Session and Signals Summary">
          <IntradaySummaryStrip
            activeCount={overviewData?.summary?.active_signals || filteredSignals.filter((s) => s.status === 'ACTIVE').length}
            triggeredCount={overviewData?.summary?.triggered_signals || filteredSignals.filter((s) => s.status === 'TRIGGERED').length}
            session={overviewData?.market_session}
            asOf={overviewData?.as_of}
          />
        </section>

        {/* 3. Error State Fallback */}
        {(recsError || overviewError) && (
          <ErrorState
            title="Failed to Load Live Intraday Signals"
            message={recsError?.message || overviewError?.message || 'Unable to communicate with intraday strategy engine.'}
            onRetry={handleRefresh}
          />
        )}

        {/* 4. Main Intraday Signals Table & Detail Drawer */}
        <section aria-label="Intraday Signal Scanner">
          <div style={{ display: 'grid', gridTemplateColumns: selectedSignal ? '1fr 380px' : '1fr', gap: 'var(--space-6)', alignItems: 'start' }}>
            {/* Table Container */}
            <Card header={`Active Strategy Candidates (${filteredSignals.length} Signals)`}>
              {isRecsLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                  <Skeleton height="36px" />
                </div>
              ) : filteredSignals.length === 0 ? (
                <EmptyState
                  icon="⚡"
                  title="No Active Intraday Signals"
                  description={
                    !isTrading
                      ? 'The Indian equity market is currently outside active trading hours (09:15 - 15:30 IST). Intraday detectors are paused.'
                      : 'No stock candidates currently meet the selected intraday strategy and timeframe criteria.'
                  }
                  action={
                    <Button variant="secondary" size="sm" onClick={handleResetFilters}>
                      Reset All Filters
                    </Button>
                  }
                />
              ) : (
                <IntradaySignalTable
                  signals={filteredSignals}
                  selectedId={selectedSignal?.id}
                  onSelectSignal={(item) => setSelectedSignal(item)}
                  onCheckDataQuality={handleOpenDataQuality}
                  isLoading={isRecsLoading}
                />
              )}
            </Card>

            {/* Side Drawer Signal Detail */}
            {selectedSignal && (
              <SignalDetailDrawer
                signal={selectedSignal}
                onClose={() => setSelectedSignal(null)}
                onCheckDataQuality={handleOpenDataQuality}
              />
            )}
          </div>
        </section>

        {/* 5. On-Demand Data Quality Modal */}
        <IntradayDataQualityModal
          symbol={dqModalSymbol}
          timeframe={dqModalTimeframe}
          isOpen={Boolean(dqModalSymbol)}
          onClose={() => setDqModalSymbol(null)}
        />
      </div>
    </PageContainer>
  );
};
export default IntradayPage;
