import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ISTClock } from '@/components/common/ISTClock';
import { MarketSessionIndicator } from '@/components/common/MarketSessionIndicator';
import { useMarketOverview } from '@/hooks/useMarketOverview';
import { useStockSearch } from '@/hooks/useStock';

export const TopHeader: React.FC = () => {
  const navigate = useNavigate();
  const { data: marketData } = useMarketOverview('NIFTY50');
  const [searchQuery, setSearchQuery] = useState('');
  const { data: searchResults } = useStockSearch(searchQuery);

  return (
    <header
      style={{
        height: '52px',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 var(--space-6)',
        position: 'sticky',
        top: 0,
        zIndex: 40,
      }}
    >
      {/* Search Input */}
      <div style={{ position: 'relative', width: '320px' }}>
        <input
          type="text"
          placeholder="Search symbol (e.g. RELIANCE, TCS)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            width: '100%',
            backgroundColor: 'var(--bg-surface-sunken)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-1-5) var(--space-3)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
        {/* Quick Search Dropdown */}
        {searchResults && searchResults.results && searchResults.results.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-popover)',
              zIndex: 100,
              maxHeight: '240px',
              overflowY: 'auto',
            }}
          >
            {searchResults.results.map((res) => (
              <div
                key={res.symbol}
                onClick={() => {
                  setSearchQuery('');
                  navigate(`/stocks/${res.symbol}`);
                }}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {res.symbol}
                  </span>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginLeft: 'var(--space-2)' }}>
                    {res.name}
                  </span>
                </div>
                <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>{res.sector}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Market Indicators & IST Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-6)' }}>
        <MarketSessionIndicator sessionInfo={marketData?.market_session} />
        <div style={{ height: '16px', width: '1px', backgroundColor: 'var(--border-subtle)' }} />
        <ISTClock />
      </div>
    </header>
  );
};
