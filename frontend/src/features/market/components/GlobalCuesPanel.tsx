import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { GlobalCue } from '@/lib/api/types';

export interface GlobalCuesPanelProps {
  cues?: Record<string, any> | GlobalCue[] | null;
}

export const GlobalCuesPanel: React.FC<GlobalCuesPanelProps> = ({ cues }) => {
  // Normalize cues into array
  const cueItems: GlobalCue[] = [];
  if (cues) {
    if (Array.isArray(cues)) {
      cueItems.push(...cues);
    } else if (typeof cues === 'object') {
      Object.entries(cues).forEach(([key, val]) => {
        if (typeof val === 'object' && val !== null) {
          cueItems.push({
            name: val.name || key,
            symbol: val.symbol || key,
            price: val.price ?? null,
            change_percent: val.change_percent ?? val.change ?? null,
            impact_bias: val.impact_bias || val.bias || 'NEUTRAL',
          });
        }
      });
    }
  }

  // Fallback if backend returns empty cross-market cues
  const displayItems =
    cueItems.length > 0
      ? cueItems
      : [
          { name: 'S&P 500 (US)', symbol: '^GSPC', price: null, change_percent: null, impact_bias: 'NEUTRAL' },
          { name: 'Nasdaq 100', symbol: '^IXIC', price: null, change_percent: null, impact_bias: 'NEUTRAL' },
          { name: 'Brent Crude ($/bbl)', symbol: 'BZ=F', price: null, change_percent: null, impact_bias: 'NEUTRAL' },
          { name: 'US 10Y Treasury Yield', symbol: '^TNX', price: null, change_percent: null, impact_bias: 'NEUTRAL' },
        ];

  return (
    <Card header="Global Market Context & Macro Cues">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        {displayItems.map((item) => {
          const change = item.change_percent;
          const isPos = change !== null && change !== undefined && change > 0;
          const isNeg = change !== null && change !== undefined && change < 0;
          const biasVariant =
            item.impact_bias === 'BULLISH' ? 'positive' : item.impact_bias === 'BEARISH' ? 'negative' : 'neutral';

          return (
            <div
              key={item.symbol}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 'var(--space-2) var(--space-3)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)' }}>
                  {item.name}
                </div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {item.symbol}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                {change !== null && change !== undefined ? (
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--text-sm)',
                      fontWeight: 'var(--weight-semibold)',
                      color: isPos ? 'var(--positive)' : isNeg ? 'var(--negative)' : 'var(--text-secondary)',
                    }}
                  >
                    {isPos ? '+' : ''}{change.toFixed(2)}%
                  </span>
                ) : (
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>—</span>
                )}

                <Badge variant={biasVariant} size="sm">
                  {item.impact_bias}
                </Badge>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
