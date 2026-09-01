import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '../components/layout/AppShell';

describe('Application Shell & Navigation', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it('renders Sidebar with all primary financial workspace links', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/market']}>
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText('NOMAD ANALYST')).toBeInTheDocument();
    expect(screen.getByText('Market Overview')).toBeInTheDocument();
    expect(screen.getByText('Intraday Scanner')).toBeInTheDocument();
    expect(screen.getByText('Opportunities')).toBeInTheDocument();
    expect(screen.getByText('Stocks & Research')).toBeInTheDocument();
    expect(screen.getByText('Recommendations')).toBeInTheDocument();
    expect(screen.getByText('AI Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Backtesting Lab')).toBeInTheDocument();
    expect(screen.getByText('Watchlists')).toBeInTheDocument();
    expect(screen.getByText('Design System')).toBeInTheDocument();
  });
});
