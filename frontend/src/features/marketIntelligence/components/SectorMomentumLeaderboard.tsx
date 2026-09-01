import React from 'react';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { SectorRanking } from '@/lib/api/types';

export interface SectorMomentumLeaderboardProps {
  sectors: SectorRanking[];
  selectedSector: string;
  onSelectSector: (sector: string) => void;
}

export const SectorMomentumLeaderboard: React.FC<SectorMomentumLeaderboardProps> = ({
  sectors = [],
  selectedSector,
  onSelectSector,
}) => {
  const columns: TableColumn<SectorRanking>[] = [
    {
      key: 'rank',
      header: 'Rank',
      width: '60px',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)' }}>
          #{r.rank}
        </span>
      ),
    },
    {
      key: 'sector',
      header: 'Sector',
      render: (r) => {
        const isSelected = r.sector === selectedSector;
        return (
          <span
            style={{
              fontWeight: isSelected ? 'var(--weight-bold)' : 'var(--weight-semibold)',
              color: isSelected ? 'var(--brand-primary)' : 'var(--text-primary)',
            }}
          >
            {r.sector}
          </span>
        );
      },
    },
    {
      key: 'average_return',
      header: '1D Return',
      isNumeric: true,
      render: (r) => {
        const val = Number(r.average_return) || 0;
        const isPositive = val >= 0;
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 'var(--weight-semibold)',
              color: isPositive ? 'var(--positive)' : 'var(--negative)',
            }}
          >
            {isPositive ? '+' : ''}
            {val.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'relative_return_vs_nifty',
      header: 'vs Nifty 50',
      isNumeric: true,
      render: (r) => {
        const val = Number(r.relative_return_vs_nifty) || 0;
        const isPositive = val >= 0;
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              color: isPositive ? 'var(--positive)' : 'var(--negative)',
            }}
          >
            {isPositive ? '+' : ''}
            {val.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'average_rsi',
      header: 'Avg RSI',
      isNumeric: true,
      render: (r) => (r.average_rsi ? Number(r.average_rsi).toFixed(1) : '—'),
    },
    {
      key: 'tier',
      header: 'Tier',
      render: (r) => {
        const tier = (r.tier || 'neutral').toLowerCase();
        if (tier === 'strongest') return <Badge variant="positive" size="sm">STRONGEST</Badge>;
        if (tier === 'weakest') return <Badge variant="negative" size="sm">WEAKEST</Badge>;
        return <Badge variant="neutral" size="sm">NEUTRAL</Badge>;
      },
    },
    {
      key: 'momentum_state',
      header: 'Momentum Delta',
      render: (r) => {
        const state = (r.momentum_state || 'stable').toLowerCase();
        if (state === 'improving') return <Badge variant="positive" size="sm">📈 IMPROVING</Badge>;
        if (state === 'deteriorating') return <Badge variant="negative" size="sm">📉 DETERIORATING</Badge>;
        return <Badge variant="neutral" size="sm">STABLE</Badge>;
      },
    },
  ];

  return (
    <Card
      header="Sector Relative Strength & Momentum Leaderboard"
      action={
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          Click row to drill into constituents & opportunities
        </span>
      }
      data-testid="sector-momentum-leaderboard"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Visual 1D Return Strip */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-1-5)',
            backgroundColor: 'var(--bg-surface-sunken)',
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            1D Sector Performance Spread:
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-1-5)', flexWrap: 'wrap' }}>
            {sectors.map((s) => {
              const val = Number(s.average_return) || 0;
              const isSelected = s.sector === selectedSector;
              return (
                <button
                  key={s.sector}
                  type="button"
                  onClick={() => onSelectSector(s.sector)}
                  style={{
                    padding: '2px 8px',
                    fontSize: 'var(--text-xs)',
                    fontFamily: 'var(--font-mono)',
                    color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                    backgroundColor: isSelected ? 'var(--brand-subtle)' : 'var(--bg-surface-elevated)',
                    border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-xs)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <span>{s.sector}:</span>
                  <strong style={{ color: val >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                    {val >= 0 ? '+' : ''}{val.toFixed(1)}%
                  </strong>
                </button>
              );
            })}
          </div>
        </div>

        {/* Autoranking Table */}
        <Table
          columns={columns}
          data={sectors}
          keyExtractor={(r) => r.sector || r.rank}
          onRowClick={(r) => onSelectSector(r.sector)}
          emptyMessage="No sector rankings data available."
        />
      </div>
    </Card>
  );
};
