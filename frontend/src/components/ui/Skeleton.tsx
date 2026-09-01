import React from 'react';

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '16px',
  borderRadius = 'var(--radius-xs)',
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: 'var(--bg-surface-elevated)',
        opacity: 0.6,
        animation: 'pulse 1.5s ease-in-out infinite',
        ...style,
      }}
    />
  );
};
