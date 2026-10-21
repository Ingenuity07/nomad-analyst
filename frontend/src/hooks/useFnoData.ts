/**
 * Nomad Analyst — F&O Laboratory React Query Hooks
 * Read-only queries for F&O Overview, Strategy, Paper Trades, and Diagnostics.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import {
  FnoOverviewResponse,
  FnoStrategyResponse,
  FnoTradesResponse,
  FnoDiagnosticsResponse,
} from '@/lib/api/types';

export function useFnoOverview() {
  return useQuery({
    queryKey: ['fno', 'overview'],
    queryFn: () => apiClient<FnoOverviewResponse>(ENDPOINTS.FNO_OVERVIEW),
    refetchInterval: 3000, // 3-second cadence for quote snapshots and feed freshness
    staleTime: 2000,
  });
}

export function useFnoStrategy() {
  return useQuery({
    queryKey: ['fno', 'strategy'],
    queryFn: () => apiClient<FnoStrategyResponse>(ENDPOINTS.FNO_STRATEGY),
    refetchInterval: 5000, // 5-second cadence for breakout signals and opening range
    staleTime: 3000,
  });
}

export function useFnoTrades() {
  return useQuery({
    queryKey: ['fno', 'trades'],
    queryFn: () => apiClient<FnoTradesResponse>(ENDPOINTS.FNO_TRADES),
    refetchInterval: 5000, // 5-second cadence for paper ledger and fills
    staleTime: 3000,
  });
}

export function useFnoDiagnostics() {
  return useQuery({
    queryKey: ['fno', 'diagnostics'],
    queryFn: () => apiClient<FnoDiagnosticsResponse>(ENDPOINTS.FNO_DIAGNOSTICS),
    refetchInterval: 10000, // 10-second cadence for feed completeness and daemon status
    staleTime: 5000,
  });
}
