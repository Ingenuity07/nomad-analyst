import React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';

export const PageLoadingFallback: React.FC = () => {
  return (
    <div
      data-testid="page-loading-fallback"
      style={{
        padding: 'var(--space-6)',
        maxWidth: '1600px',
        width: '100%',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-6)',
      }}
    >
      {/* Header Skeleton */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        <Skeleton height="32px" width="300px" />
        <Skeleton height="16px" width="520px" />
      </div>

      {/* Metric Cards Skeleton Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 'var(--space-4)',
        }}
      >
        <Skeleton height="88px" />
        <Skeleton height="88px" />
        <Skeleton height="88px" />
        <Skeleton height="88px" />
      </div>

      {/* Main Content Area Skeleton */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-6)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)',
        }}
      >
        <Skeleton height="24px" width="200px" />
        <Skeleton height="280px" />
      </div>
    </div>
  );
};
export default PageLoadingFallback;
