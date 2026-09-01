import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';

export function useMarketRegime(universe = 'NIFTY50', asOf?: string) {
  return useQuery({
    queryKey: ['market', 'regime', universe, asOf],
    queryFn: () => apiClient<any>(ENDPOINTS.MARKET_REGIME, {
      params: { universe, as_of: asOf },
    }),
  });
}
