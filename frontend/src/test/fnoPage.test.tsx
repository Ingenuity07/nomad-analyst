import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { FnoPage } from '../pages/FnoPage';
import { FnoOverviewTab } from '../features/fno/components/FnoOverviewTab';
import { FnoStrategyTab } from '../features/fno/components/FnoStrategyTab';
import { FnoLedgerTab } from '../features/fno/components/FnoLedgerTab';
import { FnoDiagnosticsTab } from '../features/fno/components/FnoDiagnosticsTab';

const mockOverviewData = {
  underlying: {
    symbol: '^NSEI',
    spot_price: 24520.5,
    market_direction: 'BULLISH',
    market_regime: 'TRENDING_UP',
    atm_strike: 24500,
  },
  feed: {
    status: 'ACTIVE',
    market_session: 'OPEN',
    ticker_running: true,
    latest_exchange_timestamp: '2026-10-21T10:00:00Z',
    latest_received_wall_clock: '2026-10-21T10:00:00.200Z',
    quote_age_seconds: 0.8,
    active_contracts_tracked: 4,
  },
  quotes: [
    {
      id: 1,
      instrument_token: 101,
      tradingsymbol: 'NIFTY26O2124500CE',
      exchange_timestamp_utc: '2026-10-21T10:00:00Z',
      received_wall_clock_utc: '2026-10-21T10:00:00.100Z',
      exchange_time_status: 'VALID',
      best_bid: '120.00',
      best_ask: '120.50',
      bid_quantity_l1: 150,
      ask_quantity_l1: 225,
      depth: {},
      quote_status: 'VALID',
      is_stale: false,
      is_locked: false,
      is_crossed: false,
      is_execution_eligible: true,
      spread_pct: '0.41',
      spread_abs: '0.50',
      created_at: '2026-10-21T10:00:00.100Z',
    },
    {
      id: 2,
      instrument_token: 102,
      tradingsymbol: 'NIFTY26O2124500PE',
      exchange_timestamp_utc: '2026-10-21T10:00:00Z',
      received_wall_clock_utc: '2026-10-21T10:00:00.100Z',
      exchange_time_status: 'VALID',
      best_bid: '95.00',
      best_ask: '95.80',
      bid_quantity_l1: 300,
      ask_quantity_l1: 150,
      depth: {},
      quote_status: 'VALID',
      is_stale: false,
      is_locked: false,
      is_crossed: false,
      is_execution_eligible: true,
      spread_pct: '0.83',
      spread_abs: '0.80',
      created_at: '2026-10-21T10:00:00.100Z',
    },
  ],
  timestamp: '2026-10-21T10:00:00Z',
};

const mockStrategyData = {
  strategy: {
    strategy_id: 'STRAT-ORB-15M',
    name: 'NIFTY 15m Opening Range Breakout',
    version: '1.0.0',
    status: 'ACTIVE',
    runtime_telemetry_available: true,
    session_date: '2026-10-21',
  },
  opening_range: {
    expected_bars: 15,
    available_bars: 15,
    runtime_established: true,
    range_high: 24550.0,
    range_low: 24480.0,
    range_width: 70.0,
    status: 'LOCKED',
    time_window: '09:15–09:30 IST',
  },
  audit_trail: {
    evaluations_count: 284,
    eligible_evaluations: 284,
    signals_count: 1,
    rejections_count: 3,
    recent_signals: [
      {
        trade_id: 1001,
        strategy_id: 'STRAT-ORB-15M',
        strategy_version: '1.0.0',
        signal_id: '11111111-1111-1111-1111-111111111111',
        instrument_token: 101,
        tradingsymbol: 'NIFTY26O2124500CE',
        option_type: 'CE',
        strike_price: '24500.00',
        expiry_date: '2026-10-21',
        entry_timestamp: '2026-10-21T09:35:00Z',
        entry_fill_price: '125.00',
        entry_slippage: '0.25',
        quantity: 25,
        exit_timestamp: null,
        exit_trigger_reason: null,
        fill_type: 'MARKET_TAKER',
        exit_fill_price: null,
        exit_slippage: '0.00',
        gross_pnl: null,
        total_frictions: '14.50',
        net_pnl: null,
        friction_breakdown: {},
        statutory_breakdown: {},
        market_regime_at_entry: 'TRENDING_UP',
        vix_level_at_entry: '12.5',
        status: 'OPEN',
        rejection_reason: null,
        created_at: '2026-10-21T09:35:00Z',
      },
    ],
    rejection_summary: {
      INSUFFICIENT_LIQUIDITY: 3,
    },
    total_signals_today: 1,
  },
  timestamp: '2026-10-21T10:00:00Z',
};

