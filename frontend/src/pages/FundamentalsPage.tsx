import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';

import { useStock } from '@/hooks/useStock';
import { useStockFundamentals } from '@/hooks/useStockFundamentals';
import { useStockEvents } from '@/hooks/useStockEvents';
import { useStockNews } from '@/hooks/useStockNews';

import { CompanySearchSelector } from '@/features/fundamentals/components/CompanySearchSelector';
import { CompanyProfileHeader } from '@/features/fundamentals/components/CompanyProfileHeader';
import { FundamentalSnapshotCards } from '@/features/fundamentals/components/FundamentalSnapshotCards';
import { FinancialStatementExplorer } from '@/features/fundamentals/components/FinancialStatementExplorer';
import { ExchangeDisclosuresCard } from '@/features/fundamentals/components/ExchangeDisclosuresCard';
import { RecentNewsCard } from '@/features/fundamentals/components/RecentNewsCard';

export const FundamentalsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const symbol = searchParams.get('symbol') || 'RELIANCE';

  const handleSelectSymbol = (newSymbol: string) => {
    setSearchParams({ symbol: newSymbol });
  };

  // Queries
  const { data: stockData, isLoading: isStockLoading, error: stockError, refetch: refetchStock } = useStock(symbol);
  const { data: fundamentalsData, isLoading: isFundLoading, error: fundError, refetch: refetchFund } = useStockFundamentals(symbol);
  const { data: eventsData, isLoading: isEventsLoading } = useStockEvents(symbol, 30);
  const { data: newsData } = useStockNews(symbol, 5);

  const companyName = stockData?.instrument?.company?.name || fundamentalsData?.company_name || symbol;

  return (
    <PageContainer
      title="Company Fundamentals & Corporate Intelligence"
      subtitle="Audited financial statements, derived balance sheet health, valuation ratios, and exchange regulatory disclosures."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* 1. Quick Company Selector */}
        <section aria-label="Company Selector">
          <CompanySearchSelector
            currentSymbol={symbol}
            onSelectSymbol={handleSelectSymbol}
          />
        </section>

        {/* 2. Company Profile & Header */}
        <section aria-label="Company Profile Header">
          {isStockLoading ? (
            <Skeleton height="140px" />
          ) : stockError || !stockData ? (
            <ErrorState
              title={`Company Profile Unavailable for ${symbol}`}
              message={stockError?.message || 'Failed to load company details and profile.'}
              onRetry={() => refetchStock()}
            />
          ) : (
            <CompanyProfileHeader data={stockData} symbol={symbol} />
          )}
        </section>

        {/* 3. Key Derived Financial Ratios & Health Metrics */}
        <section aria-label="Fundamental Ratios">
          {isFundLoading ? (
            <Skeleton height="160px" />
          ) : (
            <FundamentalSnapshotCards
              metrics={fundamentalsData?.metrics || []}
              companyName={companyName}
            />
          )}
        </section>

        {/* 4. Financial Statement Explorer (Income, Balance Sheet, Cash Flow + Trends) */}
        <section aria-label="Financial Statements">
          {isFundLoading ? (
            <Skeleton height="350px" />
          ) : fundError ? (
            <ErrorState
              title="Financial Statements Unavailable"
              message={fundError?.message || 'Failed to load audited financial statements.'}
              onRetry={() => refetchFund()}
            />
          ) : (
            <FinancialStatementExplorer
              incomeStatements={fundamentalsData?.statements?.income_statement || []}
              balanceSheets={fundamentalsData?.statements?.balance_sheet || []}
              cashFlows={fundamentalsData?.statements?.cash_flow || []}
              companyName={companyName}
            />
          )}
        </section>

        {/* 5. Split Bottom Row: Exchange Regulatory Filings & Recent Material News */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 'var(--space-6)' }}>
          {/* Exchange Disclosures */}
          <section aria-label="Exchange Filings">
            {isEventsLoading ? (
              <Skeleton height="240px" />
            ) : (
              <ExchangeDisclosuresCard
                disclosures={eventsData?.results || []}
                companyName={companyName}
              />
            )}
          </section>

          {/* Recent News */}
          <section aria-label="Recent News">
            <RecentNewsCard
              news={newsData?.results || []}
              symbol={symbol}
            />
          </section>
        </div>
      </div>
    </PageContainer>
  );
};
