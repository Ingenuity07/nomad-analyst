import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Tabs } from '@/components/ui/Tabs';
import { Skeleton } from '@/components/ui/Skeleton';

import { useSectorConstituents } from '@/hooks/useSectorConstituents';
import { useOpportunities } from '@/hooks/useOpportunities';
import { StockSummary, StockOpportunitySnapshot } from '@/lib/api/types';

export interface SelectedSectorDetailProps {
  sector: string;
}

export const SelectedSectorDetail: React.FC<SelectedSectorDetailProps> = ({ sector }) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<string>('constituents');

  const { data: constituentsData, isLoading: isStocksLoading } = useSectorConstituents(sector, 1);
  const { data: oppsData, isLoading: isOppsLoading } = useOpportunities({ sector });

  const stocks = constituentsData?.results || [];
  const opportunities = oppsData?.results || [];

  const tabs = [
    { key: 'constituents', label: `Constituent Equities (${constituentsData?.count ?? stocks.length})` },
    { key: 'opportunities', label: `Delivery Opportunities (${opportunities.length})` },
  ];

  const stockCols: TableColumn<StockSummary>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)' }}>
          {r.symbol}
        </span>
      ),
    },
    {
      key: 'company_name',
      header: 'Company Name',
      render: (r) => r.company_name || r.name || '—',
    },
    {
      key: 'exchange',
      header: 'Exchange',
      render: (r) => <Badge variant="neutral" size="sm">{r.exchange || 'NSE'}</Badge>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div style={{ display: 'flex', gap: 'var(--space-1-5)' }}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/stocks/${r.symbol}`);
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
              navigate(`/fundamentals?symbol=${r.symbol}`);
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
            Fundamentals ↗
          </button>
        </div>
      ),
    },
  ];

  const oppCols: TableColumn<StockOpportunitySnapshot>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)' }}>
          {r.symbol}
        </span>
      ),
    },
    {
      key: 'opportunity_type',
      header: 'Setup Type',
      render: (r) => <Badge variant="brand" size="sm">{r.opportunity_type || 'SWING'}</Badge>,
    },
    {
      key: 'final_score',
      header: 'Score',
      isNumeric: true,
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)' }}>
          {Number(r.final_score ?? r.final_opportunity_score ?? 0).toFixed(0)}/100
        </span>
      ),
    },
    {
      key: 'reasons',
      header: 'Primary Drivers',
      render: (r) => (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          {r.reasons && r.reasons.length > 0 ? r.reasons[0] : 'Momentum alignment'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Action',
      render: () => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/delivery?sector=${encodeURIComponent(sector)}`);
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
          View Setup ↗
        </button>
      ),
    },
  ];

  const handleResearchSector = () => {
    const question = `Perform an institutional sector outlook and momentum analysis on the ${sector} sector in India.`;
    navigate(`/research?question=${encodeURIComponent(question)}`);
  };

  return (
    <Card
      header={`Sector Drill-Down — ${sector}`}
      action={
        <Button
          data-testid="research-sector-button"
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleResearchSector}
        >
          🤖 Synthesize Sector Thesis in AI Laboratory
        </Button>
      }
      data-testid="selected-sector-detail"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Tabs tabs={tabs} activeKey={activeTab} onChange={setActiveTab} />

        {activeTab === 'constituents' && (
          <div>
            {isStocksLoading ? (
              <Skeleton height="200px" />
            ) : (
              <Table
                columns={stockCols}
                data={stocks}
                keyExtractor={(r) => r.symbol}
                onRowClick={(r) => navigate(`/stocks/${r.symbol}`)}
                emptyMessage={`No constituent equities found for sector '${sector}'.`}
              />
            )}
          </div>
        )}

        {activeTab === 'opportunities' && (
          <div>
            {isOppsLoading ? (
              <Skeleton height="200px" />
            ) : (
              <Table
                columns={oppCols}
                data={opportunities}
                keyExtractor={(r) => r.symbol || r.id}
                onRowClick={(r) => navigate(`/stocks/${r.symbol}`)}
                emptyMessage={`No active delivery swing opportunities currently recorded for '${sector}'.`}
              />
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
