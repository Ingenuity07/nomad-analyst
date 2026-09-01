import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { MonitorEvent } from '../storage';

export interface AlertDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  event: MonitorEvent | null;
}

export const AlertDetailDrawer: React.FC<AlertDetailDrawerProps> = ({
  isOpen,
  onClose,
  event,
}) => {
  const navigate = useNavigate();

  if (!event) return null;

  const getSeverityBadge = (sev: string) => {
    if (sev === 'HIGH') return <Badge variant="negative" size="sm">HIGH PRIORITY</Badge>;
    if (sev === 'MEDIUM') return <Badge variant="brand" size="sm">MEDIUM PRIORITY</Badge>;
    return <Badge variant="neutral" size="sm">INFORMATIONAL</Badge>;
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Alert & Event Dossier"
    >
      <div data-testid="alert-detail-drawer" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Header Summary Box */}
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            backgroundColor: 'var(--bg-surface-sunken)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--space-2)',
          }}
        >
          <div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {event.symbol ? `${event.symbol} — ${event.title}` : event.title}
            </div>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
              Category: {event.category} • Source: {event.source}
            </div>
          </div>
          {getSeverityBadge(event.severity)}
        </div>

        {/* Narrative & Explanation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 'var(--weight-medium)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Event Analysis:
          </span>
          <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {event.summary}
          </p>
        </div>

        {/* Timestamps */}
        <div
          style={{
            padding: 'var(--space-2-5) var(--space-3)',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-xs)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <span>Observed In-Session:</span>
          <strong style={{ fontFamily: 'var(--font-mono)' }}>{new Date(event.observedAt).toLocaleString()}</strong>
        </div>

        {/* Contextual Navigation Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
          {event.symbol && (
            <>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  onClose();
                  navigate(`/stocks/${event.symbol}`);
                }}
              >
                📈 Stock Terminal
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  onClose();
                  navigate(`/fundamentals?symbol=${event.symbol}`);
                }}
              >
                🏛️ Fundamentals
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => {
                  onClose();
                  navigate(`/research?symbol=${event.symbol}`);
                }}
              >
                🤖 AI Research
              </Button>
            </>
          )}

          {event.navigationLink && !event.symbol && (
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => {
                onClose();
                navigate(event.navigationLink!);
              }}
            >
              Open Workspace ↗
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
};
