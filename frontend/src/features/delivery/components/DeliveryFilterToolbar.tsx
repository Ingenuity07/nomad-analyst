import React from 'react';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export interface DeliveryFilterToolbarProps {
  universe: string;
  onUniverseChange: (val: string) => void;
  horizon: string;
  onHorizonChange: (val: string) => void;
  sector: string;
  onSectorChange: (val: string) => void;
  minScore: number;
  onMinScoreChange: (val: number) => void;
  searchQuery: string;
  onSearchChange: (val: string) => void;
  availableSectors?: string[];
  onReset: () => void;
}

export const DeliveryFilterToolbar: React.FC<DeliveryFilterToolbarProps> = ({
  universe,
  onUniverseChange,
  horizon,
  onHorizonChange,
  sector,
  onSectorChange,
  minScore,
  onMinScoreChange,
  searchQuery,
  onSearchChange,
  availableSectors = [],
  onReset,
}) => {
  const sectorOptions = [
    { value: '', label: 'All Sectors' },
    ...availableSectors.map((s) => ({ value: s, label: s })),
  ];

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
      <div style={{ minWidth: '160px' }}>
        <Select
          label="Universe"
          value={universe}
          onChange={(e) => onUniverseChange(e.target.value)}
          options={[
            { value: 'NIFTY50', label: 'NIFTY 50' },
            { value: 'NIFTYNEXT50', label: 'NIFTY Next 50' },
            { value: 'NIFTYMIDCAP50', label: 'NIFTY MidCap 50' },
          ]}
        />
      </div>

      <div style={{ minWidth: '170px' }}>
        <Select
          label="Holding Horizon"
          value={horizon}
          onChange={(e) => onHorizonChange(e.target.value)}
          options={[
            { value: 'DELIVERY_SWING', label: 'Delivery Swing (2-15d)' },
            { value: 'DELIVERY_POSITIONAL', label: 'Positional (2-8w)' },
          ]}
        />
      </div>

      <div style={{ minWidth: '160px' }}>
        <Select
          label="Sector Filter"
          value={sector}
          onChange={(e) => onSectorChange(e.target.value)}
          options={sectorOptions}
        />
      </div>

      <div style={{ minWidth: '140px' }}>
        <Select
          label="Min Opp Score"
          value={String(minScore)}
          onChange={(e) => onMinScoreChange(Number(e.target.value))}
          options={[
            { value: '0', label: 'All Scores (≥ 0)' },
            { value: '50', label: 'Moderate (≥ 50)' },
            { value: '70', label: 'High Quality (≥ 70)' },
            { value: '80', label: 'Top Tier (≥ 80)' },
          ]}
        />
      </div>

      <div style={{ flex: 1, minWidth: '200px' }}>
        <Input
          label="Filter Candidates"
          placeholder="Filter symbol (e.g. RELIANCE)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      {(sector || minScore > 0 || searchQuery || universe !== 'NIFTY50' || horizon !== 'DELIVERY_SWING') && (
        <Button variant="ghost" size="sm" onClick={onReset} style={{ height: '36px', alignSelf: 'flex-end' }}>
          ✕ Reset Filters
        </Button>
      )}
    </div>
  );
};
