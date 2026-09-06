import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { DataStatus } from '@/components/ui/DataStatus';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';

import { useIntradayOverview } from '@/hooks/useIntradayOverview';
import { useIntradayRecommendations } from '@/hooks/useIntradayRecommendations';
import {
  useIntradayMarketContext,
  useIntradayStocks,
  useIntradayWebSocket,
} from '@/hooks/useIntradayMarketContext';
import { StockRecommendation } from '@/lib/api/types';

import { IntradayFilterToolbar } from '@/features/intraday/components/IntradayFilterToolbar';
import { IntradaySummaryStrip } from '@/features/intraday/components/IntradaySummaryStrip';
import { IntradaySignalTable } from '@/features/intraday/components/IntradaySignalTable';
import { SignalDetailDrawer } from '@/features/intraday/components/SignalDetailDrawer';
import { IntradayDataQualityModal } from '@/features/intraday/components/IntradayDataQualityModal';
import { KiteDataHealthCard } from '@/features/kite/components/KiteDataHealthCard';

// Phase 17C Components
import { IntradayMarketHeader } from '@/features/intraday/components/IntradayMarketHeader';
import { IntradayBreadthCard } from '@/features/intraday/components/IntradayBreadthCard';
import { IntradaySectorStrengthPanel } from '@/features/intraday/components/IntradaySectorStrength';
import { IntradayStockContextTable } from '@/features/intraday/components/IntradayStockContextTable';

// Phase 17D Components
import { IntradayOpportunityDashboard } from '@/features/intraday/components/IntradayOpportunityDashboard';

