import React from 'react';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export interface RecommendationFilterToolbarProps {
  horizon: string;
  onHorizonChange: (val: string) => void;
  signal: string;
  onSignalChange: (val: string) => void;
  setupType: string;
  onSetupTypeChange: (val: string) => void;
  status: string;
  onStatusChange: (val: string) => void;
  confidence: string;
  onConfidenceChange: (val: string) => void;
  searchQuery: string;
  onSearchChange: (val: string) => void;
  onReset: () => void;
}

export const RecommendationFilterToolbar: React.FC<RecommendationFilterToolbarProps> = ({
  horizon,
  onHorizonChange,
  signal,
  onSignalChange,
  setupType,
  onSetupTypeChange,
  status,
  onStatusChange,
  confidence,
  onConfidenceChange,
  searchQuery,
  onSearchChange,
  onReset,
}) => {
  const hasActiveFilters =
    horizon !== '' || signal !== '' || setupType !== '' || status !== '' || confidence !== '' || searchQuery !== '';

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-3) var(--space-4)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 'var(--space-3)',
        alignItems: 'flex-end',
      }}
    >
      <div style={{ minWidth: '150px' }}>
        <Select
          label="Time Horizon"
          value={horizon}
          onChange={(e) => onHorizonChange(e.target.value)}
          options={[
            { value: '', label: 'All Horizons' },
            { value: 'DELIVERY_SWING', label: 'Delivery / Swing' },
            { value: 'INTRADAY', label: 'Intraday' },
            { value: 'LONG_TERM', label: 'Long Term' },
          ]}
        />
      </div>

      <div style={{ minWidth: '120px' }}>
        <Select
          label="Direction"
          value={signal}
          onChange={(e) => onSignalChange(e.target.value)}
          options={[
            { value: '', label: 'All Signals' },
            { value: 'BUY', label: '▲ BUY' },
            { value: 'SELL', label: '▼ SELL' },
          ]}
        />
      </div>

      <div style={{ minWidth: '170px' }}>
        <Select
          label="Setup Pattern"
          value={setupType}
          onChange={(e) => onSetupTypeChange(e.target.value)}
          options={[
            { value: '', label: 'All Setups' },
            { value: 'BREAKOUT', label: 'Breakout' },
            { value: 'PULLBACK', label: 'Pullback' },
            { value: 'MOMENTUM', label: 'Momentum' },
            { value: 'ORB_BREAKOUT', label: 'Opening Range Breakout' },
            { value: 'VWAP_RECLAIM', label: 'VWAP Reclaim' },
            { value: 'TREND_CONTINUATION', label: 'Trend Continuation' },
            { value: 'MEAN_REVERSION', label: 'Mean Reversion' },
          ]}
        />
      </div>

      <div style={{ minWidth: '130px' }}>
        <Select
          label="Lifecycle Status"
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          options={[
            { value: '', label: 'All Statuses' },
            { value: 'ACTIVE', label: 'ACTIVE' },
            { value: 'TRIGGERED', label: 'TRIGGERED' },
            { value: 'TARGET_HIT', label: 'TARGET HIT' },
            { value: 'STOPPED', label: 'STOPPED' },
            { value: 'EXPIRED', label: 'EXPIRED' },
            { value: 'CANCELLED', label: 'CANCELLED' },
          ]}
        />
      </div>

      <div style={{ minWidth: '120px' }}>
        <Select
          label="Confidence"
          value={confidence}
          onChange={(e) => onConfidenceChange(e.target.value)}
          options={[
            { value: '', label: 'All Levels' },
            { value: 'HIGH', label: 'High' },
            { value: 'MEDIUM', label: 'Medium' },
            { value: 'LOW', label: 'Low' },
          ]}
        />
      </div>

      <div style={{ flex: 1, minWidth: '170px' }}>
        <Input
          label="Search Symbol"
          placeholder="Filter ticker (e.g. RELIANCE)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={onReset} style={{ height: '36px', alignSelf: 'flex-end' }}>
          ✕ Reset
        </Button>
      )}
    </div>
  );
};
