import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StockFundamentalsResponse } from '@/lib/api/types';

export function useStockFundamentals(symbol: string) {
  return useQuery({
    queryKey: ['stock', symbol, 'fundamentals'],
    queryFn: () => apiClient<StockFundamentalsResponse>(ENDPOINTS.STOCK_FUNDAMENTALS(symbol)),
    enabled: Boolean(symbol),
    staleTime: 5 * 60 * 1000, // Fundamentals don't change intra-day
  });
}
