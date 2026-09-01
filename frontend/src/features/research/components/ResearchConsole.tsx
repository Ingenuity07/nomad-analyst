import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ResearchRequestPayload } from '@/lib/api/types';

export interface ResearchConsoleProps {
  initialSymbol?: string;
  onSubmit: (payload: ResearchRequestPayload) => void;
  isLoading: boolean;
  elapsedSeconds?: number;
}

const PROMPT_SUGGESTIONS = [
  'Comprehensive Investment Thesis & Risk Analysis',
  'Assess Technical Structure, Trend & Momentum',
  'Evaluate Debt Leverage & Return on Capital (ROE/ROCE)',
  'Analyze Recent News, Catalysts & Events',
];

const POPULAR_SYMBOLS = [
  'RELIANCE',
  'TCS',
  'INFY',
  'HDFCBANK',
  'ICICIBANK',
  'SBIN',
  'BHARTIARTL',
  'ITC',
  'LT',
  'TATAMOTORS',
];

export const ResearchConsole: React.FC<ResearchConsoleProps> = ({
  initialSymbol = 'RELIANCE',
  onSubmit,
  isLoading,
  elapsedSeconds = 0,
}) => {
  const [symbol, setSymbol] = useState<string>(initialSymbol);
  const [question, setQuestion] = useState<string>('Assess the current fundamental investment case, key operational growth drivers, and primary risk factors.');
  const [depth, setDepth] = useState<'quick' | 'standard' | 'deep'>('standard');
  const [isHistorical, setIsHistorical] = useState<boolean>(false);
  const [asOfDate, setAsOfDate] = useState<string>('2026-08-20T10:00:00Z');

  const handleSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    if (!symbol.trim() || !question.trim()) return;

    const payload: ResearchRequestPayload = {
      symbol: symbol.trim().toUpperCase(),
      question: question.trim(),
      depth,
      as_of: isHistorical && asOfDate.trim() ? asOfDate.trim() : undefined,
    };

    onSubmit(payload);
  };

  return (
    <Card header="AI Equity Intelligence & Synthesis Console">
      <form
        data-testid="research-console-form"
        onSubmit={handleSubmit}
        style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
      >
        {/* Row 1: Stock Symbol and Popular Ticker Pills */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ minWidth: '220px', flex: '1 1 220px' }}>
              <Input
                label="Target Stock Symbol"
                placeholder="e.g. RELIANCE, TCS, INFY"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                disabled={isLoading}
                required
              />
            </div>

            {/* Depth Selector */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <label style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Research Depth
              </label>
              <div style={{ display: 'flex', gap: 'var(--space-1)', backgroundColor: 'var(--bg-surface-sunken)', padding: '2px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                {(['quick', 'standard', 'deep'] as const).map((d) => {
                  const isSelected = depth === d;
                  const labelMap = { quick: 'Quick (~6 steps)', standard: 'Standard (~9 steps)', deep: 'Deep (~12 steps)' };
                  return (
                    <button
                      key={d}
                      type="button"
                      disabled={isLoading}
                      onClick={() => setDepth(d)}
                      style={{
                        padding: 'var(--space-1-5) var(--space-3)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                        color: isSelected ? 'var(--text-primary)' : 'var(--text-muted)',
                        backgroundColor: isSelected ? 'var(--bg-surface)' : 'transparent',
                        borderRadius: 'var(--radius-sm)',
                        border: 'none',
                        cursor: isLoading ? 'not-allowed' : 'pointer',
                        transition: 'all var(--transition-fast)',
                        boxShadow: isSelected ? 'var(--shadow-sm)' : 'none',
                      }}
                    >
                      {labelMap[d]}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Popular ticker quick select */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1-5)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Presets:
            </span>
            {POPULAR_SYMBOLS.map((sym) => (
              <button
                key={sym}
                type="button"
                disabled={isLoading}
                onClick={() => setSymbol(sym)}
                style={{
                  padding: '1px 6px',
                  fontSize: 'var(--text-2xs)',
                  fontFamily: 'var(--font-mono)',
                  color: symbol === sym ? 'var(--brand-primary)' : 'var(--text-secondary)',
                  backgroundColor: symbol === sym ? 'var(--brand-subtle)' : 'var(--bg-surface-subtle)',
                  border: `1px solid ${symbol === sym ? 'var(--brand-border)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-xs)',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>

        {/* Row 2: Research Question Input & Prompt Suggestion Pills */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <label style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Research Prompt / Analytical Thesis
          </label>
          <textarea
            data-testid="research-question-input"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={isLoading}
            placeholder="Ask specific analytical questions about this stock..."
            style={{
              width: '100%',
              backgroundColor: 'var(--bg-surface-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-2) var(--space-3)',
              fontSize: 'var(--text-sm)',
              color: 'var(--text-primary)',
              fontFamily: 'inherit',
              resize: 'vertical',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />

          {/* Quick prompts */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1-5)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>Suggested:</span>
            {PROMPT_SUGGESTIONS.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                disabled={isLoading}
                onClick={() => setQuestion(`Analyze ${symbol}: ${preset}`)}
                style={{
                  padding: '2px 8px',
                  fontSize: 'var(--text-2xs)',
                  color: 'var(--text-secondary)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  textAlign: 'left',
                }}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        {/* Row 3: Point-in-Time as_of Date Control & Execution Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)' }}>
          {/* As of Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1-5)', cursor: isLoading ? 'not-allowed' : 'pointer', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={isHistorical}
                onChange={(e) => setIsHistorical(e.target.checked)}
                disabled={isLoading}
              />
              <span>Point-In-Time Historical Mode (as_of)</span>
            </label>

            {isHistorical && (
              <div style={{ width: '220px' }}>
                <Input
                  type="text"
                  placeholder="e.g. 2026-08-20T10:00:00Z"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            )}
          </div>

          {/* Submit Action */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            {isLoading && elapsedSeconds > 0 && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Elapsed: {elapsedSeconds}s
              </span>
            )}
            <Button
              data-testid="run-research-button"
              type="button"
              variant="primary"
              size="md"
              disabled={isLoading || !symbol.trim() || !question.trim()}
              onClick={() => handleSubmit()}
            >
              {isLoading ? '▶ Synthesizing Intelligence...' : '▶ Run Research Analysis'}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
};
