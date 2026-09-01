import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StockRecommendation } from '@/lib/api/types';

export interface SignalDetailDrawerProps {
  signal: StockRecommendation | null;
  onClose: () => void;
  onCheckDataQuality: (symbol: string, timeframe: string) => void;
}

export const SignalDetailDrawer: React.FC<SignalDetailDrawerProps> = ({
  signal,
  onClose,
  onCheckDataQuality,
}) => {
  const navigate = useNavigate();
  if (!signal) return null;

  const isBuy = signal.signal === 'BUY';
  const isSell = signal.signal === 'SELL';

  return (
    <div
      data-testid="signal-detail-drawer"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-medium)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-5)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-4)',
        boxShadow: 'var(--shadow-medium)',
      }}
    >
      {/* Drawer Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {signal.symbol}
            </span>
            <Badge variant={isBuy ? 'positive' : isSell ? 'negative' : 'neutral'} size="sm">
              {isBuy ? '▲ BUY' : isSell ? '▼ SELL' : '● NO ACTION'}
            </Badge>
            <Badge variant="neutral" size="sm">{signal.timeframe || '5m'}</Badge>
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {signal.company_name} • {signal.sector}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Badge variant="brand" size="sm">{signal.status}</Badge>
          <button onClick={onClose} aria-label="Close panel" style={{ color: 'var(--text-muted)', fontSize: 'var(--text-md)', padding: 'var(--space-1)' }}>
            ✕
          </button>
        </div>
      </div>

      {/* Trade Parameters Grid */}
      <div>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
          Execution Parameters
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>ENTRY PRICE</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {signal.entry_price ? `₹${signal.entry_price.toFixed(2)}` : 'Market'}
            </div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{signal.entry_type}</div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>STOP LOSS</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--negative)', fontFamily: 'var(--font-mono)' }}>
              {signal.stop_price ? `₹${signal.stop_price.toFixed(2)}` : '—'}
            </div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{signal.stop_method}</div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TARGET 1</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--positive)', fontFamily: 'var(--font-mono)' }}>
              {signal.target_price ? `₹${signal.target_price.toFixed(2)}` : '—'}
            </div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{signal.target_method}</div>
          </div>
        </div>
      </div>

      {/* Risk-Reward & Strategy Info */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
        <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>RISK / REWARD RATIO</div>
          <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {signal.risk_reward_ratio ? `${signal.risk_reward_ratio.toFixed(2)} : 1` : '—'}
          </div>
        </div>
        <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>CONFIDENCE GRADE</div>
          <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)', fontFamily: 'var(--font-mono)' }}>
            {signal.confidence}
          </div>
        </div>
      </div>

      {/* Entry Condition Note */}
      {signal.entry_condition && (
        <div style={{ padding: 'var(--space-2-5) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Execution Condition</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', marginTop: '2px' }}>
            {signal.entry_condition}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
        <Button variant="outline" size="sm" onClick={() => onCheckDataQuality(signal.symbol, signal.timeframe || '5m')}>
          🔍 Check Data Quality
        </Button>
        <Button variant="primary" size="sm" onClick={() => navigate(`/stocks/${signal.symbol}`)}>
          Open Stock Terminal →
        </Button>
      </div>
    </div>
  );
};
