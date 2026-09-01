import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';

const FaultyComponent: React.FC<{ shouldThrow?: boolean }> = ({ shouldThrow = true }) => {
  if (shouldThrow) {
    throw new Error('Test rendering crash in component tree');
  }
  return <div>Healthy Component Content</div>;
};

describe('Global ErrorBoundary (FE-13)', () => {
  it('renders children when no rendering exception is thrown', () => {
    render(
      <ErrorBoundary>
        <FaultyComponent shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Healthy Component Content')).toBeInTheDocument();
  });

  it('catches render exceptions, displays clean recovery screen, and hides stack trace in fallback UI', () => {
    // Suppress console.error in test output for caught error
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <FaultyComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('error-boundary-fallback')).toBeInTheDocument();
    expect(screen.getByText('Application Error Encountered')).toBeInTheDocument();
    expect(screen.getByText('Test rendering crash in component tree')).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
    expect(screen.getByText('Reload Page')).toBeInTheDocument();
    expect(screen.getByText('Return to Market Overview')).toBeInTheDocument();

    spy.mockRestore();
  });

  it('allows user to trigger reset via Try Again button', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let shouldCrash = true;
    const DynamicComponent: React.FC = () => {
      if (shouldCrash) throw new Error('Dynamic crash');
      return <div>Recovered Successfully</div>;
    };

    const { rerender } = render(
      <ErrorBoundary>
        <DynamicComponent />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('error-boundary-fallback')).toBeInTheDocument();

    // Fix condition and click Try Again
    shouldCrash = false;
    fireEvent.click(screen.getByText('Try Again'));

    rerender(
      <ErrorBoundary>
        <DynamicComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Recovered Successfully')).toBeInTheDocument();

    spy.mockRestore();
  });
});
