import React, { useState, useEffect, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { PageContainer } from '@/components/layout/PageContainer';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockDetailResponse } from '@/lib/api/types';

import { useMarketOverview } from '@/hooks/useMarketOverview';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import { useRecommendations } from '@/hooks/useRecommendations';
import { useOpportunities } from '@/hooks/useOpportunities';

import {
  loadMonitorStore,
  saveMonitorStore,
  MonitorStore,
  MonitorRule,
  MonitorEvent,
} from '@/features/alerts/storage';

import { CommandCenterStatusStrip } from '@/features/alerts/components/CommandCenterStatusStrip';
import { CustomMonitorManager } from '@/features/alerts/components/CustomMonitorManager';
import { ActiveEventFeed } from '@/features/alerts/components/ActiveEventFeed';
import { AlertDetailDrawer } from '@/features/alerts/components/AlertDetailDrawer';
import { ServerNotificationBoundaryCard } from '@/features/alerts/components/ServerNotificationBoundaryCard';

export const AlertsPage: React.FC = () => {
  const [store, setStore] = useState<MonitorStore>(() => loadMonitorStore());
  const [selectedDrawerEvent, setSelectedDrawerEvent] = useState<MonitorEvent | null>(null);
  const seenRef = React.useRef<Set<string>>(new Set(store.seenEventIds));

  // Sync to localStorage
  useEffect(() => {
    saveMonitorStore(store);
  }, [store]);

  // Polling feeds with TanStack Query
  const { data: overview } = useMarketOverview('NIFTY50');
  const session = overview?.market_session;
  const isTradingHour = session?.is_trading_hour ?? false;

  const pollInterval = isTradingHour ? 30 * 1000 : 120 * 1000;

  const { data: regimeData } = useMarketRegime('NIFTY50', undefined);
  const { data: recsData } = useRecommendations({ status: 'ACTIVE' });
  const { data: oppsData } = useOpportunities();

  // Distinct symbols monitored by price rules
  const priceMonitoredSymbols = useMemo(() => {
    const syms = new Set<string>();
    store.rules.forEach((r) => {
      if (r.enabled && (r.type === 'PRICE_ABOVE' || r.type === 'PRICE_BELOW') && r.symbol) {
        syms.add(r.symbol.toUpperCase());
      }
    });
    return Array.from(syms);
  }, [store.rules]);

  // Query live prices for monitored symbols
  const priceQueries = useQueries({
    queries: priceMonitoredSymbols.map((sym) => ({
      queryKey: ['stock', sym],
      queryFn: () => apiClient<StockDetailResponse>(ENDPOINTS.STOCK_DETAIL(sym)),
      refetchInterval: pollInterval,
    })),
  });

  // Evaluate Active Monitor Rules against live responses
  useEffect(() => {
    const newEvents: MonitorEvent[] = [];
    const seen = seenRef.current;
    const updatedRules = [...store.rules];

    // 1. Evaluate Recommendations (NEW_ACTIVE_BUY)
    const activeRecs = recsData?.results || [];
    const buyRules = updatedRules.filter((r) => r.enabled && r.type === 'NEW_ACTIVE_BUY');
    if (buyRules.length > 0 && activeRecs.length > 0) {
      activeRecs.forEach((rec) => {
        if (rec.signal === 'BUY') {
          const eventId = `rec-${rec.id}`;
          if (!seen.has(eventId)) {
            seen.add(eventId);
            newEvents.push({
              id: eventId,
              category: 'RECOMMENDATIONS',
              source: 'StrategyEngine',
              symbol: rec.symbol,
              title: `New Active BUY Signal: ${rec.setup_type || 'MOMENTUM'}`,
              summary: `${rec.horizon} setup with entry at ₹${rec.entry_price || '—'}, stop loss ₹${rec.stop_price || '—'}, target ₹${rec.target_price || '—'}.`,
              severity: 'HIGH',
              observedAt: new Date().toISOString(),
              sourceTimestamp: rec.as_of,
              navigationLink: '/recommendations',
            });
          }
        }
      });
    }

    // 2. Evaluate Opportunities (OPPORTUNITY_SCORE_ABOVE)
    const activeOpps = oppsData?.results || [];
    const oppRules = updatedRules.filter((r) => r.enabled && r.type === 'OPPORTUNITY_SCORE_ABOVE');
    oppRules.forEach((rule) => {
      const minScore = rule.threshold ?? 80;
      activeOpps.forEach((opp) => {
        const score = Number(opp.final_score ?? opp.final_opportunity_score ?? 0);
        if (score >= minScore) {
          const eventId = `opp-${opp.id}-${minScore}`;
          if (!seen.has(eventId)) {
            seen.add(eventId);
            newEvents.push({
              id: eventId,
              ruleId: rule.id,
              category: 'OPPORTUNITIES',
              source: 'DiscoveryEngine',
              symbol: opp.symbol,
              title: `High Opportunity Score: ${score.toFixed(0)}/100`,
              summary: `Scored setup in ${opp.sector} sector with primary driver: ${opp.reasons && opp.reasons.length > 0 ? opp.reasons[0] : 'Momentum factor'}.`,
              severity: 'MEDIUM',
              observedAt: new Date().toISOString(),
              sourceTimestamp: opp.as_of,
              navigationLink: '/delivery',
            });
          }
        }
      });
    });

    // 3. Evaluate Market Regime (REGIME_SHIFT_TO_BEARISH)
    const regimeRules = updatedRules.filter((r) => r.enabled && r.type === 'REGIME_SHIFT_TO_BEARISH');
    if (regimeRules.length > 0 && regimeData) {
      const trend = regimeData.trend_regime?.trend || regimeData.trend || '';
      if (trend === 'BEARISH') {
        const eventId = `regime-bearish-${regimeData.as_of || 'latest'}`;
        if (!seen.has(eventId)) {
          seen.add(eventId);
          newEvents.push({
            id: eventId,
            category: 'MARKET_REGIME',
            source: 'MarketContextService',
            title: 'Market Regime Shift: BEARISH Trend Detected',
            summary: 'Benchmark index closed below structural SMA200 indicating elevated defensive risks.',
            severity: 'HIGH',
            observedAt: new Date().toISOString(),
            navigationLink: '/market-intelligence',
          });
        }
      }
    }

    // 4. Evaluate Price Rules (PRICE_ABOVE / PRICE_BELOW)
    updatedRules.forEach((rule) => {
      if (!rule.enabled || !rule.symbol || rule.threshold === undefined) return;
      const qIdx = priceMonitoredSymbols.indexOf(rule.symbol);
      if (qIdx === -1) return;

      const q = priceQueries[qIdx];
      const snapshot = q?.data?.latest_snapshot;
      if (!snapshot?.close) return;

      const currentPrice = Number(snapshot.close);
      const prevPrice = rule.lastObservedPrice;

      if (prevPrice !== undefined && rule.baselineEstablished) {
        if (rule.type === 'PRICE_ABOVE' && prevPrice < rule.threshold && currentPrice >= rule.threshold) {
          const eventId = `price-above-${rule.symbol}-${rule.threshold}-${Date.now()}`;
          newEvents.push({
            id: eventId,
            ruleId: rule.id,
            category: 'WATCHLIST_TRIGGERS',
            source: 'PriceMonitor',
            symbol: rule.symbol,
            title: `Price Cross: ${rule.symbol} > ₹${rule.threshold}`,
            summary: `Stock crossed above threshold level to ₹${currentPrice.toFixed(2)}.`,
            severity: 'HIGH',
            observedAt: new Date().toISOString(),
            navigationLink: `/stocks/${rule.symbol}`,
          });
          seen.add(eventId);
        } else if (rule.type === 'PRICE_BELOW' && prevPrice > rule.threshold && currentPrice <= rule.threshold) {
          const eventId = `price-below-${rule.symbol}-${rule.threshold}-${Date.now()}`;
          newEvents.push({
            id: eventId,
            ruleId: rule.id,
            category: 'WATCHLIST_TRIGGERS',
            source: 'PriceMonitor',
            symbol: rule.symbol,
            title: `Price Cross: ${rule.symbol} < ₹${rule.threshold}`,
            summary: `Stock broke below support threshold level to ₹${currentPrice.toFixed(2)}.`,
            severity: 'HIGH',
            observedAt: new Date().toISOString(),
            navigationLink: `/stocks/${rule.symbol}`,
          });
          seen.add(eventId);
        }
      }
    });

    // If new events occurred, save state
    if (newEvents.length > 0) {
      setStore((prev) => ({
        ...prev,
        events: [...newEvents, ...prev.events],
        seenEventIds: Array.from(seen),
      }));
    }
  }, [recsData, oppsData, regimeData, priceQueries, priceMonitoredSymbols]);

  // Handlers for Rule Manager
  const handleAddRule = (rule: Omit<MonitorRule, 'id' | 'createdAt' | 'updatedAt'>) => {
    const newRule: MonitorRule = {
      ...rule,
      id: `rule-${Date.now()}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setStore((prev) => ({
      ...prev,
      rules: [...prev.rules, newRule],
    }));
  };

  const handleToggleRule = (id: string) => {
    setStore((prev) => ({
      ...prev,
      rules: prev.rules.map((r) =>
        r.id === id ? { ...r, enabled: !r.enabled, updatedAt: new Date().toISOString() } : r
      ),
    }));
  };

  const handleDeleteRule = (id: string) => {
    setStore((prev) => ({
      ...prev,
      rules: prev.rules.filter((r) => r.id !== id),
    }));
  };

  const handleClearEvents = () => {
    setStore((prev) => ({
      ...prev,
      events: [],
    }));
  };

  const activeRulesCount = store.rules.filter((r) => r.enabled).length;
  const highSeverityCount = store.events.filter((e) => e.severity === 'HIGH').length;

  return (
    <PageContainer
      title="Alerts & Monitoring Command Center"
      subtitle="In-browser analytical monitoring of live strategy signals, regime shifts, and custom price thresholds."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* 1. Status Strip */}
        <section aria-label="System Status">
          <CommandCenterStatusStrip
            session={session}
            activeRulesCount={activeRulesCount}
            totalEventsCount={store.events.length}
            highSeverityCount={highSeverityCount}
            isPollingActive={isTradingHour}
          />
        </section>

        {/* 2. Custom Monitor Rules Manager */}
        <section aria-label="Monitor Rule Manager">
          <CustomMonitorManager
            rules={store.rules}
            onAddRule={handleAddRule}
            onToggleRule={handleToggleRule}
            onDeleteRule={handleDeleteRule}
          />
        </section>

        {/* 3. Real-Time Event Feed */}
        <section aria-label="Active Event Feed">
          <ActiveEventFeed
            events={store.events}
            onSelectEvent={(ev) => setSelectedDrawerEvent(ev)}
            onClearEvents={handleClearEvents}
          />
        </section>

        {/* 4. Server Boundary Disclaimer */}
        <section aria-label="Server Notification Boundary">
          <ServerNotificationBoundaryCard />
        </section>

        {/* 5. Detail Drawer */}
        <AlertDetailDrawer
          isOpen={Boolean(selectedDrawerEvent)}
          onClose={() => setSelectedDrawerEvent(null)}
          event={selectedDrawerEvent}
        />
      </div>
    </PageContainer>
  );
};
export default AlertsPage;
