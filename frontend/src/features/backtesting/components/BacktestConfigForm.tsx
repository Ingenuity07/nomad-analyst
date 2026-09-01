import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { BacktestRunPayload } from '@/lib/api/types';

export interface BacktestConfigFormProps {
  onSubmit: (payload: BacktestRunPayload) => void;
  isLoading: boolean;
}

export const BacktestConfigForm: React.FC<BacktestConfigFormProps> = ({
  onSubmit,
  isLoading,
}) => {
  const [universeName, setUniverseName] = useState<string>('NIFTY50');
  const [horizon, setHorizon] = useState<string>('DELIVERY_SWING');
  const [timeframe, setTimeframe] = useState<string>('1d');
  const [startDate, setStartDate] = useState<string>('2026-03-01');
  const [endDate, setEndDate] = useState<string>('2026-09-01');
  const [costMode, setCostMode] = useState<string>('REALISTIC');
  const [brokeragePct, setBrokeragePct] = useState<number>(0.03);
  const [sttPct, setSttPct] = useState<number>(0.025);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [ambiguityPolicy, setAmbiguityPolicy] = useState<string>('CONSERVATIVE');

  const handleSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    const payload: BacktestRunPayload = {
      universe_name: universeName,
      horizon,
      timeframe,
      start_date: startDate,
      end_date: endDate,
      cost_mode: costMode,
      ambiguity_policy: ambiguityPolicy,
    };

    if (costMode === 'CUSTOM') {
      payload.brokerage_pct = brokeragePct;
      payload.stt_pct = sttPct;
      payload.slippage_bps = slippageBps;
    }

    onSubmit(payload);
  };

  return (
    <Card header="Historical Simulation Configuration">
      <form
        data-testid="backtest-config-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
      >
        {/* Strategy Context */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
          <Select
            label="Universe"
            value={universeName}
            onChange={(e) => setUniverseName(e.target.value)}
            options={[
              { value: 'NIFTY50', label: 'NIFTY 50' },
              { value: 'NIFTY_NEXT50', label: 'NIFTY Next 50' },
              { value: 'NIFTY_MIDCAP50', label: 'NIFTY Midcap 50' },
              { value: 'CUSTOM_UNIV', label: 'Custom Research Universe' },
            ]}
          />

          <Select
            label="Horizon"
            value={horizon}
            onChange={(e) => {
              const val = e.target.value;
              setHorizon(val);
              if (val === 'INTRADAY' && timeframe === '1d') setTimeframe('5m');
            }}
            options={[
              { value: 'DELIVERY_SWING', label: 'Delivery / Swing (2-15d)' },
              { value: 'INTRADAY', label: 'Intraday (Single-day session)' },
              { value: 'LONG_TERM', label: 'Long Term / Positional' },
            ]}
          />

          <Select
            label="Bar Timeframe"
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            options={
              horizon === 'INTRADAY'
                ? [
                    { value: '5m', label: '5 Minutes' },
                    { value: '15m', label: '15 Minutes' },
                    { value: '1h', label: '1 Hour' },
                  ]
                : [
                    { value: '1d', label: '1 Day (Daily)' },
                    { value: '1h', label: '1 Hour' },
                  ]
            }
          />
        </div>

        {/* Historical Period */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
          <Input
            label="Start Date (Inclusive)"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <Input
            label="End Date (Inclusive)"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>

        {/* Execution & Cost Assumptions */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
          <Select
            label="Transaction Cost Mode"
            value={costMode}
            onChange={(e) => setCostMode(e.target.value)}
            options={[
              { value: 'REALISTIC', label: 'Realistic NSE Equities (Brokerage + STT + 5bps slippage)' },
              { value: 'NO_COST', label: 'Zero Transaction Cost (Pure Strategy Alpha)' },
              { value: 'CUSTOM', label: 'Custom Cost & Slippage Parameters' },
            ]}
          />

          <Select
            label="Ambiguity Resolution Policy"
            value={ambiguityPolicy}
            onChange={(e) => setAmbiguityPolicy(e.target.value)}
            options={[
              { value: 'CONSERVATIVE', label: 'Conservative (Stop loss wins on same-bar collision)' },
              { value: 'OPTIMISTIC', label: 'Optimistic (Target wins on same-bar collision)' },
              { value: 'EXCLUDE', label: 'Exclude (Omit same-bar collisions from stats)' },
            ]}
          />
        </div>

        {/* Custom Cost Inputs (Progressive disclosure) */}
        {costMode === 'CUSTOM' && (
          <div
            style={{
              padding: 'var(--space-3)',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 'var(--space-3)',
            }}
          >
            <Input
              label="Brokerage (%)"
              type="number"
              step="0.01"
              value={brokeragePct}
              onChange={(e) => setBrokeragePct(parseFloat(e.target.value) || 0)}
            />
            <Input
              label="STT (%)"
              type="number"
              step="0.005"
              value={sttPct}
              onChange={(e) => setSttPct(parseFloat(e.target.value) || 0)}
            />
            <Input
              label="Slippage (bps)"
              type="number"
              step="1"
              value={slippageBps}
              onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
            />
          </div>
        )}

        {/* Submit */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)' }}>
          <Button
            data-testid="run-backtest-button"
            type="button"
            variant="primary"
            size="md"
            disabled={isLoading || !startDate || !endDate}
            onClick={() => handleSubmit()}
          >
            {isLoading ? '▶ Running Walk-Forward Simulation...' : '▶ Run Backtest Simulation'}
          </Button>
        </div>
      </form>
    </Card>
  );
};
