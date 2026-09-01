import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { DerivedFundamentalMetric } from '@/lib/api/types';

export interface FundamentalSnapshotCardsProps {
  metrics: DerivedFundamentalMetric[];
  companyName: string;
}

export const FundamentalSnapshotCards: React.FC<FundamentalSnapshotCardsProps> = ({
  metrics = [],
  companyName,
}) => {
  const getMetricVal = (name: string): { formatted: string; raw: number | null } => {
    const item = metrics.find((m) => m.name === name);
    if (!item || item.value === null) return { formatted: '—', raw: null };
    const num = Number(item.value);
    if (name.includes('growth') || name.includes('margin') || name.includes('return')) {
      return { formatted: `${(num * 100).toFixed(2)}%`, raw: num };
    }
    if (name.includes('ratio')) {
      return { formatted: `${num.toFixed(1)}x`, raw: num };
    }
    return { formatted: num.toFixed(2), raw: num };
  };

  const pe = getMetricVal('pe_ratio');
  const roe = getMetricVal('return_on_equity');
  const roce = getMetricVal('return_on_capital_employed');
  const debtEquity = getMetricVal('debt_equity');
  const ebitdaMargin = getMetricVal('ebitda_margin');
  const netMargin = getMetricVal('net_margin');
  const revGrowth = getMetricVal('revenue_growth_yoy');
  const patGrowth = getMetricVal('pat_growth_yoy');
  const cfoPat = getMetricVal('cfo_pat');

  return (
    <Card header={`Key Fundamental & Profitability Metrics — ${companyName}`}>
      <div
        data-testid="fundamental-snapshot-cards"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 'var(--space-4)',
        }}
      >
        <Metric
          label="P/E Ratio"
          value={pe.formatted}
          subtext="Price to Earnings"
        />
        <Metric
          label="Return on Equity"
          value={roe.formatted}
          subtext="ROE (PAT / Equity)"
        />
        <Metric
          label="ROCE"
          value={roce.formatted}
          subtext="Return on Cap Employed"
        />
        <Metric
          label="Debt / Equity"
          value={debtEquity.formatted}
          subtext="Financial Leverage"
        />
        <Metric
          label="EBITDA Margin"
          value={ebitdaMargin.formatted}
          subtext="Operating Efficiency"
        />
        <Metric
          label="Net Profit Margin"
          value={netMargin.formatted}
          subtext="Bottom-line Margin"
        />
        <Metric
          label="Revenue Growth YoY"
          value={revGrowth.formatted}
          subtext="Top-line YoY"
        />
        <Metric
          label="PAT Growth YoY"
          value={patGrowth.formatted}
          subtext="Earnings YoY"
        />
        <Metric
          label="CFO / PAT"
          value={cfoPat.formatted}
          subtext="Cash Conversion"
        />
      </div>
    </Card>
  );
};
