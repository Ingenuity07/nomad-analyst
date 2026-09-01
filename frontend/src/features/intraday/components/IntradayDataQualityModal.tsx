import React from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { useIntradayDataQuality } from '@/hooks/useIntradayDataQuality';

export interface IntradayDataQualityModalProps {
  symbol: string | null;
  timeframe: string;
  isOpen: boolean;
  onClose: () => void;
}

export const IntradayDataQualityModal: React.FC<IntradayDataQualityModalProps> = ({
  symbol,
  timeframe,
  isOpen,
  onClose,
}) => {
  const { data, isLoading, error, refetch } = useIntradayDataQuality(
    symbol || '',
    timeframe,
    { enabled: isOpen && Boolean(symbol) }
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Intraday Data Quality Readiness — ${symbol || ''} (${timeframe})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <Skeleton height="36px" />
            <Skeleton height="36px" />
            <Skeleton height="60px" />
          </div>
        ) : error ? (
          <div style={{ padding: 'var(--space-4)', backgroundColor: 'var(--negative-bg)', color: 'var(--negative)', borderRadius: 'var(--radius-sm)' }}>
            Failed to evaluate intraday data readiness.
          </div>
        ) : data ? (
          <>
            {/* Readiness Summary */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>READINESS STATUS</div>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: data.is_ready ? 'var(--positive)' : 'var(--warning)', marginTop: '2px' }}>
                  {data.is_ready ? 'READY FOR STRATEGY EXECUTION' : 'INSUFFICIENT DATA / NOT READY'}
                </div>
              </div>
              <Badge variant={data.is_ready ? 'positive' : 'warning'} size="md">
                {data.is_ready ? 'PASSED' : 'BLOCKED'}
              </Badge>
            </div>

            {/* Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
              <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>BAR COUNT</div>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {data.bar_count} / {data.required_bars}
                </div>
              </div>

              <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TIMEFRAME</div>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {data.timeframe}
                </div>
              </div>

              <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EVALUATED AS OF</div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(data.checked_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })}
                </div>
              </div>
            </div>

            {/* Checks Passed */}
            {data.checks_passed && data.checks_passed.length > 0 && (
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--positive)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
                  ✓ Passed Checks
                </div>
                <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
                  {data.checks_passed.map((chk, i) => (
                    <li key={i} style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <span style={{ color: 'var(--positive)' }}>•</span>
                      <span>{chk}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Checks Failed / Reason */}
            {data.checks_failed && data.checks_failed.length > 0 && (
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--negative)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
                  ✕ Failed Checks / Impediments
                </div>
                <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  {data.checks_failed.map((chk, i) => (
                    <li key={i} style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <span style={{ color: 'var(--negative)' }}>•</span>
                      <span>{chk}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : null}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)' }}>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            ↻ Re-check Readiness
          </Button>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
};
