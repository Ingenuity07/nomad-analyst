import React from 'react';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { Badge } from '@/components/ui/Badge';
import { useStockTechnicals } from '@/hooks/useStockTechnicals';

export interface TechnicalsTabProps {
  symbol: string;
}

export const TechnicalsTab: React.FC<TechnicalsTabProps> = ({ symbol }) => {
  const { data, isLoading, error } = useStockTechnicals(symbol, '1d');

  if (isLoading) {
    return <Skeleton height="280px" />;
  }

  if (error || !data || data.status === 'INSUFFICIENT_DATA') {
    return (
      <Card>
        <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
          Technical indicator calculations unavailable or insufficient historical bars for {symbol}.
        </div>
      </Card>
    );
  }

  const indicators = data.indicators || {};

  const getVal = (name: string): number | null => {
    return indicators[name]?.value !== undefined ? indicators[name].value : null;
  };

  const rsi = getVal('RSI_14');
  const sma20 = getVal('SMA_20');
  const sma50 = getVal('SMA_50');
  const sma200 = getVal('SMA_200');
  const ema20 = getVal('EMA_20');
  const ema50 = getVal('EMA_50');
  const ema200 = getVal('EMA_200');
  const macdLine = getVal('MACD_line');
  const macdSignal = getVal('MACD_signal');
  const macdHist = getVal('MACD_hist');
  const atr = getVal('ATR_14');
  const volSma = getVal('volume_sma_20');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* 1. Moving Averages Trend Grid */}
      <Card header="Moving Averages & Trend Alignment">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-3)' }}>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SMA 20 (SHORT-TERM)</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {sma20 !== null ? `₹${sma20.toFixed(2)}` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SMA 50 (MEDIUM-TERM)</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {sma50 !== null ? `₹${sma50.toFixed(2)}` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SMA 200 (LONG-TERM)</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {sma200 !== null ? `₹${sma200.toFixed(2)}` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EMA 20</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {ema20 !== null ? `₹${ema20.toFixed(2)}` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EMA 50</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {ema50 !== null ? `₹${ema50.toFixed(2)}` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EMA 200</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {ema200 !== null ? `₹${ema200.toFixed(2)}` : '—'}
            </div>
          </div>
        </div>
      </Card>

      {/* 2. Momentum & Volatility Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-6)' }}>
        {/* RSI & MACD */}
        <Card header="Momentum Oscillators">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Relative Strength Index (RSI 14)</div>
                <div style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {rsi !== null ? rsi.toFixed(1) : '—'}
                </div>
              </div>
              {rsi !== null && (
                <Badge variant={rsi > 70 ? 'warning' : rsi < 30 ? 'positive' : 'neutral'} size="md">
                  {rsi > 70 ? 'Overbought (>70)' : rsi < 30 ? 'Oversold (<30)' : 'Neutral (30–70)'}
                </Badge>
              )}
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>MACD LINE</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {macdLine !== null ? macdLine.toFixed(2) : '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SIGNAL</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {macdSignal !== null ? macdSignal.toFixed(2) : '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>HISTOGRAM</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)', color: macdHist !== null && macdHist >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                  {macdHist !== null ? macdHist.toFixed(2) : '—'}
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Volatility & Volume */}
        <Card header="Volatility & Volume Profile">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-4)' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Average True Range (ATR 14)</div>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: 'var(--space-1)' }}>
                {atr !== null ? `₹${atr.toFixed(2)}` : '—'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>Daily price span volatility</div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>Volume 20-Day SMA</div>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: 'var(--space-1)' }}>
                {volSma !== null ? `${(volSma / 1e5).toFixed(2)} L` : '—'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>Baseline trading liquidity</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