export const IntradayPage: React.FC = () => {
  const [timeframe, setTimeframe] = useState<string>('');
  const [setupType, setSetupType] = useState<string>('');
  const [signal, setSignal] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSignal, setSelectedSignal] = useState<StockRecommendation | null>(null);
  const [searchParams] = useSearchParams();

  // Data Quality modal state
  const [dqModalSymbol, setDqModalSymbol] = useState<string | null>(null);
  const [dqModalTimeframe, setDqModalTimeframe] = useState<string>('5m');

  // WebSocket connection for live pushes
  const { isConnected: wsConnected } = useIntradayWebSocket();

  // Phase 17C live market context & stocks
  const {
    data: marketContextData,
    isLoading: isContextLoading,
    refetch: refetchContext,
  } = useIntradayMarketContext();

  const {
    data: stocksData,
    isLoading: isStocksLoading,
    refetch: refetchStocks,
  } = useIntradayStocks();

  // Existing overview & strategy signals
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useIntradayOverview();

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
    refetchContext();
    refetchStocks();
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
            status={marketContextData?.is_fresh ? 'LIVE' : isOverviewLoading ? 'LOADING' : isTrading ? 'LIVE' : 'UNAVAILABLE'}
            source="Kite Connect Live"
            lastUpdated={marketContextData?.as_of ? new Date(marketContextData.as_of).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST' : undefined}
          />
          <Button variant="outline" size="sm" onClick={handleRefresh} isLoading={isRecsLoading || isContextLoading}>
            ↻ Refresh
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* Kite Auth Callback Notification Banner */}
        {searchParams.get('kite_auth') === 'success' && (
          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              backgroundColor: 'var(--positive-bg, rgba(34,197,94,0.1))',
              color: 'var(--positive)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--positive)',
              fontSize: 'var(--text-sm)',
              fontWeight: 'var(--weight-medium)',
            }}
          >
            ✓ Zerodha Kite Connect authenticated successfully! Real-time market data session is active.
          </div>
        )}
        {(searchParams.get('kite_auth') === 'error' || searchParams.get('kite_auth') === 'cancelled') && (
          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              backgroundColor: 'var(--negative-bg, rgba(239,68,68,0.1))',
              color: 'var(--negative)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--negative)',
              fontSize: 'var(--text-sm)',
              fontWeight: 'var(--weight-medium)',
            }}
          >
            ✕ Kite authentication {searchParams.get('kite_auth')}: {searchParams.get('msg') || 'Unable to establish session.'}
          </div>
        )}

        {/* Kite Market Data Layer Health Card */}
        <section aria-label="Kite Market Data Layer">
          <KiteDataHealthCard />
        </section>

        {/* ========================================================================
            PHASE 17C: INTRADAY MARKET CONTEXT & SIGNAL FOUNDATION
            ======================================================================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* 1. Market Header (NIFTY, BANKNIFTY, Regime, Freshness) */}
          <section aria-label="Intraday Market Header">
            <IntradayMarketHeader
              context={marketContextData}
              isLoading={isContextLoading}
              wsConnected={wsConnected}
            />
          </section>

          {/* 2. Breadth & Sector Rotation Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
            <section aria-label="NIFTY Breadth">
              <IntradayBreadthCard
                breadth={marketContextData?.breadth}
                isLoading={isContextLoading}
              />
            </section>

            <section aria-label="Sector Rotation">
              <IntradaySectorStrengthPanel
                sectors={marketContextData?.sectors}
                sectorLeader={marketContextData?.sector_leader}
                sectorLaggard={marketContextData?.sector_laggard}
                isLoading={isContextLoading}
              />
            </section>
          </div>

          {/* 3. Intraday Opportunity Engine (Phase 17D) */}
          <section aria-label="Intraday Opportunities">
            <IntradayOpportunityDashboard />
          </section>

          {/* 4. Constituent Stock Context Table (Phase 17C) */}
          <section aria-label="NIFTY 50 Stock Context">
            <IntradayStockContextTable
              stocks={stocksData?.stocks || []}
              isLoading={isStocksLoading}
            />
          </section>
        </div>

        {/* ========================================================================
            EXISTING STRATEGY SIGNAL SCANNER SECTION
            ======================================================================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', marginTop: 'var(--space-4)' }}>
          {/* Filter Toolbar */}
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

          {/* Top Summary Metric Strip */}
          <section aria-label="Session and Signals Summary">
            <IntradaySummaryStrip
              activeCount={overviewData?.summary?.active_signals || filteredSignals.filter((s) => s.status === 'ACTIVE').length}
              triggeredCount={overviewData?.summary?.triggered_signals || filteredSignals.filter((s) => s.status === 'TRIGGERED').length}
              session={overviewData?.market_session}
              asOf={overviewData?.as_of}
            />
          </section>

          {/* Error State Fallback */}
          {(recsError || overviewError) && (
            <ErrorState
              title="Failed to Load Live Intraday Signals"
              message={recsError?.message || overviewError?.message || 'Unable to communicate with intraday strategy engine.'}
              onRetry={handleRefresh}
            />
          )}

          {/* Main Intraday Signals Table & Detail Drawer */}
          <section aria-label="Intraday Signal Scanner">
            <div style={{ display: 'grid', gridTemplateColumns: selectedSignal ? '1fr 380px' : '1fr', gap: 'var(--space-6)', alignItems: 'start' }}>
              <Card style={{ padding: 'var(--space-4)' }}>
                {isRecsLoading && allResults.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', padding: 'var(--space-4)' }}>
                    <Skeleton height="32px" />
                    <Skeleton height="40px" />
                    <Skeleton height="40px" />
                  </div>
                ) : filteredSignals.length === 0 ? (
                  <EmptyState
                    title="No Signals Found"
                    description="No active intraday strategy setups match your selected filters."
                    action={
                      <Button variant="outline" size="sm" onClick={handleResetFilters}>
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

              {selectedSignal && (
                <SignalDetailDrawer
                  signal={selectedSignal}
                  onClose={() => setSelectedSignal(null)}
                  onCheckDataQuality={handleOpenDataQuality}
                />
              )}
            </div>
          </section>
        </div>

        {/* On-Demand Data Quality Modal */}
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
