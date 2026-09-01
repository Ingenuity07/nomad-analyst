import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { RecommendationOutcome } from '@/lib/api/types';

export interface HistoricalOutcomesTableProps {
  outcomes: RecommendationOutcome[];
  selectedId?: string | null;
  onSelect: (item: RecommendationOutcome) => void;
  isLoading?: boolean;
}

export const HistoricalOutcomesTable: React.FC<HistoricalOutcomesTableProps> = ({
  outcomes,
  selectedId,
  onSelect,
  isLoading = false,
}) => {
  const columns: TableColumn<RecommendationOutcome>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (item) => (
        <div>
          <div style={{ fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {item.symbol}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            {item.horizon}
          </div>
        </div>
      ),
    },
    {
      key: 'signal',
      header: 'Signal',
      render: (item) => {
        const sig = item.signal || 'BUY';
        const isBuy = sig === 'BUY';
        return (
          <Badge variant={isBuy ? 'positive' : 'negative'} size="sm">
            {isBuy ? '▲ BUY' : '▼ SELL'}
          </Badge>
        );
      },
    },
    {
      key: 'setup_type',
      header: 'Setup',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
          {item.setup_type || '—'}
        </span>
      ),
    },
    {
      key: 'exit_reason',
      header: 'Exit Reason',
      render: (item) => {
        const reason = item.exit_reason;
        const variant =
          reason === 'TARGET_HIT' || reason === 'TARGET_2_HIT'
            ? 'positive'
            : reason === 'STOP_HIT'
            ? 'negative'
            : 'neutral';
        return <Badge variant={variant} size="sm">{reason || 'COMPLETED'}</Badge>;
      },
    },
    {
      key: 'actual_entry_price',
      header: 'Entry Price',
      isNumeric: true,
      render: (item) => (
        <span style={{ color: 'var(--text-primary)' }}>
          {item.actual_entry_price ? `₹${Number(item.actual_entry_price).toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'actual_exit_price',
      header: 'Exit Price',
      isNumeric: true,
      render: (item) => (
        <span style={{ color: 'var(--text-primary)' }}>
          {item.actual_exit_price ? `₹${Number(item.actual_exit_price).toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'net_pnl_percent',
      header: 'Net P&L',
      isNumeric: true,
      render: (item) => {
        if (item.net_pnl_percent === null || item.net_pnl_percent === undefined) return <span>—</span>;
        const pnl = Number(item.net_pnl_percent);
        const isPos = pnl >= 0;
        return (
          <span style={{ fontWeight: 'var(--weight-bold)', color: isPos ? 'var(--positive)' : 'var(--negative)' }}>
            {isPos ? '+' : ''}{(pnl * 100).toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'r_multiple',
      header: 'R-Multiple',
      isNumeric: true,
      render: (item) => {
        if (item.r_multiple === null || item.r_multiple === undefined) return <span>—</span>;
        const r = Number(item.r_multiple);
        const isPos = r >= 0;
        return (
          <span style={{ fontWeight: 'var(--weight-bold)', color: isPos ? 'var(--positive)' : 'var(--negative)' }}>
            {isPos ? '+' : ''}{r.toFixed(2)} R
          </span>
        );
      },
    },
    {
      key: 'excursion',
      header: 'MFE / MAE',
      render: (item) => (
        <div style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)' }}>
          <span style={{ color: 'var(--positive)' }}>+{((item.max_favorable_excursion || 0) * 100).toFixed(1)}%</span>
          {' / '}
          <span style={{ color: 'var(--negative)' }}>-{((item.max_adverse_excursion || 0) * 100).toFixed(1)}%</span>
        </div>
      ),
    },
    {
      key: 'holding_duration_bars',
      header: 'Bars',
      isNumeric: true,
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          {item.holding_duration_bars !== null ? `${item.holding_duration_bars}b` : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      width: '90px',
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
          }}
        >
          Inspect →
        </button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      data={outcomes}
      keyExtractor={(item) => item.id}
      onRowClick={onSelect}
      emptyMessage={isLoading ? 'Loading historical outcomes...' : 'No historical trade outcomes match the selected filters.'}
    />
  );
};
