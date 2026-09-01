import React from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';

export interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  evidence: string[];
  companyName: string;
  symbol: string;
  asOf?: string | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  evidence = [],
  companyName,
  symbol,
  asOf,
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Factual Evidence Traces — ${symbol}`}
      maxWidth="680px"
    >
      <div data-testid="evidence-drawer-content" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Subtitle / context info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', paddingBottom: 'var(--space-3)', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
            {companyName} ({symbol})
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            {asOf ? `Historical evaluation as of ${new Date(asOf).toLocaleString()}` : 'Live evaluation using deterministic tools'}
          </div>
        </div>

        {/* Evidence List */}
        {evidence.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
            No explicit factual citations linked to this synthesis report.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', maxHeight: '400px', overflowY: 'auto', paddingRight: 'var(--space-1)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)' }}>
              Total Cited Sources ({evidence.length}):
            </div>
            {evidence.map((item, idx) => (
              <div
                key={idx}
                style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-2)',
                }}
              >
                <Badge variant="neutral" size="sm">
                  #{idx + 1}
                </Badge>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', lineHeight: 1.5, wordBreak: 'break-word', fontFamily: 'var(--font-mono)' }}>
                  {item}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Provenance note */}
        <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
          <strong>Evidence Grounding:</strong> All numbers, ratios, dates, and historical indicators are strictly retrieved from deterministic financial tools and exchange feeds.
        </div>
      </div>
    </Modal>
  );
};