const mockTradesData = {
  summary: {
    ledger_status: 'POPULATED',
    total_trades: 2,
    open_positions_count: 1,
    wins: 2,
    losses: 0,
    win_rate_pct: 100.0,
    gross_pnl: '1250.00',
    net_pnl: '1185.50',
    total_frictions: '64.50',
    is_paper_trading: true,
  },
  open_positions: [
    {
      trade_id: 1001,
      strategy_id: 'STRAT-ORB-15M',
      strategy_version: '1.0.0',
      signal_id: '11111111-1111-1111-1111-111111111111',
      instrument_token: 101,
      tradingsymbol: 'NIFTY26O2124500CE',
      option_type: 'CE',
      strike_price: '24500.00',
      expiry_date: '2026-10-21',
      entry_timestamp: '2026-10-21T09:35:00Z',
      entry_fill_price: '125.00',
      entry_slippage: '0.25',
      quantity: 25,
      exit_timestamp: null,
      exit_trigger_reason: null,
      fill_type: 'MARKET_TAKER',
      exit_fill_price: null,
      exit_slippage: '0.00',
      gross_pnl: null,
      total_frictions: '14.50',
      net_pnl: null,
      friction_breakdown: {},
      statutory_breakdown: {},
      market_regime_at_entry: 'TRENDING_UP',
      vix_level_at_entry: '12.5',
      status: 'OPEN',
      rejection_reason: null,
      created_at: '2026-10-21T09:35:00Z',
    },
  ],
  closed_trades: [
    {
      trade_id: 1000,
      strategy_id: 'STRAT-ORB-15M',
      strategy_version: '1.0.0',
      signal_id: '00000000-0000-0000-0000-000000000000',
      instrument_token: 101,
      tradingsymbol: 'NIFTY26O2124500CE',
      option_type: 'CE',
      strike_price: '24500.00',
      expiry_date: '2026-10-21',
      entry_timestamp: '2026-10-21T09:31:00Z',
      entry_fill_price: '110.00',
      entry_slippage: '0.20',
      quantity: 25,
      exit_timestamp: '2026-10-21T09:50:00Z',
      exit_trigger_reason: 'TARGET',
      fill_type: 'MARKET_TAKER',
      exit_fill_price: '160.00',
      exit_slippage: '0.30',
      gross_pnl: '1250.00',
      total_frictions: '64.50',
      net_pnl: '1185.50',
      friction_breakdown: {},
      statutory_breakdown: {},
      market_regime_at_entry: 'TRENDING_UP',
      vix_level_at_entry: '12.5',
      status: 'CLOSED',
      rejection_reason: null,
      created_at: '2026-10-21T09:31:00Z',
    },
  ],
  rejections: [
    {
      trade_id: 999,
      strategy_id: 'STRAT-ORB-15M',
      strategy_version: '1.0.0',
      signal_id: '22222222-2222-2222-2222-222222222222',
      instrument_token: 102,
      tradingsymbol: 'NIFTY26O2124500PE',
      option_type: 'PE',
      strike_price: '24500.00',
      expiry_date: '2026-10-21',
      entry_timestamp: '2026-10-21T09:33:00Z',
      entry_fill_price: '0.00',
      entry_slippage: '0.00',
      quantity: 25,
      exit_timestamp: null,
      exit_trigger_reason: null,
      fill_type: 'MARKET_TAKER',
      exit_fill_price: null,
      exit_slippage: '0.00',
      gross_pnl: null,
      total_frictions: '0.00',
      net_pnl: null,
      friction_breakdown: {},
      statutory_breakdown: {},
      market_regime_at_entry: 'TRENDING_UP',
      vix_level_at_entry: '12.5',
      status: 'REJECTED',
      rejection_reason: 'INSUFFICIENT_LIQUIDITY',
      created_at: '2026-10-21T09:33:00Z',
    },
  ],
  timestamp: '2026-10-21T10:00:00Z',
};

