import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { RecommendationOutcome, PaginatedResponse } from '@/lib/api/types';

export function useOutcomes(params: {
  signal?: string;
  setup_type?: string;
  exit_reason?: string;
  page?: number;
} = {}) {
  return useQuery({
    queryKey: ['outcomes', params],
    queryFn: () => apiClient<PaginatedResponse<RecommendationOutcome>>(ENDPOINTS.OUTCOMES, {
      params,
    }),
  });
}

export function useRecommendationOutcome(recommendationId: string | null) {
  return useQuery({
    queryKey: ['recommendation', recommendationId, 'outcome'],
    queryFn: () => apiClient<RecommendationOutcome>(ENDPOINTS.RECOMMENDATION_OUTCOME(recommendationId!)),
    enabled: Boolean(recommendationId),
  });
}
