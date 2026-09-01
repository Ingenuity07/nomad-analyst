import React from 'react';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { StockOpportunitySnapshot } from '@/lib/api/types';

export interface OpportunityCandidateTableProps {
  candidates: StockOpportunitySnapshot[];
  selectedId?: string | null;
  onSelectCandidate: (item: StockOpportunitySnapshot) => void;
  isLoading?: boolean;
}

export const OpportunityCandidateTable: React.FC<OpportunityCandidateTableProps> = ({
  candidates,
  selectedId,
  onSelectCandidate,
  isLoading = false,
}) => {
  const columns: TableColumn<StockOpportunitySnapshot>[] = [
    {
      key: 'rank',
      header: 'Rank',
      width: '50px',
      render: (_, index = 0) => (
        <span style={{ fontWeight: 'var(--weight-bold)', color: (index || 0) < 3 ? 'var(--brand-primary)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          #{(index || 0) + 1}
        </span>
      ),
    },
    {
      key: 'symbol',
      header: 'Symbol',
      render: (item) => (
        <div>
          <div style={{ fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {item.symbol}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            {item.company_name}
          </div>
        </div>
      ),
    },
    {
      key: 'sector',
      header: 'Sector',
      render: (item) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          {item.sector}
        </span>
      ),
    },
    {
      key: 'opportunity_type',
      header: 'Setup Type',
      render: (item) => {
        const typeStr = (item.opportunity_type || 'STANDARD').replace('_', ' ');
        return (
          <Badge variant={typeStr.includes('BREAKOUT') || typeStr.includes('MOMENTUM') ? 'brand' : 'neutral'} size="sm">
            {typeStr}
          </Badge>
        );
      },
    },
    {
      key: 'final_opportunity_score',
      header: 'Opp Score',
      isNumeric: true,
      render: (item) => {
        const score = typeof item.final_opportunity_score === 'number'
          ? item.final_opportunity_score
          : parseFloat(item.final_opportunity_score) || 0;
        const variant = score >= 80 ? 'positive' : score >= 60 ? 'brand' : 'warning';
        return (
          <Badge variant={variant} size="md">
            ★ {score.toFixed(1)}
          </Badge>
        );
      },
    },
    {
      key: 'component_scores',
      header: 'Tech / Fund / Sec',
      isNumeric: true,
      render: (item) => {
        const tech = item.component_scores?.technical ?? '—';
        const fund = item.component_scores?.fundamental ?? '—';
        const sec = item.component_scores?.sector ?? '—';
        return (
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            {typeof tech === 'number' ? tech.toFixed(0) : tech} / {typeof fund === 'number' ? fund.toFixed(0) : fund} / {typeof sec === 'number' ? sec.toFixed(0) : sec}
          </span>
        );
      },
    },
    {
      key: 'primary_pro',
      header: 'Key Supporting Factor',
      render: (item) => {
        const pro = item.supporting_features?.pros?.[0] || '—';
        return (
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', maxWidth: '300px', display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={pro}>
            ✓ {pro}
          </span>
        );
      },
    },
    {
      key: 'action',
      header: '',
      width: '100px',
      render: (item) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSelectCandidate(item);
          }}
          style={{
            fontSize: 'var(--text-xs)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-xs)',
            backgroundColor: item.id === selectedId ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
            color: item.id === selectedId ? '#FFFFFF' : 'var(--text-primary)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          Inspect →
        </button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      data={candidates}
      keyExtractor={(item) => item.id || item.symbol}
      onRowClick={onSelectCandidate}
      emptyMessage={isLoading ? 'Loading ranked delivery candidates...' : 'No delivery opportunities match the active filters.'}
    />
  );
};
