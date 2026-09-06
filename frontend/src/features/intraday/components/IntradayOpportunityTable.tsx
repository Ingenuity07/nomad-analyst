import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { IntradayOpportunityItem, OpportunityType, OpportunityState } from '@/lib/api/types';

interface IntradayOpportunityTableProps {
  opportunities: IntradayOpportunityItem[];
  selectedSymbol: string | null;
  onSelectOpportunity: (opp: IntradayOpportunityItem) => void;
  onExamine?: (symbol: string) => void;
  isLoading?: boolean;
}

export const IntradayOpportunityTable: React.FC<IntradayOpportunityTableProps> = ({
  opportunities,
  selectedSymbol,
  onSelectOpportunity,
  onExamine,
  isLoading,
}) => {
  const getOpportunityTypeBadge = (type: OpportunityType) => {
    switch (type) {
      case 'MOMENTUM_CONTINUATION':
        return <Badge variant="brand">MOMENTUM</Badge>;
      case 'RELATIVE_STRENGTH':
        return <Badge variant="positive">REL STRENGTH</Badge>;
      case 'VWAP_TREND':
        return <Badge variant="brand">VWAP TREND</Badge>;
      case 'OPENING_RANGE_BREAKOUT':
        return <Badge variant="positive">ORB BREAKOUT</Badge>;
      case 'OPENING_RANGE_BREAKDOWN':
        return <Badge variant="negative">ORB BREAKDOWN</Badge>;
      case 'SECTOR_LEADERSHIP':
        return <Badge variant="positive">SECTOR LEADER</Badge>;
      case 'MEAN_REVERSION_CONTEXT':
        return <Badge variant="warning">MEAN REVERSION</Badge>;
      default:
        return <Badge variant="neutral">NEUTRAL</Badge>;
    }
  };

  const getStateBadge = (state: OpportunityState) => {
    switch (state) {
      case 'CONFIRMED':
        return <Badge variant="positive">CONFIRMED</Badge>;
      case 'EMERGING':
        return <Badge variant="brand">EMERGING</Badge>;
      case 'WEAKENING':
        return <Badge variant="warning">WEAKENING</Badge>;
      case 'INVALIDATED':
        return <Badge variant="neutral">INVALIDATED</Badge>;
      case 'STALE':
        return <Badge variant="negative">STALE</Badge>;
      default:
        return <Badge variant="neutral">{state}</Badge>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 75) return 'var(--positive, #22c55e)';
    if (score >= 60) return 'var(--brand-primary, #3b82f6)';
    if (score >= 45) return 'var(--warning, #eab308)';
    return 'var(--text-muted, #94a3b8)';
  };

  if (isLoading && opportunities.length === 0) {
    return (
      <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
        Evaluating intraday opportunities across universe...
      </div>
    );
  }

  if (opportunities.length === 0) {
    return (
      <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
        No intraday opportunities match the selected criteria.
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto', width: '100%' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-muted)' }}>
            <th style={{ padding: 'var(--space-2) var(--space-3)', width: '48px' }}>#</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)' }}>Symbol</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)' }}>Opportunity Type</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)' }}>State</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>Score</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>Confidence</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>Price / Chg</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>vs VWAP</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>RS (Mkt)</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'right' }}>RVOL</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)' }}>Sector</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)' }}>Mkt Alignment</th>
            <th style={{ padding: 'var(--space-2) var(--space-3)', textAlign: 'center' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((opp) => {
            const isSelected = selectedSymbol === opp.symbol;
            const changePct = opp.metrics?.change_pct ?? 0;
            const vwapDiff = opp.metrics?.vwap_diff_pct ?? 0;
            const rsMkt = opp.metrics?.relative_strength_vs_market ?? 0;
            const rvol = opp.metrics?.relative_volume ?? 1.0;

            return (
              <tr
                key={opp.symbol}
                onClick={() => onSelectOpportunity(opp)}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  backgroundColor: isSelected ? 'var(--bg-active, rgba(59,130,246,0.08))' : 'transparent',
                  transition: 'background-color 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-hover, rgba(255,255,255,0.03))';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {/* Rank */}
                <td style={{ padding: 'var(--space-3)', fontWeight: 'var(--weight-bold)', color: 'var(--text-muted)' }}>
                  {opp.rank ?? '-'}
                </td>

                {/* Symbol & Bias */}
                <td style={{ padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                      {opp.symbol}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {opp.bias}
                    </span>
                  </div>
                </td>

                {/* Type Badge */}
                <td style={{ padding: 'var(--space-3)' }}>
                  {getOpportunityTypeBadge(opp.opportunity_type)}
                </td>

                {/* State Badge */}
                <td style={{ padding: 'var(--space-3)' }}>
                  {getStateBadge(opp.state)}
                </td>

                {/* Score */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                    <span style={{ fontWeight: 'var(--weight-bold)', color: getScoreColor(opp.score), fontSize: 'var(--text-base)' }}>
                      {opp.score.toFixed(1)}
                    </span>
                    {opp.score_change !== undefined && opp.score_change !== 0 && (
                      <span style={{ fontSize: '10px', color: opp.score_change > 0 ? 'var(--positive)' : 'var(--negative)' }}>
                        {opp.score_change > 0 ? `+${opp.score_change.toFixed(1)}` : opp.score_change.toFixed(1)}
                      </span>
                    )}
                  </div>
                </td>

                {/* Confidence */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right', fontWeight: 'var(--weight-medium)' }}>
                  {(opp.confidence * 100).toFixed(0)}%
                </td>

                {/* Price & Change % */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                    <span>₹{opp.metrics?.last_price?.toFixed(2) ?? '-'}</span>
                    <span style={{ fontSize: '11px', color: changePct >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                      {changePct >= 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`}
                    </span>
                  </div>
                </td>

                {/* VWAP Diff */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right' }}>
                  <span style={{ color: vwapDiff >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                    {vwapDiff >= 0 ? `+${vwapDiff.toFixed(2)}%` : `${vwapDiff.toFixed(2)}%`}
                  </span>
                </td>

                {/* Relative Strength (Mkt) */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right' }}>
                  <span style={{ color: rsMkt >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                    {rsMkt >= 0 ? `+${rsMkt.toFixed(2)}%` : `${rsMkt.toFixed(2)}%`}
                  </span>
                </td>

                {/* RVOL */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'right', fontWeight: 'var(--weight-medium)' }}>
                  {rvol.toFixed(1)}x
                </td>

                {/* Sector */}
                <td style={{ padding: 'var(--space-3)', color: 'var(--text-secondary)' }}>
                  {opp.sector?.name ?? 'Unknown'}
                </td>

                {/* Market Alignment */}
                <td style={{ padding: 'var(--space-3)' }}>
                  <Badge variant={opp.market_alignment.includes('ALIGNED') ? 'positive' : opp.market_alignment.includes('DIVERGENT') ? 'negative' : 'neutral'}>
                    {opp.market_alignment}
                  </Badge>
                </td>

                {/* Action */}
                <td style={{ padding: 'var(--space-3)', textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    data-testid={`examine-btn-${opp.symbol}`}
                    onClick={() => onExamine ? onExamine(opp.symbol) : onSelectOpportunity(opp)}
                    style={{
                      padding: '4px 10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      borderRadius: 'var(--radius-sm, 4px)',
                      backgroundColor: 'rgba(59, 130, 246, 0.12)',
                      color: 'var(--brand-primary, #3b82f6)',
                      border: '1px solid rgba(59, 130, 246, 0.25)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      letterSpacing: '0.02em',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--brand-primary, #3b82f6)';
                      e.currentTarget.style.color = '#ffffff';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.12)';
                      e.currentTarget.style.color = 'var(--brand-primary, #3b82f6)';
                    }}
                  >
                    EXAMINE
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
