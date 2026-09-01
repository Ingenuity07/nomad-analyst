import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { CrossMarketCues } from '@/lib/api/types';

export function useMarketGlobal(asOf?: string) {
  return useQuery({
    queryKey: ['market', 'global', asOf],
    queryFn: () =>
      apiClient<{ global_cues: CrossMarketCues; as_of: string }>(ENDPOINTS.MARKET_GLOBAL, {
        params: { as_of: asOf },
      }),
  });
}
