import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StockOpportunitySnapshot, StockRecommendation } from '@/lib/api/types';

export interface OpportunityQuickViewDrawerProps {
  candidate: StockOpportunitySnapshot | null;
  recommendation?: StockRecommendation | null;
  onClose: () => void;
}

export const OpportunityQuickViewDrawer: React.FC<OpportunityQuickViewDrawerProps> = ({
  candidate,
  recommendation,
  onClose,
}) => {
  const navigate = useNavigate();
  if (!candidate) return null;

  const score = typeof candidate.final_opportunity_score === 'number'
    ? candidate.final_opportunity_score
    : parseFloat(candidate.final_opportunity_score) || 0;

  const closePrice = candidate.supporting_features?.close;
  const pros = candidate.supporting_features?.pros || [];
  const risks = candidate.risks || [];
  const compScores = candidate.component_scores || {};

  return (
    <div
      data-testid="quick-view-drawer"
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
              {candidate.symbol}
            </span>
            <Badge variant="brand" size="sm">{candidate.sector || 'General'}</Badge>
            <Badge variant="neutral" size="sm">{(candidate.horizon || 'DELIVERY').replace('_', ' ')}</Badge>
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {candidate.company_name}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Opportunity Score</div>
            <div style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--weight-bold)', color: score >= 80 ? 'var(--positive)' : 'var(--brand-primary)', fontFamily: 'var(--font-mono)' }}>
              ★ {score.toFixed(1)}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close panel" style={{ color: 'var(--text-muted)', fontSize: 'var(--text-md)', padding: 'var(--space-1)' }}>
            ✕
          </button>
        </div>
      </div>

      {/* Component Scores Breakdown */}
      <div>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
          Factor Score Breakdown
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-2)' }}>
          <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>TECHNICAL</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {typeof compScores.technical === 'number' ? compScores.technical.toFixed(0) : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>FUNDAMENTAL</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {typeof compScores.fundamental === 'number' ? compScores.fundamental.toFixed(0) : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SECTOR LEAD</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {typeof compScores.sector === 'number' ? compScores.sector.toFixed(0) : '—'}
            </div>
          </div>
          <div style={{ padding: 'var(--space-2)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>NEWS / SENT</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {typeof compScores.news === 'number' ? compScores.news.toFixed(0) : '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Why this stock surfaced (Supporting Factors) */}
      <div>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--positive)', textTransform: 'uppercase', marginBottom: 'var(--space-1-5)' }}>
          ✓ Why It Surfaced (Supporting Evidence)
        </div>
        {pros.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No positive catalysts flagged.</div>
        ) : (
          <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {pros.map((p: string, idx: number) => (
              <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--positive)' }}>•</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Identified Risks */}
      <div>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--warning)', textTransform: 'uppercase', marginBottom: 'var(--space-1-5)' }}>
          ⚠ Structural Risks & Headwinds
        </div>
        {risks.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Zero major structural risks detected.</div>
        ) : (
          <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            {risks.map((r: string, idx: number) => (
              <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--warning)' }}>•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Linked Recommendation if present */}
      {recommendation && (
        <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-medium)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              Linked Trade Signal: {recommendation.signal}
            </span>
            <Badge variant={recommendation.signal === 'BUY' ? 'positive' : 'negative'} size="sm">
              {recommendation.signal} • {recommendation.confidence}
            </Badge>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
            <div>Entry: {recommendation.entry_price ? `₹${recommendation.entry_price.toFixed(2)}` : 'Market'}</div>
            <div>Stop: {recommendation.stop_price ? `₹${recommendation.stop_price.toFixed(2)}` : '—'}</div>
            <div>Target: {recommendation.target_price ? `₹${recommendation.target_price.toFixed(2)}` : '—'}</div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {closePrice ? `LTP: ₹${closePrice.toFixed(2)}` : ''}
        </span>
        <Button variant="primary" size="sm" onClick={() => navigate(`/stocks/${candidate.symbol}`)}>
          Open Full Stock Terminal →
        </Button>
      </div>
    </div>
  );
};
