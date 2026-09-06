import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import {
  IntradayMarketContextResponse,
  IntradayStocksResponse,
} from '@/lib/api/types';

export function useIntradayMarketContext() {
  return useQuery<IntradayMarketContextResponse>({
    queryKey: ['intraday', 'market-context'],
    queryFn: () => apiClient<IntradayMarketContextResponse>('/api/v1/intraday/market-context/'),
    refetchInterval: 5000,
    staleTime: 3000,
  });
}

export function useIntradayStocks(filters?: {
  sector?: string;
  volume_confirmation?: string;
  search?: string;
  sort_by?: string;
  order?: 'asc' | 'desc';
}) {
  const params = new URLSearchParams();
  if (filters?.sector) params.append('sector', filters.sector);
  if (filters?.volume_confirmation) params.append('volume_confirmation', filters.volume_confirmation);
  if (filters?.search) params.append('search', filters.search);
  if (filters?.sort_by) params.append('sort_by', filters.sort_by);
  if (filters?.order) params.append('order', filters.order);

  const url = `/api/v1/intraday/stocks/${params.toString() ? `?${params.toString()}` : ''}`;

  return useQuery<IntradayStocksResponse>({
    queryKey: ['intraday', 'stocks', filters],
    queryFn: () => apiClient<IntradayStocksResponse>(url),
    refetchInterval: 5000,
    staleTime: 3000,
  });
}

export function useIntradayWebSocket() {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessageAt, setLastMessageAt] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    // Port 8000 for backend ASGI Channels server
    const port = '8000';
    const wsUrl = `${protocol}//${host}:${port}/ws/intraday/`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onclose = () => {
        setIsConnected(false);
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setLastMessageAt(new Date());

          if (payload.type === 'market_context_init' || payload.type === 'market_context_update') {
            queryClient.setQueryData(['intraday', 'market-context'], (prev: any) => ({
              ...prev,
              ...payload.data,
            }));
          } else if (payload.type === 'stock_context_update') {
            queryClient.setQueryData(['intraday', 'stocks'], (prev: any) => ({
              ...prev,
              stocks: payload.data.stocks,
              as_of: payload.data.as_of,
            }));
          }
        } catch (err) {
          console.debug('Failed to parse WS message:', err);
        }
      };
    } catch (err) {
      console.debug('WebSocket connection could not be established:', err);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [queryClient]);

  return { isConnected, lastMessageAt };
}
