import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockRecommendation, PaginatedResponse } from '@/lib/api/types';

export function useRecommendations(params: {
  horizon?: string;
  signal?: string;
  setup_type?: string;
  status?: string;
  confidence?: string;
  sector?: string;
  as_of?: string;
  page?: number;
} = {}) {
  return useQuery({
    queryKey: ['recommendations', params],
    queryFn: () => apiClient<PaginatedResponse<StockRecommendation>>(ENDPOINTS.RECOMMENDATIONS, {
      params,
    }),
  });
}

export function useRecommendationDetail(id: string) {
  return useQuery({
    queryKey: ['recommendation', id],
    queryFn: () => apiClient<StockRecommendation>(ENDPOINTS.RECOMMENDATION_DETAIL(id)),
    enabled: Boolean(id),
  });
}
