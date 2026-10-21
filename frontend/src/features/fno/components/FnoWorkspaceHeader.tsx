import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { Metric } from '@/components/ui/Metric';
import { Card } from '@/components/ui/Card';
import { FnoOverviewResponse } from '@/lib/api/types';

interface FnoWorkspaceHeaderProps {
  overview?: FnoOverviewResponse;
  isLoading?: boolean;
}

export const FnoWorkspaceHeader: React.FC<FnoWorkspaceHeaderProps> = ({ overview }) => {
  const spot = overview?.underlying.spot_price;
  const atm = overview?.underlying.atm_strike;
  const feedStatus = overview?.feed.status || 'DISCONNECTED';
  const quoteAge = overview?.feed.quote_age_seconds;
  const activeContracts = overview?.feed.active_contracts_tracked ?? 0;

  const getFeedBadgeVariant = (status: string): 'positive' | 'negative' | 'warning' | 'neutral' | 'brand' => {
    switch (status) {
      case 'ACTIVE':
        return 'positive';
      case 'STANDBY_MARKET_CLOSED':
        return 'brand';
      case 'DEGRADED':
        return 'warning';
      default:
        return 'negative';
    }
  };

  const getFeedBadgeLabel = (status: string): string => {
    switch (status) {
      case 'ACTIVE':
        return 'FEED LIVE';
      case 'STANDBY_MARKET_CLOSED':
        return 'MARKET CLOSED (STANDBY)';
      case 'DEGRADED':
        return 'FEED LAGGING';
      default:
        return 'FEED DISCONNECTED';
    }
  };

  return (
    <Card
      style={{
        marginBottom: 'var(--space-4)',
        padding: 'var(--space-4)',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-4)',
        }}
      >
        {/* Left: Workspace Title & Badge */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <h1
              style={{
                fontSize: 'var(--text-xl)',
                fontWeight: 'var(--weight-bold)',
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                margin: 0,
              }}
            >
              F&O Laboratory
            </h1>
            <Badge variant="brand" size="sm">
              PHASE FNO-1 BETA
            </Badge>
            <Badge variant={getFeedBadgeVariant(feedStatus)} size="sm">
              {getFeedBadgeLabel(feedStatus)}
            </Badge>
          </div>
          <div
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--text-muted)',
              marginTop: 'var(--space-1)',
            }}
          >
            NIFTY 50 Options Analysis • STRAT-ORB-15M Strategy Lab • Real-Time Paper Execution
          </div>
        </div>

        {/* Right: Key Metrics Strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-6)' }}>
          <Metric
            label="NIFTY 50 SPOT"
            value={spot !== null && spot !== undefined ? spot.toFixed(2) : '—'}
            subtext={overview?.underlying.market_direction || 'NEUTRAL'}
          />

          <Metric
            label="ATM STRIKE"
            value={atm !== null && atm !== undefined ? `${atm}` : '—'}
            subtext="Dynamic ±50 strike"
          />

          <Metric
            label="QUOTE AGE"
            value={quoteAge !== null && quoteAge !== undefined ? `${quoteAge.toFixed(1)}s` : '—'}
            subtext={quoteAge !== null && quoteAge !== undefined && quoteAge > 3.0 ? 'Delayed' : 'Real-time'}
          />

          <Metric
            label="TRACKED STRIKES"
            value={`${activeContracts}`}
            subtext="Active contracts"
          />
        </div>
      </div>
    </Card>
  );
};
