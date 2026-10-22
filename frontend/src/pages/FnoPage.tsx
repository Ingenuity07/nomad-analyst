import React, { useState } from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Tabs, TabItem } from '@/components/ui/Tabs';
import { useFnoOverview } from '@/hooks/useFnoData';
import { FnoWorkspaceHeader } from '@/features/fno/components/FnoWorkspaceHeader';
import { FnoOverviewTab } from '@/features/fno/components/FnoOverviewTab';
import { FnoStrategyTab } from '@/features/fno/components/FnoStrategyTab';
import { FnoLedgerTab } from '@/features/fno/components/FnoLedgerTab';
import { FnoDiagnosticsTab } from '@/features/fno/components/FnoDiagnosticsTab';

const TABS: TabItem[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'trades', label: 'Paper Trading' },
  { key: 'diagnostics', label: 'Diagnostics' },
];

export const FnoPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const { data: overview, isLoading: isOverviewLoading } = useFnoOverview();

  const handleTabChange = (key: string) => {
    setActiveTab(key);
  };

  return (
    <PageContainer
      title="F&O Laboratory"
      subtitle="Institutional-grade options intelligence, strategy telemetry, and paper trade ledger (Trial Inactive — Approval Required)"
    >
      {/* Workspace Metric Header */}
      <FnoWorkspaceHeader overview={overview} isLoading={isOverviewLoading} />

      {/* Tab Navigation */}
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <Tabs
          tabs={TABS}
          activeKey={activeTab}
          onChange={handleTabChange}
          variant="underline"
        />
      </div>

      {/* Tab Content Display */}
      {activeTab === 'overview' && <FnoOverviewTab />}
      {activeTab === 'strategy' && <FnoStrategyTab />}
      {activeTab === 'trades' && <FnoLedgerTab />}
      {activeTab === 'diagnostics' && <FnoDiagnosticsTab />}
    </PageContainer>
  );
};

export default FnoPage;
