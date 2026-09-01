import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { SectorRanking } from '@/lib/api/types';

export function useMarketSectors(asOf?: string) {
  return useQuery({
    queryKey: ['market', 'sectors', asOf],
    queryFn: () => apiClient<{ sector_rankings: SectorRanking[]; as_of: string }>(ENDPOINTS.MARKET_SECTORS, {
      params: { as_of: asOf },
    }),
  });
}
