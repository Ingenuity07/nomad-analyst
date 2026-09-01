import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';
import { Table, TableColumn } from '@/components/ui/Table';
import { Button } from '@/components/ui/Button';
import { IncomeStatement, BalanceSheetStatement, CashFlowStatement } from '@/lib/api/types';
import { FinancialTrendCharts } from './FinancialTrendCharts';

export interface FinancialStatementExplorerProps {
  incomeStatements: IncomeStatement[];
  balanceSheets: BalanceSheetStatement[];
  cashFlows: CashFlowStatement[];
  companyName: string;
}

export const FinancialStatementExplorer: React.FC<FinancialStatementExplorerProps> = ({
  incomeStatements = [],
  balanceSheets = [],
  cashFlows = [],
  companyName,
}) => {
  const [statementType, setStatementType] = useState<string>('income');
  const [viewMode, setViewMode] = useState<'table' | 'trend'>('table');

  const tabs = [
    { key: 'income', label: `Income Statement (${incomeStatements.length})` },
    { key: 'balance', label: `Balance Sheet (${balanceSheets.length})` },
    { key: 'cash', label: `Cash Flow (${cashFlows.length})` },
  ];

  // Table Columns
  const incomeCols: TableColumn<IncomeStatement>[] = [
    { key: 'period_string', header: 'Fiscal Period', render: (r) => r.period_string || String(r.fiscal_year) },
    { key: 'revenue', header: 'Revenue (₹ Cr)', isNumeric: true, render: (r) => r.revenue !== null && r.revenue !== undefined ? `₹${Number(r.revenue).toFixed(2)}` : '—' },
    { key: 'expenses', header: 'Expenses (₹ Cr)', isNumeric: true, render: (r) => r.expenses !== null && r.expenses !== undefined ? `₹${Number(r.expenses).toFixed(2)}` : '—' },
    { key: 'ebitda', header: 'EBITDA (₹ Cr)', isNumeric: true, render: (r) => r.ebitda !== null && r.ebitda !== undefined ? `₹${Number(r.ebitda).toFixed(2)}` : '—' },
    { key: 'ebit', header: 'EBIT (₹ Cr)', isNumeric: true, render: (r) => r.ebit !== null && r.ebit !== undefined ? `₹${Number(r.ebit).toFixed(2)}` : '—' },
    { key: 'pbt', header: 'PBT (₹ Cr)', isNumeric: true, render: (r) => r.pbt !== null && r.pbt !== undefined ? `₹${Number(r.pbt).toFixed(2)}` : '—' },
    { key: 'tax', header: 'Tax (₹ Cr)', isNumeric: true, render: (r) => r.tax !== null && r.tax !== undefined ? `₹${Number(r.tax).toFixed(2)}` : '—' },
    { key: 'pat', header: 'PAT (₹ Cr)', isNumeric: true, render: (r) => r.pat !== null && r.pat !== undefined ? `₹${Number(r.pat).toFixed(2)}` : '—' },
    { key: 'eps', header: 'EPS (₹)', isNumeric: true, render: (r) => r.eps !== null && r.eps !== undefined ? `₹${Number(r.eps).toFixed(2)}` : '—' },
    { key: 'filing_date', header: 'Filing Date (PIT)', render: (r) => r.filing_date || 'Historical (PIT Unavail)' },
  ];

  const balanceCols: TableColumn<BalanceSheetStatement>[] = [
    { key: 'period_string', header: 'Fiscal Period', render: (r) => r.period_string || String(r.fiscal_year) },
    { key: 'equity_capital', header: 'Equity (₹ Cr)', isNumeric: true, render: (r) => r.equity_capital !== null && r.equity_capital !== undefined ? `₹${Number(r.equity_capital).toFixed(2)}` : '—' },
    { key: 'reserves', header: 'Reserves (₹ Cr)', isNumeric: true, render: (r) => r.reserves !== null && r.reserves !== undefined ? `₹${Number(r.reserves).toFixed(2)}` : '—' },
    { key: 'borrowings', header: 'Borrowings (₹ Cr)', isNumeric: true, render: (r) => r.borrowings !== null && r.borrowings !== undefined ? `₹${Number(r.borrowings).toFixed(2)}` : '—' },
    { key: 'other_liabilities', header: 'Other Liab (₹ Cr)', isNumeric: true, render: (r) => r.other_liabilities !== null && r.other_liabilities !== undefined ? `₹${Number(r.other_liabilities).toFixed(2)}` : '—' },
    { key: 'total_liabilities', header: 'Total Liab (₹ Cr)', isNumeric: true, render: (r) => r.total_liabilities !== null && r.total_liabilities !== undefined ? `₹${Number(r.total_liabilities).toFixed(2)}` : '—' },
    { key: 'fixed_assets', header: 'Fixed Assets (₹ Cr)', isNumeric: true, render: (r) => r.fixed_assets !== null && r.fixed_assets !== undefined ? `₹${Number(r.fixed_assets).toFixed(2)}` : '—' },
    { key: 'investments', header: 'Investments (₹ Cr)', isNumeric: true, render: (r) => r.investments !== null && r.investments !== undefined ? `₹${Number(r.investments).toFixed(2)}` : '—' },
    { key: 'total_assets', header: 'Total Assets (₹ Cr)', isNumeric: true, render: (r) => r.total_assets !== null && r.total_assets !== undefined ? `₹${Number(r.total_assets).toFixed(2)}` : '—' },
    { key: 'filing_date', header: 'Filing Date (PIT)', render: (r) => r.filing_date || 'Historical (PIT Unavail)' },
  ];

  const cashCols: TableColumn<CashFlowStatement>[] = [
    { key: 'period_string', header: 'Fiscal Period', render: (r) => r.period_string || String(r.fiscal_year) },
    { key: 'operating_cash_flow', header: 'Operating CF (₹ Cr)', isNumeric: true, render: (r) => r.operating_cash_flow !== null && r.operating_cash_flow !== undefined ? `₹${Number(r.operating_cash_flow).toFixed(2)}` : '—' },
    { key: 'investing_cash_flow', header: 'Investing CF (₹ Cr)', isNumeric: true, render: (r) => r.investing_cash_flow !== null && r.investing_cash_flow !== undefined ? `₹${Number(r.investing_cash_flow).toFixed(2)}` : '—' },
    { key: 'financing_cash_flow', header: 'Financing CF (₹ Cr)', isNumeric: true, render: (r) => r.financing_cash_flow !== null && r.financing_cash_flow !== undefined ? `₹${Number(r.financing_cash_flow).toFixed(2)}` : '—' },
    { key: 'free_cash_flow', header: 'Free CF (₹ Cr)', isNumeric: true, render: (r) => r.free_cash_flow !== null && r.free_cash_flow !== undefined ? `₹${Number(r.free_cash_flow).toFixed(2)}` : '—' },
    { key: 'filing_date', header: 'Filing Date (PIT)', render: (r) => r.filing_date || 'Historical (PIT Unavail)' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }} data-testid="financial-statement-explorer">
      {/* View Switcher Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <Tabs tabs={tabs} activeKey={statementType} onChange={setStatementType} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Button
            type="button"
            variant={viewMode === 'table' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setViewMode('table')}
          >
            📋 Tabular Statement View
          </Button>
          <Button
            type="button"
            variant={viewMode === 'trend' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setViewMode('trend')}
          >
            📈 Performance Trends
          </Button>
        </div>
      </div>

      {/* Main Statement Content */}
      {viewMode === 'table' ? (
        <Card header={`${tabs.find((t) => t.key === statementType)?.label} — ${companyName}`}>
          {statementType === 'income' && (
            <Table
              columns={incomeCols}
              data={incomeStatements}
              keyExtractor={(r) => r.id || r.period_string || String(r.fiscal_year)}
              emptyMessage="No income statement periods recorded."
            />
          )}
          {statementType === 'balance' && (
            <Table
              columns={balanceCols}
              data={balanceSheets}
              keyExtractor={(r) => r.id || r.period_string || String(r.fiscal_year)}
              emptyMessage="No balance sheet periods recorded."
            />
          )}
          {statementType === 'cash' && (
            <Table
              columns={cashCols}
              data={cashFlows}
              keyExtractor={(r) => r.id || r.period_string || String(r.fiscal_year)}
              emptyMessage="No cash flow periods recorded."
            />
          )}
        </Card>
      ) : (
        <FinancialTrendCharts
          incomeStatements={incomeStatements}
          cashFlows={cashFlows}
          balanceSheets={balanceSheets}
        />
      )}
    </div>
  );
};
