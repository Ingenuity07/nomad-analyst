import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';

export interface BacktestSummaryKPIsProps {
  result: Record<string, any> | null;
}

export const BacktestSummaryKPIs: React.FC<BacktestSummaryKPIsProps> = ({ result }) => {
  if (!result) {
    return null;
  }

  const winRate = result.win_rate !== null && result.win_rate !== undefined
    ? `${(result.win_rate * 100).toFixed(1)}%`
    : 'Insufficient Sample';

  const expectancy = result.expectancy !== null && result.expectancy !== undefined
    ? `${result.expectancy >= 0 ? '+' : ''}${result.expectancy.toFixed(2)} R`
    : 'Insufficient Sample';

  const profitFactor = result.profit_factor !== null && result.profit_factor !== undefined
    ? result.profit_factor.toFixed(2)
    : '—';

  const maxDrawdown = result.max_drawdown_r !== null && result.max_drawdown_r !== undefined
    ? `-${Math.abs(result.max_drawdown_r).toFixed(2)} R`
    : '0.00 R';

  return (
    <Card header="Simulated Strategy Performance Summary" data-testid="backtest-summary-kpis">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-4)' }}>
        <Metric
          label="Win Rate"
          value={winRate}
          subtext={`${result.wins || 0} Wins / ${result.losses || 0} Losses`}
        />
        <Metric
          label="Expectancy"
          value={expectancy}
          subtext="Net R-multiple expectancy per signal"
        />
        <Metric
          label="Profit Factor"
          value={profitFactor}
          subtext="Gross Wins / Gross Losses"
        />
        <Metric
          label="Max Drawdown"
          value={maxDrawdown}
          subtext="Peak-to-trough in R-multiple"
        />
        <Metric
          label="Trade Execution Count"
          value={`${result.triggered || 0} / ${result.total_signals || 0}`}
          subtext={`${result.untriggered || 0} signals untriggered`}
        />
      </div>
    </Card>
  );
};
