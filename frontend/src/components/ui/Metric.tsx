import React from 'react';

export interface MetricProps {
  label: string;
  value: React.ReactNode;
  delta?: number;
  deltaSuffix?: string;
  prefix?: string;
  suffix?: string;
  isPositiveGood?: boolean;
  subtext?: string;
}

export const Metric: React.FC<MetricProps> = ({
  label,
  value,
  delta,
  deltaSuffix = '%',
  prefix,
  suffix,
  isPositiveGood = true,
  subtext,
}) => {
  const isPositive = delta !== undefined && delta > 0;

  const deltaColor =
    delta === undefined || delta === 0
      ? 'var(--text-muted)'
      : (isPositive && isPositiveGood) || (!isPositive && !isPositiveGood)
      ? 'var(--positive)'
      : 'var(--negative)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 'var(--weight-medium)' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-2)' }}>
        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
          {prefix}{value}{suffix}
        </div>
        {delta !== undefined && (
          <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', fontWeight: 'var(--weight-medium)', color: deltaColor }}>
            {delta > 0 ? '+' : ''}{delta.toFixed(2)}{deltaSuffix}
          </div>
        )}
      </div>
      {subtext && <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>{subtext}</div>}
    </div>
  );
};
