import { Component, ErrorInfo, ReactNode } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });
    // In production, error telemetry dispatch hook would be triggered here
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary caught error]:', error, errorInfo);
    }
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  public handleReload = () => {
    window.location.reload();
  };

  public handleReturnToMarket = () => {
    window.location.href = '/market';
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          data-testid="error-boundary-fallback"
          style={{
            padding: 'var(--space-8)',
            maxWidth: '640px',
            margin: 'var(--space-12) auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-4)',
          }}
        >
          <Card header="Application Error Encountered">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6, margin: 0 }}>
                An unexpected interface rendering issue occurred in this workspace. Your cached session data remains intact.
              </p>

              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  backgroundColor: 'var(--bg-surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {this.state.error?.message || 'Unknown runtime error'}
              </div>

              {/* Developer diagnostics only in development mode */}
              {import.meta.env.DEV && this.state.errorInfo && (
                <details
                  style={{
                    backgroundColor: 'var(--bg-surface-elevated)',
                    padding: 'var(--space-2) var(--space-3)',
                    borderRadius: 'var(--radius-xs)',
                    fontSize: 'var(--text-2xs)',
                    color: 'var(--text-disabled)',
                    cursor: 'pointer',
                  }}
                >
                  <summary style={{ color: 'var(--warning)', fontWeight: 'var(--weight-medium)' }}>
                    Developer Component Stack
                  </summary>
                  <pre style={{ margin: 'var(--space-2) 0 0 0', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                    {this.state.errorInfo.componentStack}
                  </pre>
                </details>
              )}

              <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
                <Button variant="primary" size="sm" onClick={this.handleReset}>
                  Try Again
                </Button>
                <Button variant="secondary" size="sm" onClick={this.handleReload}>
                  Reload Page
                </Button>
                <Button variant="outline" size="sm" onClick={this.handleReturnToMarket}>
                  Return to Market Overview
                </Button>
              </div>
            </div>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
