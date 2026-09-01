import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Tabs } from '@/components/ui/Tabs';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';

import { useStock } from '@/hooks/useStock';
import { StockHeader } from '@/features/stockDetail/components/StockHeader';
import { StockChartCard } from '@/features/stockDetail/components/StockChartCard';
import { OverviewTab } from '@/features/stockDetail/components/OverviewTab';
import { TechnicalsTab } from '@/features/stockDetail/components/TechnicalsTab';
import { FundamentalsTab } from '@/features/stockDetail/components/FundamentalsTab';
import { NewsEventsTab } from '@/features/stockDetail/components/NewsEventsTab';
import { AIResearchTab } from '@/features/stockDetail/components/AIResearchTab';

export const StockDetailPage: React.FC = () => {
  const { symbol = '' } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<string>('overview');

  const { data: stockData, isLoading, error, refetch } = useStock(symbol);

  if (!symbol) {
    return (
      <PageContainer title="Stock Not Specified">
        <ErrorState
          title="Missing Stock Symbol"
          message="No ticker symbol was provided in the route."
          onRetry={() => navigate('/market')}
        />
      </PageContainer>
    );
  }

  if (isLoading) {
    return (
      <PageContainer title={`Loading ${symbol.toUpperCase()}...`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          <Skeleton height="80px" />
          <Skeleton height="400px" />
          <Skeleton height="250px" />
        </div>
      </PageContainer>
    );
  }

  if (error || !stockData) {
    return (
      <PageContainer title={`Stock Not Found — ${symbol.toUpperCase()}`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', alignItems: 'center' }}>
          <ErrorState
            title={`Symbol '${symbol.toUpperCase()}' Not Found`}
            message={error?.message || 'Unable to load company details and financial time-series.'}
            onRetry={() => refetch()}
          />
          <Button variant="secondary" size="sm" onClick={() => navigate('/delivery')}>
            ← Back to Opportunities
          </Button>
        </div>
      </PageContainer>
    );
  }

  const tabs = [
    { key: 'overview', label: 'Overview & Signals' },
    { key: 'technicals', label: 'Technical Indicators' },
    { key: 'fundamentals', label: 'Audited Statements & Ratios' },
    { key: 'news', label: 'News & Disclosures' },
    { key: 'ai', label: 'AI Research Synthesis' },
  ];

  return (
    <PageContainer title={`${symbol.toUpperCase()} — Financial Research Terminal`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        {/* 1. Header with Quote & Freshness */}
        <section aria-label="Stock Header">
          <StockHeader data={stockData} symbol={symbol} />
        </section>

        {/* 2. Interactive Lightweight Candlestick + Volume Chart */}
        <section aria-label="Interactive Stock Chart">
          <StockChartCard symbol={symbol} />
        </section>

        {/* 3. Research Navigation Tabs */}
        <section aria-label="Stock Research Tabs">
          <Tabs
            tabs={tabs}
            activeKey={activeTab}
            onChange={setActiveTab}
          />
        </section>

        {/* 4. Active Tab Content Panel */}
        <section aria-label="Stock Research Panel">
          {activeTab === 'overview' && (
            <OverviewTab data={stockData} symbol={symbol} />
          )}
          {activeTab === 'technicals' && (
            <TechnicalsTab symbol={symbol} />
          )}
          {activeTab === 'fundamentals' && (
            <FundamentalsTab symbol={symbol} />
          )}
          {activeTab === 'news' && (
            <NewsEventsTab symbol={symbol} />
          )}
          {activeTab === 'ai' && (
            <AIResearchTab symbol={symbol} />
          )}
        </section>
      </div>
    </PageContainer>
  );
};
export default StockDetailPage;
