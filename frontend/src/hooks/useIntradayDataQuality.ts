import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { IntradayReadinessResponse } from '@/lib/api/types';

export function useIntradayDataQuality(symbol: string, timeframe = '5m') {
  return useQuery({
    queryKey: ['intraday', 'quality', symbol, timeframe],
    queryFn: () => apiClient<IntradayReadinessResponse>(ENDPOINTS.INTRADAY_DATA_QUALITY, {
      params: { symbol, timeframe },
    }),
    enabled: Boolean(symbol),
  });
}