const mockDiagnosticsData = {
  session_date: '2026-10-21',
  bars: {
    total_today: 120,
    complete_count: 120,
    partial_count: 0,
    partial_ratio_pct: 0.0,
    quality_status: 'EXCELLENT',
  },
  quotes: {
    total_today: 45000,
    eligible_count: 44200,
    stale_count: 800,
    latest_feed_latency_seconds: 0.045,
  },
  components: {
    postgresql: 'HEALTHY',
    ticker_daemon: 'RUNNING',
    ticker_pid: 41325,
    fee_schedule: 'NSE_CIRCULAR_73061_0.03553%',
    paper_execution_mode: 'STRICT_SIMULATED',
  },
  timestamp: '2026-10-21T10:00:00Z',
};

describe('F&O Laboratory Workspace (Phase FNO-1 & FNO-1A)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
        },
      },
    });

    global.fetch = vi.fn().mockImplementation((input: any) => {
      const url = typeof input === 'string' ? input : input?.url || String(input);
      let data: any = {};
      if (url.includes('/fno/overview/')) data = mockOverviewData;
      else if (url.includes('/fno/strategy/')) data = mockStrategyData;
      else if (url.includes('/fno/trades/')) data = mockTradesData;
      else if (url.includes('/fno/diagnostics/')) data = mockDiagnosticsData;

      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => data,
      });
    });
  });

  it('renders workspace title, header metrics, and tabs on master page', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <FnoPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getAllByText('F&O Laboratory').length).toBeGreaterThan(0);
    expect(screen.getByText('PHASE FNO-1 BETA')).toBeInTheDocument();
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Paper Trading')).toBeInTheDocument();
    expect(screen.getByText('Diagnostics')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('24520.50')).toBeInTheDocument();
      expect(screen.getByText('24500')).toBeInTheDocument();
      expect(screen.getByText('FEED LIVE')).toBeInTheDocument();
    });
  });

  it('renders Overview tab with option quotes ladder and filters', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FnoOverviewTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('NIFTY26O2124500CE')).toBeInTheDocument();
      expect(screen.getByText('NIFTY26O2124500PE')).toBeInTheDocument();
    });

    // Test filtering by CE
    const ceButton = screen.getByRole('button', { name: /^CE$/i });
    fireEvent.click(ceButton);

    expect(screen.getByText('NIFTY26O2124500CE')).toBeInTheDocument();
    expect(screen.queryByText('NIFTY26O2124500PE')).not.toBeInTheDocument();
  });

  it('renders Strategy tab with opening range meter and audit trail', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FnoStrategyTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('STRAT-ORB-15M Specification')).toBeInTheDocument();
    });
    expect(screen.getByText(/15 \/ 15 Bars \(100%\) — Range Locked/)).toBeInTheDocument();
    expect(screen.getByText('₹24550.00')).toBeInTheDocument();
    expect(screen.getByText('₹24480.00')).toBeInTheDocument();
    expect(screen.getByText('70 pts')).toBeInTheDocument();
    expect(screen.getByText('INSUFFICIENT_LIQUIDITY: 3')).toBeInTheDocument();
  });

  it('renders Paper Trading tab and switches subtabs between open, closed, and rejections', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FnoLedgerTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Paper Trading Session Performance')).toBeInTheDocument();
      expect(screen.getByText('₹1185.50')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    // Verify trial-not-started notice banner
    expect(screen.getByText('20-Session Prospective Paper Trial: Inactive')).toBeInTheDocument();
    expect(screen.getByText('APPROVAL REQUIRED')).toBeInTheDocument();

    // Default open positions subtab
    expect(screen.getByText('#1001')).toBeInTheDocument();

    // Click Closed Trades
    const closedButton = screen.getByRole('button', { name: /Closed Trades/i });
    fireEvent.click(closedButton);

    await waitFor(() => {
      expect(screen.getByText('#1000')).toBeInTheDocument();
      expect(screen.getByText('TARGET')).toBeInTheDocument();
    });

    // Click Rejections
    const rejectionsButton = screen.getByRole('button', { name: /Rejections/i });
    fireEvent.click(rejectionsButton);

    await waitFor(() => {
      expect(screen.getByText('#999')).toBeInTheDocument();
      expect(screen.getByText('INSUFFICIENT_LIQUIDITY')).toBeInTheDocument();
    });
  });

  it('renders Diagnostics tab with bar completeness, PostgreSQL, and ticker daemon status', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FnoDiagnosticsTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('1-Minute Option Bar Completeness')).toBeInTheDocument();
      expect(screen.getByText('EXCELLENT')).toBeInTheDocument();
      expect(screen.getByText('PostgreSQL Database Connection')).toBeInTheDocument();
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
      expect(screen.getByText(/Live Ticker Daemon/)).toBeInTheDocument();
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
      expect(screen.getByText('NSE_CIRCULAR_73061_0.03553%')).toBeInTheDocument();
    });
  });

  it('renders offline telemetry banner when runtime_telemetry_available is false', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          strategy: {
            strategy_id: 'STRAT-ORB-15M',
            name: 'NIFTY 15m Opening Range Breakout',
            version: '1.0.0',
            status: 'UNAVAILABLE',
            runtime_telemetry_available: false,
            session_date: '2026-10-21',
          },
          opening_range: {
            expected_bars: 15,
            available_bars: 0,
            range_high: null,
            range_low: null,
            range_width: null,
            status: 'UNAVAILABLE',
            time_window: '09:15–09:30 IST',
          },
          audit_trail: {
            evaluations_count: null,
            rejections_count: 0,
            rejection_summary: {},
            recent_signals: [],
            total_signals_today: 0,
          },
          timestamp: '2026-10-21T10:00:00Z',
        }),
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <FnoStrategyTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Runtime Strategy Telemetry Offline')).toBeInTheDocument();
      expect(screen.getByText('AWAITING RUNTIME')).toBeInTheDocument();
    });
  });

  it('renders clean zero-exposure banner when ledger is empty and trial not started', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          summary: {
            ledger_status: 'EMPTY',
            total_trades: 0,
            open_positions_count: 0,
            wins: 0,
            losses: 0,
            win_rate_pct: 0,
            gross_pnl: '0.00',
            net_pnl: '0.00',
            total_frictions: '0.00',
            is_paper_trading: true,
          },
          open_positions: [],
          closed_trades: [],
          rejections: [],
          timestamp: '2026-10-21T10:00:00Z',
        }),
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <FnoLedgerTab />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Zero-Exposure Paper Ledger:/)).toBeInTheDocument();
      expect(screen.getByText('CLEAN TRIAL LEDGER')).toBeInTheDocument();
      expect(screen.getByText('LEDGER EMPTY')).toBeInTheDocument();
      expect(screen.getByText('No Open Positions')).toBeInTheDocument();
      expect(screen.getByText(/Trial not started\. No simulated positions are active/)).toBeInTheDocument();
    });
  });

  describe('Regression: Quote Freshness Presentation & Disagreement', () => {
    it('separates feed health (ACTIVE) from quote freshness (STALE >3.0s)', async () => {
      global.fetch = vi.fn().mockImplementation((input: any) => {
        const url = typeof input === 'string' ? input : input?.url || String(input);
        if (url.includes('/fno/overview/')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({
              ...mockOverviewData,
              feed: {
                ...mockOverviewData.feed,
                status: 'ACTIVE',
                quote_age_seconds: 4.8,
              },
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        });
      });

      render(
        <QueryClientProvider client={queryClient}>
          <FnoOverviewTab />
        </QueryClientProvider>
      );

      await waitFor(() => {
        // Feed connection is Live (Streaming)
        expect(screen.getByText('Live (Streaming)')).toBeInTheDocument();
        // Quote freshness clearly indicates Stale and taker ineligible despite active feed
        expect(screen.getByText('4.8s Age')).toBeInTheDocument();
        expect(screen.getByText('Stale (>3.0s — Taker Ineligible)')).toBeInTheDocument();
        // Crucially, verify it is NEVER labeled Optimal or Real-Time
        expect(screen.queryByText(/Optimal/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/Real-Time/i)).not.toBeInTheDocument();
      });
    });

    it('handles missing quote timestamps explicitly without inventing freshness values', async () => {
      global.fetch = vi.fn().mockImplementation((input: any) => {
        const url = typeof input === 'string' ? input : input?.url || String(input);
        if (url.includes('/fno/overview/')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({
              ...mockOverviewData,
              feed: {
                ...mockOverviewData.feed,
                status: 'ACTIVE',
                latest_exchange_timestamp: null,
                latest_received_wall_clock: null,
                quote_age_seconds: null,
              },
              quotes: [
                {
                  ...mockOverviewData.quotes[0],
                  exchange_timestamp_utc: null,
                  exchange_time_status: 'UNAVAILABLE',
                  is_execution_eligible: false,
                },
              ],
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        });
      });

      render(
        <QueryClientProvider client={queryClient}>
          <FnoOverviewTab />
        </QueryClientProvider>
      );

      await waitFor(() => {
        // Must show Unavailable instead of a fabricated 0.0s or Real-time
        expect(screen.getByText('Unavailable')).toBeInTheDocument();
        expect(screen.getByText('Awaiting quote timestamp')).toBeInTheDocument();
        expect(screen.getByText('Timestamp Unavailable')).toBeInTheDocument();
      });
    });
  });

  describe('Regression: Opening Range Bar Count vs Authority', () => {
    it('does not imply opening range is established even if available_bars is 15 when runtime telemetry is UNAVAILABLE', async () => {
      global.fetch = vi.fn().mockImplementation((input: any) => {
        const url = typeof input === 'string' ? input : input?.url || String(input);
        if (url.includes('/fno/strategy/')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({
              strategy: {
                strategy_id: 'STRAT-ORB-15M',
                name: 'NIFTY 15m Opening Range Breakout',
                version: '1.0.0',
                status: 'UNAVAILABLE',
                runtime_telemetry_available: false,
                session_date: '2026-10-21',
              },
              opening_range: {
                expected_bars: 15,
                available_bars: 15, // Historical bars exist in DB
                runtime_established: false, // NOT established by runtime daemon
                range_high: 24550.0,
                range_low: 24480.0,
                range_width: 70.0,
                status: 'UNAVAILABLE',
                time_window: '09:15–09:30 IST',
              },
              audit_trail: {
                evaluations_count: null,
                rejections_count: 0,
                rejection_summary: {},
                recent_signals: [],
                total_signals_today: 0,
              },
              timestamp: '2026-10-21T10:00:00Z',
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({}),
        });
      });

      render(
        <QueryClientProvider client={queryClient}>
          <FnoStrategyTab />
        </QueryClientProvider>
      );

      await waitFor(() => {
        // Bar completeness MUST show UNAVAILABLE (Awaiting Runtime), not 100% or Locked
        expect(screen.getByText('UNAVAILABLE (Awaiting Runtime)')).toBeInTheDocument();
        // Bounds must show '—' because runtime has not confirmed them
        expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
        // Explanatory note must be visible
        expect(
          screen.getByText(
            'Historical database bars alone do not establish a valid range without active strategy daemon verification.'
          )
        ).toBeInTheDocument();
      });
    });
  });

  describe('Regression: Prospective Paper Trial Messaging', () => {
    it('clearly communicates in header and ledger that the trial has NOT started and requires approval', async () => {
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <FnoPage />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('TRIAL NOT STARTED')).toBeInTheDocument();
      });

      // Header trial status badge and subtitle
      expect(
        screen.getByText(/20-Session Trial: Not Started \(Approval Required\)/)
      ).toBeInTheDocument();

      // Switch to Paper Trading tab
      const paperTab = screen.getByRole('button', { name: /^Paper Trading$/i });
      fireEvent.click(paperTab);

      await waitFor(() => {
        expect(
          screen.getByText('20-Session Prospective Paper Trial: Inactive')
        ).toBeInTheDocument();
        expect(screen.getByText('APPROVAL REQUIRED')).toBeInTheDocument();
      });
    });
  });
});
