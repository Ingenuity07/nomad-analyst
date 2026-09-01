import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { StockRecommendation } from '@/lib/api/types';

export interface ActiveSignalsTableProps {
  recommendations: StockRecommendation[];
  selectedId?: string | null;
  onSelect: (item: StockRecommendation) => void;
  isLoading?: boolean;
}

export const ActiveSignalsTable: React.FC<ActiveSignalsTableProps> = ({
  recommendations,
  selectedId,
  onSelect,
  isLoading = false,
}) => {
  const columns: TableColumn<StockRecommendation>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (item) => (
        <div>
          <div style={{ fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {item.symbol}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            {item.company_name}
          </div>
        </div>
      ),
    },
    {
      key: 'signal',
      header: 'Signal',
      render: (item) => {
        const isBuy = item.signal === 'BUY';
        const isSell = item.signal === 'SELL';
        return (
          <Badge variant={isBuy ? 'positive' : isSell ? 'negative' : 'neutral'} size="sm">
            {isBuy ? '▲ BUY' : isSell ? '▼ SELL' : '● NO ACTION'}
          </Badge>
        );
      },
    },
    {
      key: 'horizon',
      header: 'Horizon',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          {item.horizon === 'DELIVERY_SWING' ? 'Swing (2-15d)' : item.horizon === 'INTRADAY' ? 'Intraday' : item.horizon}
        </span>
      ),
    },
    {
      key: 'setup_type',
      header: 'Setup',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
          {item.setup_type}
        </span>
      ),
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (item) => {
        const conf = item.confidence;
        const variant = conf === 'HIGH' ? 'positive' : conf === 'MEDIUM' ? 'brand' : 'neutral';
        return <Badge variant={variant} size="sm">{conf}</Badge>;
      },
    },
    {
      key: 'entry_price',
      header: 'Entry',
      isNumeric: true,
      render: (item) => (
        <div>
          <div style={{ color: 'var(--text-primary)' }}>
            {item.entry_price ? `₹${item.entry_price.toFixed(2)}` : 'Market'}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            {item.entry_type}
          </div>
        </div>
      ),
    },
    {
      key: 'stop_price',
      header: 'Stop Loss',
      isNumeric: true,
      render: (item) => (
        <span style={{ color: 'var(--negative)' }}>
          {item.stop_price ? `₹${item.stop_price.toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'target_price',
      header: 'Target 1',
      isNumeric: true,
      render: (item) => (
        <span style={{ color: 'var(--positive)' }}>
          {item.target_price ? `₹${item.target_price.toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'risk_reward_ratio',
      header: 'R : R',
      isNumeric: true,
      render: (item) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          {item.risk_reward_ratio ? `${item.risk_reward_ratio.toFixed(2)}:1` : '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => {
        const variant = item.status === 'ACTIVE' ? 'brand' : item.status === 'TRIGGERED' ? 'positive' : 'neutral';
        return <Badge variant={variant} size="sm">{item.status}</Badge>;
      },
    },
    {
      key: 'generated_at',
      header: 'Generated',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {new Date(item.generated_at || item.as_of).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' })}
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
      data={recommendations}
      keyExtractor={(item) => item.id}
      onRowClick={onSelect}
      emptyMessage={isLoading ? 'Loading active recommendations...' : 'No active or triggered recommendations match the selected filters.'}
    />
  );
};
