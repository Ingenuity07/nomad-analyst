import React from 'react';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export interface IntradayFilterToolbarProps {
  timeframe: string;
  onTimeframeChange: (val: string) => void;
  setupType: string;
  onSetupTypeChange: (val: string) => void;
  signal: string;
  onSignalChange: (val: string) => void;
  status: string;
  onStatusChange: (val: string) => void;
  searchQuery: string;
  onSearchChange: (val: string) => void;
  onReset: () => void;
}

export const IntradayFilterToolbar: React.FC<IntradayFilterToolbarProps> = ({
  timeframe,
  onTimeframeChange,
  setupType,
  onSetupTypeChange,
  signal,
  onSignalChange,
  status,
  onStatusChange,
  searchQuery,
  onSearchChange,
  onReset,
}) => {
  const hasActiveFilters =
    timeframe !== '' || setupType !== '' || signal !== '' || status !== '' || searchQuery !== '';

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
      <div style={{ minWidth: '130px' }}>
        <Select
          label="Timeframe"
          value={timeframe}
          onChange={(e) => onTimeframeChange(e.target.value)}
          options={[
            { value: '', label: 'All Intervals' },
            { value: '5m', label: '5 Minutes' },
            { value: '15m', label: '15 Minutes' },
            { value: '1h', label: '1 Hour' },
          ]}
        />
      </div>

      <div style={{ minWidth: '170px' }}>
        <Select
          label="Setup Detector"
          value={setupType}
          onChange={(e) => onSetupTypeChange(e.target.value)}
          options={[
            { value: '', label: 'All Setups' },
            { value: 'ORB_BREAKOUT', label: 'Opening Range Breakout' },
            { value: 'VWAP_RECLAIM', label: 'VWAP Reclaim / Rejection' },
            { value: 'TREND_CONTINUATION', label: 'Trend Continuation' },
            { value: 'MEAN_REVERSION', label: 'Mean Reversion' },
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

      <div style={{ minWidth: '140px' }}>
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
          ]}
        />
      </div>

      <div style={{ flex: 1, minWidth: '180px' }}>
        <Input
          label="Search Candidate"
          placeholder="Filter symbol (e.g. RELIANCE)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={onReset} style={{ height: '36px', alignSelf: 'flex-end' }}>
          ✕ Reset Filters
        </Button>
      )}
    </div>
  );
};
