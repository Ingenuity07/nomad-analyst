import React, { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { useStockSearch } from '@/hooks/useStock';

export interface WatchlistSearchAddProps {
  existingSymbols: string[];
  onAddSymbol: (symbol: string) => void;
}

export const WatchlistSearchAdd: React.FC<WatchlistSearchAddProps> = ({
  existingSymbols,
  onAddSymbol,
}) => {
  const [query, setQuery] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: searchResults, isLoading } = useStockSearch(query);

  const handleAdd = (sym: string) => {
    const cleanSym = sym.trim().toUpperCase();
    if (!cleanSym) return;

    if (existingSymbols.includes(cleanSym)) {
      setFeedback(`'${cleanSym}' is already in this watchlist.`);
      setTimeout(() => setFeedback(null), 3000);
      return;
    }

    onAddSymbol(cleanSym);
    setQuery('');
    setFeedback(`Added '${cleanSym}' to watchlist.`);
    setTimeout(() => setFeedback(null), 2500);
  };

  const handleSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!query.trim()) return;
    handleAdd(query.trim().toUpperCase());
  };

  const results = searchResults?.results || [];

  return (
    <div
      data-testid="watchlist-search-add"
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-2)',
        flexWrap: 'wrap',
      }}
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flex: 1, maxWidth: '400px' }}>
        <Input
          placeholder="Add stock (e.g. RELIANCE, TCS, INFY)..."
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={!query.trim()}
          onClick={() => handleSubmit()}
        >
          + Add
        </Button>
      </form>

      {/* Inline Feedback */}
      {feedback && (
        <span
          style={{
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            color: feedback.includes('already') ? 'var(--negative)' : 'var(--positive)',
          }}
        >
          {feedback}
        </span>
      )}

      {/* Autocomplete Dropdown */}
      {query.length >= 2 && results.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 40,
            width: '380px',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'var(--shadow-md)',
            marginTop: 'var(--space-1)',
            maxHeight: '220px',
            overflowY: 'auto',
          }}
        >
          {isLoading ? (
            <div style={{ padding: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Searching equities...
            </div>
          ) : (
            results.map((r) => {
              const isAlreadyInList = existingSymbols.includes(r.symbol);
              return (
                <div
                  key={r.symbol}
                  onClick={() => handleAdd(r.symbol)}
                  style={{
                    padding: 'var(--space-2) var(--space-3)',
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'pointer',
                    backgroundColor: 'transparent',
                    transition: 'background var(--transition-fast)',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)' }}>
                      {r.symbol}
                    </span>
                    <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>
                      {r.name} • {r.sector}
                    </span>
                  </div>
                  <span style={{ fontSize: 'var(--text-2xs)', color: isAlreadyInList ? 'var(--text-muted)' : 'var(--positive)' }}>
                    {isAlreadyInList ? 'In List' : '+ Add'}
                  </span>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
