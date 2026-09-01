import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { MarketSessionInfo } from '@/lib/api/types';

export interface MarketSessionIndicatorProps {
  sessionInfo?: MarketSessionInfo | null;
}

export const MarketSessionIndicator: React.FC<MarketSessionIndicatorProps> = ({ sessionInfo }) => {
  if (!sessionInfo) {
    return (
      <Badge variant="neutral" size="sm">
        ⚪ SESSION UNKNOWN
      </Badge>
    );
  }

  const { window, is_trading_hour, minutes_remaining } = sessionInfo;

  let badgeVariant: 'positive' | 'warning' | 'neutral' = 'neutral';
  let icon = '⚪';
  let label: string = window;

  if (window === 'HISTORICAL') {
    badgeVariant = 'neutral';
    icon = '📜';
    label = 'HISTORICAL PIT';
  } else if (is_trading_hour) {
    badgeVariant = 'positive';
    icon = '🟢';
    label = `OPEN • ${window}`;
  } else if (window === 'OUTSIDE') {
    badgeVariant = 'neutral';
    icon = '🔴';
    label = 'CLOSED';
  }

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}>
      <Badge variant={badgeVariant} size="sm">
        {icon} {label}
      </Badge>
      {is_trading_hour && minutes_remaining !== undefined && minutes_remaining > 0 && (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          ({minutes_remaining}m left)
        </span>
      )}
    </div>
  );
};
