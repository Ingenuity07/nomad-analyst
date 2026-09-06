import React, { useState, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { useIntradayOpportunities } from '@/hooks/useIntradayOpportunities';
import { IntradayOpportunityTable } from './IntradayOpportunityTable';
import { IntradayOpportunityDetailDrawer } from './IntradayOpportunityDetailDrawer';
import { IntradayResearchModal } from '@/features/research/components/IntradayResearchModal';
import { IntradayOpportunityItem } from '@/lib/api/types';

export const IntradayOpportunityDashboard: React.FC = () => {
  const [mode, setMode] = useState<'RAW_RANKING' | 'SECTOR_DIVERSIFIED'>('RAW_RANKING');
  const [oppType, setOppType] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('');
  const [sectorFilter, setSectorFilter] = useState<string>('');
  const [minScore, setMinScore] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedOpportunity, setSelectedOpportunity] = useState<IntradayOpportunityItem | null>(null);
  const [examiningSymbol, setExaminingSymbol] = useState<string | null>(null);

  const { data, isLoading, refetch } = useIntradayOpportunities({
    mode,
    opportunity_type: oppType || undefined,
    state: stateFilter || undefined,
    sector: sectorFilter || undefined,
    min_score: minScore ? Number(minScore) : undefined,
    limit: 20,
  });

  const opportunities = useMemo(() => {
    let list = data?.opportunities || [];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (o) => o.symbol.toLowerCase().includes(q) || o.sector?.name.toLowerCase().includes(q)
      );
    }
    return list;
  }, [data?.opportunities, searchQuery]);

  const uniqueSectors = useMemo(() => {
    const set = new Set<string>();
    (data?.opportunities || []).forEach((o) => {
      if (o.sector?.name) set.add(o.sector.name);
    });
    return Array.from(set).sort();
  }, [data?.opportunities]);

  return (
    <Card style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Header & Stats Strip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)' }}>
              Intraday Opportunities
            </h2>
            <Badge variant="brand">NIFTY 50</Badge>
            <Badge variant="neutral">{mode === 'RAW_RANKING' ? 'Raw Ranking' : 'Sector Diversified'}</Badge>
          </div>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            Ranked intraday discovery based on momentum, relative strength, VWAP, volume, and sector rotation.
          </span>
        </div>

        {/* Evaluation Stats Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-xs)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Evaluated: <strong>{data?.total_evaluated ?? 0}</strong></span>
          <span style={{ color: 'var(--text-muted)' }}>•</span>
          <span style={{ color: 'var(--positive)' }}>Eligible: <strong>{data?.total_eligible ?? 0}</strong></span>
          <span style={{ color: 'var(--text-muted)' }}>•</span>
          <span style={{ color: 'var(--text-muted)' }}>Excluded: <strong>{data?.total_excluded ?? 0}</strong></span>
          <Button variant="outline" size="sm" onClick={() => refetch()}>Refresh</Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', alignItems: 'center' }}>
        {/* Mode Toggle Button */}
        <Button
          variant={mode === 'RAW_RANKING' ? 'primary' : 'outline'}
          size="sm"
          onClick={() => setMode(mode === 'RAW_RANKING' ? 'SECTOR_DIVERSIFIED' : 'RAW_RANKING')}
        >
          {mode === 'RAW_RANKING' ? 'Mode: Raw Score' : 'Mode: Diversified'}
        </Button>

        {/* Opportunity Type */}
        <Select
          value={oppType}
          onChange={(e) => setOppType(e.target.value)}
          options={[
            { label: 'All Opportunity Types', value: '' },
            { label: 'Momentum Continuation', value: 'MOMENTUM_CONTINUATION' },
            { label: 'Relative Strength', value: 'RELATIVE_STRENGTH' },
            { label: 'VWAP Trend', value: 'VWAP_TREND' },
            { label: 'ORB Breakout', value: 'OPENING_RANGE_BREAKOUT' },
            { label: 'ORB Breakdown', value: 'OPENING_RANGE_BREAKDOWN' },
            { label: 'Sector Leadership', value: 'SECTOR_LEADERSHIP' },
            { label: 'Mean Reversion Context', value: 'MEAN_REVERSION_CONTEXT' },
          ]}
        />

        {/* State Filter */}
        <Select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          options={[
            { label: 'All States', value: '' },
            { label: 'Confirmed', value: 'CONFIRMED' },
            { label: 'Emerging', value: 'EMERGING' },
            { label: 'Weakening', value: 'WEAKENING' },
            { label: 'Invalidated', value: 'INVALIDATED' },
            { label: 'Stale', value: 'STALE' },
          ]}
        />

        {/* Sector Filter */}
        <Select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          options={[
            { label: 'All Sectors', value: '' },
            ...uniqueSectors.map((sec) => ({ label: sec, value: sec })),
          ]}
        />

        {/* Min Score Filter */}
        <Select
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
          options={[
            { label: 'Min Score: Any', value: '' },
            { label: 'Score >= 50', value: '50' },
            { label: 'Score >= 65', value: '65' },
            { label: 'Score >= 75', value: '75' },
            { label: 'Score >= 85', value: '85' },
          ]}
        />

        {/* Search */}
        <div style={{ minWidth: '160px' }}>
          <Input
            placeholder="Search symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Main Table + Drawer Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: selectedOpportunity ? '1fr 380px' : '1fr',
        gap: 'var(--space-4)',
        alignItems: 'start',
      }}>
        <div style={{ backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <IntradayOpportunityTable
            opportunities={opportunities}
            selectedSymbol={selectedOpportunity?.symbol || null}
            onSelectOpportunity={(opp) => setSelectedOpportunity(opp)}
            onExamine={(sym) => setExaminingSymbol(sym)}
            isLoading={isLoading}
          />
        </div>

        {selectedOpportunity && (
          <IntradayOpportunityDetailDrawer
            opportunity={selectedOpportunity}
            onClose={() => setSelectedOpportunity(null)}
            onExamine={(sym) => setExaminingSymbol(sym)}
          />
        )}
      </div>

      {/* Phase 17E Deep AI Research Modal */}
      <IntradayResearchModal
        isOpen={Boolean(examiningSymbol)}
        onClose={() => setExaminingSymbol(null)}
        symbol={examiningSymbol}
        mode="INTRADAY"
      />
    </Card>
  );
};
