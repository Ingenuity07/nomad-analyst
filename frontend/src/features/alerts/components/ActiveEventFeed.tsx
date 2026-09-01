import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { MonitorEvent } from '../storage';

export interface ActiveEventFeedProps {
  events: MonitorEvent[];
  onSelectEvent: (event: MonitorEvent) => void;
  onClearEvents: () => void;
}

export const ActiveEventFeed: React.FC<ActiveEventFeedProps> = ({
  events = [],
  onSelectEvent,
  onClearEvents,
}) => {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  const categories: Array<{ key: string; label: string }> = [
    { key: 'ALL', label: 'All Events' },
    { key: 'RECOMMENDATIONS', label: 'Recommendations' },
    { key: 'OPPORTUNITIES', label: 'Opportunities' },
    { key: 'INTRADAY', label: 'Intraday' },
    { key: 'MARKET_REGIME', label: 'Market Regime' },
    { key: 'WATCHLIST_TRIGGERS', label: 'Watchlist Triggers' },
  ];

  const filteredEvents = events.filter((ev) => {
    if (selectedCategory === 'ALL') return true;
    return ev.category === selectedCategory;
  });

  const getSeverityBadge = (sev: string) => {
    if (sev === 'HIGH') return <Badge variant="negative" size="sm">HIGH</Badge>;
    if (sev === 'MEDIUM') return <Badge variant="brand" size="sm">MEDIUM</Badge>;
    return <Badge variant="neutral" size="sm">INFO</Badge>;
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <Card
      header="Analytical Event Log & Real-Time Alerts"
      action={
        events.length > 0 ? (
          <Button type="button" variant="ghost" size="sm" onClick={onClearEvents}>
            Clear Feed
          </Button>
        ) : undefined
      }
      data-testid="active-event-feed"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {/* Category Filter Pills */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat.key;
            return (
              <button
                key={cat.key}
                type="button"
                onClick={() => setSelectedCategory(cat.key)}
                style={{
                  padding: 'var(--space-1) var(--space-2-5)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                  color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                  backgroundColor: isSelected ? 'var(--brand-subtle)' : 'var(--bg-surface-sunken)',
                  border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-xs)',
                  cursor: 'pointer',
                }}
              >
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Events List */}
        {filteredEvents.length === 0 ? (
          <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
            No monitoring events recorded in this category yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {filteredEvents.map((ev) => (
              <div
                key={ev.id}
                onClick={() => onSelectEvent(ev)}
                style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  cursor: 'pointer',
                  transition: 'border-color var(--transition-fast)',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                    {getSeverityBadge(ev.severity)}
                    {ev.symbol && (
                      <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)', fontSize: 'var(--text-xs)' }}>
                        {ev.symbol}
                      </span>
                    )}
                    <span style={{ fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
                      {ev.title}
                    </span>
                  </div>

                  <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {ev.summary}
                  </p>

                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                    Source: {ev.source} • Time: {formatTimestamp(ev.observedAt)}
                  </div>
                </div>

                {ev.navigationLink && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(ev.navigationLink!);
                    }}
                  >
                    Open ↗
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
};
