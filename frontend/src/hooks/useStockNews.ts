import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { NewsItem, PaginatedResponse } from '@/lib/api/types';

export function useStockNews(symbol: string, limit = 20) {
  return useQuery({
    queryKey: ['stock', symbol, 'news', limit],
    queryFn: () => apiClient<PaginatedResponse<NewsItem>>(ENDPOINTS.STOCK_NEWS(symbol), {
      params: { page_size: limit },
    }),
    enabled: Boolean(symbol),
  });
}
