import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export const ThemeRoadmapCard: React.FC = () => {
  return (
    <Card header="Thematic Intelligence & RRG Rotation Trajectories — Planned Capabilities" data-testid="theme-roadmap-card">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Badge variant="neutral" size="sm">FUTURE BACKEND CAPABILITY</Badge>
          <span>Quantitative theme classification (e.g. AI, Defence, EV, Renewables) and 4-quadrant RRG rotation curves.</span>
        </div>
        <p style={{ margin: 0 }}>
          Nomad Analyst strictly avoids synthetic frontend modeling. High-conviction thematic baskets and multi-timeframe JdK Relative Rotation Graph (RRG) coordinates will be activated upon deployment of the backend thematic factor engine.
        </p>
      </div>
    </Card>
  );
};
