import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { MarketIndexItem, MarketSessionInfo, DataFreshness } from '@/lib/api/types';

export interface BenchmarkRegimeBarProps {
  indices: MarketIndexItem[];
  session?: MarketSessionInfo;
  freshness?: DataFreshness;
}

export const BenchmarkRegimeBar: React.FC<BenchmarkRegimeBarProps> = ({
  indices = [],
  session,
  freshness,
}) => {
  const getTrendBadge = (regime?: string) => {
    const r = (regime || 'UNKNOWN').toUpperCase();
    if (r === 'BULLISH') return <Badge variant="positive" size="sm">BULLISH TREND</Badge>;
    if (r === 'BEARISH') return <Badge variant="negative" size="sm">BEARISH TREND</Badge>;
    return <Badge variant="neutral" size="sm">SIDEWAYS</Badge>;
  };

  return (
    <div
      data-testid="benchmark-regime-bar"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-4) var(--space-5)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
      }}
    >
      {/* Top row: Session window & data freshness */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 'var(--weight-semibold)' }}>
            Trading Session:
          </span>
          <Badge variant={session?.is_trading_hour ? 'positive' : 'neutral'} size="sm">
            {session?.window || 'HISTORICAL'}
          </Badge>
          {session?.is_trading_hour && session?.minutes_remaining !== undefined && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              ({session.minutes_remaining}m remaining)
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          <span>Freshness:</span>
          <Badge variant={freshness?.status === 'LIVE' ? 'positive' : 'neutral'} size="sm">
            {freshness?.status || 'PIT SAFE'}
          </Badge>
        </div>
      </div>

      {/* Benchmarks grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 'var(--space-3)',
        }}
      >
        {indices.map((idx) => {
          const isPositive = (idx.change_percent ?? 0) >= 0;
          return (
            <div
              key={idx.symbol}
              style={{
                backgroundColor: 'var(--bg-surface-sunken)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: 'var(--space-3)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1-5)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                  {idx.name || idx.symbol}
                </span>
                {getTrendBadge(idx.regime)}
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-2)' }}>
                <span style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {idx.price ? `₹${idx.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </span>
                {idx.change_percent !== null && idx.change_percent !== undefined && (
                  <span
                    style={{
                      fontSize: 'var(--text-xs)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 'var(--weight-semibold)',
                      color: isPositive ? 'var(--positive)' : 'var(--negative)',
                    }}
                  >
                    {isPositive ? '+' : ''}
                    {Number(idx.change_percent).toFixed(2)}%
                  </span>
                )}
              </div>

              {idx.above_sma_200 !== undefined && idx.above_sma_200 !== null && (
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                  SMA 200: {idx.above_sma_200 ? '✅ Above 200-day average' : '⚠️ Below 200-day average'}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
