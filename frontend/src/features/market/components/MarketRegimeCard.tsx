import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { IndexRegime } from '@/lib/api/types';

export interface MarketRegimeCardProps {
  regimeData?: Record<string, IndexRegime> | IndexRegime[] | null;
  breadthRegime?: string;
  asOf?: string;
}

export const MarketRegimeCard: React.FC<MarketRegimeCardProps> = ({ regimeData, breadthRegime, asOf }) => {
  // Extract primary benchmark regime (^NSEI)
  let nseiRegime: IndexRegime | null = null;
  if (regimeData) {
    if (Array.isArray(regimeData)) {
      nseiRegime = regimeData.find((r) => r.symbol === '^NSEI' || r.symbol === 'NIFTY50') || regimeData[0] || null;
    } else if (typeof regimeData === 'object') {
      nseiRegime = regimeData['^NSEI'] || regimeData['NIFTY50'] || Object.values(regimeData)[0] || null;
    }
  }

  const rawTrend = (nseiRegime?.trend || nseiRegime?.regime || 'NEUTRAL').toUpperCase();
  const isBullish = rawTrend.includes('BULL');
  const isBearish = rawTrend.includes('BEAR');
  const badgeVariant: 'positive' | 'negative' | 'neutral' = isBullish ? 'positive' : isBearish ? 'negative' : 'neutral';

  const volatility = nseiRegime?.volatility_regime || 'NORMAL';
  const sma50 = nseiRegime?.sma_50 ?? null;
  const sma200 = nseiRegime?.sma_200 ?? null;
  const dist52w = nseiRegime?.distance_from_52w_high ?? null;

  return (
    <Card
      header="Market Regime & Macro Trend"
      action={<Badge variant={badgeVariant}>{isBullish ? '▲ ' : isBearish ? '▼ ' : '● '}{rawTrend}</Badge>}
      footer={asOf ? `Anchored As Of: ${new Date(asOf).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST` : undefined}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Core Indicators Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Volatility State</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
              {volatility}
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Breadth Alignment</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
              {breadthRegime ? breadthRegime.toUpperCase() : 'NEUTRAL'}
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>52W High Distance</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
              {dist52w !== null ? `${dist52w > 0 ? '+' : ''}${dist52w.toFixed(2)}%` : '—'}
            </div>
          </div>
        </div>

        {/* Moving Average Evidence */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-1)' }}>
            <span>50-Day Simple Moving Average</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {sma50 !== null ? `₹${sma50.toFixed(2)}` : '—'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>200-Day Long-Term Trend SMA</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {sma200 !== null ? `₹${sma200.toFixed(2)}` : '—'}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
};
