import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { IntradayOverviewResponse } from '@/lib/api/types';

export function useIntradayOverview() {
  return useQuery({
    queryKey: ['intraday', 'overview'],
    queryFn: () => apiClient<IntradayOverviewResponse>(ENDPOINTS.INTRADAY_OVERVIEW),
    refetchInterval: 15 * 1000, // 15-second refresh during market
  });
}
