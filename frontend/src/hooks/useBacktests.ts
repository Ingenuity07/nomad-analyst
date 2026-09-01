import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { BacktestRun, BacktestRunPayload, PaginatedResponse } from '@/lib/api/types';

export function useBacktests(page = 1) {
  return useQuery({
    queryKey: ['backtests', page],
    queryFn: () => apiClient<PaginatedResponse<BacktestRun>>(ENDPOINTS.BACKTESTS, {
      params: { page },
    }),
  });
}

export function useBacktestDetail(runId: string) {
  return useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => apiClient<BacktestRun>(ENDPOINTS.BACKTEST_DETAIL(runId)),
    enabled: Boolean(runId),
  });
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: (payload: BacktestRunPayload) =>
      apiClient<BacktestRun>(ENDPOINTS.BACKTEST_RUN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
  });
}
