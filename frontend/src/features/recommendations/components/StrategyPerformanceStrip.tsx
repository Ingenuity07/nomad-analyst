import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { useStrategyPerformance } from '@/hooks/useStrategies';

export interface StrategyPerformanceStripProps {
  strategy: string;
  onStrategyChange: (st: string) => void;
}

export const StrategyPerformanceStrip: React.FC<StrategyPerformanceStripProps> = ({
  strategy,
  onStrategyChange,
}) => {
  const { data, isLoading, error } = useStrategyPerformance(strategy);

  return (
    <Card
      header="Audited Strategy Performance Attribution"
      action={
        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
          <button
            onClick={() => onStrategyChange('DELIVERY_SWING')}
            style={{
              fontSize: 'var(--text-xs)',
              padding: 'var(--space-1) var(--space-2)',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: strategy === 'DELIVERY_SWING' ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
              color: strategy === 'DELIVERY_SWING' ? '#FFFFFF' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            Delivery / Swing
          </button>
          <button
            onClick={() => onStrategyChange('INTRADAY')}
            style={{
              fontSize: 'var(--text-xs)',
              padding: 'var(--space-1) var(--space-2)',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: strategy === 'INTRADAY' ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
              color: strategy === 'INTRADAY' ? '#FFFFFF' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            Intraday
          </button>
        </div>
      }
    >
      {isLoading ? (
        <Skeleton height="70px" />
      ) : error || !data ? (
        <div style={{ padding: 'var(--space-3)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
          Performance metrics currently unavailable for {strategy}.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 'var(--space-4)', alignItems: 'center' }}>
            <Metric
              label="Win Rate"
              value={`${(data.win_rate * 100).toFixed(1)}%`}
              subtext={`${data.wins} Wins / ${data.losses} Losses`}
            />
            <Metric
              label="Average Expectancy"
              value={data.avg_r_multiple !== null ? `${data.avg_r_multiple >= 0 ? '+' : ''}${data.avg_r_multiple.toFixed(2)} R` : '—'}
              subtext="Net R-multiple per signal"
            />
            <Metric
              label="Sample Size"
              value={`${data.sample_size} Trades`}
              subtext="Completed & evaluated"
            />

            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
                Statistical Reliability
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Badge variant={data.is_small_sample ? 'warning' : 'positive'} size="md">
                  {data.is_small_sample ? '⚠ SMALL SAMPLE (< 30 TRADES)' : '✓ STATISTICALLY ADEQUATE'}
                </Badge>
              </div>
            </div>
          </div>

          {data.is_small_sample && (
            <div
              style={{
                fontSize: 'var(--text-2xs)',
                color: 'var(--warning)',
                backgroundColor: 'var(--warning-bg)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--warning-border)',
              }}
            >
              Note: Sample size is below the 30-trade threshold. Win rate and average R metrics should not be treated as long-term statistical certainties.
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
