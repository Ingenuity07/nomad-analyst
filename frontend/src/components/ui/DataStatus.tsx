import React from 'react';
import { Badge } from './Badge';

export type FreshnessState = 'LIVE' | 'STALE' | 'INCOMPLETE' | 'UNAVAILABLE' | 'LOADING';

export interface DataStatusProps {
  status: FreshnessState;
  source?: string;
  lastUpdated?: string;
}

export const DataStatus: React.FC<DataStatusProps> = ({
  status,
  source,
  lastUpdated,
}) => {
  const getBadgeVariant = () => {
    switch (status) {
      case 'LIVE':
        return 'positive';
      case 'STALE':
      case 'INCOMPLETE':
        return 'warning';
      case 'UNAVAILABLE':
        return 'negative';
      case 'LOADING':
      default:
        return 'neutral';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'LIVE':
        return '🟢';
      case 'STALE':
        return '🟡';
      case 'INCOMPLETE':
        return '🟠';
      case 'UNAVAILABLE':
        return '🔴';
      case 'LOADING':
      default:
        return '⏳';
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}>
      <Badge variant={getBadgeVariant()} size="sm">
        {getStatusIcon()} {status}
      </Badge>
      {source && (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          [{source}]
        </span>
      )}
      {lastUpdated && (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {lastUpdated}
        </span>
      )}
    </div>
  );
};
