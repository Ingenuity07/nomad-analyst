import React from 'react';
import { Card } from '@/components/ui/Card';
import { Metric } from '@/components/ui/Metric';
import { MarketSessionInfo } from '@/lib/api/types';

export interface CommandCenterStatusStripProps {
  session?: MarketSessionInfo;
  activeRulesCount: number;
  totalEventsCount: number;
  highSeverityCount: number;
  isPollingActive: boolean;
}

export const CommandCenterStatusStrip: React.FC<CommandCenterStatusStripProps> = ({
  session,
  activeRulesCount,
  totalEventsCount,
  highSeverityCount,
  isPollingActive,
}) => {
  const isTradingHour = session?.is_trading_hour ?? false;

  return (
    <Card data-testid="command-center-status-strip">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 'var(--space-3)',
          alignItems: 'center',
        }}
      >
        <Metric
          label="Market Session"
          value={isTradingHour ? 'REGULAR' : 'CLOSED'}
          subtext={isTradingHour ? 'MARKET OPEN' : 'AFTER HOURS'}
        />
        <Metric
          label="Monitoring Engine"
          value={isPollingActive ? 'Active (30s)' : 'Idle'}
          subtext={isPollingActive ? '● Live polling heartbeat' : '○ Polling slowed outside hours'}
        />
        <Metric
          label="Active Rules"
          value={String(activeRulesCount)}
          subtext="Condition triggers configured"
        />
        <Metric
          label="Events Today"
          value={String(totalEventsCount)}
          subtext={`${highSeverityCount} high-priority actionable`}
        />
      </div>
    </Card>
  );
};
