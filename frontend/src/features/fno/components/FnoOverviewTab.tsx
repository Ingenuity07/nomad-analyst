import React, { useState, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableColumn } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { OptionQuoteSnapshotItem } from '@/lib/api/types';
import { useFnoOverview } from '@/hooks/useFnoData';

export const FnoOverviewTab: React.FC = () => {
  const { data, isLoading, error, refetch } = useFnoOverview();
  const [filterType, setFilterType] = useState<'ALL' | 'CE' | 'PE'>('ALL');

  const quotes = useMemo(() => {
    if (!data?.quotes) return [];
    if (filterType === 'ALL') return data.quotes;
    return data.quotes.filter((q) => {
      const sym = q.tradingsymbol.toUpperCase();
      return filterType === 'CE' ? sym.endsWith('CE') : sym.endsWith('PE');
    });
  }, [data?.quotes, filterType]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Skeleton height={120} />
        <Skeleton height={320} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to Load F&O Overview"
        message={error instanceof Error ? error.message : 'Unable to query F&O feed endpoints'}
        onRetry={() => refetch()}
      />
    );
  }

  const columns: TableColumn<OptionQuoteSnapshotItem>[] = [
    {
      key: 'tradingsymbol',
      header: 'Contract',
      render: (row) => (
        <span style={{ fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)' }}>
          {row.tradingsymbol}
        </span>
      ),
    },
    {
      key: 'best_bid',
      header: 'Bid (L1)',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--positive)' }}>
          {row.best_bid !== null && row.best_bid !== undefined ? Number(row.best_bid).toFixed(2) : '—'}
          {row.bid_quantity_l1 ? (
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginLeft: '4px' }}>
              ({row.bid_quantity_l1})
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: 'best_ask',
      header: 'Ask (L1)',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--negative)' }}>
          {row.best_ask !== null && row.best_ask !== undefined ? Number(row.best_ask).toFixed(2) : '—'}
          {row.ask_quantity_l1 ? (
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginLeft: '4px' }}>
              ({row.ask_quantity_l1})
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: 'spread',
      header: 'Spread (Abs / %)',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
          {row.spread_abs !== null && row.spread_abs !== undefined ? (
            <>
              ₹{row.spread_abs} <span style={{ color: 'var(--text-muted)' }}>({row.spread_pct}%)</span>
            </>
          ) : (
            '—'
          )}
        </span>
      ),
    },
    {
      key: 'quote_status',
      header: 'Quote Status',
      render: (row) => {
        let variant: 'positive' | 'negative' | 'warning' | 'neutral' = 'neutral';
        if (row.quote_status === 'VALID' && !row.is_stale) variant = 'positive';
        else if (row.is_stale) variant = 'warning';
        else if (row.is_locked || row.is_crossed) variant = 'negative';

        return (
          <Badge variant={variant} size="sm">
            {row.is_stale ? 'STALE' : row.is_locked ? 'LOCKED' : row.is_crossed ? 'CROSSED' : row.quote_status}
          </Badge>
        );
      },
    },
    {
      key: 'is_execution_eligible',
      header: 'Taker Eligible',
      align: 'center',
      render: (row) => (
        <Badge variant={row.is_execution_eligible ? 'positive' : 'neutral'} size="sm">
          {row.is_execution_eligible ? 'ELIGIBLE' : 'INELIGIBLE'}
        </Badge>
      ),
    },
    {
      key: 'exchange_timestamp_utc',
      header: 'Time Status',
      render: (row) => (
        <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          <span>{row.exchange_time_status}</span>
          {row.exchange_timestamp_utc && (
            <div style={{ color: 'var(--text-secondary)' }}>
              {new Date(row.exchange_timestamp_utc).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Feed Context Overview Card */}
      <Card header="NIFTY Context & Feed Freshness">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-4)',
            paddingTop: 'var(--space-2)',
          }}
        >
          <div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Market Regime
            </div>
            <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {data?.underlying.market_regime || 'UNKNOWN'}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Direction: {data?.underlying.market_direction || 'NEUTRAL'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              ATM Strike (Dynamic)
            </div>
            <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {data?.underlying.atm_strike ? `${data.underlying.atm_strike} Strike` : 'Awaiting Spot'}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Spot: {data?.underlying.spot_price ? `₹${data.underlying.spot_price.toFixed(2)}` : '—'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Feed Freshness
            </div>
            <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {data?.feed.status === 'ACTIVE'
                ? 'Optimal (<1.0s)'
                : data?.feed.status === 'DEGRADED'
                ? 'Lagging (>3.0s)'
                : data?.feed.status === 'STANDBY_MARKET_CLOSED'
                ? 'Standby (Market Closed)'
                : 'Disconnected'}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Arrival: {data?.feed.latest_received_wall_clock ? new Date(data.feed.latest_received_wall_clock).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST' : 'No Ticks'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Tracked Option Strikes
            </div>
            <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {data?.feed.active_contracts_tracked ?? 0} Contracts
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Rolling 5-Day L1 & L2 Depth
            </div>
          </div>
        </div>
      </Card>

      {/* Filter and Strike Ladder Card */}
      <Card
        header="Live Option Quote Ladder"
        action={
          <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
            {(['ALL', 'CE', 'PE'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                style={{
                  padding: 'var(--space-1) var(--space-2-5)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: filterType === type ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                  backgroundColor: filterType === type ? 'var(--bg-surface-elevated)' : 'transparent',
                  color: filterType === type ? 'var(--text-primary)' : 'var(--text-secondary)',
                  border: filterType === type ? '1px solid var(--border-strong)' : '1px solid transparent',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                {type}
              </button>
            ))}
          </div>
        }
      >
        {quotes.length === 0 ? (
          <EmptyState
            title="No Option Quotes Available"
            description="No quote snapshots have been recorded for the current active universe yet."
          />
        ) : (
          <Table
            columns={columns}
            data={quotes}
            keyExtractor={(row) => String(row.id || row.instrument_token)}
          />
        )}
      </Card>
    </div>
  );
};
