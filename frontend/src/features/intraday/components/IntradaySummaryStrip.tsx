import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { Badge } from '@/components/ui/Badge';
import { MarketSessionInfo } from '@/lib/api/types';

export interface IntradaySummaryStripProps {
  activeCount?: number;
  triggeredCount?: number;
  session?: MarketSessionInfo | null;
  asOf?: string;
}

export const IntradaySummaryStrip: React.FC<IntradaySummaryStripProps> = ({
  activeCount = 0,
  triggeredCount = 0,
  session,
  asOf,
}) => {
  const window = session?.window || 'OUTSIDE';
  const isTrading = session?.is_trading_hour || false;
  const minutesRemaining = session?.minutes_remaining ?? -1;

  let sessionStatusLabel = 'CLOSED';
  let badgeVariant: 'positive' | 'warning' | 'neutral' = 'neutral';

  if (window === 'HISTORICAL') {
    sessionStatusLabel = 'HISTORICAL PIT';
    badgeVariant = 'neutral';
  } else if (isTrading) {
    sessionStatusLabel = `OPEN • ${window}`;
    badgeVariant = 'positive';
  }

  return (
    <Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-6)', alignItems: 'center' }}>
        <Metric
          label="Active Signals"
          value={activeCount}
          subtext="Armed & waiting entry"
        />
        <Metric
          label="Triggered in Session"
          value={triggeredCount}
          subtext="In execution"
        />
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
            Trading Session Window
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Badge variant={badgeVariant} size="md">
              {isTrading ? '🟢 ' : '🔴 '}{sessionStatusLabel}
            </Badge>
            {isTrading && minutesRemaining > 0 && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {minutesRemaining}m left
              </span>
            )}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
            Scanning Polling Cycle
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Badge variant={isTrading ? 'brand' : 'neutral'} size="sm">
              {isTrading ? '⚡ 15s AUTO-REFRESH' : '⏸ POLLING PAUSED'}
            </Badge>
            {asOf && (
              <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {new Date(asOf).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })} IST
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};
