import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { StockRecommendation, RecommendationOutcome } from '@/lib/api/types';
import { useRecommendationOutcome } from '@/hooks/useOutcomes';
import { useRecommendationDetail } from '@/hooks/useRecommendations';

export interface RecommendationDetailDrawerProps {
  recommendation?: StockRecommendation | null;
  recommendationId?: string | null;
  attachedOutcome?: RecommendationOutcome | null;
  onClose: () => void;
}

export const RecommendationDetailDrawer: React.FC<RecommendationDetailDrawerProps> = ({
  recommendation: initialRec,
  recommendationId,
  attachedOutcome,
  onClose,
}) => {
  const navigate = useNavigate();

  const recId = initialRec?.id || recommendationId || attachedOutcome?.recommendation;

  const { data: fetchedRec, isLoading: isRecLoading } = useRecommendationDetail(
    !initialRec && recId ? recId : ''
  );

  const recommendation = initialRec || fetchedRec;

  // If outcome is not attached, fetch on demand using hook
  const { data: fetchedOutcome } = useRecommendationOutcome(
    recommendation && !attachedOutcome ? recommendation.id : null
  );

  const outcome = attachedOutcome || fetchedOutcome;

  if (isRecLoading) {
    return (
      <div style={{ backgroundColor: 'var(--bg-surface)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)' }}>
        <Skeleton height="200px" />
      </div>
    );
  }

  if (!recommendation && !outcome) return null;

  const symbol = recommendation?.symbol || outcome?.symbol || 'UNKNOWN';
  const signal = recommendation?.signal || outcome?.signal || 'BUY';
  const isBuy = signal === 'BUY';
  const isSell = signal === 'SELL';
  const horizon = recommendation?.horizon || outcome?.horizon || 'DELIVERY_SWING';
  const setupType = recommendation?.setup_type || outcome?.setup_type || '—';

  return (
    <div
      data-testid="recommendation-detail-drawer"
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
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {symbol}
            </span>
            <Badge variant={isBuy ? 'positive' : isSell ? 'negative' : 'neutral'} size="sm">
              {isBuy ? '▲ BUY' : isSell ? '▼ SELL' : 'NO ACTION'}
            </Badge>
            <Badge variant="brand" size="sm">{horizon}</Badge>
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {recommendation?.company_name || symbol} • {setupType}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {recommendation?.status && (
            <Badge variant={recommendation.status === 'ACTIVE' ? 'brand' : recommendation.status === 'TARGET_HIT' ? 'positive' : recommendation.status === 'STOPPED' ? 'negative' : 'neutral'} size="sm">
              {recommendation.status}
            </Badge>
          )}
          <button onClick={onClose} aria-label="Close panel" style={{ color: 'var(--text-muted)', fontSize: 'var(--text-md)', padding: 'var(--space-1)', cursor: 'pointer' }}>
            ✕
          </button>
        </div>
      </div>

      {/* Planned Execution Parameters */}
      {recommendation && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
            Planned Trade Execution Parameters
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>ENTRY LEVEL</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {recommendation.entry_price ? `₹${recommendation.entry_price.toFixed(2)}` : 'Market'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{recommendation.entry_type}</div>
            </div>

            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>STOP LOSS</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--negative)', fontFamily: 'var(--font-mono)' }}>
                {recommendation.stop_price ? `₹${recommendation.stop_price.toFixed(2)}` : '—'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{recommendation.stop_method}</div>
            </div>

            <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TARGET 1</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--positive)', fontFamily: 'var(--font-mono)' }}>
                {recommendation.target_price ? `₹${recommendation.target_price.toFixed(2)}` : '—'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{recommendation.target_method}</div>
            </div>
          </div>
        </div>
      )}

      {/* R:R and Confidence */}
      {recommendation && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>PLANNED RISK / REWARD</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {recommendation.risk_reward_ratio ? `${recommendation.risk_reward_ratio.toFixed(2)} : 1` : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>CONFIDENCE LEVEL</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)', fontFamily: 'var(--font-mono)' }}>
              {recommendation.confidence}
            </div>
          </div>
        </div>
      )}

      {/* Realized Outcome Section (if evaluated) */}
      {outcome && (
        <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-medium)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
            ✓ Realized Trade Outcome Evaluation
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
            <div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>NET P&L</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: outcome.net_pnl_percent !== null && outcome.net_pnl_percent >= 0 ? 'var(--positive)' : 'var(--negative)', fontFamily: 'var(--font-mono)' }}>
                {outcome.net_pnl_percent !== null ? `${outcome.net_pnl_percent >= 0 ? '+' : ''}${(outcome.net_pnl_percent * 100).toFixed(2)}%` : '—'}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>R-MULTIPLE</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: outcome.r_multiple !== null && outcome.r_multiple >= 0 ? 'var(--positive)' : 'var(--negative)', fontFamily: 'var(--font-mono)' }}>
                {outcome.r_multiple !== null ? `${outcome.r_multiple >= 0 ? '+' : ''}${Number(outcome.r_multiple).toFixed(2)} R` : '—'}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>EXIT REASON</div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                {outcome.exit_reason || '—'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Supporting Factors */}
      {recommendation?.supporting_factors && recommendation.supporting_factors.length > 0 && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--positive)', textTransform: 'uppercase', marginBottom: 'var(--space-1)' }}>
            ✓ Supporting Factors
          </div>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {recommendation.supporting_factors.map((f, i) => (
              <li key={i} style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--positive)' }}>•</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)' }}>
        <Button variant="primary" size="sm" onClick={() => navigate(`/stocks/${symbol}`)}>
          Open Stock Terminal →
        </Button>
      </div>
    </div>
  );
};
