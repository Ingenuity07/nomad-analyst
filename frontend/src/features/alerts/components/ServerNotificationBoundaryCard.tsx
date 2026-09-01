import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export const ServerNotificationBoundaryCard: React.FC = () => {
  return (
    <Card header="In-Browser Monitoring & Server Boundary" data-testid="server-notification-boundary-card">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Badge variant="neutral" size="sm">CLIENT-SIDE COMMAND CENTER</Badge>
          <span>All triggers and threshold checks are evaluated live in your browser session while the workspace is open.</span>
        </div>
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>
          Server-side automated alert daemons, external webhook delivery (Slack / Telegram), SMS, and email dispatches remain planned backend infrastructure (FUTURE).
        </p>
      </div>
    </Card>
  );
};
