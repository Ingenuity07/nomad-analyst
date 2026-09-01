import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ResearchReportResponse } from '@/lib/api/types';

export interface ResearchReportHeaderProps {
  report: ResearchReportResponse;
  onOpenEvidence: () => void;
  onNewInquiry: () => void;
}

export const ResearchReportHeader: React.FC<ResearchReportHeaderProps> = ({
  report,
  onOpenEvidence,
  onNewInquiry,
}) => {
  const evidenceCount = report.evidence ? report.evidence.length : 0;
  const isHistorical = !!report.as_of;

  return (
    <div
      data-testid="research-report-header"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-4) var(--space-5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 'var(--space-4)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', margin: 0 }}>
            {report.company || report.instrument}
          </h2>
          <Badge variant="brand" size="sm">
            {report.instrument}
          </Badge>
          {isHistorical ? (
            <Badge variant="warning" size="sm">
              Historical PIT Mode
            </Badge>
          ) : (
            <Badge variant="positive" size="sm">
              Live Evaluation
            </Badge>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          <span>
            <strong>Research As-Of:</strong>{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {report.as_of ? new Date(report.as_of).toLocaleString() : 'Current Active Bar'}
            </span>
          </span>
          <span>•</span>
          <span>
            <strong>Generated:</strong>{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {report.generated_at ? new Date(report.generated_at).toLocaleString() : 'Just now'}
            </span>
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <Button
          data-testid="open-evidence-button"
          type="button"
          variant="secondary"
          size="sm"
          onClick={onOpenEvidence}
        >
          🔍 Evidence Traces ({evidenceCount})
        </Button>
        <Button
          data-testid="new-inquiry-button"
          type="button"
          variant="secondary"
          size="sm"
          onClick={onNewInquiry}
        >
          + New Inquiry
        </Button>
      </div>
    </div>
  );
};
