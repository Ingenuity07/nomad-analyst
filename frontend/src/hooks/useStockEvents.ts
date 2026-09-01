import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { CorporateDisclosure, PaginatedResponse } from '@/lib/api/types';

export function useStockEvents(symbol: string, limit = 20) {
  return useQuery({
    queryKey: ['stock', symbol, 'events', limit],
    queryFn: () => apiClient<PaginatedResponse<CorporateDisclosure>>(ENDPOINTS.STOCK_EVENTS(symbol), {
      params: { page_size: limit },
    }),
    enabled: Boolean(symbol),
  });
}
