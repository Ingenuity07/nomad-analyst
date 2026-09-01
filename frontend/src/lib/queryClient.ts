import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds default freshness
      gcTime: 5 * 60 * 1000, // 5 minutes cache retention
      retry: (failureCount, error: any) => {
        // Do not retry 404s or 400s
        if (error?.status === 404 || error?.status === 400) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false, // Prevent unwanted refetches
    },
  },
});
