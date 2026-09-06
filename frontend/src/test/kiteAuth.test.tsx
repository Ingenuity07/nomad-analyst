import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { KiteStatusBadge } from '@/features/kite/components/KiteStatusBadge';
import { KiteDataHealthCard } from '@/features/kite/components/KiteDataHealthCard';
import * as kiteHooks from '@/hooks/useKiteAuth';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('Kite Authentication & Intraday Data Health (Phase 17B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders KiteStatusBadge as Disconnected when unauthenticated', () => {
    vi.spyOn(kiteHooks, 'useKiteStatus').mockReturnValue({
      data: {
        configured: true,
        authenticated: false,
        status: 'AUTHENTICATION_REQUIRED',
        user_id: null,
        user_name: null,
        authenticated_at: null,
        expires_at: null,
        last_error: null,
        login_url: 'https://kite.zerodha.com/connect/login?api_key=test',
        provider: 'kite',
      },
      isLoading: false,
      refetch: vi.fn(),
    } as any);

    render(<KiteStatusBadge />, { wrapper: createWrapper() });
    expect(screen.getByText('Connect Kite')).toBeInTheDocument();
  });

  it('renders KiteStatusBadge as Connected when authenticated', () => {
    vi.spyOn(kiteHooks, 'useKiteStatus').mockReturnValue({
      data: {
        configured: true,
        authenticated: true,
        status: 'CONNECTED',
        user_id: 'AB1234',
        user_name: 'Shivam Singh',
        authenticated_at: '2026-09-04T10:00:00Z',
        expires_at: '2026-09-05T00:30:00Z',
        last_error: null,
        login_url: null,
        provider: 'kite',
      },
      isLoading: false,
      refetch: vi.fn(),
    } as any);

    render(<KiteStatusBadge />, { wrapper: createWrapper() });
    expect(screen.getByText('Kite Connected')).toBeInTheDocument();
  });

  it('renders KiteStatusBadge as Expired when token is expired', () => {
    vi.spyOn(kiteHooks, 'useKiteStatus').mockReturnValue({
      data: {
        configured: true,
        authenticated: false,
        status: 'EXPIRED',
        user_id: 'AB1234',
        user_name: 'Shivam Singh',
        authenticated_at: '2026-09-03T10:00:00Z',
        expires_at: '2026-09-04T00:30:00Z',
        last_error: null,
        login_url: 'https://kite.zerodha.com/connect/login?api_key=test',
        provider: 'kite',
      },
      isLoading: false,
      refetch: vi.fn(),
    } as any);

    render(<KiteStatusBadge />, { wrapper: createWrapper() });
    expect(screen.getByText('Kite Expired')).toBeInTheDocument();
  });

  it('opens KiteAuthModal on badge click', () => {
    vi.spyOn(kiteHooks, 'useKiteStatus').mockReturnValue({
      data: {
        configured: true,
        authenticated: true,
        status: 'CONNECTED',
        user_id: 'AB1234',
        user_name: 'Shivam Singh',
        authenticated_at: '2026-09-04T10:00:00Z',
        expires_at: '2026-09-05T00:30:00Z',
        last_error: null,
        login_url: null,
        provider: 'kite',
      },
      isLoading: false,
      refetch: vi.fn(),
    } as any);

    vi.spyOn(kiteHooks, 'useKiteDataHealth').mockReturnValue({
      data: {
        provider: 'kite',
        authenticated: true,
        connection_status: 'CONNECTED',
        market_session: 'CLOSED',
        is_market_open: false,
        data_status: 'MARKET CLOSED',
        subscribed_instruments_count: 52,
        last_tick: null,
        last_snapshot_timestamp: null,
        as_of: '2026-09-04T22:00:00Z',
      },
      isLoading: false,
    } as any);

    render(<KiteStatusBadge />, { wrapper: createWrapper() });
    const badge = screen.getByText('Kite Connected');
    fireEvent.click(badge);

    expect(screen.getByText('Zerodha Kite Connect Authentication')).toBeInTheDocument();
    expect(screen.getByText('Active Kite Market Data Session')).toBeInTheDocument();
    expect(screen.getByText('AB1234')).toBeInTheDocument();
  });

  it('renders KiteDataHealthCard with session state and universe count', () => {
    vi.spyOn(kiteHooks, 'useKiteStatus').mockReturnValue({
      data: {
        configured: true,
        authenticated: true,
        status: 'CONNECTED',
        user_id: 'AB1234',
        user_name: 'Shivam Singh',
        authenticated_at: '2026-09-04T10:00:00Z',
        expires_at: '2026-09-05T00:30:00Z',
        last_error: null,
        login_url: null,
        provider: 'kite',
      },
      isLoading: false,
      refetch: vi.fn(),
    } as any);

    vi.spyOn(kiteHooks, 'useKiteDataHealth').mockReturnValue({
      data: {
        provider: 'kite',
        authenticated: true,
        connection_status: 'CONNECTED',
        market_session: 'CLOSED',
        is_market_open: false,
        data_status: 'MARKET CLOSED',
        subscribed_instruments_count: 52,
        last_tick: null,
        last_snapshot_timestamp: '2026-09-04T15:30:00Z',
        as_of: '2026-09-04T22:00:00Z',
      },
      isLoading: false,
    } as any);

    render(<KiteDataHealthCard />, { wrapper: createWrapper() });
    expect(screen.getByText('Zerodha Kite Connect Market Data Layer')).toBeInTheDocument();
    expect(screen.getByText('MARKET CLOSED')).toBeInTheDocument();
    expect(screen.getByText('52 Instruments (NIFTY 50)')).toBeInTheDocument();
  });
});
