import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { IntradayOpportunityResponse, IntradayOpportunityItem } from '@/lib/api/types';

export interface UseIntradayOpportunitiesParams {
  limit?: number;
  sector?: string;
  opportunity_type?: string;
  state?: string;
  min_score?: number;
  mode?: 'RAW_RANKING' | 'SECTOR_DIVERSIFIED';
}

export function useIntradayOpportunities(params: UseIntradayOpportunitiesParams = {}) {
  const queryKey = ['intraday-opportunities', params];

  return useQuery<IntradayOpportunityResponse>({
    queryKey,
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params.limit) searchParams.set('limit', String(params.limit));
      if (params.sector) searchParams.set('sector', params.sector);
      if (params.opportunity_type) searchParams.set('opportunity_type', params.opportunity_type);
      if (params.state) searchParams.set('state', params.state);
      if (params.min_score !== undefined) searchParams.set('min_score', String(params.min_score));
      if (params.mode) searchParams.set('mode', params.mode);

      const qs = searchParams.toString();
      const url = `/api/v1/intraday/opportunities/${qs ? `?${qs}` : ''}`;
      return apiClient<IntradayOpportunityResponse>(url);
    },
    refetchInterval: 5000,
    staleTime: 3000,
  });
}

export function useIntradayOpportunityDetail(symbol: string | null) {
  return useQuery<{
    symbol: string;
    eligible: boolean;
    opportunity?: IntradayOpportunityItem;
    exclusion_reason?: string;
    market_context?: any;
  }>({
    queryKey: ['intraday-opportunity-detail', symbol],
    queryFn: async () => {
      if (!symbol) throw new Error('Symbol is required');
      return apiClient<{
        symbol: string;
        eligible: boolean;
        opportunity?: IntradayOpportunityItem;
        exclusion_reason?: string;
        market_context?: any;
      }>(`/api/v1/intraday/opportunities/${symbol}/`);
    },
    enabled: Boolean(symbol),
    staleTime: 3000,
  });
}
