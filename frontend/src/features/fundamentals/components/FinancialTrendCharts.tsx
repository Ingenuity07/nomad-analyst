import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { IncomeStatement, CashFlowStatement, BalanceSheetStatement } from '@/lib/api/types';

export interface FinancialTrendChartsProps {
  incomeStatements: IncomeStatement[];
  cashFlows: CashFlowStatement[];
  balanceSheets: BalanceSheetStatement[];
}

export const FinancialTrendCharts: React.FC<FinancialTrendChartsProps> = ({
  incomeStatements = [],
  cashFlows = [],
}) => {
  const [metricKey, setMetricKey] = useState<'revenue' | 'ebitda' | 'pat' | 'eps' | 'cfo' | 'fcf'>('revenue');

  // Sort chronologically ascending for trends
  const sortedIncomes = [...incomeStatements].sort((a, b) => a.fiscal_year - b.fiscal_year);
  const sortedCash = [...cashFlows].sort((a, b) => a.fiscal_year - b.fiscal_year);

  const getMetricData = () => {
    if (metricKey === 'revenue') {
      return sortedIncomes.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.revenue) || 0 }));
    }
    if (metricKey === 'ebitda') {
      return sortedIncomes.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.ebitda) || 0 }));
    }
    if (metricKey === 'pat') {
      return sortedIncomes.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.pat) || 0 }));
    }
    if (metricKey === 'eps') {
      return sortedIncomes.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.eps) || 0 }));
    }
    if (metricKey === 'cfo') {
      return sortedCash.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.operating_cash_flow) || 0 }));
    }
    if (metricKey === 'fcf') {
      return sortedCash.map((d) => ({ period: d.period_string || String(d.fiscal_year), val: Number(d.free_cash_flow) || 0 }));
    }
    return [];
  };

  const data = getMetricData();
  const maxVal = Math.max(...data.map((d) => Math.abs(d.val)), 1);

  const metricsConfig = [
    { key: 'revenue', label: 'Revenue (₹ Cr)' },
    { key: 'ebitda', label: 'EBITDA (₹ Cr)' },
    { key: 'pat', label: 'PAT (₹ Cr)' },
    { key: 'eps', label: 'EPS (₹)' },
    { key: 'cfo', label: 'Operating CF (₹ Cr)' },
    { key: 'fcf', label: 'Free Cash Flow (₹ Cr)' },
  ];

  if (data.length === 0) {
    return (
      <Card header="Historical Financial Trends">
        <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
          Insufficient historical financial statement periods for chart generation.
        </div>
      </Card>
    );
  }

  return (
    <Card header="Historical Financial Trajectory & Performance Trends" data-testid="financial-trend-charts">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Metric Selector Buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {metricsConfig.map((m) => {
            const isSelected = metricKey === m.key;
            return (
              <button
                key={m.key}
                type="button"
                onClick={() => setMetricKey(m.key as any)}
                style={{
                  padding: 'var(--space-1-5) var(--space-3)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                  color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                  backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-sunken)',
                  border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                {m.label}
              </button>
            );
          })}
        </div>

        {/* Visual Bar Chart */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            gap: 'var(--space-3)',
            height: '220px',
            padding: 'var(--space-4) var(--space-2) var(--space-2) var(--space-2)',
            backgroundColor: 'var(--bg-surface-sunken)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            overflowX: 'auto',
          }}
        >
          {data.map((item, idx) => {
            const heightPercent = Math.min(Math.max((Math.abs(item.val) / maxVal) * 85, 4), 100);
            const isPositive = item.val >= 0;

            return (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 'var(--space-1)',
                  flex: '1 1 0%',
                  minWidth: '48px',
                  height: '100%',
                  justifyContent: 'flex-end',
                }}
              >
                {/* Value Label */}
                <span
                  style={{
                    fontSize: 'var(--text-2xs)',
                    fontFamily: 'var(--font-mono)',
                    color: isPositive ? 'var(--text-secondary)' : 'var(--negative)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.val >= 1000 ? `${(item.val / 1000).toFixed(1)}k` : item.val.toFixed(1)}
                </span>

                {/* Bar */}
                <div
                  style={{
                    width: '100%',
                    maxWidth: '36px',
                    height: `${heightPercent}%`,
                    backgroundColor: isPositive ? 'var(--brand-primary)' : 'var(--negative)',
                    borderRadius: 'var(--radius-xs) var(--radius-xs) 0 0',
                    transition: 'height var(--transition-normal)',
                  }}
                />

                {/* Period Label */}
                <span
                  style={{
                    fontSize: 'var(--text-2xs)',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                    marginTop: 'var(--space-1)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.period}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
};
