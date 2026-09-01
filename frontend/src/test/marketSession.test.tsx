import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarketSessionIndicator } from '../components/common/MarketSessionIndicator';
import { MarketSessionInfo } from '../lib/api/types';

describe('MarketSessionIndicator', () => {
  it('renders unknown state if session info is missing', () => {
    render(<MarketSessionIndicator sessionInfo={null} />);
    expect(screen.getByText(/SESSION UNKNOWN/i)).toBeInTheDocument();
  });

  it('renders open trading window with minutes remaining', () => {
    const openSession: MarketSessionInfo = {
      window: 'MORNING',
      is_trading_hour: true,
      minutes_elapsed: 60,
      minutes_remaining: 315,
      session_date: '2026-09-01',
    };

    render(<MarketSessionIndicator sessionInfo={openSession} />);
    expect(screen.getByText(/OPEN • MORNING/i)).toBeInTheDocument();
    expect(screen.getByText('(315m left)')).toBeInTheDocument();
  });

  it('renders closed status for outside hours', () => {
    const closedSession: MarketSessionInfo = {
      window: 'OUTSIDE',
      is_trading_hour: false,
      minutes_elapsed: -1,
      minutes_remaining: -1,
      session_date: '2026-09-01',
    };

    render(<MarketSessionIndicator sessionInfo={closedSession} />);
    expect(screen.getByText(/CLOSED/i)).toBeInTheDocument();
  });
});
