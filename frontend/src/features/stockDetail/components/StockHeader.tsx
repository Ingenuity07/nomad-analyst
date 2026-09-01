import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { DataStatus } from '@/components/ui/DataStatus';
import { StockDetailResponse } from '@/lib/api/types';

export interface StockHeaderProps {
  data?: StockDetailResponse;
  symbol: string;
}

export const StockHeader: React.FC<StockHeaderProps> = ({ data, symbol }) => {
  const navigate = useNavigate();
  const inst = data?.instrument;
  const snap = data?.latest_snapshot;
  const comp = inst?.company;

  const price = snap?.close ? Number(snap.close) : null;
  const change = snap?.change ? Number(snap.change) : 0;
  const changePct = snap?.change_percent ? Number(snap.change_percent) : 0;
  const isPositive = change >= 0;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-4) var(--space-6)',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 'var(--space-4)',
      }}
    >
      {/* Left: Symbol & Company */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            padding: 'var(--space-1) var(--space-2)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface-elevated)',
            cursor: 'pointer',
          }}
          title="Back"
        >
          ← Back
        </button>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <h1
              style={{
                fontSize: 'var(--text-xl)',
                fontWeight: 'var(--weight-bold)',
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-mono)',
                margin: 0,
              }}
            >
              {symbol.toUpperCase()}
            </h1>
            <Badge variant="neutral" size="sm">{inst?.exchange || 'NSE'}</Badge>
            {comp?.sector && <Badge variant="brand" size="sm">{comp.sector}</Badge>}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {comp?.name || 'Equity Instrument'} {comp?.industry ? `• ${comp.industry}` : ''}
          </div>
        </div>
      </div>

      {/* Right: Price & Freshness */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-6)' }}>
        {price !== null ? (
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 'var(--weight-bold)',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-primary)',
              }}
            >
              ₹{price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 'var(--weight-semibold)',
                fontFamily: 'var(--font-mono)',
                color: isPositive ? 'var(--positive)' : 'var(--negative)',
                marginTop: '1px',
              }}
            >
              {isPositive ? '+' : ''}₹{change.toFixed(2)} ({isPositive ? '+' : ''}{changePct.toFixed(2)}%)
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            Quote data pending
          </div>
        )}

        <DataStatus
          status={data?.data_freshness?.status === 'LIVE' ? 'LIVE' : 'UNAVAILABLE'}
          source="NSE"
          lastUpdated={data?.data_freshness?.timestamp ? new Date(data.data_freshness.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST' : undefined}
        />
      </div>
    </div>
  );
};
