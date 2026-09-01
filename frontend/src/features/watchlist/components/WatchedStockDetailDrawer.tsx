import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { WatchlistItem, DecisionStatus } from '../storage';
import { StockDetailResponse, StockRecommendation, StockOpportunitySnapshot } from '@/lib/api/types';

export interface WatchedStockDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  item: WatchlistItem | null;
  stockDetail?: StockDetailResponse | null;
  activeRec?: StockRecommendation | null;
  opportunity?: StockOpportunitySnapshot | null;
  onUpdateDecision: (symbol: string, status: DecisionStatus, notes?: string) => void;
  onRemoveFromList: (symbol: string) => void;
}

export const WatchedStockDetailDrawer: React.FC<WatchedStockDetailDrawerProps> = ({
  isOpen,
  onClose,
  item,
  stockDetail,
  activeRec,
  opportunity,
  onUpdateDecision,
  onRemoveFromList,
}) => {
  const navigate = useNavigate();
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState('');

  if (!item) return null;

  const symbol = item.symbol;
  const snapshot = stockDetail?.latest_snapshot;
  const company = stockDetail?.instrument?.company;

  const handleStartEdit = () => {
    setNotesDraft(item.notes || '');
    setEditingNotes(true);
  };

  const handleSaveNotes = () => {
    onUpdateDecision(symbol, item.decisionStatus, notesDraft);
    setEditingNotes(false);
  };

  const handleStatusChange = (newStatus: DecisionStatus) => {
    onUpdateDecision(symbol, newStatus, item.notes);
  };

  const isPositive = (snapshot?.change_percent ?? 0) >= 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${symbol} — Watched Decision Dossier`}
      data-testid="watched-stock-detail-drawer"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Top summary row: Company Name, Sector, Status, Quote */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            backgroundColor: 'var(--bg-surface-sunken)',
            padding: 'var(--space-3) var(--space-4)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            flexWrap: 'wrap',
            gap: 'var(--space-2)',
          }}
        >
          <div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
              {company?.name || symbol}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              {company?.sector || 'Equity'} • {company?.industry || 'NSE'}
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)' }}>
              {snapshot?.close ? `₹${Number(snapshot.close).toFixed(2)}` : '—'}
            </div>
            {snapshot?.change_percent !== undefined && (
              <div
                style={{
                  fontSize: 'var(--text-xs)',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 'var(--weight-semibold)',
                  color: isPositive ? 'var(--positive)' : 'var(--negative)',
                }}
              >
                {isPositive ? '+' : ''}{Number(snapshot.change_percent).toFixed(2)}%
              </div>
            )}
          </div>
        </div>

        {/* User Decision Status Selector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 'var(--weight-medium)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Personal Decision State:
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            {(['WATCHING', 'CONSIDERING', 'RESEARCHING', 'HOLDING'] as DecisionStatus[]).map((st) => {
              const isSelected = item.decisionStatus === st;
              return (
                <button
                  key={st}
                  type="button"
                  onClick={() => handleStatusChange(st)}
                  style={{
                    padding: 'var(--space-1) var(--space-3)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: isSelected ? 'var(--weight-semibold)' : 'var(--weight-regular)',
                    color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                    backgroundColor: isSelected ? 'var(--brand-subtle)' : 'var(--bg-surface-elevated)',
                    border: `1px solid ${isSelected ? 'var(--brand-primary)' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-xs)',
                    cursor: 'pointer',
                  }}
                >
                  {st}
                </button>
              );
            })}
          </div>
        </div>

        {/* Personal Thesis Notes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 'var(--weight-medium)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Personal Investment Thesis & Notes:
            </span>
            {!editingNotes && (
              <button
                type="button"
                onClick={handleStartEdit}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--brand-primary)',
                  fontSize: 'var(--text-xs)',
                  cursor: 'pointer',
                }}
              >
                ✏️ Edit Notes
              </button>
            )}
          </div>

          {editingNotes ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <textarea
                value={notesDraft}
                onChange={(e) => setNotesDraft(e.target.value)}
                placeholder="Enter personal investment thesis or trigger levels..."
                rows={3}
                style={{
                  width: '100%',
                  padding: 'var(--space-2)',
                  fontSize: 'var(--text-xs)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  border: '1px solid var(--brand-primary)',
                  borderRadius: 'var(--radius-xs)',
                  color: 'var(--text-primary)',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
              <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                <Button type="button" variant="primary" size="sm" onClick={handleSaveNotes}>
                  Save Thesis
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditingNotes(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: 'var(--space-2-5) var(--space-3)',
                backgroundColor: 'var(--bg-surface-sunken)',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                fontSize: 'var(--text-xs)',
                color: item.notes ? 'var(--text-primary)' : 'var(--text-muted)',
                fontStyle: item.notes ? 'normal' : 'italic',
                lineHeight: 1.5,
              }}
            >
              {item.notes || 'No personal investment thesis recorded yet. Click edit to add notes.'}
            </div>
          )}
        </div>

        {/* Active Trade Setup & Signals Context */}
        {activeRec && (
          <div
            style={{
              padding: 'var(--space-3)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                Active Strategy Setup ({activeRec.setup_type || 'SWING'})
              </span>
              <Badge variant={activeRec.signal === 'BUY' ? 'positive' : 'negative'} size="sm">
                {activeRec.signal} ({activeRec.confidence} CONFIDENCE)
              </Badge>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)', fontSize: 'var(--text-xs)' }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Entry: </span>
                <strong style={{ fontFamily: 'var(--font-mono)' }}>₹{activeRec.entry_price || '—'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Stop: </span>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--negative)' }}>₹{activeRec.stop_price || '—'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Target: </span>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--positive)' }}>₹{activeRec.target_price || '—'}</strong>
              </div>
            </div>
          </div>
        )}

        {/* Opportunity Score Context */}
        {opportunity && (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            <strong>Opportunity Score: </strong>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 'var(--weight-bold)', color: 'var(--brand-primary)' }}>
              {Number(opportunity.final_score ?? opportunity.final_opportunity_score ?? 0).toFixed(0)}/100
            </span>
            {opportunity.reasons && opportunity.reasons.length > 0 && (
              <span style={{ marginLeft: 'var(--space-2)' }}>({opportunity.reasons[0]})</span>
            )}
          </div>
        )}

        {/* Navigation Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-2)', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                onClose();
                navigate(`/stocks/${symbol}`);
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
                navigate(`/fundamentals?symbol=${symbol}`);
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
                navigate(`/research?symbol=${symbol}`);
              }}
            >
              🤖 AI Research
            </Button>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onRemoveFromList(symbol);
              onClose();
            }}
          >
            🗑️ Remove
          </Button>
        </div>
      </div>
    </Modal>
  );
};
