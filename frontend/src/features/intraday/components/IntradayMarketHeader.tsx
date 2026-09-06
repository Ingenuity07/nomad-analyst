import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { IntradayMarketContextResponse } from '@/lib/api/types';

interface IntradayMarketHeaderProps {
  context?: IntradayMarketContextResponse;
  isLoading?: boolean;
  wsConnected?: boolean;
}

export const IntradayMarketHeader: React.FC<IntradayMarketHeaderProps> = ({
  context,
  isLoading,
  wsConnected,
}) => {
  if (isLoading && !context) {
    return (
      <Card style={{ padding: 'var(--space-4)', display: 'flex', gap: 'var(--space-4)' }}>
        <div style={{ flex: 1, height: '80px', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
        <div style={{ flex: 1, height: '80px', backgroundColor: 'var(--card-bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
      </Card>
    );
  }

  const nifty = context?.nifty;
  const banknifty = context?.banknifty;
  const regime = context?.market_regime || 'UNKNOWN';
  const confidence = context?.regime_confidence ? Math.round(context.regime_confidence * 100) : null;
  const confirmation = context?.index_confirmation || 'NEUTRAL';
  const freshness = context?.freshness || 'UNAVAILABLE';

  const getRegimeBadgeVariant = (r: string): 'positive' | 'negative' | 'warning' | 'neutral' | 'brand' => {
    switch (r) {
      case 'TRENDING_UP':
        return 'positive';
      case 'TRENDING_DOWN':
        return 'negative';
      case 'VOLATILE':
        return 'warning';
      case 'RANGE':
        return 'brand';
      default:
        return 'neutral';
    }
  };

  const getFreshnessBadgeVariant = (f: string): 'positive' | 'negative' | 'warning' | 'neutral' => {
    switch (f) {
      case 'FRESH':
        return 'positive';
      case 'STALE':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
      {/* NIFTY 50 Card */}
      <Card style={{ padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
          <div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Benchmark Index
            </span>
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', margin: '2px 0 0 0' }}>
              {nifty?.name || 'NIFTY 50'}
            </h3>
          </div>
          <Badge variant={nifty && nifty.change_percent >= 0 ? 'positive' : 'negative'}>
            {nifty ? `${nifty.change_percent >= 0 ? '+' : ''}${nifty.change_percent.toFixed(2)}%` : '0.00%'}
          </Badge>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--weight-bold)' }}>
            ₹{nifty ? nifty.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          </span>
          <span style={{ fontSize: 'var(--text-sm)', color: nifty && nifty.change >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            {nifty ? `${nifty.change >= 0 ? '+' : ''}${nifty.change.toFixed(2)}` : '0.00'}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          <span>VWAP: {nifty?.vwap ? `₹${nifty.vwap.toFixed(2)}` : '—'}</span>
          <span>H: {nifty ? nifty.high.toFixed(1) : '—'} / L: {nifty ? nifty.low.toFixed(1) : '—'}</span>
        </div>
      </Card>

      {/* BANKNIFTY Card */}
      <Card style={{ padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
          <div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Sectoral Lead
            </span>
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', margin: '2px 0 0 0' }}>
              {banknifty?.name || 'NIFTY BANK'}
            </h3>
          </div>
          <Badge variant={banknifty && banknifty.change_percent >= 0 ? 'positive' : 'negative'}>
            {banknifty ? `${banknifty.change_percent >= 0 ? '+' : ''}${banknifty.change_percent.toFixed(2)}%` : '0.00%'}
          </Badge>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--weight-bold)' }}>
            ₹{banknifty ? banknifty.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          </span>
          <span style={{ fontSize: 'var(--text-sm)', color: banknifty && banknifty.change >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            {banknifty ? `${banknifty.change >= 0 ? '+' : ''}${banknifty.change.toFixed(2)}` : '0.00'}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          <span>VWAP: {banknifty?.vwap ? `₹${banknifty.vwap.toFixed(2)}` : '—'}</span>
          <span>H: {banknifty ? banknifty.high.toFixed(1) : '—'} / L: {banknifty ? banknifty.low.toFixed(1) : '—'}</span>
        </div>
      </Card>

      {/* Market Regime & Telemetry Card */}
      <Card style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Market Regime & Telemetry
            </span>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <Badge variant={getFreshnessBadgeVariant(freshness)}>
                {freshness} {wsConnected ? '⚡ WS' : '⏱ Polling'}
              </Badge>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
            <Badge variant={getRegimeBadgeVariant(regime)} style={{ fontSize: 'var(--text-sm)', padding: '4px 8px' }}>
              {regime.replace('_', ' ')} {confidence ? `(${confidence}%)` : ''}
            </Badge>
            <Badge variant={confirmation.includes('BULLISH') ? 'positive' : confirmation.includes('BEARISH') ? 'negative' : 'neutral'}>
              {confirmation.replace('_', ' ')}
            </Badge>
          </div>
        </div>

        {context?.regime_reasons && context.regime_reasons.length > 0 && (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-muted)' }}>Drivers: </span>
            {context.regime_reasons.slice(0, 2).join(' • ')}
          </div>
        )}
      </Card>
    </div>
  );
};
