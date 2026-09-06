import React, { useState } from 'react';
import { useKiteStatus } from '@/hooks/useKiteAuth';
import { KiteAuthModal } from './KiteAuthModal';

export const KiteStatusBadge: React.FC = () => {
  const { data: statusData, isLoading } = useKiteStatus();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const status = statusData?.status || 'NOT_CONFIGURED';
  const isConnected = statusData?.authenticated && status === 'CONNECTED';
  const isExpired = status === 'EXPIRED';

  let dotColor = 'var(--text-muted)';
  let label = 'Connect Kite';

  if (isLoading) {
    label = 'Kite...';
  } else if (isConnected) {
    dotColor = 'var(--positive)';
    label = 'Kite Connected';
  } else if (isExpired) {
    dotColor = 'var(--warning)';
    label = 'Kite Expired';
  } else if (status === 'AUTHENTICATING') {
    dotColor = 'var(--warning)';
    label = 'Kite Connecting...';
  } else if (status === 'ERROR') {
    dotColor = 'var(--negative)';
    label = 'Kite Error';
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
          padding: 'var(--space-1) var(--space-2-5)',
          borderRadius: 'var(--radius-full)',
          backgroundColor: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-subtle)',
          cursor: 'pointer',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-primary)',
          fontWeight: 'var(--weight-medium)',
          transition: 'background-color 0.15s ease, border-color 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover, rgba(255,255,255,0.06))';
          e.currentTarget.style.borderColor = 'var(--border-medium)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)';
          e.currentTarget.style.borderColor = 'var(--border-subtle)';
        }}
        title="Zerodha Kite Connect status and session management"
      >
        <span
          style={{
            display: 'inline-block',
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: dotColor,
            boxShadow: isConnected ? '0 0 6px var(--positive)' : 'none',
          }}
        />
        <span>{label}</span>
      </button>

      <KiteAuthModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};
