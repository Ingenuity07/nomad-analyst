import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { StockRecommendation } from '@/lib/api/types';

export interface IntradaySignalTableProps {
  signals: StockRecommendation[];
  selectedId?: string | null;
  onSelectSignal: (item: StockRecommendation) => void;
  onCheckDataQuality: (symbol: string, timeframe: string) => void;
  isLoading?: boolean;
}

export const IntradaySignalTable: React.FC<IntradaySignalTableProps> = ({
  signals,
  selectedId,
  onSelectSignal,
  onCheckDataQuality,
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
      header: 'Direction',
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
      key: 'setup_type',
      header: 'Setup Type',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {item.setup_type}
        </span>
      ),
    },
    {
      key: 'timeframe',
      header: 'TF',
      width: '50px',
      render: (item) => (
        <Badge variant="neutral" size="sm">
          {item.timeframe || '5m'}
        </Badge>
      ),
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (item) => {
        const conf = item.confidence || 'MEDIUM';
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
        const st = item.status;
        const variant =
          st === 'ACTIVE'
            ? 'brand'
            : st === 'TRIGGERED'
            ? 'positive'
            : st === 'TARGET_HIT'
            ? 'positive'
            : st === 'STOPPED'
            ? 'negative'
            : 'neutral';
        return <Badge variant={variant} size="sm">{st}</Badge>;
      },
    },
    {
      key: 'as_of',
      header: 'Generated',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {new Date(item.generated_at || item.as_of).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      width: '130px',
      render: (item) => (
        <div style={{ display: 'flex', gap: 'var(--space-1-5)' }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelectSignal(item);
            }}
            style={{
              fontSize: 'var(--text-xs)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: item.id === selectedId ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
              color: item.id === selectedId ? '#FFFFFF' : 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Inspect →
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onCheckDataQuality(item.symbol, item.timeframe || '5m');
            }}
            title="Inspect 5m intraday data quality readiness"
            style={{
              fontSize: 'var(--text-xs)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: 'transparent',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            🔍 DQ
          </button>
        </div>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      data={signals}
      keyExtractor={(item) => item.id || item.symbol}
      onRowClick={onSelectSignal}
      emptyMessage={isLoading ? 'Scanning active intraday signals...' : 'No active intraday signals match the selected filters.'}
    />
  );
};
