import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import { useStockFundamentals } from '@/hooks/useStockFundamentals';

export interface FundamentalsTabProps {
  symbol: string;
}

export const FundamentalsTab: React.FC<FundamentalsTabProps> = ({ symbol }) => {
  const [statementType, setStatementType] = useState<'income' | 'balance' | 'cash'>('income');
  const { data, isLoading, error } = useStockFundamentals(symbol);

  if (isLoading) {
    return <Skeleton height="350px" />;
  }

  if (error || !data || data.data_quality?.status === 'NO_DATA') {
    return (
      <Card>
        <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
          Audited fundamental financial statements are currently unavailable for {symbol}.
        </div>
      </Card>
    );
  }

  const statements = data.statements;
  const metrics = data.metrics || [];

  // Format ratio metrics into a quick lookup
  const getMetric = (name: string): string => {
    const item = metrics.find((m) => m.name === name);
    if (!item || item.value === null) return '—';
    const num = Number(item.value);
    if (name.includes('growth') || name.includes('margin') || name.includes('return')) {
      return `${(num * 100).toFixed(2)}%`;
    }
    return num.toFixed(2);
  };

  const incomeCols: TableColumn<any>[] = [
    { key: 'fiscal_year', header: 'Year / Period' },
    { key: 'revenue', header: 'Revenue (₹ Cr)', isNumeric: true, render: (r) => r.revenue ? `₹${Number(r.revenue).toFixed(2)}` : '—' },
    { key: 'ebitda', header: 'EBITDA (₹ Cr)', isNumeric: true, render: (r) => r.ebitda ? `₹${Number(r.ebitda).toFixed(2)}` : '—' },
    { key: 'ebit', header: 'EBIT (₹ Cr)', isNumeric: true, render: (r) => r.ebit ? `₹${Number(r.ebit).toFixed(2)}` : '—' },
    { key: 'pat', header: 'PAT (₹ Cr)', isNumeric: true, render: (r) => r.pat ? `₹${Number(r.pat).toFixed(2)}` : '—' },
    { key: 'eps', header: 'EPS (₹)', isNumeric: true, render: (r) => r.eps ? `₹${Number(r.eps).toFixed(2)}` : '—' },
  ];

  const balanceCols: TableColumn<any>[] = [
    { key: 'fiscal_year', header: 'Year / Period' },
    { key: 'equity_capital', header: 'Equity (₹ Cr)', isNumeric: true, render: (r) => r.equity_capital ? `₹${Number(r.equity_capital).toFixed(2)}` : '—' },
    { key: 'reserves', header: 'Reserves (₹ Cr)', isNumeric: true, render: (r) => r.reserves ? `₹${Number(r.reserves).toFixed(2)}` : '—' },
    { key: 'borrowings', header: 'Borrowings (₹ Cr)', isNumeric: true, render: (r) => r.borrowings ? `₹${Number(r.borrowings).toFixed(2)}` : '—' },
    { key: 'total_assets', header: 'Total Assets (₹ Cr)', isNumeric: true, render: (r) => r.total_assets ? `₹${Number(r.total_assets).toFixed(2)}` : '—' },
  ];

  const cashCols: TableColumn<any>[] = [
    { key: 'fiscal_year', header: 'Year / Period' },
    { key: 'operating_cash_flow', header: 'Operating CF (₹ Cr)', isNumeric: true, render: (r) => r.operating_cash_flow ? `₹${Number(r.operating_cash_flow).toFixed(2)}` : '—' },
    { key: 'investing_cash_flow', header: 'Investing CF (₹ Cr)', isNumeric: true, render: (r) => r.investing_cash_flow ? `₹${Number(r.investing_cash_flow).toFixed(2)}` : '—' },
    { key: 'financing_cash_flow', header: 'Financing CF (₹ Cr)', isNumeric: true, render: (r) => r.financing_cash_flow ? `₹${Number(r.financing_cash_flow).toFixed(2)}` : '—' },
    { key: 'free_cash_flow', header: 'Free CF (₹ Cr)', isNumeric: true, render: (r) => r.free_cash_flow ? `₹${Number(r.free_cash_flow).toFixed(2)}` : '—' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* 1. Derived Financial Ratios Grid */}
      <Card header="Derived Financial Ratios & Profitability">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 'var(--space-3)' }}>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>RETURN ON EQUITY (ROE)</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('return_on_equity')}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>ROCE</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('return_on_capital_employed')}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>DEBT / EQUITY</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('debt_equity')}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>NET PROFIT MARGIN</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('net_margin')}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>REV GROWTH YOY</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('revenue_growth_yoy')}
            </div>
          </div>
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>P/E RATIO</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {getMetric('pe_ratio')}
            </div>
          </div>
        </div>
      </Card>

      {/* 2. Financial Statements Table */}
      <Card
        header="Audited Financial Statements"
        action={
          <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
            <button
              onClick={() => setStatementType('income')}
              style={{
                fontSize: 'var(--text-xs)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: statementType === 'income' ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
                color: statementType === 'income' ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
              }}
            >
              Income Statement
            </button>
            <button
              onClick={() => setStatementType('balance')}
              style={{
                fontSize: 'var(--text-xs)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: statementType === 'balance' ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
                color: statementType === 'balance' ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
              }}
            >
              Balance Sheet
            </button>
            <button
              onClick={() => setStatementType('cash')}
              style={{
                fontSize: 'var(--text-xs)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: statementType === 'cash' ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
                color: statementType === 'cash' ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
              }}
            >
              Cash Flow
            </button>
          </div>
        }
      >
        {statementType === 'income' && (
          <Table
            columns={incomeCols}
            data={statements?.income_statement || []}
            keyExtractor={(r) => r.id || String(r.fiscal_year)}
            emptyMessage="No income statement periods recorded."
          />
        )}
        {statementType === 'balance' && (
          <Table
            columns={balanceCols}
            data={statements?.balance_sheet || []}
            keyExtractor={(r) => r.id || String(r.fiscal_year)}
            emptyMessage="No balance sheet periods recorded."
          />
        )}
        {statementType === 'cash' && (
          <Table
            columns={cashCols}
            data={statements?.cash_flow || []}
            keyExtractor={(r) => r.id || String(r.fiscal_year)}
            emptyMessage="No cash flow periods recorded."
          />
        )}
      </Card>
    </div>
  );
};
