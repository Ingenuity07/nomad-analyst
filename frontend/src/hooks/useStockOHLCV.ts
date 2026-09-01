import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockOHLCVResponse } from '@/lib/api/types';

export function useStockOHLCV(symbol: string, timeframe = '1d', limit = 200, startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['stock', symbol, 'ohlcv', timeframe, limit, startDate, endDate],
    queryFn: () => apiClient<StockOHLCVResponse>(ENDPOINTS.STOCK_OHLCV(symbol), {
      params: { timeframe, limit, start_date: startDate, end_date: endDate },
    }),
    enabled: Boolean(symbol),
  });
}
