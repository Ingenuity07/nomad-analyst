import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockOpportunitySnapshot, PaginatedResponse } from '@/lib/api/types';

export function useOpportunities(params: {
  universe?: string;
  horizon?: string;
  sector?: string;
  min_score?: number;
  as_of?: string;
  page?: number;
} = {}) {
  return useQuery({
    queryKey: ['opportunities', params],
    queryFn: () => apiClient<PaginatedResponse<StockOpportunitySnapshot>>(ENDPOINTS.OPPORTUNITIES, {
      params,
    }),
  });
}
