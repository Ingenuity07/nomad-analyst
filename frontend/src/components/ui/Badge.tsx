import React from 'react';

export interface BadgeProps {
  variant?: 'positive' | 'negative' | 'warning' | 'neutral' | 'brand';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  children,
  icon,
  style,
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'positive':
        return {
          backgroundColor: 'var(--positive-bg)',
          color: 'var(--positive)',
          borderColor: 'var(--positive-border)',
        };
      case 'negative':
        return {
          backgroundColor: 'var(--negative-bg)',
          color: 'var(--negative)',
          borderColor: 'var(--negative-border)',
        };
      case 'warning':
        return {
          backgroundColor: 'var(--warning-bg)',
          color: 'var(--warning)',
          borderColor: 'var(--warning-border)',
        };
      case 'brand':
        return {
          backgroundColor: 'var(--brand-subtle)',
          color: 'var(--brand-primary)',
          borderColor: 'var(--brand-border)',
        };
      case 'neutral':
      default:
        return {
          backgroundColor: 'var(--neutral-bg)',
          color: 'var(--text-secondary)',
          borderColor: 'var(--neutral-border)',
        };
    }
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--space-1)',
        padding: size === 'sm' ? '1px var(--space-1-5)' : '2px var(--space-2)',
        fontSize: size === 'sm' ? 'var(--text-2xs)' : 'var(--text-xs)',
        fontWeight: 'var(--weight-semibold)',
        fontFamily: 'var(--font-mono)',
        borderRadius: 'var(--radius-xs)',
        border: '1px solid',
        letterSpacing: '0.02em',
        lineHeight: 1.2,
        ...getVariantStyles(),
        ...style,
      }}
    >
      {icon}
      {children}
    </span>
  );
};
