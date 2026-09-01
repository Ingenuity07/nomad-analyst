import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { StrategyItem, StrategyPerformanceResponse } from '@/lib/api/types';

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient<{ strategies: StrategyItem[] }>(ENDPOINTS.STRATEGIES),
  });
}

export function useStrategyPerformance(strategy: string) {
  return useQuery({
    queryKey: ['strategy', strategy, 'performance'],
    queryFn: () => apiClient<StrategyPerformanceResponse>(ENDPOINTS.STRATEGY_PERFORMANCE(strategy)),
    enabled: Boolean(strategy),
  });
}
