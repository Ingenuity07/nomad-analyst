import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { DataStatus } from '@/components/ui/DataStatus';
import { useStock } from '@/hooks/useStock';

export const StockDetailPageShell: React.FC = () => {
  const { symbol = 'RELIANCE' } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useStock(symbol);

  return (
    <PageContainer
      title={`${symbol} — Equity Research Terminal`}
      subtitle={data?.instrument.company?.name || 'NSE Equity'}
      action={
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <DataStatus status={isLoading ? 'LOADING' : 'LIVE'} source={data?.latest_snapshot?.source || 'NSE'} />
          <Button variant="outline" size="sm" onClick={() => navigate('/stocks')}>
            ← Back to Directory
          </Button>
        </div>
      }
    >
      <Card header="Stock Detail Workspace Shell (FE-5 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Interactive TradingView candlestick charts with synchronized Volume/RSI/MACD panes, Screener financial statements, and technical indicator metrics.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          Symbol: {symbol} • Latest Close: {data?.latest_snapshot?.close ? `₹${data.latest_snapshot.close.toFixed(2)}` : '—'} • Sector: {data?.instrument.company?.sector || '—'}
        </div>
      </Card>
    </PageContainer>
  );
};
