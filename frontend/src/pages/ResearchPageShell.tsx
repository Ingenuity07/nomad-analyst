import React from 'react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';

export const ResearchPageShell: React.FC = () => {
  return (
    <PageContainer
      title="AI Intelligence & Synthesis"
      subtitle="Deterministic financial tool routing powered by Google Gemini and Claude 3.5 Sonnet"
    >
      <Card header="AI Research Console Shell (FE-8 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Ask natural-language equity questions, inspect deterministic tool trace logs, and generate cited investment memos.
        </p>
        <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          AI Provider: Gemini 2.5 Flash / Pro • Endpoint: POST /api/v1/research/
        </div>
      </Card>
    </PageContainer>
  );
};
