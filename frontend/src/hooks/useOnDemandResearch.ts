import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import {
  ExamineResponse,
  ResearchRunItem,
  ResearchDeltaItem
} from '@/lib/api/types';

export interface ExaminePayload {
  symbol: string;
  mode?: 'INTRADAY' | 'LONG_TERM' | 'GENERAL';
  force_refresh?: boolean;
}

export function useExamineStock() {
  const queryClient = useQueryClient();

  return useMutation<ExamineResponse, Error, ExaminePayload>({
    mutationFn: async (payload: ExaminePayload) => {
      return apiClient<ExamineResponse>(ENDPOINTS.RESEARCH_EXAMINE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: payload.symbol,
          mode: payload.mode || 'INTRADAY',
          force_refresh: Boolean(payload.force_refresh)
        })
      });
    },
    onSuccess: (data, variables) => {
      if (data?.research?.id) {
        queryClient.setQueryData(['research-detail', data.research.id], {
          research: data.research,
          delta: data.delta
        });
        queryClient.invalidateQueries({ queryKey: ['company-research', variables.symbol] });
      }
    }
  });
}

export function useRefreshResearchRun() {
  const queryClient = useQueryClient();

  return useMutation<ExamineResponse, Error, string>({
    mutationFn: async (researchId: string) => {
      return apiClient<ExamineResponse>(ENDPOINTS.RESEARCH_REFRESH(researchId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
    },
    onSuccess: (data) => {
      if (data?.research?.id) {
        queryClient.setQueryData(['research-detail', data.research.id], {
          research: data.research,
          delta: data.delta
        });
        queryClient.invalidateQueries({ queryKey: ['company-research', data.research.symbol] });
      }
    }
  });
}

export function useResearchRun(id: string | null) {
  return useQuery<{
    research: ResearchRunItem;
    delta?: ResearchDeltaItem | null;
    zero_llm_call_verified: boolean;
  }>({
    queryKey: ['research-detail', id],
    queryFn: async () => {
      if (!id) throw new Error('Research ID is required');
      return apiClient<{
        research: ResearchRunItem;
        delta?: ResearchDeltaItem | null;
        zero_llm_call_verified: boolean;
      }>(ENDPOINTS.RESEARCH_DETAIL(id));
    },
    enabled: Boolean(id),
    staleTime: 10000,
  });
}

export function useCompanyResearch(symbol: string | null, mode: 'INTRADAY' | 'LONG_TERM' | 'GENERAL' = 'INTRADAY') {
  return useQuery<{
    exists: boolean;
    symbol: string;
    mode: string;
    research?: ResearchRunItem;
    delta?: ResearchDeltaItem | null;
  }>({
    queryKey: ['company-research', symbol, mode],
    queryFn: async () => {
      if (!symbol) throw new Error('Symbol is required');
      return apiClient<{
        exists: boolean;
        symbol: string;
        mode: string;
        research?: ResearchRunItem;
        delta?: ResearchDeltaItem | null;
      }>(ENDPOINTS.RESEARCH_COMPANY(symbol, mode));
    },
    enabled: Boolean(symbol),
    staleTime: 10000,
  });
}

export function useResearchDelta(id: string | null, refetchIntervalMs: number = 10000) {
  return useQuery<ResearchDeltaItem>({
    queryKey: ['research-delta', id],
    queryFn: async () => {
      if (!id) throw new Error('Research ID is required');
      return apiClient<ResearchDeltaItem>(ENDPOINTS.RESEARCH_DELTA(id));
    },
    enabled: Boolean(id),
    refetchInterval: refetchIntervalMs,
    staleTime: 5000,
  });
}
