import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { IntradaySectorStrength } from '@/lib/api/types';

interface IntradaySectorStrengthProps {
  sectors?: IntradaySectorStrength[];
  sectorLeader?: string | null;
  sectorLaggard?: string | null;
  isLoading?: boolean;
}

export const IntradaySectorStrengthPanel: React.FC<IntradaySectorStrengthProps> = ({
  sectors = [],
  sectorLeader,
  sectorLaggard,
  isLoading,
}) => {
  if (isLoading && sectors.length === 0) {
    return (
      <Card style={{ padding: 'var(--space-4)', height: '220px' }}>
        <div style={{ height: '100%', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
      </Card>
    );
  }

  return (
    <Card style={{ padding: 'var(--space-4)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Sectoral Strength & Relative Rotation
        </span>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {sectorLeader && (
            <Badge variant="positive">Leader: {sectorLeader}</Badge>
          )}
          {sectorLaggard && (
            <Badge variant="negative">Laggard: {sectorLaggard}</Badge>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 'var(--space-2)' }}>
        {sectors.map((sec) => {
          const isPositive = sec.average_return >= 0;
          return (
            <div
              key={sec.sector}
              style={{
                padding: 'var(--space-2) var(--space-3)',
                backgroundColor: 'var(--card-bg-elevated)',
                borderRadius: 'var(--radius-sm)',
                borderLeft: `3px solid ${isPositive ? 'var(--positive)' : 'var(--negative)'}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  #{sec.rank} {sec.sector}
                </span>
                <span
                  style={{
                    fontSize: 'var(--text-xs)',
                    fontWeight: 'var(--weight-bold)',
                    color: isPositive ? 'var(--positive)' : 'var(--negative)',
                  }}
                >
                  {isPositive ? '+' : ''}{sec.average_return.toFixed(2)}%
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
                <span>{sec.constituent_count} stocks ({sec.advance_count}↑ {sec.decline_count}↓)</span>
                <span>VWAP: {sec.above_vwap_pct.toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
