import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ResearchReportResponse } from '@/lib/api/types';

export interface HistoryItem {
  id: string;
  report: ResearchReportResponse;
  question: string;
  depth?: string;
}

export interface SessionResearchHistoryProps {
  history: HistoryItem[];
  selectedId: string | null;
  onSelect: (item: HistoryItem) => void;
  onClear: () => void;
}

export const SessionResearchHistory: React.FC<SessionResearchHistoryProps> = ({
  history,
  selectedId,
  onSelect,
  onClear,
}) => {
  if (history.length === 0) return null;

  return (
    <Card
      header="Recent Inquiries (This Session)"
      action={
        <Button variant="ghost" size="sm" onClick={onClear}>
          Clear History
        </Button>
      }
      data-testid="session-research-history"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        {history.map((item) => {
          const isSelected = selectedId === item.id;
          return (
            <div
              key={item.id}
              onClick={() => onSelect(item)}
              style={{
                padding: 'var(--space-2-5) var(--space-3)',
                backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-sunken)',
                border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 'var(--space-3)',
                transition: 'all var(--transition-fast)',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <Badge variant="brand" size="sm">
                    {item.report.instrument}
                  </Badge>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.report.company || item.report.instrument}
                  </span>
                  {item.depth && (
                    <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      ({item.depth})
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.question}
                </div>
              </div>

              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                {item.report.generated_at ? new Date(item.report.generated_at).toLocaleTimeString() : ''}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
