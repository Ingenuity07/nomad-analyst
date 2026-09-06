import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { useKiteStatus, useKiteDataHealth, useKiteDisconnect, initiateKiteLogin } from '@/hooks/useKiteAuth';

export interface KiteAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KiteAuthModal: React.FC<KiteAuthModalProps> = ({ isOpen, onClose }) => {
  const { data: statusData, isLoading: isStatusLoading, refetch: refetchStatus } = useKiteStatus();
  const { data: healthData } = useKiteDataHealth();
  const disconnectMutation = useKiteDisconnect();
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleConnect = async () => {
    try {
      setIsLoggingIn(true);
      await initiateKiteLogin();
    } catch (err) {
      console.error(err);
      setIsLoggingIn(false);
    }
  };

  const handleDisconnect = async () => {
    await disconnectMutation.mutateAsync();
    refetchStatus();
  };

  const status = statusData?.status || 'NOT_CONFIGURED';
  const isConnected = statusData?.authenticated && status === 'CONNECTED';
  const isExpired = status === 'EXPIRED';

  const getStatusBadge = () => {
    switch (status) {
      case 'CONNECTED':
        return <Badge variant="positive" size="md">CONNECTED</Badge>;
      case 'AUTHENTICATING':
        return <Badge variant="warning" size="md">CONNECTING...</Badge>;
      case 'EXPIRED':
        return <Badge variant="warning" size="md">TOKEN EXPIRED</Badge>;
      case 'ERROR':
        return <Badge variant="negative" size="md">ERROR</Badge>;
      case 'AUTHENTICATION_REQUIRED':
        return <Badge variant="neutral" size="md">AUTH REQUIRED</Badge>;
      default:
        return <Badge variant="neutral" size="md">NOT CONFIGURED</Badge>;
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Zerodha Kite Connect Authentication">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {isStatusLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <Skeleton height="40px" />
            <Skeleton height="60px" />
          </div>
        ) : (
          <>
            {/* Status Header Box */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: 'var(--space-3)',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>CONNECTION LIFECYCLE</div>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {isConnected ? 'Active Kite Market Data Session' : isExpired ? 'Daily Session Expired (2FA Needed)' : 'Kite Session Inactive'}
                </div>
              </div>
              {getStatusBadge()}
            </div>

            {/* Error banner if present */}
            {statusData?.last_error && (
              <div
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  backgroundColor: 'var(--negative-bg)',
                  color: 'var(--negative)',
                  borderRadius: 'var(--radius-xs)',
                  fontSize: 'var(--text-xs)',
                  border: '1px solid var(--negative-border, var(--negative))',
                }}
              >
                {statusData.last_error}
              </div>
            )}

            {/* Credential Details */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)' }}>
              <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>CLIENT ID</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {statusData?.user_id || 'Personal Zerodha Account'}
                </div>
              </div>
              <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>DAILY TOKEN EXPIRY</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {statusData?.expires_at ? new Date(statusData.expires_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' }) + ' IST' : '06:00 AM IST daily'}
                </div>
              </div>
            </div>

            {/* Data Health Telemetry */}
            <div
              style={{
                padding: 'var(--space-3)',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
                LIVE MARKET DATA HEALTH
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
                <div>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>STREAM STATUS</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-bold)', color: healthData?.data_status === 'LIVE' ? 'var(--positive)' : 'var(--text-secondary)' }}>
                    {healthData?.data_status || 'MARKET CLOSED'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>MARKET SESSION</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                    {healthData?.market_session || 'CLOSED'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>UNIVERSE SIZE</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                    50 EQ + 2 INDICES
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
              {isConnected ? (
                <>
                  <Button variant="outline" size="sm" onClick={handleDisconnect} isLoading={disconnectMutation.isPending}>
                    Disconnect
                  </Button>
                  <Button variant="primary" size="sm" onClick={handleConnect} isLoading={isLoggingIn}>
                    Reconnect Kite
                  </Button>
                </>
              ) : (
                <Button variant="primary" size="sm" onClick={handleConnect} isLoading={isLoggingIn}>
                  Connect Kite (2FA)
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
