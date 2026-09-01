import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { CorporateDisclosure } from '@/lib/api/types';

export interface ExchangeDisclosuresCardProps {
  disclosures: CorporateDisclosure[];
  companyName: string;
}

export const ExchangeDisclosuresCard: React.FC<ExchangeDisclosuresCardProps> = ({
  disclosures = [],
  companyName,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Distinct categories
  const categories = ['ALL', ...Array.from(new Set(disclosures.map((d) => d.category).filter(Boolean)))];

  const filtered = selectedCategory === 'ALL'
    ? disclosures
    : disclosures.filter((d) => d.category === selectedCategory);

  return (
    <Card header={`Exchange Regulatory Filings & Corporate Announcements — ${companyName}`} data-testid="exchange-disclosures-card">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Category Filter Pills */}
        {categories.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1-5)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Filter Category:</span>
            {categories.map((cat) => {
              const isSelected = selectedCategory === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  style={{
                    padding: '2px 8px',
                    fontSize: 'var(--text-xs)',
                    color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                    backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-sunken)',
                    border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-xs)',
                    cursor: 'pointer',
                  }}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        )}

        {/* Disclosures List */}
        {filtered.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
            No exchange regulatory disclosures recorded for this period.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2-5)' }}>
            {filtered.map((item, idx) => {
              return (
                <div
                  key={item.id || idx}
                  style={{
                    padding: 'var(--space-3)',
                    backgroundColor: 'var(--bg-surface-sunken)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-1-5)',
                  }}
                >
                  {/* Top line: Badges and Timestamps */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <Badge variant="brand" size="sm">
                        {item.source || 'NSE'}
                      </Badge>
                      {item.category && (
                        <Badge variant="neutral" size="sm">
                          {item.category}
                        </Badge>
                      )}
                      {item.announcement_id && (
                        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          ID: {item.announcement_id}
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Published: {item.published_at ? new Date(item.published_at).toLocaleString() : 'Recent'}
                    </div>
                  </div>

                  {/* Headline */}
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    {item.headline}
                  </div>

                  {/* External official filing URL if available */}
                  {item.url && (
                    <div style={{ marginTop: 'var(--space-1)' }}>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          fontSize: 'var(--text-xs)',
                          color: 'var(--brand-primary)',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 'var(--space-1)',
                        }}
                      >
                        📄 View Official Exchange Filing ↗
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
};
