import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  leftIcon,
  rightIcon,
  style,
  id,
  ...props
}) => {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', width: '100%' }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 'var(--weight-medium)',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {label}
        </label>
      )}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          backgroundColor: 'var(--bg-surface-sunken)',
          border: error ? '1px solid var(--negative)' : '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '0 var(--space-3)',
          transition: 'border-color var(--transition-fast)',
        }}
      >
        {leftIcon && <div style={{ color: 'var(--text-muted)', marginRight: 'var(--space-2)', display: 'flex' }}>{leftIcon}</div>}
        <input
          id={inputId}
          style={{
            flex: 1,
            backgroundColor: 'transparent',
            border: 'none',
            outline: 'none',
            padding: 'var(--space-2) 0',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)',
            width: '100%',
            ...style,
          }}
          {...props}
        />
        {rightIcon && <div style={{ color: 'var(--text-muted)', marginLeft: 'var(--space-2)', display: 'flex' }}>{rightIcon}</div>}
      </div>
      {error && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--negative)' }}>{error}</span>}
    </div>
  );
};
