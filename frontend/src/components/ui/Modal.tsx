import React, { useEffect } from 'react';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = '560px',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 'var(--space-4)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-strong)',
          borderRadius: 'var(--radius-lg)',
          width: '100%',
          maxWidth,
          boxShadow: 'var(--shadow-popover)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div
            style={{
              padding: 'var(--space-3) var(--space-4)',
              borderBottom: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-surface-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-md)', color: 'var(--text-primary)' }}>
              {title}
            </div>
            <button
              onClick={onClose}
              aria-label="Close dialog"
              style={{
                color: 'var(--text-secondary)',
                fontSize: 'var(--text-lg)',
                lineHeight: 1,
                padding: 'var(--space-1)',
              }}
            >
              ✕
            </button>
          </div>
        )}
        <div style={{ padding: 'var(--space-4)', overflowY: 'auto' }}>{children}</div>
      </div>
    </div>
  );
};
