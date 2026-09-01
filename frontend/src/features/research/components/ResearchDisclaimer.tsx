import React from 'react';

export const ResearchDisclaimer: React.FC = () => {
  return (
    <div
      data-testid="research-disclaimer"
      style={{
        padding: 'var(--space-3) var(--space-4)',
        backgroundColor: 'var(--bg-surface-subtle)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        fontSize: 'var(--text-xs)',
        color: 'var(--text-muted)',
      }}
    >
      <span style={{ fontSize: 'var(--text-sm)' }}>ℹ️</span>
      <div>
        <strong style={{ color: 'var(--text-secondary)' }}>Non-Advisory Research Notice: </strong>
        AI-generated synthesis for research and informational purposes only. Nomad Analyst does not provide personalized investment advice or guaranteed trade execution.
      </div>
    </div>
  );
};
