import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { AppShell } from '@/components/layout/AppShell';

import { MarketPage } from '@/pages/MarketPage';
import { IntradayPage } from '@/pages/IntradayPage';
import { DeliveryPage } from '@/pages/DeliveryPage';
import { StocksPageShell } from '@/pages/StocksPageShell';
import { StockDetailPage } from '@/pages/StockDetailPage';
import { RecommendationsPage } from '@/pages/RecommendationsPage';
import { ResearchPage } from '@/pages/ResearchPage';
import { FundamentalsPage } from '@/pages/FundamentalsPage';
import { BacktestsPage } from '@/pages/BacktestsPage';
import { WatchlistPageShell } from '@/pages/WatchlistPageShell';
import { DesignSystemShowcase } from '@/pages/DesignSystemShowcase';

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<Navigate to="/market" replace />} />
            <Route path="market" element={<MarketPage />} />
            <Route path="intraday" element={<IntradayPage />} />
            <Route path="delivery" element={<DeliveryPage />} />
            <Route path="stocks" element={<StocksPageShell />} />
            <Route path="stocks/:symbol" element={<StockDetailPage />} />
            <Route path="fundamentals" element={<FundamentalsPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="research" element={<ResearchPage />} />
            <Route path="backtests" element={<BacktestsPage />} />
            <Route path="watchlist" element={<WatchlistPageShell />} />
            <Route path="design-system" element={<DesignSystemShowcase />} />
            <Route path="*" element={<Navigate to="/market" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
export default App;
