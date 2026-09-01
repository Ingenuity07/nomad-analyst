import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Watchlist } from '../storage';

export interface WatchlistManagerTabsProps {
  watchlists: Watchlist[];
  activeId: string;
  onSelectWatchlist: (id: string) => void;
  onCreateWatchlist: (name: string) => void;
  onRenameWatchlist: (id: string, newName: string) => void;
  onDeleteWatchlist: (id: string) => void;
}

export const WatchlistManagerTabs: React.FC<WatchlistManagerTabsProps> = ({
  watchlists,
  activeId,
  onSelectWatchlist,
  onCreateWatchlist,
  onRenameWatchlist,
  onDeleteWatchlist,
}) => {
  const [isCreating, setIsCreating] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  const activeList = watchlists.find((w) => w.id === activeId) || watchlists[0];

  const handleCreateSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!newListName.trim()) return;
    onCreateWatchlist(newListName.trim());
    setNewListName('');
    setIsCreating(false);
  };

  const handleRenameSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!renameValue.trim()) return;
    onRenameWatchlist(activeId, renameValue.trim());
    setIsRenaming(false);
  };

  return (
    <div
      data-testid="watchlist-manager-tabs"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
        backgroundColor: 'var(--bg-surface)',
        padding: 'var(--space-3) var(--space-4)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      {/* Top Row: Watchlist Tabs and Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        {/* Watchlist Selection Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {watchlists.map((wl) => {
            const isSelected = wl.id === activeId;
            return (
              <button
                key={wl.id}
                type="button"
                onClick={() => {
                  onSelectWatchlist(wl.id);
                  setIsRenaming(false);
                }}
                style={{
                  padding: 'var(--space-1-5) var(--space-3)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                  color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                  backgroundColor: isSelected ? 'var(--brand-subtle)' : 'var(--bg-surface-sunken)',
                  border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>{wl.name}</span>
                <span style={{ fontSize: 'var(--text-2xs)', color: isSelected ? 'var(--brand-primary)' : 'var(--text-muted)' }}>
                  ({wl.symbols.length})
                </span>
              </button>
            );
          })}

          {/* New List Button */}
          {!isCreating && (
            <button
              data-testid="add-new-watchlist-btn"
              type="button"
              onClick={() => setIsCreating(true)}
              style={{
                padding: 'var(--space-1-5) var(--space-2-5)',
                fontSize: 'var(--text-xs)',
                color: 'var(--text-muted)',
                backgroundColor: 'transparent',
                border: '1px dashed var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              + New Watchlist
            </button>
          )}
        </div>

        {/* Management Actions for Active List */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {!isRenaming && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setRenameValue(activeList?.name || '');
                setIsRenaming(true);
              }}
            >
              ✏️ Rename
            </Button>
          )}
          {watchlists.length > 1 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onDeleteWatchlist(activeId)}
            >
              🗑️ Delete
            </Button>
          )}
        </div>
      </div>

      {/* Inline Create Form */}
      {isCreating && (
        <form onSubmit={handleCreateSubmit} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <div style={{ width: '220px' }}>
            <Input
              placeholder="Watchlist name..."
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              autoFocus
            />
          </div>
          <Button type="button" variant="primary" size="sm" onClick={() => handleCreateSubmit()}>
            Create
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setIsCreating(false)}>
            Cancel
          </Button>
        </form>
      )}

      {/* Inline Rename Form */}
      {isRenaming && (
        <form onSubmit={handleRenameSubmit} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <div style={{ width: '220px' }}>
            <Input
              placeholder="New watchlist name..."
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              autoFocus
            />
          </div>
          <Button type="button" variant="primary" size="sm" onClick={() => handleRenameSubmit()}>
            Save Name
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setIsRenaming(false)}>
            Cancel
          </Button>
        </form>
      )}
    </div>
  );
};
