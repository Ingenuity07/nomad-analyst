import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Table } from '@/components/ui/Table';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Tabs } from '@/components/ui/Tabs';
import { Metric } from '@/components/ui/Metric';
import { DataStatus } from '@/components/ui/DataStatus';
import { Timestamp } from '@/components/ui/Timestamp';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Modal } from '@/components/ui/Modal';
import { Tooltip } from '@/components/ui/Tooltip';

export const DesignSystemShowcase: React.FC = () => {
  const [activeTab, setActiveTab] = useState('primitives');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');

  const sampleTableData = [
    { symbol: 'RELIANCE', sector: 'Energy', ltp: 1309.0, change: 2.51, volume: '12.61 M', score: 87.0 },
    { symbol: 'TCS', sector: 'Technology', ltp: 4215.5, change: -0.84, volume: '2.14 M', score: 74.5 },
    { symbol: 'HDFCBANK', sector: 'Financials', ltp: 1650.2, change: 1.12, volume: '8.90 M', score: 81.0 },
    { symbol: 'INFY', sector: 'Technology', ltp: 1820.0, change: -1.45, volume: '5.40 M', score: 68.0 },
  ];

  return (
    <PageContainer
      title="Design System & Component Showcase"
      subtitle="Canonical institutional design tokens, typography, tabular alignments, and component primitives"
      action={<DataStatus status="LIVE" source="Tokens v1.0" />}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        tabs={[
          { key: 'primitives', label: 'UI Primitives' },
          { key: 'financial_tables', label: 'Financial Tables' },
          { key: 'metric_tiles', label: 'Metric Tiles' },
          { key: 'states', label: 'System States' },
        ]}
      />

      <div style={{ marginTop: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {activeTab === 'primitives' && (
          <>
            {/* Buttons */}
            <Card header="1. Buttons & Actions">
              <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
                <Button variant="primary">Primary Action</Button>
                <Button variant="secondary">Secondary Action</Button>
                <Button variant="outline">Outline Action</Button>
                <Button variant="ghost">Ghost Action</Button>
                <Button variant="danger">Danger Action</Button>
                <Button variant="primary" isLoading>Loading State</Button>
                <Button variant="outline" onClick={() => setIsModalOpen(true)}>Open Modal Dialog</Button>
              </div>
            </Card>

            {/* Badges & Statuses */}
            <Card header="2. Status & Directional Badges">
              <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
                <Tooltip content="Bullish entry signal identified by momentum engine">
                  <Badge variant="positive">▲ BUY</Badge>
                </Tooltip>
                <Badge variant="negative">▼ SELL</Badge>
                <Badge variant="warning">⚠ STALE DATA</Badge>
                <Badge variant="brand">★ TOP PICK</Badge>
                <Badge variant="neutral">● NO ACTION</Badge>
                <DataStatus status="LIVE" source="NSE Cash" />
                <DataStatus status="STALE" lastUpdated="5m ago" />
                <DataStatus status="INCOMPLETE" />
                <DataStatus status="UNAVAILABLE" />
                <Timestamp isoString={new Date().toISOString()} format="full" />
              </div>
            </Card>

            {/* Form Controls */}
            <Card header="3. Form Inputs & Selects">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                <Input
                  label="Search Symbol"
                  placeholder="e.g. RELIANCE"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                />
                <Select
                  label="Execution Universe"
                  options={[
                    { value: 'NIFTY50', label: 'NIFTY 50 Benchmark' },
                    { value: 'NIFTYNEXT50', label: 'NIFTY Next 50' },
                    { value: 'NIFTYMIDCAP50', label: 'NIFTY MidCap 50' },
                  ]}
                />
              </div>
            </Card>
          </>
        )}

        {activeTab === 'financial_tables' && (
          <Card header="Financial Tabular Data (Tabular Numerals & Monospace Right Alignment)">
            <Table
              keyExtractor={(item) => item.symbol}
              data={sampleTableData}
              columns={[
                {
                  key: 'symbol',
                  header: 'Symbol',
                  render: (item) => (
                    <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      {item.symbol}
                    </span>
                  ),
                },
                { key: 'sector', header: 'Sector' },
                {
                  key: 'ltp',
                  header: 'LTP (INR)',
                  isNumeric: true,
                  render: (item) => `₹${item.ltp.toFixed(2)}`,
                },
                {
                  key: 'change',
                  header: 'Change %',
                  isNumeric: true,
                  render: (item) => (
                    <span style={{ color: item.change >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                      {item.change >= 0 ? '+' : ''}{item.change.toFixed(2)}%
                    </span>
                  ),
                },
                { key: 'volume', header: 'Volume', isNumeric: true },
                {
                  key: 'score',
                  header: 'Opp Score',
                  isNumeric: true,
                  render: (item) => (
                    <Badge variant={item.score >= 80 ? 'positive' : 'brand'}>
                      {item.score.toFixed(1)}
                    </Badge>
                  ),
                },
              ]}
            />
          </Card>
        )}

        {activeTab === 'metric_tiles' && (
          <Card header="Institutional Metric Tiles">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-6)' }}>
              <Metric label="NIFTY 50" value="25,410.80" delta={0.45} prefix="₹" subtext="All-time high zone" />
              <Metric label="Market Breadth (A/D)" value="1.85" delta={12.4} subtext="32 Adv / 18 Dec" />
              <Metric label="Avg R-Multiple" value="+1.76 R" subtext="30-day delivery swing" />
              <Metric label="Win Rate" value="68.4%" delta={-2.1} isPositiveGood={true} subtext="Delivery Swing Strategy" />
            </div>
          </Card>
        )}

        {activeTab === 'states' && (
          <>
            <Card header="Skeleton Loading States">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <Skeleton height="24px" width="40%" />
                <Skeleton height="16px" width="80%" />
                <Skeleton height="16px" width="60%" />
              </div>
            </Card>

            <Card header="Error & Empty States">
              <ErrorState
                title="Failed to Load Financial Statement"
                message="Backend provider returned 404 for requested period."
                code="STATEMENT_NOT_FOUND"
                onRetry={() => alert('Retrying...')}
              />
              <EmptyState
                icon="📊"
                title="No Active Trade Recommendations"
                description="The signal engine did not find any setups matching the current risk-reward filters."
              />
            </Card>
          </>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Sample Modal Dialog">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          This is an accessible, keyboard-dismissible institutional modal container.
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-6)' }}>
          <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
          <Button variant="primary" onClick={() => setIsModalOpen(false)}>Confirm Action</Button>
        </div>
      </Modal>
    </PageContainer>
  );
};
