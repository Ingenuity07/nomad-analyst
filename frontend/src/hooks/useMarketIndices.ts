import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { MarketIndexItem } from '@/lib/api/types';

export function useMarketIndices() {
  return useQuery({
    queryKey: ['market', 'indices'],
    queryFn: () => apiClient<{ indices: MarketIndexItem[]; as_of: string }>(ENDPOINTS.MARKET_INDICES),
  });
}
