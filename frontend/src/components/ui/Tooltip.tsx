import React, { useState } from 'react';

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
}

export const Tooltip: React.FC<TooltipProps> = ({ content, children }) => {
  const [visible, setVisible] = useState(false);

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-primary)',
            fontSize: 'var(--text-xs)',
            padding: 'var(--space-1) var(--space-2)',
            borderRadius: 'var(--radius-xs)',
            border: '1px solid var(--border-medium)',
            boxShadow: 'var(--shadow-medium)',
            whiteSpace: 'nowrap',
            zIndex: 100,
            pointerEvents: 'none',
          }}
        >
          {content}
        </div>
      )}
    </div>
  );
};
