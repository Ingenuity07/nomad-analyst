import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { BacktestRun } from '@/lib/api/types';

export interface HistoricalBacktestsTableProps {
  runs: BacktestRun[];
  selectedId?: string | null;
  onSelect: (run: BacktestRun) => void;
  isLoading?: boolean;
}

export const HistoricalBacktestsTable: React.FC<HistoricalBacktestsTableProps> = ({
  runs,
  selectedId,
  onSelect,
  isLoading = false,
}) => {
  const columns: TableColumn<BacktestRun>[] = [
    {
      key: 'run_id',
      header: 'Run Identifier',
      render: (item) => (
        <div>
          <div style={{ fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
            {item.run_id}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            v{item.strategy_version} • {new Date(item.started_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      ),
    },
    {
      key: 'universe_name',
      header: 'Universe',
      render: (item) => <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>{item.universe_name}</span>,
    },
    {
      key: 'horizon',
      header: 'Horizon',
      render: (item) => <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{item.horizon}</span>,
    },
    {
      key: 'date_range',
      header: 'Period',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {item.start_date} → {item.end_date}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => {
        const variant = item.status === 'COMPLETE' ? 'positive' : item.status === 'FAILED' ? 'negative' : 'brand';
        return <Badge variant={variant} size="sm">{item.status}</Badge>;
      },
    },
    {
      key: 'win_rate',
      header: 'Win Rate',
      isNumeric: true,
      render: (item) => {
        const wr = item.result?.win_rate;
        return <span>{wr !== null && wr !== undefined ? `${(wr * 100).toFixed(1)}%` : '—'}</span>;
      },
    },
    {
      key: 'total_signals',
      header: 'Trades',
      isNumeric: true,
      render: (item) => <span>{item.result?.triggered ?? item.result?.total_signals ?? '—'}</span>,
    },
    {
      key: 'actions',
      header: '',
      width: '100px',
      render: (item) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSelect(item);
          }}
          style={{
            fontSize: 'var(--text-xs)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-xs)',
            backgroundColor: item.id === selectedId ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
            color: item.id === selectedId ? '#FFFFFF' : 'var(--text-primary)',
            border: '1px solid var(--border-subtle)',
            cursor: 'pointer',
          }}
        >
          View Run →
        </button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      data={runs}
      keyExtractor={(item) => item.id}
      onRowClick={onSelect}
      emptyMessage={isLoading ? 'Loading backtest history...' : 'No historical backtest runs have been recorded.'}
    />
  );
};
