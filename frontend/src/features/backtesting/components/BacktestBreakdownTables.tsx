import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Card } from '@/components/ui/Card';

export interface BreakdownSlice {
  dimension_key: string;
  dimension_value: string;
  total: number;
  triggered: number;
  untriggered: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  avg_r: number | null;
  expectancy: number | null;
  profit_factor: number | null;
}

export interface BacktestBreakdownTablesProps {
  bySetupType?: Record<string, BreakdownSlice>;
  byDirection?: Record<string, BreakdownSlice>;
}

export const BacktestBreakdownTables: React.FC<BacktestBreakdownTablesProps> = ({
  bySetupType,
  byDirection,
}) => {
  const setupSlices = Object.values(bySetupType || {});
  const directionSlices = Object.values(byDirection || {});

  const columns: TableColumn<BreakdownSlice>[] = [
    {
      key: 'dimension_value',
      header: 'Pattern / Setup',
      render: (item) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
          {item.dimension_value}
        </span>
      ),
    },
    {
      key: 'total',
      header: 'Signals',
      isNumeric: true,
      render: (item) => <span>{item.total}</span>,
    },
    {
      key: 'triggered',
      header: 'Triggered',
      isNumeric: true,
      render: (item) => <span>{item.triggered}</span>,
    },
    {
      key: 'win_rate',
      header: 'Win Rate',
      isNumeric: true,
      render: (item) => (
        <span>{item.win_rate !== null ? `${(item.win_rate * 100).toFixed(1)}%` : '—'}</span>
      ),
    },
    {
      key: 'avg_r',
      header: 'Avg R',
      isNumeric: true,
      render: (item) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', color: item.avg_r !== null && item.avg_r >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
          {item.avg_r !== null ? `${item.avg_r >= 0 ? '+' : ''}${item.avg_r.toFixed(2)} R` : '—'}
        </span>
      ),
    },
    {
      key: 'profit_factor',
      header: 'Profit Factor',
      isNumeric: true,
      render: (item) => <span>{item.profit_factor !== null ? item.profit_factor.toFixed(2) : '—'}</span>,
    },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 'var(--space-4)' }}>
      <Card header="Performance Breakdown by Setup Pattern">
        <Table
          columns={columns}
          data={setupSlices}
          keyExtractor={(item) => item.dimension_value}
          emptyMessage="No pattern setup breakdown available for this run."
        />
      </Card>

      <Card header="Performance Breakdown by Signal Direction">
        <Table
          columns={columns}
          data={directionSlices}
          keyExtractor={(item) => item.dimension_value}
          emptyMessage="No direction breakdown available for this run."
        />
      </Card>
    </div>
  );
};
