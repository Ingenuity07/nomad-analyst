import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { KiteStatusResponse, KiteDataHealthResponse } from '@/lib/api/types';

export function useKiteStatus() {
  return useQuery<KiteStatusResponse>({
    queryKey: ['kite', 'status'],
    queryFn: () => apiClient<KiteStatusResponse>('/api/v1/kite/status/'),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'AUTHENTICATING') return 2000;
      return 15000;
    },
    staleTime: 5000,
  });
}

export function useKiteDataHealth() {
  return useQuery<KiteDataHealthResponse>({
    queryKey: ['kite', 'data-health'],
    queryFn: () => apiClient<KiteDataHealthResponse>('/api/v1/kite/data-health/'),
    refetchInterval: 5000,
    staleTime: 3000,
  });
}

export function useKiteDisconnect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient<{ success: boolean; message: string }>('/api/v1/kite/auth/disconnect/', {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kite'] });
    },
  });
}

export async function initiateKiteLogin() {
  try {
    const res = await apiClient<{ login_url: string }>('/api/v1/kite/auth/login/');
    if (res.login_url) {
      window.location.href = res.login_url;
    } else {
      throw new Error('No login URL returned from server.');
    }
  } catch (err) {
    console.error('Failed to initiate Kite login:', err);
    throw err;
  }
}
