import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { WatchlistItem, DecisionStatus } from '../storage';
import { StockDetailResponse, StockRecommendation, StockOpportunitySnapshot } from '@/lib/api/types';

export interface EnrichedWatchlistItem {
  item: WatchlistItem;
  stockDetail?: StockDetailResponse | null;
  activeRec?: StockRecommendation | null;
  opportunity?: StockOpportunitySnapshot | null;
  isLoading?: boolean;
}

export interface MonitoredDecisionTableProps {
  items: EnrichedWatchlistItem[];
  onSelectRow: (item: WatchlistItem) => void;
  onRemoveSymbol: (symbol: string) => void;
}

export const MonitoredDecisionTable: React.FC<MonitoredDecisionTableProps> = ({
  items = [],
  onSelectRow,
  onRemoveSymbol,
}) => {
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');

  const getStatusBadge = (status: DecisionStatus) => {
    if (status === 'HOLDING') return <Badge variant="positive" size="sm">HOLDING</Badge>;
    if (status === 'CONSIDERING') return <Badge variant="brand" size="sm">CONSIDERING</Badge>;
    if (status === 'RESEARCHING') return <Badge variant="neutral" size="sm">RESEARCHING</Badge>;
    return <Badge variant="neutral" size="sm">WATCHING</Badge>;
  };

  const columns: TableColumn<EnrichedWatchlistItem>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)' }}>
          {r.item.symbol}
        </span>
      ),
    },
    {
      key: 'company',
      header: 'Company / Sector',
      render: (r) => {
        const comp = r.stockDetail?.instrument?.company;
        return (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)' }}>
              {comp?.name || r.item.symbol}
            </span>
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
              {comp?.sector || 'Equity'}
            </span>
          </div>
        );
      },
    },
    {
      key: 'price',
      header: 'Latest Close',
      isNumeric: true,
      render: (r) => {
        const snapshot = r.stockDetail?.latest_snapshot;
        if (!snapshot?.close) return '—';
        return (
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 'var(--weight-semibold)' }}>
            ₹{Number(snapshot.close).toFixed(2)}
          </span>
        );
      },
    },
    {
      key: 'change_percent',
      header: '1D Change',
      isNumeric: true,
      render: (r) => {
        const snapshot = r.stockDetail?.latest_snapshot;
        if (snapshot?.change_percent === undefined || snapshot?.change_percent === null) return '—';
        const isPositive = Number(snapshot.change_percent) >= 0;
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 'var(--weight-semibold)',
              color: isPositive ? 'var(--positive)' : 'var(--negative)',
            }}
          >
            {isPositive ? '+' : ''}{Number(snapshot.change_percent).toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'signal',
      header: 'Strategy Signal',
      render: (r) => {
        if (!r.activeRec) {
          return <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>No signal</span>;
        }
        return (
          <Badge variant={r.activeRec.signal === 'BUY' ? 'positive' : 'negative'} size="sm">
            {r.activeRec.signal} ({r.activeRec.setup_type || 'SWING'})
          </Badge>
        );
      },
    },
    {
      key: 'opportunity_score',
      header: 'Opp Score',
      isNumeric: true,
      render: (r) => {
        if (!r.opportunity) return '—';
        const score = Number(r.opportunity.final_score ?? r.opportunity.final_opportunity_score ?? 0);
        return (
          <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)' }}>
            {score.toFixed(0)}/100
          </span>
        );
      },
    },
    {
      key: 'decision_status',
      header: 'Decision State',
      render: (r) => getStatusBadge(r.item.decisionStatus),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center' }}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/stocks/${r.item.symbol}`);
            }}
            style={{
              padding: '2px 6px',
              fontSize: 'var(--text-2xs)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-xs)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            Terminal ↗
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/research?symbol=${r.item.symbol}`);
            }}
            style={{
              padding: '2px 6px',
              fontSize: 'var(--text-2xs)',
              backgroundColor: 'var(--brand-subtle)',
              border: '1px solid var(--brand-border)',
              borderRadius: 'var(--radius-xs)',
              color: 'var(--brand-primary)',
              cursor: 'pointer',
            }}
          >
            AI Research ↗
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemoveSymbol(r.item.symbol);
            }}
            style={{
              padding: '2px 6px',
              fontSize: 'var(--text-2xs)',
              backgroundColor: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      ),
    },
  ];

  return (
    <Card
      header="Monitored Decision Matrix"
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Button
            type="button"
            variant={viewMode === 'table' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setViewMode('table')}
          >
            📋 Table
          </Button>
          <Button
            type="button"
            variant={viewMode === 'cards' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setViewMode('cards')}
          >
            🗂️ Cards
          </Button>
        </div>
      }
      data-testid="monitored-decision-table"
    >
      {items.length === 0 ? (
        <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)' }}>
          Your watchlist is empty. Add a symbol above to start tracking real-time context and decision notes.
        </div>
      ) : viewMode === 'table' ? (
        <Table
          columns={columns}
          data={items}
          keyExtractor={(r) => r.item.symbol}
          onRowClick={(r) => onSelectRow(r.item)}
          emptyMessage="No stocks in this watchlist."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-3)' }}>
          {items.map((r) => {
            const snapshot = r.stockDetail?.latest_snapshot;
            const isPositive = (snapshot?.change_percent ?? 0) >= 0;
            return (
              <div
                key={r.item.symbol}
                onClick={() => onSelectRow(r.item)}
                style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-2)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)' }}>
                      {r.item.symbol}
                    </span>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                      {r.stockDetail?.instrument?.company?.name || r.item.symbol}
                    </div>
                  </div>
                  {getStatusBadge(r.item.decisionStatus)}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)' }}>
                    {snapshot?.close ? `₹${Number(snapshot.close).toFixed(2)}` : '—'}
                  </span>
                  {snapshot?.change_percent !== undefined && (
                    <span
                      style={{
                        fontSize: 'var(--text-xs)',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 'var(--weight-semibold)',
                        color: isPositive ? 'var(--positive)' : 'var(--negative)',
                      }}
                    >
                      {isPositive ? '+' : ''}{Number(snapshot.change_percent).toFixed(2)}%
                    </span>
                  )}
                </div>

                {r.item.notes && (
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontStyle: 'italic', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-1-5)' }}>
                    "{r.item.notes}"
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};
