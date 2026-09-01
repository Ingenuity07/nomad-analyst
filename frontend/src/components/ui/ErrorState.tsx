import React from 'react';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message: string;
  code?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Unable to Load Financial Data',
  message,
  code,
  onRetry,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-8) var(--space-4)',
        textAlign: 'center',
        border: '1px solid var(--negative-border)',
        backgroundColor: 'var(--negative-bg)',
        borderRadius: 'var(--radius-md)',
        margin: 'var(--space-4) 0',
      }}
    >
      <div style={{ color: 'var(--negative)', fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-md)', marginBottom: 'var(--space-1)' }}>
        ⚠ {title}
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', maxWidth: '500px', marginBottom: 'var(--space-3)' }}>
        {message}
      </div>
      {code && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--space-4)' }}>
          Code: {code}
        </div>
      )}
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          ↻ Retry Request
        </Button>
      )}
    </div>
  );
};
