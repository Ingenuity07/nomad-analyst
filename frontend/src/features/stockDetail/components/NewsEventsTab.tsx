import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { useStockNews } from '@/hooks/useStockNews';
import { useStockEvents } from '@/hooks/useStockEvents';

export interface NewsEventsTabProps {
  symbol: string;
}

export const NewsEventsTab: React.FC<NewsEventsTabProps> = ({ symbol }) => {
  const { data: newsData, isLoading: isNewsLoading } = useStockNews(symbol, 15);
  const { data: eventsData, isLoading: isEventsLoading } = useStockEvents(symbol, 15);

  const newsItems = newsData?.results || [];
  const events = eventsData?.results || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-6)' }}>
      {/* 1. Stock News Feed */}
      <Card header={`Company News (${newsItems.length} Stories)`}>
        {isNewsLoading ? (
          <Skeleton height="200px" />
        ) : newsItems.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
            No recent company news articles recorded for {symbol}.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {newsItems.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                  <a
                    href={item.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 'var(--text-sm)',
                      fontWeight: 'var(--weight-semibold)',
                      color: 'var(--text-primary)',
                      textDecoration: 'none',
                    }}
                  >
                    {item.headline}
                  </a>
                  {item.source && <Badge variant="neutral" size="sm">{item.source}</Badge>}
                </div>
                {item.summary && (
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)', marginBottom: 0 }}>
                    {item.summary}
                  </p>
                )}
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: 'var(--space-2)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(item.published_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 2. Corporate Announcements & Filings */}
      <Card header={`Exchange Filings & Disclosures (${events.length})`}>
        {isEventsLoading ? (
          <Skeleton height="200px" />
        ) : events.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
            No corporate disclosures or regulatory announcements recorded for {symbol}.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {events.map((ev) => (
              <div
                key={ev.id}
                style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                    {ev.headline}
                  </div>
                  {ev.category && <Badge variant="brand" size="sm">{ev.category}</Badge>}
                </div>
                {ev.details && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    {typeof ev.details === 'string' ? ev.details : JSON.stringify(ev.details)}
                  </div>
                )}
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: 'var(--space-2)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(ev.published_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
