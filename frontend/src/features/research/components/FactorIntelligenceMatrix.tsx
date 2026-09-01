import React from 'react';
import { Card } from '@/components/ui/Card';

export interface FactorIntelligenceMatrixProps {
  positiveFactors?: string[];
  risks?: string[];
  contradictions?: string[];
  unknowns?: string[];
}

export const FactorIntelligenceMatrix: React.FC<FactorIntelligenceMatrixProps> = ({
  positiveFactors = [],
  risks = [],
  contradictions = [],
  unknowns = [],
}) => {
  const hasContent = positiveFactors.length > 0 || risks.length > 0 || contradictions.length > 0 || unknowns.length > 0;

  if (!hasContent) return null;

  return (
    <div
      data-testid="factor-intelligence-matrix"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 'var(--space-4)',
      }}
    >
      {/* 1. Positive Factors */}
      <Card
        header={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--positive)' }}>▲</span>
            <span>Positive Catalysts & Drivers ({positiveFactors.length})</span>
          </div>
        }
      >
        {positiveFactors.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No positive drivers identified.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {positiveFactors.map((item, idx) => (
              <li key={idx} style={{ lineHeight: 1.5 }}>
                {item}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* 2. Key Risks */}
      <Card
        header={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--negative)' }}>▼</span>
            <span>Key Risk Factors & Headwinds ({risks.length})</span>
          </div>
        }
      >
        {risks.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No critical risks identified.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {risks.map((item, idx) => (
              <li key={idx} style={{ lineHeight: 1.5 }}>
                {item}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* 3. Contradictions & Divergences */}
      <Card
        header={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--warning)' }}>⚡</span>
            <span>Contradictions & Mixed Signals ({contradictions.length})</span>
          </div>
        }
      >
        {contradictions.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No conflicting signals observed.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {contradictions.map((item, idx) => (
              <li key={idx} style={{ lineHeight: 1.5 }}>
                {item}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* 4. Unknowns & Data Limitations */}
      <Card
        header={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--text-muted)' }}>❓</span>
            <span>Data Limitations & Unknowns ({unknowns.length})</span>
          </div>
        }
      >
        {unknowns.length === 0 ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No major data gaps recorded.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)', fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
            {unknowns.map((item, idx) => (
              <li key={idx} style={{ lineHeight: 1.5 }}>
                {item}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
};
