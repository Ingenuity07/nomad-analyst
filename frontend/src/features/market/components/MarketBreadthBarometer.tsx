import React from 'react';
import { Card } from '@/components/ui/Card';
import { MarketBreadth } from '@/lib/api/types';

export interface MarketBreadthBarometerProps {
  breadth?: MarketBreadth | null;
}

export const MarketBreadthBarometer: React.FC<MarketBreadthBarometerProps> = ({ breadth }) => {
  const advances = breadth?.advances ?? breadth?.advancing ?? 0;
  const declines = breadth?.declines ?? breadth?.declining ?? 0;
  const unchanged = breadth?.unchanged ?? 0;
  const total = advances + declines + unchanged;

  const advPct = total > 0 ? (advances / total) * 100 : 50;
  const decPct = total > 0 ? (declines / total) * 100 : 50;
  const unchPct = total > 0 ? (unchanged / total) * 100 : 0;

  const adRatio = breadth?.advance_decline_ratio ?? (declines > 0 ? advances / declines : advances);
  const aboveSma50 = breadth?.participation?.pct_above_sma50 ?? breadth?.pct_above_50_sma ?? null;
  const aboveSma200 = breadth?.participation?.pct_above_sma200 ?? breadth?.pct_above_200_sma ?? null;

  return (
    <Card header="Market Breadth & Participation">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Advance / Decline Ratio Tile */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>A / D Ratio</div>
            <div style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {adRatio.toFixed(2)}
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
            <span style={{ color: 'var(--positive)' }}>{advances} Adv</span>
            <span style={{ color: 'var(--text-muted)', margin: '0 var(--space-1-5)' }}>/</span>
            <span style={{ color: 'var(--negative)' }}>{declines} Dec</span>
            {unchanged > 0 && <span style={{ color: 'var(--text-muted)', marginLeft: 'var(--space-1-5)' }}>({unchanged} Unch)</span>}
          </div>
        </div>

        {/* Visual Proportion Bar */}
        <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-surface-sunken)', borderRadius: 'var(--radius-xs)', overflow: 'hidden', display: 'flex' }}>
          <div style={{ width: `${advPct}%`, backgroundColor: 'var(--positive)', transition: 'width 0.3s ease' }} title={`Advancing: ${advPct.toFixed(1)}%`} />
          <div style={{ width: `${unchPct}%`, backgroundColor: 'var(--neutral-state)', transition: 'width 0.3s ease' }} title={`Unchanged: ${unchPct.toFixed(1)}%`} />
          <div style={{ width: `${decPct}%`, backgroundColor: 'var(--negative)', transition: 'width 0.3s ease' }} title={`Declining: ${decPct.toFixed(1)}%`} />
        </div>

        {/* Participation Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)', paddingTop: 'var(--space-1)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>% Above 50 SMA</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {aboveSma50 !== null ? `${aboveSma50.toFixed(1)}%` : '—'}
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>% Above 200 SMA</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {aboveSma200 !== null ? `${aboveSma200.toFixed(1)}%` : '—'}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};
