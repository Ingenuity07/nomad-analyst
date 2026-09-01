import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { Badge } from '@/components/ui/Badge';
import { StockDetailResponse } from '@/lib/api/types';

export interface OverviewTabProps {
  data?: StockDetailResponse;
  symbol: string;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({ data }) => {
  const snap = data?.latest_snapshot;
  const rec = data?.active_recommendation;
  const opp = data?.latest_opportunity;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* 1. Market Snapshot Metrics */}
      <Card header="Key Market & Pricing Metrics">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-4)' }}>
          <Metric
            label="Latest Price"
            value={snap?.close ? `₹${Number(snap.close).toFixed(2)}` : '—'}
            subtext={snap?.source ? `Source: ${snap.source}` : undefined}
          />
          <Metric
            label="Day High"
            value={snap?.high ? `₹${Number(snap.high).toFixed(2)}` : '—'}
          />
          <Metric
            label="Day Low"
            value={snap?.low ? `₹${Number(snap.low).toFixed(2)}` : '—'}
          />
          <Metric
            label="Day Volume"
            value={snap?.volume ? `${(Number(snap.volume) / 1e5).toFixed(2)} L` : '—'}
          />
          <Metric
            label="Prev Close"
            value={snap?.previous_close ? `₹${Number(snap.previous_close).toFixed(2)}` : '—'}
          />
        </div>
      </Card>

      {/* 2. Trade Signal & Opportunity Setup Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 'var(--space-6)' }}>
        {/* Active Recommendation Card */}
        <Card header="Active Strategy Recommendation">
          {rec ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <Badge variant={rec.signal === 'BUY' ? 'positive' : rec.signal === 'SELL' ? 'negative' : 'neutral'} size="md">
                    {rec.signal === 'BUY' ? '▲ BUY' : rec.signal === 'SELL' ? '▼ SELL' : 'NO ACTION'}
                  </Badge>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {rec.setup_type}
                  </span>
                </div>
                <Badge variant="brand" size="sm">{rec.status}</Badge>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
                <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>ENTRY</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {rec.entry_price ? `₹${rec.entry_price.toFixed(2)}` : 'Market'}
                  </div>
                </div>
                <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>STOP LOSS</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--negative)', fontFamily: 'var(--font-mono)' }}>
                    {rec.stop_price ? `₹${rec.stop_price.toFixed(2)}` : '—'}
                  </div>
                </div>
                <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TARGET 1</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--positive)', fontFamily: 'var(--font-mono)' }}>
                    {rec.target_price ? `₹${rec.target_price.toFixed(2)}` : '—'}
                  </div>
                </div>
              </div>

              {rec.entry_condition && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
                  Condition: {rec.entry_condition}
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              No active swing or intraday trade recommendation armed for this symbol.
            </div>
          )}
        </Card>

        {/* Opportunity Ranking Card */}
        <Card header="Multi-Factor Opportunity Scoring">
          {opp ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  Opportunity Type: <strong style={{ color: 'var(--text-primary)' }}>{opp.opportunity_type}</strong>
                </span>
                <Badge variant="brand" size="md">
                  ★ {Number(opp.final_opportunity_score).toFixed(1)} / 100
                </Badge>
              </div>

              {/* Component breakdown */}
              {opp.component_scores && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-1-5)' }}>
                  {Object.entries(opp.component_scores).filter(([k]) => k !== 'liquidity').map(([key, val]) => (
                    <div key={key} style={{ textAlign: 'center', padding: 'var(--space-1-5)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
                      <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{key.slice(0, 4)}</div>
                      <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                        {Number(val).toFixed(0)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Reasons */}
              {opp.reasons && opp.reasons.length > 0 && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--positive)' }}>
                  ✓ {opp.reasons[0]}
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              Stock is not currently ranked in the top opportunities pool.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
