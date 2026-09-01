import React from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
}

export const Select: React.FC<SelectProps> = ({
  label,
  options,
  error,
  id,
  style,
  ...props
}) => {
  const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      {label && (
        <label
          htmlFor={selectId}
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
      <select
        id={selectId}
        style={{
          backgroundColor: 'var(--bg-surface-sunken)',
          border: error ? '1px solid var(--negative)' : '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-2) var(--space-3)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-primary)',
          outline: 'none',
          cursor: 'pointer',
          ...style,
        }}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} style={{ backgroundColor: 'var(--bg-surface)' }}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--negative)' }}>{error}</span>}
    </div>
  );
};
