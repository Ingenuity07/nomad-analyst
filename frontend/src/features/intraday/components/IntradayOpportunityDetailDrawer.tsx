import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { IntradayOpportunityItem } from '@/lib/api/types';

interface IntradayOpportunityDetailDrawerProps {
  opportunity: IntradayOpportunityItem;
  onClose: () => void;
  onExamine?: (symbol: string) => void;
}

export const IntradayOpportunityDetailDrawer: React.FC<IntradayOpportunityDetailDrawerProps> = ({
  opportunity,
  onClose,
  onExamine,
}) => {
  const scores = opportunity.component_scores || {
    momentum_score: 0,
    relative_strength_score: 0,
    volume_score: 0,
    vwap_score: 0,
    market_alignment_score: 0,
    sector_alignment_score: 0,
    orb_score: 0,
    data_quality_score: 0,
  };

  const scoreDimensions = [
    { label: 'Momentum', score: scores.momentum_score, max: 20, weight: '20%' },
    { label: 'Relative Strength', score: scores.relative_strength_score, max: 20, weight: '20%' },
    { label: 'Volume Confirmation', score: scores.volume_score, max: 15, weight: '15%' },
    { label: 'VWAP Positioning', score: scores.vwap_score, max: 10, weight: '10%' },
    { label: 'Market Alignment', score: scores.market_alignment_score, max: 10, weight: '10%' },
    { label: 'Sector Alignment', score: scores.sector_alignment_score, max: 10, weight: '10%' },
    { label: 'ORB / Structure', score: scores.orb_score, max: 5, weight: '5%' },
    { label: 'Data Quality', score: scores.data_quality_score, max: 10, weight: '10%' },
  ];

  return (
    <Card style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)' }}>
              {opportunity.symbol}
            </h3>
            <Badge variant="brand">{opportunity.opportunity_type}</Badge>
            <Badge variant={opportunity.state === 'CONFIRMED' ? 'positive' : 'neutral'}>
              {opportunity.state}
            </Badge>
          </div>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            Sector: {opportunity.sector?.name ?? 'Unknown'} (Rank #{opportunity.sector?.rank ?? '-'})
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
      </div>

      {/* Composite Score Banner */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: 'var(--space-3)',
        backgroundColor: 'var(--bg-secondary, rgba(255,255,255,0.03))',
        borderRadius: 'var(--radius-md)',
      }}>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Opportunity Score</div>
          <div style={{ fontSize: '28px', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary, #3b82f6)' }}>
            {opportunity.score.toFixed(1)} <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>/ 100</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Confidence</div>
          <div style={{ fontSize: '20px', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
            {(opportunity.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* AI Research Action Button */}
      {onExamine && (
        <Button
          variant="primary"
          size="sm"
          data-testid="drawer-examine-ai-btn"
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-2)' }}
          onClick={() => onExamine(opportunity.symbol)}
        >
          <span>✨</span>
          <span>Examine with Deep AI Research (1 Call)</span>
        </Button>
      )}

      {/* Dimensional Score Decomposition */}
      <div>
        <h4 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          Dimensional Score Decomposition
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {scoreDimensions.map((dim) => {
            const pointsScored = (dim.score / 100) * dim.max;
            const pct = (dim.score / 100) * 100;
            return (
              <div key={dim.label} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span>{dim.label} ({dim.weight})</span>
                  <span style={{ fontWeight: 'var(--weight-semibold)' }}>{pointsScored.toFixed(1)} / {dim.max} pts</span>
                </div>
                <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-tertiary, #1e293b)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${pct}%`, height: '100%', backgroundColor: 'var(--brand-primary, #3b82f6)', borderRadius: '3px' }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Penalties if any */}
      {opportunity.penalties && opportunity.penalties.length > 0 && (
        <div style={{ padding: 'var(--space-3)', backgroundColor: 'rgba(239,68,68,0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(239,68,68,0.2)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--negative)', marginBottom: 'var(--space-1)' }}>
            Penalties Applied
          </div>
          {opportunity.penalties.map((p, i) => (
            <div key={i} style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
              <span>{p.reason}</span>
              <span style={{ color: 'var(--negative)', fontWeight: 'var(--weight-semibold)' }}>-{p.points} pts</span>
            </div>
          ))}
        </div>
      )}

      {/* Supporting Evidence */}
      {opportunity.supporting_factors && opportunity.supporting_factors.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', color: 'var(--positive)' }}>
            ✓ Supporting Factors
          </h4>
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {opportunity.supporting_factors.map((factor, idx) => (
              <li key={idx}>{factor}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Contradicting Factors */}
      {opportunity.contradicting_factors && opportunity.contradicting_factors.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', color: 'var(--negative)' }}>
            ✕ Contradicting Factors
          </h4>
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {opportunity.contradicting_factors.map((factor, idx) => (
              <li key={idx}>{factor}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {opportunity.warnings && opportunity.warnings.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', color: 'var(--warning)' }}>
            ⚠ Warnings & Contextual Risks
          </h4>
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {opportunity.warnings.map((warn, idx) => (
              <li key={idx}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Invalidation Condition */}
      {opportunity.invalidation_condition && (
        <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-secondary, rgba(255,255,255,0.03))', borderRadius: 'var(--radius-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Invalidation Threshold</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', marginTop: '2px' }}>
            {opportunity.invalidation_condition}
          </div>
        </div>
      )}

      {/* Technical Metrics Grid */}
      <div>
        <h4 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          Key Intraday Metrics
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-2)', fontSize: '11px' }}>
          <div>Last Price: ₹{opportunity.metrics?.last_price?.toFixed(2) ?? '-'}</div>
          <div>Change: {opportunity.metrics?.change_pct?.toFixed(2) ?? '-'}%</div>
          <div>VWAP: ₹{opportunity.metrics?.vwap?.toFixed(2) ?? '-'}</div>
          <div>vs VWAP: {opportunity.metrics?.vwap_diff_pct?.toFixed(2) ?? '-'}%</div>
          <div>5m Momentum: {opportunity.metrics?.momentum_5m?.toFixed(2) ?? '-'}%</div>
          <div>15m Momentum: {opportunity.metrics?.momentum_15m?.toFixed(2) ?? '-'}%</div>
          <div>RS vs NIFTY: {opportunity.metrics?.relative_strength_vs_market?.toFixed(2) ?? '-'}%</div>
          <div>Relative Volume: {opportunity.metrics?.relative_volume?.toFixed(1) ?? '-'}x</div>
          <div>ORB State: {opportunity.metrics?.opening_range_state ?? '-'}</div>
          <div>Volume State: {opportunity.metrics?.volume_confirmation ?? '-'}</div>
        </div>
      </div>
    </Card>
  );
};
