import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableColumn } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { PaperTradeLedgerItem } from '@/lib/api/types';
import { useFnoStrategy } from '@/hooks/useFnoData';

export const FnoStrategyTab: React.FC = () => {
  const { data, isLoading, error, refetch } = useFnoStrategy();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Skeleton height={140} />
        <Skeleton height={280} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to Load Strategy State"
        message={error instanceof Error ? error.message : 'Unable to query strategy telemetry'}
        onRetry={() => refetch()}
      />
    );
  }

  const openingRange = data?.opening_range;
  const auditTrail = data?.audit_trail;
  const strategy = data?.strategy;

  const barCount = openingRange?.available_bars ?? 0;
  const expectedBars = openingRange?.expected_bars ?? 15;
  const isRuntimeAvailable = Boolean(strategy?.runtime_telemetry_available);
  const isRangeLocked = openingRange?.status === 'LOCKED' && openingRange?.runtime_established === true;
  const isRangeForming = openingRange?.status === 'FORMING' && isRuntimeAvailable;
  const isRangeFailed = openingRange?.status === 'FAIL_CLOSED' || openingRange?.status === 'INCOMPLETE';

  // Reliable progress percentage strictly governed by runtime telemetry
  const effectiveProgressPct = isRangeLocked
    ? 100
    : isRangeForming
    ? Math.min(Math.round((barCount / expectedBars) * 100), 100)
    : 0;

  const getProgressLabel = () => {
    if (!isRuntimeAvailable || openingRange?.status === 'UNAVAILABLE') {
      return 'UNAVAILABLE (Awaiting Runtime)';
    }
    if (isRangeLocked) {
      return '15 / 15 Bars (100%) — Range Locked';
    }
    if (isRangeForming) {
      return `${barCount} / ${expectedBars} Bars (${effectiveProgressPct}%) — Forming`;
    }
    if (isRangeFailed) {
      return `INCOMPLETE (${barCount} / ${expectedBars} Bars) — Entries Prohibited`;
    }
    return '0 / 15 Bars (0%) — Pre-Market';
  };

  const getRangeBadgeVariant = (status?: string): 'positive' | 'negative' | 'warning' | 'neutral' => {
    if (!isRuntimeAvailable || status === 'UNAVAILABLE') return 'neutral';
    switch (status) {
      case 'LOCKED':
        return 'positive';
      case 'FORMING':
        return 'warning';
      case 'FAIL_CLOSED':
      case 'INCOMPLETE':
        return 'negative';
      default:
        return 'neutral';
    }
  };

  const signalColumns: TableColumn<PaperTradeLedgerItem>[] = [
    {
      key: 'entry_timestamp',
      header: 'Evaluated Time (IST)',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
          {new Date(row.entry_timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
        </span>
      ),
    },
    {
      key: 'tradingsymbol',
      header: 'Contract',
      render: (row) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)' }}>
          {row.tradingsymbol}
        </span>
      ),
    },
    {
      key: 'option_type',
      header: 'Type',
      align: 'center',
      render: (row) => (
        <Badge variant={row.option_type === 'CE' ? 'positive' : 'negative'} size="sm">
          {row.option_type}
        </Badge>
      ),
    },
    {
      key: 'strike_price',
      header: 'Strike',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {Number(row.strike_price).toFixed(0)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Evaluation Status',
      render: (row) => {
        let variant: 'positive' | 'negative' | 'warning' | 'neutral' = 'neutral';
        if (row.status === 'OPEN' || row.status === 'CLOSED') variant = 'positive';
        else if (row.status === 'REJECTED') variant = 'negative';
        else variant = 'warning';

        return (
          <Badge variant={variant} size="sm">
            {row.status}
          </Badge>
        );
      },
    },
    {
      key: 'rejection_reason',
      header: 'Rejection Reason / Guard',
      render: (row) => (
        <span style={{ fontSize: 'var(--text-xs)', color: row.rejection_reason ? 'var(--negative)' : 'var(--text-muted)' }}>
          {row.rejection_reason || '—'}
        </span>
      ),
    },
    {
      key: 'entry_fill_price',
      header: 'Fill Price',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {row.entry_fill_price ? `₹${Number(row.entry_fill_price).toFixed(2)}` : '—'}
        </span>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {!strategy?.runtime_telemetry_available && (
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-base)' }}>ℹ️</span>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                Runtime Strategy Telemetry Offline
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                Live evaluation metrics and range locks will synchronize when the ticker daemon evaluates STRAT-ORB-15M during market sessions.
              </div>
            </div>
          </div>
          <Badge variant="neutral" size="sm">AWAITING RUNTIME</Badge>
        </div>
      )}

      {/* Strategy Status & Opening Range Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
        {/* Strategy Specification Card */}
        <Card header="STRAT-ORB-15M Specification">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Strategy Name</span>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                {strategy?.name || 'NIFTY 15m Opening Range Breakout'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Version & Rules</span>
              <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                v{strategy?.version || '1.0.0'} (Strict Max 1 Position)
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Runtime State</span>
              <Badge variant={strategy?.status === 'ACTIVE' ? 'positive' : strategy?.status === 'UNAVAILABLE' ? 'neutral' : 'warning'} size="sm">
                {strategy?.status || 'IDLE'}
              </Badge>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Evaluations Today</span>
              <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {auditTrail?.evaluations_count !== null && auditTrail?.evaluations_count !== undefined ? auditTrail.evaluations_count : '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Rejections Today</span>
              <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: auditTrail?.rejections_count ? 'var(--warning)' : 'var(--text-muted)' }}>
                {auditTrail?.rejections_count ?? 0}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Active Evaluation Window</span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                09:30–15:15 IST
              </span>
            </div>
          </div>
        </Card>

        {/* Opening Range Readiness Card */}
        <Card
          header="Opening Range Meter (09:15–09:30 IST)"
          action={
            <Badge variant={getRangeBadgeVariant(openingRange?.status)} size="sm">
              {openingRange?.status || 'PENDING'}
            </Badge>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Bar Completeness</span>
                <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                  {getProgressLabel()}
                </span>
              </div>
              <div
                style={{
                  height: '6px',
                  width: '100%',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  borderRadius: 'var(--radius-full)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${effectiveProgressPct}%`,
                    backgroundColor: isRangeLocked
                      ? 'var(--positive)'
                      : isRangeFailed
                      ? 'var(--negative)'
                      : isRangeForming
                      ? 'var(--brand-primary)'
                      : 'transparent',
                    transition: 'width 0.4s ease',
                  }}
                />
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: 'var(--space-1)' }}>
                {!isRuntimeAvailable || openingRange?.status === 'UNAVAILABLE'
                  ? 'Historical database bars alone do not establish a valid range without active strategy daemon verification.'
                  : isRangeLocked
                  ? 'Complete 15-minute range verified and locked for breakout evaluations.'
                  : isRangeFailed
                  ? 'Window had missing minutes or corrupt bars. Strategy fails closed; breakout entries prohibited.'
                  : '09:15–09:30 IST window forming minute-by-minute.'}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-2)', paddingTop: 'var(--space-1)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>RANGE HIGH</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: isRangeLocked ? 'var(--positive)' : 'var(--text-muted)' }}>
                  {isRangeLocked && openingRange?.range_high ? `₹${openingRange.range_high.toFixed(2)}` : '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>RANGE LOW</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: isRangeLocked ? 'var(--negative)' : 'var(--text-muted)' }}>
                  {isRangeLocked && openingRange?.range_low ? `₹${openingRange.range_low.toFixed(2)}` : '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>WIDTH</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: isRangeLocked ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {isRangeLocked && openingRange?.range_width ? `${openingRange.range_width} pts` : '—'}
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Signal Audit Trail & Rejections */}
      <Card
        header="Signal Evaluations & Audit Trail"
        action={
          auditTrail?.rejection_summary && Object.keys(auditTrail.rejection_summary).length > 0 ? (
            <div style={{ display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
              {Object.entries(auditTrail.rejection_summary).map(([reason, count]) => (
                <Badge key={reason} variant="neutral" size="sm">
                  {reason}: {count}
                </Badge>
              ))}
            </div>
          ) : undefined
        }
      >
        {!auditTrail?.recent_signals || auditTrail.recent_signals.length === 0 ? (
          <EmptyState
            title="No Signal Evaluations Recorded Today"
            description="STRAT-ORB-15M evaluations emit signals only when a breakout occurs outside the locked opening range window."
          />
        ) : (
          <Table
            columns={signalColumns}
            data={auditTrail.recent_signals}
            keyExtractor={(row) => String(row.trade_id || row.signal_id)}
          />
        )}
      </Card>
    </div>
  );
};
