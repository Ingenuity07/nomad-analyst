import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { MarketIndexItem } from '@/lib/api/types';

export interface IndexStripProps {
  indices?: MarketIndexItem[];
  isLoading?: boolean;
}

const DEFAULT_DISPLAY_INDICES = [
  { symbol: '^NSEI', name: 'NIFTY 50' },
  { symbol: '^NSEBANK', name: 'NIFTY BANK' },
  { symbol: '^BSESN', name: 'BSE SENSEX' },
  { symbol: '^CNXIT', name: 'NIFTY IT' },
];

export const IndexStrip: React.FC<IndexStripProps> = ({ indices = [], isLoading = false }) => {
  const indexMap = new Map<string, MarketIndexItem>();
  indices.forEach((idx) => indexMap.set(idx.symbol, idx));

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 'var(--space-3)',
        width: '100%',
      }}
    >
      {DEFAULT_DISPLAY_INDICES.map((def) => {
        const item = indexMap.get(def.symbol);
        const hasPrice = item && item.price !== null && item.price !== undefined;
        const changePct = item?.change_percent ?? null;
        const isPositive = changePct !== null && changePct > 0;
        const isNegative = changePct !== null && changePct < 0;

        return (
          <div
            key={def.symbol}
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-3) var(--space-4)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)' }}>
                {def.name}
              </span>
              <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {def.symbol}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 'var(--space-1)' }}>
              <span
                style={{
                  fontSize: 'var(--text-lg)',
                  fontWeight: 'var(--weight-bold)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {isLoading ? (
                  '••••••'
                ) : hasPrice ? (
                  `₹${item!.price!.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                ) : (
                  '—'
                )}
              </span>

              {hasPrice && changePct !== null ? (
                <Badge variant={isPositive ? 'positive' : isNegative ? 'negative' : 'neutral'} size="sm">
                  {isPositive ? '▲ +' : isNegative ? '▼ ' : ''}
                  {changePct.toFixed(2)}%
                </Badge>
              ) : (
                <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  UNAVAILABLE
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
