import React from 'react';

export interface PageContainerProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

export const PageContainer: React.FC<PageContainerProps> = ({
  title,
  subtitle,
  action,
  children,
}) => {
  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            {title}
          </h1>
          {subtitle && (
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
              {subtitle}
            </p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
};
