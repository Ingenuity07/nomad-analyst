import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableColumn } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Metric } from '@/components/ui/Metric';
import { PaperTradeLedgerItem } from '@/lib/api/types';
import { useFnoTrades } from '@/hooks/useFnoData';

export const FnoLedgerTab: React.FC = () => {
  const { data, isLoading, error, refetch } = useFnoTrades();
  const [activeSubTab, setActiveSubTab] = useState<'OPEN' | 'CLOSED' | 'REJECTIONS'>('OPEN');

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Skeleton height={100} />
        <Skeleton height={320} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to Load Paper Ledger"
        message={error instanceof Error ? error.message : 'Unable to query paper trades'}
        onRetry={() => refetch()}
      />
    );
  }

  const summary = data?.summary;
  const openPositions = data?.open_positions || [];
  const closedTrades = data?.closed_trades || [];
  const rejections = data?.rejections || [];

  const openColumns: TableColumn<PaperTradeLedgerItem>[] = [
    {
      key: 'trade_id',
      header: 'ID',
      width: '80px',
      render: (row) => <span style={{ fontFamily: 'var(--font-mono)' }}>#{row.trade_id}</span>,
    },
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
      key: 'option_type',
      header: 'Type',
      align: 'center',
      render: (row) => (
        <Badge variant={row.option_type === 'CE' ? 'positive' : 'negative'} size="sm">
          {row.option_type}
        </Badge>
      ),
    },
    {
      key: 'quantity',
      header: 'Qty',
      align: 'right',
      render: (row) => <span style={{ fontFamily: 'var(--font-mono)' }}>{row.quantity}</span>,
    },
    {
      key: 'entry_fill_price',
      header: 'Entry Price',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>₹{Number(row.entry_fill_price).toFixed(2)}</span>
      ),
    },
    {
      key: 'entry_slippage',
      header: 'Slippage',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          ₹{Number(row.entry_slippage).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'entry_timestamp',
      header: 'Entry Time (IST)',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
          {new Date(row.entry_timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      align: 'center',
      render: (row) => (
        <Badge variant="warning" size="sm">
          {row.status}
        </Badge>
      ),
    },
  ];

  const closedColumns: TableColumn<PaperTradeLedgerItem>[] = [
    {
      key: 'trade_id',
      header: 'ID',
      width: '80px',
      render: (row) => <span style={{ fontFamily: 'var(--font-mono)' }}>#{row.trade_id}</span>,
    },
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
      key: 'entry_fill_price',
      header: 'Entry',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>₹{Number(row.entry_fill_price).toFixed(2)}</span>
      ),
    },
    {
      key: 'exit_fill_price',
      header: 'Exit',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {row.exit_fill_price ? `₹${Number(row.exit_fill_price).toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'gross_pnl',
      header: 'Gross P&L',
      align: 'right',
      render: (row) => {
        const gross = row.gross_pnl !== null && row.gross_pnl !== undefined ? Number(row.gross_pnl) : null;
        if (gross === null) return '—';
        return (
          <span style={{ fontFamily: 'var(--font-mono)', color: gross >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            ₹{gross.toFixed(2)}
          </span>
        );
      },
    },
    {
      key: 'total_frictions',
      header: 'Statutory Frictions',
      align: 'right',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          ₹{Number(row.total_frictions || 0).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'net_pnl',
      header: 'Net P&L',
      align: 'right',
      render: (row) => {
        const net = row.net_pnl !== null && row.net_pnl !== undefined ? Number(row.net_pnl) : null;
        if (net === null) return '—';
        return (
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 'var(--weight-bold)', color: net >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            ₹{net.toFixed(2)}
          </span>
        );
      },
    },
    {
      key: 'exit_trigger_reason',
      header: 'Exit Trigger',
      render: (row) => (
        <Badge variant={row.exit_trigger_reason === 'TARGET' ? 'positive' : 'neutral'} size="sm">
          {row.exit_trigger_reason || 'MANUAL'}
        </Badge>
      ),
    },
    {
      key: 'exit_timestamp',
      header: 'Exit Time',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
          {row.exit_timestamp ? new Date(row.exit_timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
        </span>
      ),
    },
  ];

  const rejectionColumns: TableColumn<PaperTradeLedgerItem>[] = [
    {
      key: 'trade_id',
      header: 'ID',
      width: '80px',
      render: (row) => <span style={{ fontFamily: 'var(--font-mono)' }}>#{row.trade_id}</span>,
    },
    {
      key: 'entry_timestamp',
      header: 'Timestamp',
      render: (row) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
          {new Date(row.entry_timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
        </span>
      ),
    },
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
      key: 'rejection_reason',
      header: 'Rejection Reason',
      render: (row) => (
        <span style={{ color: 'var(--negative)', fontWeight: 'var(--weight-semibold)' }}>
          {row.rejection_reason || 'REJECTED_UNKNOWN'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      align: 'center',
      render: (row) => (
        <Badge variant="negative" size="sm">
          {row.status}
        </Badge>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* 20-Session Prospective Paper Trial Status Banner */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Badge variant="neutral" size="sm">TRIAL NOT STARTED</Badge>
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              20-Session Prospective Paper Trial: Inactive
            </span>
            <Badge variant="warning" size="sm">APPROVAL REQUIRED</Badge>
          </div>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            The 20-session prospective paper trial has not started and requires explicit approval before execution. No paper trades are scheduled or executing.
          </span>
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
          MODE: STRICT_SIMULATED (GATED)
        </span>
      </div>

      {/* Session Ledger Performance Summary */}
      <Card
        header="Paper Trading Session Performance"
        action={
          <Badge variant={summary?.ledger_status === 'POPULATED' ? 'positive' : 'neutral'} size="sm">
            LEDGER {summary?.ledger_status || 'EMPTY'}
          </Badge>
        }
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 'var(--space-4)',
            paddingTop: 'var(--space-2)',
          }}
        >
          <Metric
            label="OPEN POSITIONS"
            value={`${summary?.open_positions_count ?? 0}`}
            subtext={summary?.open_positions_count ? 'Simulated active' : 'Trial inactive'}
          />
          <Metric
            label="COMPLETED TRADES"
            value={`${summary?.total_trades ?? 0}`}
            subtext={summary?.total_trades ? 'Closed today' : 'Zero trial trades'}
          />
          <Metric
            label="WIN RATE"
            value={`${summary?.win_rate_pct ?? 0}%`}
            subtext={`${summary?.wins ?? 0}W / ${summary?.losses ?? 0}L`}
          />
          <Metric
            label="GROSS P&L"
            value={`₹${summary?.gross_pnl ?? '0.00'}`}
            subtext="Pre-friction"
          />
          <Metric
            label="STATUTORY FRICTIONS"
            value={`₹${summary?.total_frictions ?? '0.00'}`}
            subtext="STT, GST, Exchange"
          />
          <Metric
            label="NET P&L"
            value={`₹${summary?.net_pnl ?? '0.00'}`}
            subtext="Post-statutory"
          />
        </div>
      </Card>

      {summary?.ledger_status === 'EMPTY' && (
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>
            📋 <strong>Zero-Exposure Paper Ledger:</strong> The prospective 20-session trial has not started and zero trial trades have been executed. Explicit approval is required.
          </span>
          <Badge variant="neutral" size="sm">CLEAN TRIAL LEDGER</Badge>
        </div>
      )}

      {/* Sub-Tab Navigation Strip */}
      <Card
        header="Ledger Records"
        action={
          <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
            <button
              onClick={() => setActiveSubTab('OPEN')}
              style={{
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--text-xs)',
                fontWeight: activeSubTab === 'OPEN' ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                backgroundColor: activeSubTab === 'OPEN' ? 'var(--bg-surface-elevated)' : 'transparent',
                color: activeSubTab === 'OPEN' ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: activeSubTab === 'OPEN' ? '1px solid var(--border-strong)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Open Positions ({openPositions.length})
            </button>
            <button
              onClick={() => setActiveSubTab('CLOSED')}
              style={{
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--text-xs)',
                fontWeight: activeSubTab === 'CLOSED' ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                backgroundColor: activeSubTab === 'CLOSED' ? 'var(--bg-surface-elevated)' : 'transparent',
                color: activeSubTab === 'CLOSED' ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: activeSubTab === 'CLOSED' ? '1px solid var(--border-strong)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Closed Trades ({closedTrades.length})
            </button>
            <button
              onClick={() => setActiveSubTab('REJECTIONS')}
              style={{
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--text-xs)',
                fontWeight: activeSubTab === 'REJECTIONS' ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                backgroundColor: activeSubTab === 'REJECTIONS' ? 'var(--bg-surface-elevated)' : 'transparent',
                color: activeSubTab === 'REJECTIONS' ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: activeSubTab === 'REJECTIONS' ? '1px solid var(--border-strong)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Rejections ({rejections.length})
            </button>
          </div>
        }
      >
        {activeSubTab === 'OPEN' && (
          openPositions.length === 0 ? (
            <EmptyState
              title="No Open Positions"
              description="Trial not started. No simulated positions are active in STRAT-ORB-15M."
            />
          ) : (
            <Table
              columns={openColumns}
              data={openPositions}
              keyExtractor={(row) => String(row.trade_id)}
            />
          )
        )}

        {activeSubTab === 'CLOSED' && (
          closedTrades.length === 0 ? (
            <EmptyState
              title="No Completed Trades"
              description="Zero trial trades recorded. The prospective paper trial has not begun."
            />
          ) : (
            <Table
              columns={closedColumns}
              data={closedTrades}
              keyExtractor={(row) => String(row.trade_id)}
            />
          )
        )}

        {activeSubTab === 'REJECTIONS' && (
          rejections.length === 0 ? (
            <EmptyState
              title="No Trade Rejections"
              description="No runtime rejections recorded while the prospective paper trial remains inactive."
            />
          ) : (
            <Table
              columns={rejectionColumns}
              data={rejections}
              keyExtractor={(row) => String(row.trade_id)}
            />
          )
        )}
      </Card>
    </div>
  );
};
