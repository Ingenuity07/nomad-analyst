import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StockDetailResponse } from '@/lib/api/types';

export interface CompanyProfileHeaderProps {
  data: StockDetailResponse;
  symbol: string;
}

export const CompanyProfileHeader: React.FC<CompanyProfileHeaderProps> = ({
  data,
  symbol,
}) => {
  const navigate = useNavigate();
  const [showFullDescription, setShowFullDescription] = useState(false);

  const inst = data.instrument;
  const comp = inst?.company;
  const snapshot = data.latest_snapshot;

  return (
    <div
      data-testid="company-profile-header"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-5)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-4)',
      }}
    >
      {/* Top row: Name, Ticker, Exchange, Sector, Navigation Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', margin: 0 }}>
              {comp?.name || symbol}
            </h1>
            <Badge variant="brand" size="md">
              {symbol}
            </Badge>
            <Badge variant="neutral" size="sm">
              {inst?.exchange || 'NSE'}
            </Badge>
            {comp?.sector && (
              <Badge variant="neutral" size="sm">
                {comp.sector}
              </Badge>
            )}
            {comp?.isin && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                ISIN: {comp.isin}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
            {comp?.industry && (
              <span>
                <strong>Industry:</strong> {comp.industry} {comp.sub_industry ? `(${comp.sub_industry})` : ''}
              </span>
            )}
            {comp?.legal_name && comp.legal_name !== comp.name && (
              <span>
                <strong>Legal Name:</strong> {comp.legal_name}
              </span>
            )}
            {comp?.website && (
              <a
                href={comp.website}
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--brand-primary)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '2px' }}
              >
                Website ↗
              </a>
            )}
          </div>
        </div>

        {/* Action Handoffs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <Button
            data-testid="view-stock-terminal-button"
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/stocks/${symbol}`)}
          >
            📈 Stock Terminal
          </Button>
          <Button
            data-testid="research-company-button"
            type="button"
            variant="primary"
            size="sm"
            onClick={() => navigate(`/research?symbol=${symbol}`)}
          >
            🤖 AI Research Memos
          </Button>
        </div>
      </div>

      {/* Snapshot quick strip if present */}
      {snapshot && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-4)',
            padding: 'var(--space-2-5) var(--space-3)',
            backgroundColor: 'var(--bg-surface-sunken)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            flexWrap: 'wrap',
          }}
        >
          <span>
            <strong>Latest Close:</strong>{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 'var(--weight-semibold)' }}>
              ₹{Number(snapshot.close).toFixed(2)}
            </span>
          </span>
          {snapshot.change_percent !== undefined && (
            <span>
              <strong>Day Change:</strong>{' '}
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: Number(snapshot.change_percent) >= 0 ? 'var(--positive)' : 'var(--negative)',
                  fontWeight: 'var(--weight-semibold)',
                }}
              >
                {Number(snapshot.change_percent) >= 0 ? '+' : ''}
                {Number(snapshot.change_percent).toFixed(2)}%
              </span>
            </span>
          )}
          {data.active_recommendation && (
            <span>
              <strong>Signal:</strong>{' '}
              <Badge variant="brand" size="sm">
                {data.active_recommendation.signal} ({data.active_recommendation.horizon})
              </Badge>
            </span>
          )}
        </div>
      )}

      {/* Business Description */}
      {comp?.description && (
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <span style={{ fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)' }}>Business Overview: </span>
          {showFullDescription || comp.description.length <= 250
            ? comp.description
            : `${comp.description.slice(0, 250)}...`}
          {comp.description.length > 250 && (
            <button
              type="button"
              onClick={() => setShowFullDescription(!showFullDescription)}
              style={{
                marginLeft: 'var(--space-1-5)',
                background: 'none',
                border: 'none',
                color: 'var(--brand-primary)',
                fontSize: 'var(--text-xs)',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              {showFullDescription ? 'Show less' : 'Read more'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
