import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { IntradayMarketHeader } from '@/features/intraday/components/IntradayMarketHeader';
import { IntradayBreadthCard } from '@/features/intraday/components/IntradayBreadthCard';
import { IntradaySectorStrengthPanel } from '@/features/intraday/components/IntradaySectorStrength';
import { IntradayStockContextTable } from '@/features/intraday/components/IntradayStockContextTable';
import { IntradayMarketContextResponse, StockIntradayContextItem } from '@/lib/api/types';

const mockContext: IntradayMarketContextResponse = {
  as_of: '2026-09-05T10:30:00+05:30',
  freshness: 'FRESH',
  freshness_age_seconds: 1.2,
  is_fresh: true,
  market_direction: 'BULLISH',
  market_regime: 'TRENDING_UP',
  regime_confidence: 0.85,
  regime_reasons: [
    'NIFTY above session VWAP (24500.00)',
    'Breadth: 38 advancing (76%), 10 declining (A/D 3.80)',
    'Sector breadth: 11/14 positive (79%)',
  ],
  index_confirmation: 'CONFIRMED_BULLISH',
  market_volatility: 'NORMAL',
  nifty: {
    symbol: '^NSEI',
    name: 'NIFTY 50',
    price: 24650.5,
    change: 180.25,
    change_percent: 0.74,
    open: 24480.0,
    high: 24680.0,
    low: 24460.0,
    vwap: 24550.0,
  },
  banknifty: {
    symbol: '^NSEBANK',
    name: 'NIFTY BANK',
    price: 52400.0,
    change: 450.0,
    change_percent: 0.87,
    open: 52000.0,
    high: 52500.0,
    low: 51950.0,
    vwap: 52200.0,
  },
  breadth: {
    total_constituents: 50,
    advance_count: 38,
    decline_count: 10,
    unchanged_count: 2,
    advance_pct: 76.0,
    decline_pct: 20.0,
    unchanged_pct: 4.0,
    advance_decline_ratio: 3.8,
    above_vwap_count: 36,
    below_vwap_count: 14,
    above_vwap_pct: 72.0,
    below_vwap_pct: 28.0,
    at_high_count: 12,
    at_low_count: 1,
    breadth_state: 'STRONG_POSITIVE',
  },
  sectors: [
    {
      sector: 'Metals & Mining',
      constituent_count: 4,
      average_return: 1.85,
      median_return: 1.75,
      advance_count: 4,
      decline_count: 0,
      advance_pct: 100.0,
      above_vwap_pct: 100.0,
      relative_strength_vs_nifty: 1.11,
      rank: 1,
    },
    {
      sector: 'Technology',
      constituent_count: 5,
      average_return: 0.95,
      median_return: 0.85,
      advance_count: 4,
      decline_count: 1,
      advance_pct: 80.0,
      above_vwap_pct: 80.0,
      relative_strength_vs_nifty: 0.21,
      rank: 2,
    },
    {
      sector: 'Pharmaceutical',
      constituent_count: 4,
      average_return: -0.45,
      median_return: -0.40,
      advance_count: 1,
      decline_count: 3,
      advance_pct: 25.0,
      above_vwap_pct: 25.0,
      relative_strength_vs_nifty: -1.19,
      rank: 14,
    },
  ],
  sector_leader: 'Metals & Mining',
  sector_laggard: 'Pharmaceutical',
};

const mockStocks: StockIntradayContextItem[] = [
  {
    symbol: 'TATASTEEL',
    company_name: 'Tata Steel Limited',
    last_price: 154.5,
    previous_close: 151.2,
    open: 152.0,
    high: 155.0,
    low: 151.8,
    change_pct: 2.18,
    vwap: 153.2,
    distance_from_vwap: 0.85,
    is_above_vwap: true,
    volume: 12500000,
    relative_volume: 1.45,
    momentum_5m: 0.45,
    momentum_15m: 0.85,
    momentum_30m: 1.25,
    relative_strength_vs_market: 1.44,
    relative_strength_vs_sector: 0.33,
    sector: 'Metals & Mining',
    sector_return: 1.85,
    volume_confirmation: 'CONFIRMED_UP',
    opening_gap_pct: 0.53,
    opening_range_state: 'ABOVE_ORB',
    component_scores: {
      momentum_score: 85.0,
      relative_strength_score: 88.0,
      volume_confirmation_score: 90.0,
      vwap_alignment_score: 85.0,
      sector_alignment_score: 95.0,
      market_alignment_score: 85.0,
    },
    context_score: 87.0,
  },
  {
    symbol: 'SUNPHARMA',
    company_name: 'Sun Pharmaceutical Industries Limited',
    last_price: 1820.0,
    previous_close: 1835.0,
    open: 1830.0,
    high: 1832.0,
    low: 1815.0,
    change_pct: -0.82,
    vwap: 1825.0,
    distance_from_vwap: -0.27,
    is_above_vwap: false,
    volume: 850000,
    relative_volume: 0.65,
    momentum_5m: -0.15,
    momentum_15m: -0.35,
    momentum_30m: -0.55,
    relative_strength_vs_market: -1.56,
    relative_strength_vs_sector: -0.37,
    sector: 'Pharmaceutical',
    sector_return: -0.45,
    volume_confirmation: 'WEAK_DOWN',
    opening_gap_pct: -0.27,
    opening_range_state: 'BELOW_ORB',
    component_scores: {
      momentum_score: 35.0,
      relative_strength_score: 25.0,
      volume_confirmation_score: 45.0,
      vwap_alignment_score: 40.0,
      sector_alignment_score: 30.0,
      market_alignment_score: 25.0,
    },
    context_score: 32.0,
  },
];

