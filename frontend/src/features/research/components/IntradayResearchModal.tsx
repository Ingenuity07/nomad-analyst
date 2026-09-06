import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import {
  useExamineStock,
  useRefreshResearchRun,
  useResearchDelta
} from '@/hooks/useOnDemandResearch';
import { ExamineResponse, ResearchRunItem, ResearchDeltaItem } from '@/lib/api/types';

export interface IntradayResearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string | null;
  mode?: 'INTRADAY' | 'LONG_TERM' | 'GENERAL';
}

export const IntradayResearchModal: React.FC<IntradayResearchModalProps> = ({
  isOpen,
  onClose,
  symbol,
  mode = 'INTRADAY',
}) => {
  const [data, setData] = useState<ExamineResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const examineMutation = useExamineStock();
  const refreshMutation = useRefreshResearchRun();

  // Polling delta in background with ZERO LLM calls
  const researchId = data?.research?.id || null;
  const { data: liveDelta } = useResearchDelta(researchId, 10000);

  const delta: ResearchDeltaItem | null = liveDelta || data?.delta || null;
  const research: ResearchRunItem | null = data?.research || null;

  useEffect(() => {
    if (isOpen && symbol) {
      setData(null);
      setErrorMsg(null);
      examineMutation.mutate(
        { symbol, mode, force_refresh: false },
        {
          onSuccess: (res) => {
            setData(res);
          },
          onError: (err) => {
            setErrorMsg(err.message || 'Failed to complete stock examination.');
          },
        }
      );
    }
  }, [isOpen, symbol, mode]);

  const handleRefresh = () => {
    if (!research?.id) return;
    refreshMutation.mutate(research.id, {
      onSuccess: (res) => {
        setData(res);
      },
      onError: (err) => {
        setErrorMsg(err.message || 'Failed to refresh research.');
      },
    });
  };

  const isLoading = examineMutation.isPending || refreshMutation.isPending;
  const output = research?.output;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="840px"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span>AI Research Engine: <strong>{symbol}</strong></span>
          <Badge variant="brand">{mode}</Badge>
          {research?.status && (
            <Badge variant={research.status === 'completed' ? 'positive' : research.status === 'failed' ? 'negative' : 'neutral'}>
              {research.status.toUpperCase()}
            </Badge>
          )}
          {data?.reused && (
            <Badge variant="neutral">Cached (0 AI Calls)</Badge>
          )}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Loading State */}
        {isLoading && (
          <div style={{ padding: 'var(--space-8)', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-3)' }}>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              Gathering deterministic evidence & synthesizing AI report...
            </div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Collecting orderbook VWAP, momentum, relative strength, sector rotation, and market context into 1 complete request.
            </span>
          </div>
        )}

        {/* Error State */}
        {errorMsg && !isLoading && (
          <div style={{ padding: 'var(--space-4)', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--negative)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontWeight: 'var(--weight-bold)', color: 'var(--negative)', fontSize: 'var(--text-sm)' }}>
              Research Execution Error
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '4px' }}>
              {errorMsg}
            </div>
            <Button
              variant="outline"
              size="sm"
              style={{ marginTop: 'var(--space-3)' }}
              onClick={() => symbol && examineMutation.mutate({ symbol, mode, force_refresh: true })}
            >
              Retry Examination
            </Button>
          </div>
        )}

        {/* Content View */}
        {!isLoading && research && output && (
          <>
            {/* 1. Basis & Live Changes Since Analysis (Delta) */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 'var(--space-3)',
              backgroundColor: 'var(--bg-secondary, rgba(255,255,255,0.03))',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)'
            }}>
              {/* Research Basis */}
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Research Basis (Snapshot)
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.6 }}>
                  <div>Score: <strong>{research.basis?.score?.toFixed(1) ?? '-'}</strong> | Rank: <strong>#{research.basis?.rank ?? '-'}</strong></div>
                  <div>State: <strong>{research.basis?.state ?? '-'}</strong> | Regime: <strong>{research.basis?.market_regime ?? '-'}</strong></div>
                  <div>Sector: <strong>{research.basis?.sector_name ?? '-'}</strong> (Rank #{research.basis?.sector_rank ?? '-'})</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                    Analyzed: {research.started_at ? new Date(research.started_at).toLocaleTimeString() : '-'}
                  </div>
                </div>
              </div>

              {/* Real-Time Delta */}
              {delta && (
                <div style={{ borderLeft: '1px solid var(--border-subtle)', paddingLeft: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Changes Since Analysis (Delta)
                    </span>
                    <Badge variant={delta.freshness === 'FRESH' ? 'positive' : delta.freshness === 'AGING' ? 'warning' : 'negative'}>
                      {delta.freshness}
                    </Badge>
                  </div>

                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.6 }}>
                    <div>
                      Current Score: <strong>{delta.current?.score?.toFixed(1) ?? '-'}</strong>
                      {delta.deltas?.score_change !== 0 && (
                        <span style={{ marginLeft: '4px', color: delta.deltas?.score_change > 0 ? 'var(--positive)' : 'var(--negative)' }}>
                          ({delta.deltas?.score_change > 0 ? `+${delta.deltas?.score_change}` : delta.deltas?.score_change})
                        </span>
                      )}
                      {' '}| Rank: <strong>#{delta.current?.rank ?? '-'}</strong>
                    </div>

                    {delta.staleness_reasons && delta.staleness_reasons.length > 0 ? (
                      <ul style={{ margin: '4px 0 0 0', paddingLeft: 'var(--space-3)', color: 'var(--warning)', fontSize: '11px' }}>
                        {delta.staleness_reasons.map((r, idx) => <li key={idx}>{r}</li>)}
                      </ul>
                    ) : (
                      <span style={{ color: 'var(--positive)', fontSize: '11px' }}>
                        ✓ Market conditions align with analysis snapshot.
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Refresh Action Banner */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'var(--bg-surface-sunken)',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 'var(--text-xs)'
            }}>
              <span style={{ color: 'var(--text-muted)' }}>
                Viewing saved research. 0 LLM calls consumed on open.
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isLoading}
              >
                Refresh Research (1 AI Call)
              </Button>
            </div>

            {/* 2. Executive Summary & Thesis */}
            <Card style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)' }}>
                  Executive Research Synthesis
                </h4>
                <div style={{ display: 'flex', gap: 'var(--space-1-5)' }}>
                  <Badge variant="brand">Confidence: {output.research_confidence}</Badge>
                  <Badge variant="positive">Thesis: {output.thesis_strength}</Badge>
                </div>
              </div>

              <div style={{ fontSize: 'var(--text-sm)', lineHeight: 1.6, color: 'var(--text-primary)' }}>
                {output.summary}
              </div>

              {output.thesis && (
                <div style={{
                  padding: 'var(--space-3)',
                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                  borderLeft: '3px solid var(--brand-primary)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--text-primary)'
                }}>
                  <strong>Central Thesis:</strong> {output.thesis}
                </div>
              )}
            </Card>

            {/* 3. Observed Facts vs Analyst Interpretation */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-3)' }}>
              {/* Observed Facts */}
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  📊 Verified Empirical Facts
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.observed_facts?.map((fact, idx) => (
                    <li key={idx}>{fact}</li>
                  ))}
                </ul>
              </Card>

              {/* Analyst Interpretation */}
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--brand-primary)' }}>
                  💡 Analyst Reasoning & Dynamics
                </h5>
                <div style={{ fontSize: 'var(--text-xs)', lineHeight: 1.6, color: 'var(--text-primary)' }}>
                  {output.analyst_interpretation}
                </div>
              </Card>
            </div>

            {/* 4. Supporting vs Contradicting Evidence */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-3)' }}>
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--positive)' }}>
                  ✓ Supporting Evidence & Drivers
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.supporting_evidence?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </Card>

              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--warning)' }}>
                  ⚠ Contradicting Signals & Divergences
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.contradicting_evidence?.length > 0 ? (
                    output.contradicting_evidence.map((item, idx) => <li key={idx}>{item}</li>)
                  ) : (
                    <li style={{ color: 'var(--text-muted)' }}>No material contradictory signals detected.</li>
                  )}
                </ul>
              </Card>
            </div>

            {/* 5. Market & Sector Context Interpretation */}
            {(output.market_context_interpretation || output.sector_context_interpretation) && (
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                  🌐 Market & Sector Rotation Context
                </h5>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  {output.market_context_interpretation && (
                    <div><strong>Market Context:</strong> {output.market_context_interpretation}</div>
                  )}
                  {output.sector_context_interpretation && (
                    <div><strong>Sector Rotation:</strong> {output.sector_context_interpretation}</div>
                  )}
                </div>
              </Card>
            )}

            {/* 6. What to Monitor & Invalidation Developments */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-3)' }}>
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--brand-primary)' }}>
                  🔍 What to Monitor Next
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.what_to_monitor?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </Card>

              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--negative)' }}>
                  ⛔ Thesis Invalidation Developments
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.invalidating_developments?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </Card>
            </div>

            {/* 7. Key Risks & Known Unknowns */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-3)' }}>
              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--negative)' }}>
                  Risk Factors
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.key_risks?.map((r, idx) => <li key={idx}>{r}</li>)}
                </ul>
              </Card>

              <Card style={{ padding: 'var(--space-3)' }}>
                <h5 style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  Data Gaps & Unknowns
                </h5>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {output.unknowns?.map((u, idx) => <li key={idx}>{u}</li>)}
                </ul>
              </Card>
            </div>

            {/* Telemetry Strip */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '10px',
              color: 'var(--text-muted)',
              borderTop: '1px solid var(--border-subtle)',
              paddingTop: 'var(--space-2)'
            }}>
              <span>Model: <strong>{research.model_name || 'N/A'}</strong> ({research.provider || 'default'})</span>
              <span>Tokens: <strong>{research.tokens_used}</strong></span>
              <span>Duration: <strong>{research.duration_ms}ms</strong></span>
              <span>Hash: <code style={{ fontSize: '9px' }}>{research.evidence_hash?.substring(0, 12)}...</code></span>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
