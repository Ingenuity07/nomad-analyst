import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockTechnicalsResponse } from '@/lib/api/types';

export function useStockTechnicals(symbol: string, timeframe = '1d', asOf?: string) {
  return useQuery({
    queryKey: ['stock', symbol, 'technicals', timeframe, asOf],
    queryFn: () => apiClient<StockTechnicalsResponse>(ENDPOINTS.STOCK_TECHNICALS(symbol), {
      params: { timeframe, as_of: asOf },
    }),
    enabled: Boolean(symbol),
  });
}
