import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  disabled,
  style,
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'primary':
        return {
          backgroundColor: 'var(--brand-primary)',
          color: '#FFFFFF',
          border: '1px solid var(--brand-primary)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-medium)',
        };
      case 'ghost':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-secondary)',
          border: '1px solid transparent',
        };
      case 'danger':
        return {
          backgroundColor: 'var(--negative-bg)',
          color: 'var(--negative)',
          border: '1px solid var(--negative-border)',
        };
      case 'secondary':
      default:
        return {
          backgroundColor: 'var(--bg-surface-elevated)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-subtle)',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return {
          padding: 'var(--space-1) var(--space-2)',
          fontSize: 'var(--text-xs)',
          gap: 'var(--space-1)',
        };
      case 'lg':
        return {
          padding: 'var(--space-3) var(--space-6)',
          fontSize: 'var(--text-md)',
          gap: 'var(--space-3)',
        };
      case 'md':
      default:
        return {
          padding: 'var(--space-2) var(--space-4)',
          fontSize: 'var(--text-sm)',
          gap: 'var(--space-2)',
        };
    }
  };

  return (
    <button
      disabled={disabled || isLoading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 'var(--weight-medium)',
        borderRadius: 'var(--radius-md)',
        transition: 'all var(--transition-fast)',
        cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
        opacity: disabled || isLoading ? 0.6 : 1,
        ...getVariantStyles(),
        ...getSizeStyles(),
        ...style,
      }}
      {...props}
    >
      {isLoading ? (
        <span style={{ display: 'inline-block', width: '12px', height: '12px', border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
};
