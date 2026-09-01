import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';

export interface DeepAnalysisSectionsProps {
  technicalAnalysis?: string;
  fundamentalAnalysis?: string;
  newsAnalysis?: string;
}

export const DeepAnalysisSections: React.FC<DeepAnalysisSectionsProps> = ({
  technicalAnalysis = '',
  fundamentalAnalysis = '',
  newsAnalysis = '',
}) => {
  const [activeTab, setActiveTab] = useState<string>('all');

  const tabs = [
    { key: 'all', label: 'All Analytical Dimensions' },
    { key: 'technical', label: 'Technical & Trends' },
    { key: 'fundamental', label: 'Financials & Valuation' },
    { key: 'news', label: 'News & Events' },
  ];

  return (
    <Card header="Domain Intelligence Analysis" data-testid="deep-analysis-sections">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Tabs tabs={tabs} activeKey={activeTab} onChange={setActiveTab} />

        {/* Section 1: Technicals */}
        {(activeTab === 'all' || activeTab === 'technical') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              📈 Technical & Price Action Structure
            </div>
            <div
              data-testid="technical-analysis-text"
              style={{
                fontSize: 'var(--text-sm)',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
                backgroundColor: 'var(--bg-surface-sunken)',
                padding: 'var(--space-3) var(--space-4)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {technicalAnalysis || 'No technical analysis generated for this asset.'}
            </div>
          </div>
        )}

        {/* Section 2: Fundamentals */}
        {(activeTab === 'all' || activeTab === 'fundamental') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              📊 Fundamental, Statement & Margin Trends
            </div>
            <div
              data-testid="fundamental-analysis-text"
              style={{
                fontSize: 'var(--text-sm)',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
                backgroundColor: 'var(--bg-surface-sunken)',
                padding: 'var(--space-3) var(--space-4)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {fundamentalAnalysis || 'No fundamental analysis available for this asset.'}
            </div>
          </div>
        )}

        {/* Section 3: News & Catalysts */}
        {(activeTab === 'all' || activeTab === 'news') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              📰 News Headlines & Corporate Disclosures Impact
            </div>
            <div
              data-testid="news-analysis-text"
              style={{
                fontSize: 'var(--text-sm)',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
                backgroundColor: 'var(--bg-surface-sunken)',
                padding: 'var(--space-3) var(--space-4)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {newsAnalysis || 'No material corporate news impact recorded.'}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};
