import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockRecommendation, PaginatedResponse } from '@/lib/api/types';

export function useIntradayRecommendations(params: {
  timeframe?: string;
  signal?: string;
  status?: string;
  setup_type?: string;
} = {}) {
  return useQuery({
    queryKey: ['intraday', 'recommendations', params],
    queryFn: () => apiClient<PaginatedResponse<StockRecommendation>>(ENDPOINTS.INTRADAY_RECOMMENDATIONS, {
      params,
    }),
    refetchInterval: 15 * 1000,
  });
}