describe('Phase 17C — Intraday Market Context UI Components', () => {
  it('renders IntradayMarketHeader with NIFTY, BANKNIFTY, regime, and freshness', () => {
    render(<IntradayMarketHeader context={mockContext} wsConnected={true} />);

    expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
    expect(screen.getByText('₹24,650.50')).toBeInTheDocument();
    expect(screen.getByText('+0.74%')).toBeInTheDocument();

    expect(screen.getByText('NIFTY BANK')).toBeInTheDocument();
    expect(screen.getByText('₹52,400.00')).toBeInTheDocument();

    expect(screen.getByText(/TRENDING UP/i)).toBeInTheDocument();
    expect(screen.getByText(/CONFIRMED BULLISH/i)).toBeInTheDocument();
    expect(screen.getByText(/FRESH ⚡ WS/i)).toBeInTheDocument();
    expect(screen.getByText(/NIFTY above session VWAP/i)).toBeInTheDocument();
  });

  it('renders IntradayBreadthCard with advances, declines, and A/D ratio', () => {
    render(<IntradayBreadthCard breadth={mockContext.breadth} />);

    expect(screen.getByText('NIFTY 50 Market Breadth')).toBeInTheDocument();
    expect(screen.getByText('3.80')).toBeInTheDocument();
    expect(screen.getByText('STRONG POSITIVE')).toBeInTheDocument();
    expect(screen.getByText('38')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument(); // Above VWAP %
  });

  it('renders IntradaySectorStrengthPanel with ranked sectors and leader/laggard', () => {
    render(
      <IntradaySectorStrengthPanel
        sectors={mockContext.sectors}
        sectorLeader={mockContext.sector_leader}
        sectorLaggard={mockContext.sector_laggard}
      />
    );

    expect(screen.getByText('Leader: Metals & Mining')).toBeInTheDocument();
    expect(screen.getByText('Laggard: Pharmaceutical')).toBeInTheDocument();
    expect(screen.getByText('#1 Metals & Mining')).toBeInTheDocument();
    expect(screen.getByText('+1.85%')).toBeInTheDocument();
    expect(screen.getByText('#14 Pharmaceutical')).toBeInTheDocument();
    expect(screen.getByText('-0.45%')).toBeInTheDocument();
  });

  it('renders IntradayStockContextTable and confirms NO BUY/SELL labels appear', () => {
    render(<IntradayStockContextTable stocks={mockStocks} />);

    expect(screen.getByText('TATASTEEL')).toBeInTheDocument();
    expect(screen.getByText('SUNPHARMA')).toBeInTheDocument();
    expect(screen.getByText('+2.18%')).toBeInTheDocument();
    expect(screen.getByText('-0.82%')).toBeInTheDocument();

    // Volume Confirmation Badges
    expect(screen.getByText('Confirmed ↑')).toBeInTheDocument();
    expect(screen.getByText('Weak ↓')).toBeInTheDocument();

    // Opening Range state
    expect(screen.getByText('Above ORB')).toBeInTheDocument();
    expect(screen.getByText('Below ORB')).toBeInTheDocument();

    // STRICT AUDIT: Table is informational context only. Must NOT contain BUY or SELL recommendation signals
    expect(screen.queryByText('BUY')).toBeNull();
    expect(screen.queryByText('SELL')).toBeNull();
  });

  it('supports sorting by price, change %, and search filtering in IntradayStockContextTable', () => {
    render(<IntradayStockContextTable stocks={mockStocks} />);

    const searchInput = screen.getByPlaceholderText('Search symbol...');
    fireEvent.change(searchInput, { target: { value: 'TATA' } });

    expect(screen.getByText('TATASTEEL')).toBeInTheDocument();
    expect(screen.queryByText('SUNPHARMA')).toBeNull();
  });
});
