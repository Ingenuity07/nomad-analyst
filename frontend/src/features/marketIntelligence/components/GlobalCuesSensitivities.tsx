import React from 'react';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { GlobalCueItem, CrossMarketCues } from '@/lib/api/types';

export interface GlobalCuesSensitivitiesProps {
  cues?: CrossMarketCues;
  macroEvents?: Array<{ type?: string; headline: string; published_at: string; source: string } | any>;
}

export const GlobalCuesSensitivities: React.FC<GlobalCuesSensitivitiesProps> = ({
  cues,
  macroEvents = [],
}) => {
  const globalItems: Array<GlobalCueItem & { ticker: string }> = [];

  if (cues) {
    Object.entries(cues).forEach(([ticker, val]) => {
      if (typeof val === 'object' && val !== null && 'name' in val) {
        globalItems.push({ ...(val as GlobalCueItem), ticker });
      }
    });
  }

  const columns: TableColumn<GlobalCueItem & { ticker: string }>[] = [
    {
      key: 'name',
      header: 'Global Asset / Cue',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          {r.name || r.ticker}
        </span>
      ),
    },
    {
      key: 'close',
      header: 'Price / Yield',
      isNumeric: true,
      render: (r) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {r.close !== null && r.close !== undefined ? Number(r.close).toFixed(2) : '—'}
        </span>
      ),
    },
    {
      key: 'daily_change_percent',
      header: '1D Change',
      isNumeric: true,
      render: (r) => {
        const val = Number(r.daily_change_percent) || 0;
        const isPositive = val >= 0;
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 'var(--weight-semibold)',
              color: isPositive ? 'var(--positive)' : 'var(--negative)',
            }}
          >
            {isPositive ? '+' : ''}
            {val.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'stale',
      header: 'Status',
      render: (r) => (
        <Badge variant={r.stale ? 'neutral' : 'positive'} size="sm">
          {r.stale ? 'STALE (>48h)' : 'ACTIVE'}
        </Badge>
      ),
    },
  ];

  return (
    <Card header="Global Market Cues & Macroeconomic Disclosures" data-testid="global-cues-sensitivities">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Global Assets Table */}
        <Table
          columns={columns}
          data={globalItems}
          keyExtractor={(r) => r.ticker}
          emptyMessage="No global cue assets available."
        />

        {/* Macro Events Disclosure List */}
        {macroEvents.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)' }}>
              Recent Macroeconomic Catalysts & Central Bank Disclosures:
            </div>
            {macroEvents.slice(0, 3).map((ev, idx) => (
              <div
                key={idx}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 'var(--text-xs)',
                  gap: 'var(--space-2)',
                }}
              >
                <span style={{ color: 'var(--text-primary)', fontWeight: 'var(--weight-medium)' }}>
                  {ev.headline}
                </span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', whiteSpace: 'nowrap' }}>
                  {ev.source} • {new Date(ev.published_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
};
