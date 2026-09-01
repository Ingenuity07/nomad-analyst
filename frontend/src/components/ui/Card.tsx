import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  header?: React.ReactNode;
  action?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  header,
  action,
  footer,
  children,
  style,
  ...props
}) => {
  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        ...style,
      }}
      {...props}
    >
      {(header || action) && (
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontWeight: 'var(--weight-medium)', fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
            {header}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div style={{ padding: 'var(--space-4)', flex: 1 }}>{children}</div>
      {footer && (
        <div
          style={{
            padding: 'var(--space-2) var(--space-4)',
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface-subtle)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
          }}
        >
          {footer}
        </div>
      )}
    </div>
  );
};
