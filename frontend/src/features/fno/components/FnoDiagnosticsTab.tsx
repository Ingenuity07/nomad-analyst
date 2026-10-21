import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Metric } from '@/components/ui/Metric';
import { useFnoDiagnostics } from '@/hooks/useFnoData';

export const FnoDiagnosticsTab: React.FC = () => {
  const { data, isLoading, error, refetch } = useFnoDiagnostics();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Skeleton height={140} />
        <Skeleton height={240} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to Load Diagnostics"
        message={error instanceof Error ? error.message : 'Unable to query diagnostics metrics'}
        onRetry={() => refetch()}
      />
    );
  }

  const bars = data?.bars;
  const quotes = data?.quotes;
  const components = data?.components;

  const getQualityVariant = (status?: string): 'positive' | 'negative' | 'warning' | 'neutral' => {
    switch (status) {
      case 'EXCELLENT':
        return 'positive';
      case 'DEGRADED':
        return 'warning';
      default:
        return 'negative';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* 1-Minute Bar Completeness Card */}
      <Card
        header="1-Minute Option Bar Completeness"
        action={
          <Badge variant={getQualityVariant(bars?.quality_status)} size="sm">
            {bars?.quality_status || 'UNKNOWN'}
          </Badge>
        }
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--space-4)',
            paddingTop: 'var(--space-2)',
          }}
        >
          <Metric
            label="TOTAL 1M BARS TODAY"
            value={`${bars?.total_today ?? 0}`}
            subtext="fno_option_ohlcvbar"
          />
          <Metric
            label="COMPLETE BARS"
            value={`${bars?.complete_count ?? 0}`}
            subtext="Uninterrupted"
          />
          <Metric
            label="PARTIAL BARS"
            value={`${bars?.partial_count ?? 0}`}
            subtext="Disconnect overlap"
          />
          <Metric
            label="PARTIAL BAR RATIO"
            value={`${bars?.partial_ratio_pct ?? 0}%`}
            subtext="Target < 2.0%"
          />
        </div>
        <div
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            marginTop: 'var(--space-3)',
            paddingTop: 'var(--space-2)',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          A bar is flagged partial if a network reconnect gap coincided with the 1-minute interval. Strategy entries reject breakout evaluations on partial bars.
        </div>
      </Card>

      {/* Quote Snapshot Health Card */}
      <Card header="High-Frequency Quote Snapshot Ingestion">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--space-4)',
            paddingTop: 'var(--space-2)',
          }}
        >
          <Metric
            label="QUOTES RECORDED TODAY"
            value={`${quotes?.total_today ?? 0}`}
            subtext="Rolling 5-day retention"
          />
          <Metric
            label="EXECUTION ELIGIBLE"
            value={`${quotes?.eligible_count ?? 0}`}
            subtext="Tight spread & fresh"
          />
          <Metric
            label="STALE QUOTES (>3.0s)"
            value={`${quotes?.stale_count ?? 0}`}
            subtext="Rejected for fills"
          />
          <Metric
            label="FEED LATENCY"
            value={quotes?.latest_feed_latency_seconds !== null && quotes?.latest_feed_latency_seconds !== undefined ? `${quotes.latest_feed_latency_seconds}s` : '—'}
            subtext="Arrival vs Exchange"
          />
        </div>
        <div
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            marginTop: 'var(--space-3)',
            paddingTop: 'var(--space-2)',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          Quotes are captured under a rolling 5-day retention table (`fno_option_quote_snapshot`) with 5-level market depth and exchange timestamp verification.
        </div>
      </Card>

      {/* System Infrastructure Health */}
      <Card header="Engine & Infrastructure Status">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>PostgreSQL Database Connection</span>
            <Badge variant={components?.postgresql === 'HEALTHY' ? 'positive' : 'negative'} size="sm">
              {components?.postgresql || 'UNKNOWN'}
            </Badge>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Live Ticker Daemon {components?.ticker_pid ? `(PID ${components.ticker_pid})` : ''}
            </span>
            <Badge variant={components?.ticker_daemon === 'RUNNING' ? 'positive' : 'negative'} size="sm">
              {components?.ticker_daemon || 'STOPPED'}
            </Badge>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Statutory Fee Schedule</span>
            <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {components?.fee_schedule || 'NSE_CIRCULAR_73061_0.03553%'}
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Execution Engine Mode</span>
            <Badge variant="brand" size="sm">
              {components?.paper_execution_mode || 'STRICT_SIMULATED'}
            </Badge>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Session Reporting Date</span>
            <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {data?.session_date || '—'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
};
