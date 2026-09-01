import React, { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export interface CompanySearchSelectorProps {
  currentSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}

const POPULAR_COMPANIES = [
  { symbol: 'RELIANCE', name: 'Reliance Industries' },
  { symbol: 'TCS', name: 'Tata Consultancy Services' },
  { symbol: 'INFY', name: 'Infosys' },
  { symbol: 'HDFCBANK', name: 'HDFC Bank' },
  { symbol: 'ICICIBANK', name: 'ICICI Bank' },
  { symbol: 'SBIN', name: 'State Bank of India' },
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel' },
  { symbol: 'ITC', name: 'ITC Ltd' },
  { symbol: 'LT', name: 'Larsen & Toubro' },
  { symbol: 'TATAMOTORS', name: 'Tata Motors' },
];

export const CompanySearchSelector: React.FC<CompanySearchSelectorProps> = ({
  currentSymbol,
  onSelectSymbol,
}) => {
  const [inputVal, setInputVal] = useState<string>('');

  const handleSearchSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!inputVal.trim()) return;
    onSelectSymbol(inputVal.trim().toUpperCase());
    setInputVal('');
  };

  return (
    <div
      data-testid="company-search-selector"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-3) var(--space-4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 'var(--space-3)',
      }}
    >
      {/* Quick Presets */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1-5)', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 'var(--weight-medium)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Select Company:
        </span>
        {POPULAR_COMPANIES.map((c) => {
          const isSelected = currentSymbol.toUpperCase() === c.symbol;
          return (
            <button
              key={c.symbol}
              type="button"
              onClick={() => onSelectSymbol(c.symbol)}
              style={{
                padding: 'var(--space-1) var(--space-2-5)',
                fontSize: 'var(--text-xs)',
                fontFamily: 'var(--font-mono)',
                color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                backgroundColor: isSelected ? 'var(--brand-subtle)' : 'var(--bg-surface-subtle)',
                border: `1px solid ${isSelected ? 'var(--brand-border)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-xs)',
                cursor: 'pointer',
                fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                transition: 'all var(--transition-fast)',
              }}
            >
              {c.symbol}
            </button>
          );
        })}
      </div>

      {/* Manual Input */}
      <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <div style={{ width: '180px' }}>
          <Input
            placeholder="Search symbol (e.g. WIPRO)..."
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value.toUpperCase())}
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={!inputVal.trim()}
          onClick={() => handleSearchSubmit()}
        >
          Load
        </Button>
      </form>
    </div>
  );
};
