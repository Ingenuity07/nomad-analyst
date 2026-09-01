import React from 'react';

export interface TabItem {
  key: string;
  label: string;
  count?: number;
  icon?: React.ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  activeKey: string;
  onChange: (key: string) => void;
  variant?: 'underline' | 'pill';
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeKey,
  onChange,
  variant = 'underline',
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: variant === 'pill' ? 'var(--space-1)' : 'var(--space-4)',
        borderBottom: variant === 'underline' ? '1px solid var(--border-subtle)' : 'none',
        paddingBottom: variant === 'underline' ? '0' : 'var(--space-2)',
      }}
    >
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey;
        if (variant === 'pill') {
          return (
            <button
              key={tab.key}
              onClick={() => onChange(tab.key)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-1-5)',
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--text-xs)',
                fontWeight: isActive ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                backgroundColor: isActive ? 'var(--bg-surface-elevated)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: isActive ? '1px solid var(--border-strong)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                transition: 'all var(--transition-fast)',
              }}
            >
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>({tab.count})</span>
              )}
            </button>
          );
        }

        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--space-1-5)',
              padding: 'var(--space-2) 0',
              fontSize: 'var(--text-sm)',
              fontWeight: isActive ? 'var(--weight-semibold)' : 'var(--weight-regular)',
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              borderBottom: isActive ? '2px solid var(--brand-primary)' : '2px solid transparent',
              marginBottom: '-1px',
              transition: 'all var(--transition-fast)',
            }}
          >
            {tab.icon}
            {tab.label}
            {tab.count !== undefined && (
              <span
                style={{
                  fontSize: 'var(--text-2xs)',
                  padding: '1px 5px',
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  color: 'var(--text-muted)',
                }}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
