import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockDetailResponse, PaginatedResponse, InstrumentSearchResult } from '@/lib/api/types';

export function useStock(symbol: string, asOf?: string) {
  return useQuery({
    queryKey: ['stock', symbol, asOf],
    queryFn: () => apiClient<StockDetailResponse>(ENDPOINTS.STOCK_DETAIL(symbol), {
      params: { as_of: asOf },
    }),
    enabled: Boolean(symbol),
  });
}

export function useStockSearch(query: string) {
  return useQuery({
    queryKey: ['stock', 'search', query],
    queryFn: () => apiClient<PaginatedResponse<InstrumentSearchResult>>(ENDPOINTS.STOCK_SEARCH, {
      params: { q: query },
    }),
    enabled: query.length >= 2,
    staleTime: 60 * 1000,
  });
}
