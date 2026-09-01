import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { apiClient } from '@/lib/api/client';

export interface AIResearchTabProps {
  symbol: string;
}

export const AIResearchTab: React.FC<AIResearchTabProps> = ({ symbol }) => {
  const [query, setQuery] = useState<string>(`Analyze the investment thesis, key growth drivers, and primary risks for ${symbol}.`);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [response, setResponse] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await apiClient<{ response: string; tools_called?: any[]; as_of?: string }>('/api/v1/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      });
      setResponse(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to generate AI research report.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card header={`Nomad Analyst AI Research — ${symbol}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: 0 }}>
          Direct integration with the Module 5 Agentic Research Orchestrator. The AI uses point-in-time tools to inspect price action, fundamentals, sector leadership, and news before synthesizing findings.
        </p>

        {/* Input and Ask Action */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <Input
              label="Research Question / Prompt"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask an analytical question regarding this stock..."
            />
          </div>
          <Button variant="primary" size="md" onClick={handleAsk} isLoading={isLoading}>
            Generate Research Report →
          </Button>
        </div>

        {/* Report Output */}
        {error && (
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--negative-bg)', color: 'var(--negative)', borderRadius: 'var(--radius-xs)', fontSize: 'var(--text-xs)' }}>
            {error}
          </div>
        )}

        {response && (
          <div
            data-testid="ai-research-output"
            style={{
              marginTop: 'var(--space-2)',
              padding: 'var(--space-4)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
              Analytical Research Synthesis
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', whiteSpace: 'pre-line', lineHeight: '1.6' }}>
              {response.response}
            </div>
            {response.as_of && (
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: 'var(--space-3)', fontFamily: 'var(--font-mono)' }}>
                Synthesized as of {new Date(response.as_of).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
