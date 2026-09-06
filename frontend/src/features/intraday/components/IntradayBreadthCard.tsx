import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { IntradayBreadth } from '@/lib/api/types';

interface IntradayBreadthCardProps {
  breadth?: IntradayBreadth;
  isLoading?: boolean;
}

export const IntradayBreadthCard: React.FC<IntradayBreadthCardProps> = ({
  breadth,
  isLoading,
}) => {
  if (isLoading && !breadth) {
    return (
      <Card style={{ padding: 'var(--space-4)', height: '140px' }}>
        <div style={{ height: '100%', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
      </Card>
    );
  }

  const adv = breadth?.advance_count || 0;
  const dec = breadth?.decline_count || 0;
  const unch = breadth?.unchanged_count || 0;
  const advPct = breadth?.advance_pct || 0;
  const decPct = breadth?.decline_pct || 0;
  const unchPct = breadth?.unchanged_pct || 0;
  const adRatio = breadth?.advance_decline_ratio || 1.0;
  const aboveVwapPct = breadth?.above_vwap_pct || 0;
  const state = breadth?.breadth_state || 'NEUTRAL';

  const getStateVariant = (s: string): 'positive' | 'negative' | 'neutral' => {
    if (s.includes('STRONG_POSITIVE') || s.includes('POSITIVE')) return 'positive';
    if (s.includes('STRONG_NEGATIVE') || s.includes('NEGATIVE')) return 'negative';
    return 'neutral';
  };

  return (
    <Card style={{ padding: 'var(--space-4)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            NIFTY 50 Market Breadth
          </span>
          <Badge variant={getStateVariant(state)}>
            {state.replace('_', ' ')}
          </Badge>
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          A/D Ratio: <strong style={{ color: 'var(--text-primary)' }}>{adRatio.toFixed(2)}</strong>
        </div>
      </div>

      {/* Visual Breadth Stack Bar */}
      <div style={{ display: 'flex', height: '10px', borderRadius: '5px', overflow: 'hidden', marginBottom: 'var(--space-3)', backgroundColor: 'var(--border-subtle)' }}>
        <div style={{ width: `${advPct}%`, backgroundColor: 'var(--positive, #22c55e)', transition: 'width 0.3s ease' }} title={`Advances: ${adv} (${advPct}%)`} />
        <div style={{ width: `${unchPct}%`, backgroundColor: 'var(--text-muted, #71717a)', transition: 'width 0.3s ease' }} title={`Unchanged: ${unch} (${unchPct}%)`} />
        <div style={{ width: `${decPct}%`, backgroundColor: 'var(--negative, #ef4444)', transition: 'width 0.3s ease' }} title={`Declines: ${dec} (${decPct}%)`} />
      </div>

      {/* Numerical Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-2)', textAlign: 'center' }}>
        <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--positive)' }}>Advancing</span>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--positive)' }}>
            {adv} <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'normal' }}>({advPct}%)</span>
          </div>
        </div>

        <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--negative)' }}>Declining</span>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--negative)' }}>
            {dec} <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'normal' }}>({decPct}%)</span>
          </div>
        </div>

        <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Above VWAP</span>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)' }}>
            {aboveVwapPct.toFixed(0)}%
          </div>
        </div>

        <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>At Highs / Lows</span>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)' }}>
            <span style={{ color: 'var(--positive)' }}>{breadth?.at_high_count || 0}</span>
            {' / '}
            <span style={{ color: 'var(--negative)' }}>{breadth?.at_low_count || 0}</span>
          </div>
        </div>
      </div>
    </Card>
  );
};
