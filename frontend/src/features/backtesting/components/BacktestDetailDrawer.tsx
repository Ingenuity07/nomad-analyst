import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { BacktestRun } from '@/lib/api/types';

export interface BacktestDetailDrawerProps {
  run: BacktestRun | null;
  onClose: () => void;
}

export const BacktestDetailDrawer: React.FC<BacktestDetailDrawerProps> = ({
  run,
  onClose,
}) => {
  if (!run) return null;

  const res = run.result;

  return (
    <div
      data-testid="backtest-detail-drawer"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-medium)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-5)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-4)',
        boxShadow: 'var(--shadow-medium)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {run.run_id}
            </span>
            <Badge variant={run.status === 'COMPLETE' ? 'positive' : run.status === 'FAILED' ? 'negative' : 'brand'} size="sm">
              {run.status}
            </Badge>
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Strategy Version: v{run.strategy_version} • Universe: {run.universe_name}
          </div>
        </div>

        <button onClick={onClose} aria-label="Close drawer" style={{ color: 'var(--text-muted)', fontSize: 'var(--text-md)', padding: 'var(--space-1)', cursor: 'pointer' }}>
          ✕
        </button>
      </div>

      {/* Configuration Snapshot */}
      <div>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
          Simulation Parameters
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>PERIOD</div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {run.start_date} → {run.end_date}
            </div>
          </div>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>HORIZON & TIMEFRAME</div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {run.horizon} ({run.timeframe})
            </div>
          </div>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>AMBIGUITY POLICY</div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {run.config?.ambiguity_policy || 'CONSERVATIVE'}
            </div>
          </div>
        </div>
      </div>

      {/* Result Metrics */}
      {res && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
            Key Performance Metrics
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>WIN RATE</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                {res.win_rate !== null ? `${(res.win_rate * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EXPECTANCY</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                {res.expectancy !== null ? `${res.expectancy >= 0 ? '+' : ''}${res.expectancy.toFixed(2)} R` : '—'}
              </div>
            </div>
            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TRADES</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                {res.triggered || 0} / {res.total_signals || 0}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Data Quality Warnings */}
      {run.data_quality_warnings && run.data_quality_warnings.length > 0 && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--warning)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
            ⚠ Data Quality & Bias Warnings
          </div>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', paddingLeft: 'var(--space-3)' }}>
            {run.data_quality_warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
