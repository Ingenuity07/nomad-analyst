import React, { useState, useEffect, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { PageContainer } from '@/components/layout/PageContainer';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockDetailResponse } from '@/lib/api/types';
import { useRecommendations } from '@/hooks/useRecommendations';
import { useOpportunities } from '@/hooks/useOpportunities';

import {
  loadWatchlistStore,
  saveWatchlistStore,
  WatchlistStore,
  WatchlistItem,
  DecisionStatus,
} from '@/features/watchlist/storage';

import { WatchlistManagerTabs } from '@/features/watchlist/components/WatchlistManagerTabs';
import { WatchlistSearchAdd } from '@/features/watchlist/components/WatchlistSearchAdd';
import { WatchlistSummaryStrip } from '@/features/watchlist/components/WatchlistSummaryStrip';
import { MonitoredDecisionTable, EnrichedWatchlistItem } from '@/features/watchlist/components/MonitoredDecisionTable';
import { WatchedStockDetailDrawer } from '@/features/watchlist/components/WatchedStockDetailDrawer';
import { PortfolioBoundaryCard } from '@/features/watchlist/components/PortfolioBoundaryCard';

export const WatchlistPage: React.FC = () => {
  const [store, setStore] = useState<WatchlistStore>(() => loadWatchlistStore());
  const [selectedDrawerItem, setSelectedDrawerItem] = useState<WatchlistItem | null>(null);

  // Sync to localStorage on store updates
  useEffect(() => {
    saveWatchlistStore(store);
  }, [store]);

  const activeWatchlist = useMemo(() => {
    return store.watchlists.find((w) => w.id === store.activeWatchlistId) || store.watchlists[0];
  }, [store]);

  // Fetch all active recommendations and opportunities for matching
  const { data: recsData } = useRecommendations({ status: 'ACTIVE' });
  const { data: oppsData } = useOpportunities();

  const activeRecommendations = recsData?.results || [];
  const activeOpportunities = oppsData?.results || [];

  // Fetch live quotes / details for all symbols in the active watchlist
  const symbolQueries = useQueries({
    queries: activeWatchlist.symbols.map((item) => ({
      queryKey: ['stock', item.symbol],
      queryFn: () => apiClient<StockDetailResponse>(ENDPOINTS.STOCK_DETAIL(item.symbol)),
      staleTime: 60 * 1000,
    })),
  });

  // Combine local state with backend context
  const enrichedItems: EnrichedWatchlistItem[] = useMemo(() => {
    return activeWatchlist.symbols.map((item, idx) => {
      const q = symbolQueries[idx];
      const stockDetail = q?.data || null;
      const activeRec = activeRecommendations.find((r) => r.symbol === item.symbol) || null;
      const opportunity = activeOpportunities.find((o) => o.symbol === item.symbol) || null;

      return {
        item,
        stockDetail,
        activeRec,
        opportunity,
        isLoading: q?.isLoading,
      };
    });
  }, [activeWatchlist.symbols, symbolQueries, activeRecommendations, activeOpportunities]);

  // Derived Summary Counts
  let advancingCount = 0;
  let decliningCount = 0;
  let activeSignalsCount = 0;
  let totalScoreSum = 0;
  let scoreCount = 0;

  enrichedItems.forEach((ei) => {
    const chg = ei.stockDetail?.latest_snapshot?.change_percent;
    if (chg !== undefined && chg !== null) {
      if (Number(chg) > 0) advancingCount += 1;
      else if (Number(chg) < 0) decliningCount += 1;
    }
    if (ei.activeRec) activeSignalsCount += 1;
    if (ei.opportunity) {
      const s = Number(ei.opportunity.final_score ?? ei.opportunity.final_opportunity_score ?? 0);
      if (s > 0) {
        totalScoreSum += s;
        scoreCount += 1;
      }
    }
  });

  const avgOppScore = scoreCount > 0 ? totalScoreSum / scoreCount : null;

  // Watchlist Management Handlers
  const handleSelectWatchlist = (id: string) => {
    setStore((prev) => ({ ...prev, activeWatchlistId: id }));
  };

  const handleCreateWatchlist = (name: string) => {
    const newId = `wl-${Date.now()}`;
    const newList = {
      id: newId,
      name,
      symbols: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setStore((prev) => ({
      ...prev,
      activeWatchlistId: newId,
      watchlists: [...prev.watchlists, newList],
    }));
  };

  const handleRenameWatchlist = (id: string, newName: string) => {
    setStore((prev) => ({
      ...prev,
      watchlists: prev.watchlists.map((w) =>
        w.id === id ? { ...w, name: newName, updatedAt: new Date().toISOString() } : w
      ),
    }));
  };

  const handleDeleteWatchlist = (id: string) => {
    if (store.watchlists.length <= 1) return;
    const remaining = store.watchlists.filter((w) => w.id !== id);
    setStore({
      ...store,
      activeWatchlistId: remaining[0].id,
      watchlists: remaining,
    });
  };

  // Symbol Membership & Decision State Handlers
  const handleAddSymbol = (symbol: string) => {
    const newItem: WatchlistItem = {
      symbol: symbol.toUpperCase(),
      decisionStatus: 'WATCHING',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setStore((prev) => ({
      ...prev,
      watchlists: prev.watchlists.map((w) =>
        w.id === activeWatchlist.id
          ? {
              ...w,
              symbols: [...w.symbols.filter((s) => s.symbol !== symbol.toUpperCase()), newItem],
              updatedAt: new Date().toISOString(),
            }
          : w
      ),
    }));
  };

  const handleRemoveSymbol = (symbol: string) => {
    setStore((prev) => ({
      ...prev,
      watchlists: prev.watchlists.map((w) =>
        w.id === activeWatchlist.id
          ? {
              ...w,
              symbols: w.symbols.filter((s) => s.symbol !== symbol.toUpperCase()),
              updatedAt: new Date().toISOString(),
            }
          : w
      ),
    }));
  };

  const handleUpdateDecision = (symbol: string, status: DecisionStatus, notes?: string) => {
    setStore((prev) => ({
      ...prev,
      watchlists: prev.watchlists.map((w) =>
        w.id === activeWatchlist.id
          ? {
              ...w,
              symbols: w.symbols.map((s) =>
                s.symbol === symbol
                  ? { ...s, decisionStatus: status, notes, updatedAt: new Date().toISOString() }
                  : s
              ),
              updatedAt: new Date().toISOString(),
            }
          : w
      ),
    }));

    if (selectedDrawerItem && selectedDrawerItem.symbol === symbol) {
      setSelectedDrawerItem((prev) => (prev ? { ...prev, decisionStatus: status, notes } : null));
    }
  };

  const activeDrawerEnriched = enrichedItems.find((ei) => ei.item.symbol === selectedDrawerItem?.symbol);

  return (
    <PageContainer
      title="Watchlist & Personal Decisions"
      subtitle="Curate custom symbol baskets, record thesis trigger notes, and monitor real-time strategy recommendations."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* 1. Watchlist Manager Tabs & Add Symbol Search */}
        <section aria-label="Watchlist Management">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <WatchlistManagerTabs
              watchlists={store.watchlists}
              activeId={activeWatchlist.id}
              onSelectWatchlist={handleSelectWatchlist}
              onCreateWatchlist={handleCreateWatchlist}
              onRenameWatchlist={handleRenameWatchlist}
              onDeleteWatchlist={handleDeleteWatchlist}
            />

            <WatchlistSearchAdd
              existingSymbols={activeWatchlist.symbols.map((s) => s.symbol)}
              onAddSymbol={handleAddSymbol}
            />
          </div>
        </section>

        {/* 2. Summary Strip */}
        <section aria-label="Watchlist Summary">
          <WatchlistSummaryStrip
            totalCount={activeWatchlist.symbols.length}
            advancingCount={advancingCount}
            decliningCount={decliningCount}
            activeSignalsCount={activeSignalsCount}
            avgOpportunityScore={avgOppScore}
          />
        </section>

        {/* 3. Main Monitored Decision Matrix */}
        <section aria-label="Monitored Decision Table">
          <MonitoredDecisionTable
            items={enrichedItems}
            onSelectRow={(item) => setSelectedDrawerItem(item)}
            onRemoveSymbol={handleRemoveSymbol}
          />
        </section>

        {/* 4. Portfolio Capabilities Boundary */}
        <section aria-label="Portfolio Boundary">
          <PortfolioBoundaryCard />
        </section>

        {/* 5. Watched Stock Detail Drawer */}
        <WatchedStockDetailDrawer
          isOpen={Boolean(selectedDrawerItem)}
          onClose={() => setSelectedDrawerItem(null)}
          item={selectedDrawerItem}
          stockDetail={activeDrawerEnriched?.stockDetail}
          activeRec={activeDrawerEnriched?.activeRec}
          opportunity={activeDrawerEnriched?.opportunity}
          onUpdateDecision={handleUpdateDecision}
          onRemoveFromList={handleRemoveSymbol}
        />
      </div>
    </PageContainer>
  );
};
export default WatchlistPage;
