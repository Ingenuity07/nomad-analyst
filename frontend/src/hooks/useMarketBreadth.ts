import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { MarketBreadth } from '@/lib/api/types';

export function useMarketBreadth(universe = 'NIFTY50', asOf?: string) {
  return useQuery({
    queryKey: ['market', 'breadth', universe, asOf],
    queryFn: () =>
      apiClient<{ universe: string; breadth: MarketBreadth; as_of: string }>(ENDPOINTS.MARKET_BREADTH, {
        params: { universe, as_of: asOf },
      }),
  });
}
