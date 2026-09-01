import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { NewsItem } from '@/lib/api/types';

export interface MarketNewsFeedProps {
  news?: NewsItem[];
}

export const MarketNewsFeed: React.FC<MarketNewsFeedProps> = ({ news = [] }) => {
  return (
    <Card header="Market News & Regulatory Announcements">
      {news.length === 0 ? (
        <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          No material market disclosures in the last session.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {news.slice(0, 5).map((item) => (
            <div
              key={item.id}
              style={{
                paddingBottom: 'var(--space-2-5)',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {item.source} • {new Date(item.published_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })} IST
                </span>
                {item.event_type && <Badge variant="neutral" size="sm">{item.event_type}</Badge>}
              </div>

              <a
                href={item.url || '#'}
                target={item.url ? '_blank' : '_self'}
                rel="noreferrer"
                style={{
                  fontSize: 'var(--text-sm)',
                  fontWeight: 'var(--weight-medium)',
                  color: 'var(--text-primary)',
                  lineHeight: 1.4,
                  textDecoration: 'none',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--brand-primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
              >
                {item.headline}
              </a>

              {item.summary && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {item.summary.length > 140 ? `${item.summary.slice(0, 140)}...` : item.summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
