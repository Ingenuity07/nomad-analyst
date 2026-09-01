import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { MarketOverviewResponse } from '@/lib/api/types';

export function useMarketOverview(universe = 'NIFTY50', asOf?: string) {
  return useQuery({
    queryKey: ['market', 'overview', universe, asOf],
    queryFn: () => apiClient<MarketOverviewResponse>(ENDPOINTS.MARKET_OVERVIEW, {
      params: { universe, as_of: asOf },
    }),
  });
}
