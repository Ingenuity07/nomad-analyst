import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { ResearchRequestPayload, ResearchReportResponse } from '@/lib/api/types';

import { ResearchConsole } from '@/features/research/components/ResearchConsole';
import { ResearchReportHeader } from '@/features/research/components/ResearchReportHeader';
import { ResearchSummaryCard } from '@/features/research/components/ResearchSummaryCard';
import { FactorIntelligenceMatrix } from '@/features/research/components/FactorIntelligenceMatrix';
import { DeepAnalysisSections } from '@/features/research/components/DeepAnalysisSections';
import { EvidenceDrawer } from '@/features/research/components/EvidenceDrawer';
import { SessionResearchHistory, HistoryItem } from '@/features/research/components/SessionResearchHistory';
import { ResearchDisclaimer } from '@/features/research/components/ResearchDisclaimer';

export const ResearchPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const initialSymbol = searchParams.get('symbol') || 'RELIANCE';

  // Research State
  const [activeReport, setActiveReport] = useState<ResearchReportResponse | null>(null);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  // Evidence Drawer & History State
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState<boolean>(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Timer Ref
  const timerRef = useRef<any>(null);

  useEffect(() => {
    if (isLoading) {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isLoading]);

  const handleRunResearch = async (payload: ResearchRequestPayload) => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await apiClient<ResearchReportResponse>(ENDPOINTS.RESEARCH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const reportId = `report-${Date.now()}`;
      setActiveReport(res);
      setActiveReportId(reportId);

      // Add to session history
      const historyEntry: HistoryItem = {
        id: reportId,
        report: res,
        question: payload.question || 'Equity Synthesis Report',
        depth: payload.depth,
      };

      setHistory((prev) => [historyEntry, ...prev.slice(0, 9)]);
    } catch (err: any) {
      setError(err?.message || 'Failed to complete AI research synthesis.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectHistoryItem = (item: HistoryItem) => {
    setActiveReport(item.report);
    setActiveReportId(item.id);
    setError(null);
  };

  const handleNewInquiry = () => {
    setActiveReport(null);
    setActiveReportId(null);
    setError(null);
  };

  const handleClearHistory = () => {
    setHistory([]);
  };

  return (
    <PageContainer
      title="Equity Intelligence & Research Laboratory"
      subtitle="Deterministic financial tool routing powered by Google Gemini and Claude 3.5 Sonnet."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* Research Input Console */}
        <section aria-label="Research Console">
          <ResearchConsole
            initialSymbol={initialSymbol}
            onSubmit={handleRunResearch}
            isLoading={isLoading}
            elapsedSeconds={elapsedSeconds}
          />
        </section>

        {/* Error State */}
        {error && (
          <ErrorState
            title="Research Execution Failed"
            message={error}
            onRetry={() => setError(null)}
          />
        )}

        {/* Active Synthesized Report */}
        {activeReport ? (
          <div data-testid="research-report-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
            {/* Header */}
            <section aria-label="Report Header">
              <ResearchReportHeader
                report={activeReport}
                onOpenEvidence={() => setIsEvidenceDrawerOpen(true)}
                onNewInquiry={handleNewInquiry}
              />
            </section>

            {/* Executive Summary */}
            <section aria-label="Executive Summary">
              <ResearchSummaryCard
                summary={activeReport.summary}
                marketSnapshot={activeReport.market_snapshot}
              />
            </section>

            {/* Factor Intelligence Matrix */}
            <section aria-label="Factor Intelligence Matrix">
              <FactorIntelligenceMatrix
                positiveFactors={activeReport.positive_factors}
                risks={activeReport.risks}
                contradictions={activeReport.contradictions}
                unknowns={activeReport.unknowns}
              />
            </section>

            {/* Deep Domain Analysis (Technicals, Fundamentals, News) */}
            <section aria-label="Domain Analysis">
              <DeepAnalysisSections
                technicalAnalysis={activeReport.technical_analysis}
                fundamentalAnalysis={activeReport.fundamental_analysis}
                newsAnalysis={activeReport.news_analysis}
              />
            </section>

            {/* Evidence Drawer */}
            <EvidenceDrawer
              isOpen={isEvidenceDrawerOpen}
              onClose={() => setIsEvidenceDrawerOpen(false)}
              evidence={activeReport.evidence || []}
              companyName={activeReport.company || activeReport.instrument}
              symbol={activeReport.instrument}
              asOf={activeReport.as_of}
            />
          </div>
        ) : !isLoading && !error ? (
          <EmptyState
            title="No Research Synthesis Generated Yet"
            description="Select an Indian stock symbol above, specify an analytical question or thesis, and run the multi-tool research analysis."
          />
        ) : null}

        {/* Session Research History */}
        <section aria-label="Session History">
          <SessionResearchHistory
            history={history}
            selectedId={activeReportId}
            onSelect={handleSelectHistoryItem}
            onClear={handleClearHistory}
          />
        </section>

        {/* Persistent Legal & Non-Advisory Notice */}
        <section aria-label="Disclaimer">
          <ResearchDisclaimer />
        </section>
      </div>
    </PageContainer>
  );
};
export default ResearchPage;

