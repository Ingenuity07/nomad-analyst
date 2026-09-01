import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { AppShell } from '@/components/layout/AppShell';

import { MarketPage } from '@/pages/MarketPage';
import { IntradayPage } from '@/pages/IntradayPage';
import { DeliveryPage } from '@/pages/DeliveryPage';
import { StocksPageShell } from '@/pages/StocksPageShell';
import { StockDetailPageShell } from '@/pages/StockDetailPageShell';
import { RecommendationsPageShell } from '@/pages/RecommendationsPageShell';
import { ResearchPageShell } from '@/pages/ResearchPageShell';
import { BacktestsPageShell } from '@/pages/BacktestsPageShell';
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
            <Route path="stocks/:symbol" element={<StockDetailPageShell />} />
            <Route path="recommendations" element={<RecommendationsPageShell />} />
            <Route path="research" element={<ResearchPageShell />} />
            <Route path="backtests" element={<BacktestsPageShell />} />
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
