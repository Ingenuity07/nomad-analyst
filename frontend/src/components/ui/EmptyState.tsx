import React from 'react';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-10) var(--space-4)',
        textAlign: 'center',
        color: 'var(--text-secondary)',
      }}
    >
      {icon && <div style={{ fontSize: '32px', color: 'var(--text-muted)', marginBottom: 'var(--space-3)' }}>{icon}</div>}
      <div style={{ fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-md)', color: 'var(--text-primary)', marginBottom: 'var(--space-1)' }}>
        {title}
      </div>
      {description && (
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', maxWidth: '400px', marginBottom: 'var(--space-4)' }}>
          {description}
        </div>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};
