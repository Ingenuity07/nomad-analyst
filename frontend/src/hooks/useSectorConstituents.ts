import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { PaginatedResponse, StockSummary } from '@/lib/api/types';

export function useSectorConstituents(sector: string, page = 1) {
  return useQuery({
    queryKey: ['stocks', 'sector', sector, page],
    queryFn: () =>
      apiClient<PaginatedResponse<StockSummary>>(ENDPOINTS.STOCKS, {
        params: { sector, page },
      }),
    enabled: Boolean(sector),
    staleTime: 5 * 60 * 1000,
  });
}
