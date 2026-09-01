import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { Badge } from '@/components/ui/Badge';
import { MarketBreadth } from '@/lib/api/types';

export interface MarketBreadthCardProps {
  breadth?: MarketBreadth;
  universe?: string;
}

export const MarketBreadthCard: React.FC<MarketBreadthCardProps> = ({
  breadth,
  universe = 'NIFTY50',
}) => {
  if (!breadth) {
    return (
      <Card header="Market Breadth & Participation">
        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)' }}>
          Breadth data currently unavailable.
        </div>
      </Card>
    );
  }

  const advancing = breadth.advancing ?? 0;
  const declining = breadth.declining ?? 0;
  const unchanged = breadth.unchanged ?? 0;
  const total = Math.max(advancing + declining + unchanged, 1);
  const advPercent = (advancing / total) * 100;
  const decPercent = (declining / total) * 100;

  const getBreadthRegimeBadge = (regime?: string) => {
    const r = (regime || 'NEUTRAL').toUpperCase();
    if (r === 'STRONG') return <Badge variant="positive" size="sm">STRONG BREADTH</Badge>;
    if (r === 'WEAK') return <Badge variant="negative" size="sm">WEAK BREADTH</Badge>;
    return <Badge variant="neutral" size="sm">NEUTRAL BREADTH</Badge>;
  };

  return (
    <Card
      header={`Market Breadth & Internal Participation — ${universe}`}
      action={getBreadthRegimeBadge(breadth.breadth_regime)}
      data-testid="market-breadth-card"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Advance / Decline Progress Bar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            <span>
              <strong style={{ color: 'var(--positive)' }}>{advancing} Advances</strong> ({advPercent.toFixed(1)}%)
            </span>
            <span>{unchanged} Unchanged</span>
            <span>
              <strong style={{ color: 'var(--negative)' }}>{declining} Declines</strong> ({decPercent.toFixed(1)}%)
            </span>
          </div>

          <div
            style={{
              height: '8px',
              backgroundColor: 'var(--bg-surface-sunken)',
              borderRadius: 'var(--radius-pill)',
              overflow: 'hidden',
              display: 'flex',
            }}
          >
            <div style={{ width: `${advPercent}%`, backgroundColor: 'var(--positive)', transition: 'width var(--transition-normal)' }} />
            <div style={{ width: `${(unchanged / total) * 100}%`, backgroundColor: 'var(--text-muted)' }} />
            <div style={{ width: `${decPercent}%`, backgroundColor: 'var(--negative)', transition: 'width var(--transition-normal)' }} />
          </div>
        </div>

        {/* Breadth Metrics Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: 'var(--space-3)',
          }}
        >
          <Metric
            label="A/D Ratio"
            value={breadth.advance_decline_ratio ? `${breadth.advance_decline_ratio.toFixed(2)}x` : '—'}
            subtext="Advance/Decline"
          />
          <Metric
            label="Above SMA 20"
            value={breadth.participation?.pct_above_sma20 ? `${breadth.participation.pct_above_sma20.toFixed(1)}%` : '—'}
            subtext="Short-term momentum"
          />
          <Metric
            label="Above SMA 50"
            value={breadth.participation?.pct_above_sma50 ? `${breadth.participation.pct_above_sma50.toFixed(1)}%` : '—'}
            subtext="Intermediate trend"
          />
          <Metric
            label="Above SMA 200"
            value={breadth.participation?.pct_above_sma200 ? `${breadth.participation.pct_above_sma200.toFixed(1)}%` : '—'}
            subtext="Structural bull health"
          />
          <Metric
            label="52W Highs / Lows"
            value={`${breadth.new_highs_count ?? 0} / ${breadth.new_lows_count ?? 0}`}
            subtext="New 52W Extremes"
          />
        </div>
      </div>
    </Card>
  );
};
