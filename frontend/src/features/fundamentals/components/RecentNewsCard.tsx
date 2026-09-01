import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { NewsItem } from '@/lib/api/types';

export interface RecentNewsCardProps {
  news: NewsItem[];
  symbol: string;
}

export const RecentNewsCard: React.FC<RecentNewsCardProps> = ({
  news = [],
  symbol,
}) => {
  const navigate = useNavigate();
  const recent = news.slice(0, 5);

  return (
    <Card
      header="Recent Corporate & Material News"
      action={
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/stocks/${symbol}`)}
        >
          View All in Terminal →
        </Button>
      }
      data-testid="recent-news-card"
    >
      {recent.length === 0 ? (
        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
          No recent corporate news items recorded.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {recent.map((item, idx) => (
            <div
              key={item.id || idx}
              style={{
                padding: 'var(--space-2-5) var(--space-3)',
                backgroundColor: 'var(--bg-surface-sunken)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                <span>{item.source || 'News Wire'}</span>
                <span>{item.published_at ? new Date(item.published_at).toLocaleDateString() : ''}</span>
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', fontWeight: 'var(--weight-medium)' }}>
                {item.headline}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
