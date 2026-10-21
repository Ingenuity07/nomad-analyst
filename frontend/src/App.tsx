import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { AppShell } from '@/components/layout/AppShell';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { PageLoadingFallback } from '@/components/common/PageLoadingFallback';

// Route-level code splitting for major workspace pages
const MarketPage = lazy(() => import('@/pages/MarketPage'));
const MarketIntelligencePage = lazy(() => import('@/pages/MarketIntelligencePage'));
const IntradayPage = lazy(() => import('@/pages/IntradayPage'));
const FnoPage = lazy(() => import('@/pages/FnoPage'));
const DeliveryPage = lazy(() => import('@/pages/DeliveryPage'));
const StocksDirectoryPage = lazy(() => import('@/pages/StocksDirectoryPage'));
const StockDetailPage = lazy(() => import('@/pages/StockDetailPage'));
const FundamentalsPage = lazy(() => import('@/pages/FundamentalsPage'));
const RecommendationsPage = lazy(() => import('@/pages/RecommendationsPage'));
const ResearchPage = lazy(() => import('@/pages/ResearchPage'));
const BacktestsPage = lazy(() => import('@/pages/BacktestsPage'));
const WatchlistPage = lazy(() => import('@/pages/WatchlistPage'));
const AlertsPage = lazy(() => import('@/pages/AlertsPage'));
const DesignSystemShowcase = lazy(() => import('@/pages/DesignSystemShowcase'));

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<Navigate to="/market" replace />} />
              <Route
                path="market"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <MarketPage />
                  </Suspense>
                }
              />
              <Route
                path="market-intelligence"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <MarketIntelligencePage />
                  </Suspense>
                }
              />
              <Route
                path="sectors"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <MarketIntelligencePage />
                  </Suspense>
                }
              />
              <Route
                path="intraday"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <IntradayPage />
                  </Suspense>
                }
              />
              <Route
                path="fno"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <FnoPage />
                  </Suspense>
                }
              />
              <Route
                path="delivery"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <DeliveryPage />
                  </Suspense>
                }
              />
              <Route
                path="stocks"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <StocksDirectoryPage />
                  </Suspense>
                }
              />
              <Route
                path="stocks/:symbol"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <StockDetailPage />
                  </Suspense>
                }
              />
              <Route
                path="fundamentals"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <FundamentalsPage />
                  </Suspense>
                }
              />
              <Route
                path="recommendations"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <RecommendationsPage />
                  </Suspense>
                }
              />
              <Route
                path="research"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <ResearchPage />
                  </Suspense>
                }
              />
              <Route
                path="backtests"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <BacktestsPage />
                  </Suspense>
                }
              />
              <Route
                path="watchlist"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <WatchlistPage />
                  </Suspense>
                }
              />
              <Route
                path="alerts"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <AlertsPage />
                  </Suspense>
                }
              />
              <Route
                path="design-system"
                element={
                  <Suspense fallback={<PageLoadingFallback />}>
                    <DesignSystemShowcase />
                  </Suspense>
                }
              />
              <Route path="*" element={<Navigate to="/market" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
export default App;
