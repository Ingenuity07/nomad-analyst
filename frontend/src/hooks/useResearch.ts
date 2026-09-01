import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { ResearchRequestPayload, ResearchReportResponse } from '@/lib/api/types';

export function useResearch() {
  return useMutation({
    mutationFn: (payload: ResearchRequestPayload) =>
      apiClient<ResearchReportResponse>(ENDPOINTS.RESEARCH, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  });
}
