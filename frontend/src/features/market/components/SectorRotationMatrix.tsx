import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { SectorRanking } from '@/lib/api/types';

export interface SectorRotationMatrixProps {
  sectors?: SectorRanking[];
  isLoading?: boolean;
}

type SortField = 'rank' | 'change' | 'relative' | 'rsi' | 'volatility';

export const SectorRotationMatrix: React.FC<SectorRotationMatrixProps> = ({ sectors = [], isLoading = false }) => {
  const [sortField, setSortField] = useState<SortField>('rank');
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'rank');
    }
  };

  const sortedSectors = [...sectors].sort((a, b) => {
    let valA = 0;
    let valB = 0;

    switch (sortField) {
      case 'rank':
        valA = a.rank ?? 99;
        valB = b.rank ?? 99;
        break;
      case 'change':
        valA = a.average_return ?? a.change_percent ?? 0;
        valB = b.average_return ?? b.change_percent ?? 0;
        break;
      case 'relative':
        valA = a.relative_return_vs_nifty ?? a.relative_strength_score ?? 0;
        valB = b.relative_return_vs_nifty ?? b.relative_strength_score ?? 0;
        break;
      case 'rsi':
        valA = a.average_rsi ?? 50;
        valB = b.average_rsi ?? 50;
        break;
      case 'volatility':
        valA = a.average_volatility ?? 0;
        valB = b.average_volatility ?? 0;
        break;
    }

    return sortAsc ? valA - valB : valB - valA;
  });

  const columns: TableColumn<SectorRanking>[] = [
    {
      key: 'rank',
      header: 'Rank',
      width: '60px',
      render: (item) => (
        <span style={{ fontWeight: 'var(--weight-bold)', color: item.rank <= 3 ? 'var(--brand-primary)' : 'var(--text-muted)' }}>
          #{item.rank}
        </span>
      ),
    },
    {
      key: 'sector',
      header: 'Sector',
      render: (item) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          {item.sector}
        </span>
      ),
    },
    {
      key: 'average_return',
      header: '1D Return %',
      isNumeric: true,
      render: (item) => {
        const ret = item.average_return ?? item.change_percent ?? null;
        if (ret === null) return '—';
        const isPos = ret > 0;
        return (
          <span style={{ color: isPos ? 'var(--positive)' : 'var(--negative)' }}>
            {isPos ? '+' : ''}{ret.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'relative_return_vs_nifty',
      header: 'Alpha vs NIFTY',
      isNumeric: true,
      render: (item) => {
        const alpha = item.relative_return_vs_nifty ?? item.relative_strength_score ?? null;
        if (alpha === null) return '—';
        const isPos = alpha > 0;
        return (
          <span style={{ color: isPos ? 'var(--positive)' : 'var(--negative)' }}>
            {isPos ? '+' : ''}{alpha.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'average_rsi',
      header: 'Avg RSI',
      isNumeric: true,
      render: (item) => (item.average_rsi !== undefined && item.average_rsi !== null ? item.average_rsi.toFixed(1) : '—'),
    },
    {
      key: 'momentum_state',
      header: 'Momentum State',
      render: (item) => {
        const state = (item.momentum_state || item.trend || 'STABLE').toUpperCase();
        const variant = state.includes('IMPROV') || state.includes('LEAD') ? 'positive' : state.includes('WEAK') || state.includes('DETERIORAT') ? 'negative' : 'neutral';
        return <Badge variant={variant} size="sm">{state}</Badge>;
      },
    },
    {
      key: 'tier',
      header: 'Tier',
      render: (item) => {
        const tier = (item.tier || 'NEUTRAL').toUpperCase();
        const variant = tier === 'STRONGEST' ? 'brand' : tier === 'WEAKEST' ? 'negative' : 'neutral';
        return <Badge variant={variant} size="sm">{tier}</Badge>;
      },
    },
  ];

  return (
    <Card
      header="Sector Rotation & Relative Strength Matrix"
      action={
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button
            onClick={() => handleSort('rank')}
            style={{
              padding: '2px 8px',
              fontSize: 'var(--text-xs)',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: sortField === 'rank' ? 'var(--bg-surface-elevated)' : 'transparent',
              color: sortField === 'rank' ? 'var(--brand-primary)' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Sort by Rank
          </button>
          <button
            onClick={() => handleSort('change')}
            style={{
              padding: '2px 8px',
              fontSize: 'var(--text-xs)',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: sortField === 'change' ? 'var(--bg-surface-elevated)' : 'transparent',
              color: sortField === 'change' ? 'var(--brand-primary)' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Sort by Return
          </button>
        </div>
      }
    >
      <Table
        columns={columns}
        data={sortedSectors}
        keyExtractor={(item) => item.sector}
        emptyMessage={isLoading ? 'Loading sector rankings...' : 'No sector ranking data available.'}
      />
    </Card>
  );
};
