import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Metric } from '../components/ui/Metric';
import { DataStatus } from '../components/ui/DataStatus';
import { ErrorState } from '../components/ui/ErrorState';
import { EmptyState } from '../components/ui/EmptyState';

describe('UI Primitives', () => {
  it('renders Button with variants and states', () => {
    const { rerender } = render(<Button variant="primary">Execute Order</Button>);
    expect(screen.getByRole('button', { name: /execute order/i })).toBeInTheDocument();

    rerender(<Button isLoading>Submitting</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders Badge with semantic styles', () => {
    render(<Badge variant="positive">▲ BUY</Badge>);
    expect(screen.getByText('▲ BUY')).toBeInTheDocument();
  });

  it('renders Metric with tabular numerals and delta', () => {
    render(<Metric label="NIFTY 50" value="25,410.80" delta={1.25} prefix="₹" />);
    expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
    expect(screen.getByText('₹25,410.80')).toBeInTheDocument();
    expect(screen.getByText('+1.25%')).toBeInTheDocument();
  });

  it('renders DataStatus indicator', () => {
    render(<DataStatus status="LIVE" source="NSE Cash" />);
    expect(screen.getByText(/LIVE/i)).toBeInTheDocument();
    expect(screen.getByText(/\[NSE Cash\]/i)).toBeInTheDocument();
  });

  it('renders ErrorState and EmptyState properly', () => {
    const { rerender } = render(
      <ErrorState title="Data Load Failed" message="Network error occurred" code="ERR_NETWORK" />
    );
    expect(screen.getByText(/Data Load Failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Code: ERR_NETWORK/i)).toBeInTheDocument();

    rerender(<EmptyState title="No Trades Found" description="Try broadening search filters" />);
    expect(screen.getByText('No Trades Found')).toBeInTheDocument();
  });
});
