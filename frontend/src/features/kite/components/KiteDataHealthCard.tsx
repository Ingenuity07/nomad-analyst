import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useKiteStatus, useKiteDataHealth, initiateKiteLogin } from '@/hooks/useKiteAuth';
import { KiteAuthModal } from './KiteAuthModal';

export const KiteDataHealthCard: React.FC = () => {
  const { data: statusData } = useKiteStatus();
  const { data: healthData } = useKiteDataHealth();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const isConnected = statusData?.authenticated && statusData?.status === 'CONNECTED';
  const dataStatus = healthData?.data_status || 'MARKET CLOSED';

  const handleConnect = async () => {
    try {
      setIsLoggingIn(true);
      await initiateKiteLogin();
    } catch (err) {
      console.error(err);
      setIsLoggingIn(false);
    }
  };

  return (
    <>
      <Card style={{ padding: 'var(--space-4)', backgroundColor: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isConnected ? 'var(--positive)' : 'var(--warning)',
                boxShadow: isConnected ? '0 0 6px var(--positive)' : 'none',
              }}
            />
            <span style={{ fontWeight: 'var(--weight-bold)', fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
              Zerodha Kite Connect Market Data Layer
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Badge variant={dataStatus === 'LIVE' ? 'positive' : 'neutral'} size="sm">
              {dataStatus}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => setIsModalOpen(true)}>
              Session Details
            </Button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-3)' }}>
          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SESSION STATUS</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: isConnected ? 'var(--positive)' : 'var(--warning)' }}>
              {isConnected ? 'Active Authenticated' : statusData?.status || 'Disconnected'}
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>MARKET SESSION</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              {healthData?.market_session || 'CLOSED'}
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SUBSCRIBED UNIVERSE</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              {healthData?.subscribed_instruments_count || 52} Instruments (NIFTY 50)
            </div>
          </div>

          <div style={{ padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>LAST MARKET SNAPSHOT</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {healthData?.last_snapshot_timestamp
                ? new Date(healthData.last_snapshot_timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST'
                : 'Awaiting Ticks'}
            </div>
          </div>
        </div>

        {!isConnected && (
          <div style={{ marginTop: 'var(--space-3)', display: 'flex', justifyContent: 'flex-end' }}>
            <Button variant="primary" size="sm" onClick={handleConnect} isLoading={isLoggingIn}>
              Connect Kite Connect (2FA)
            </Button>
          </div>
        )}
      </Card>

      <KiteAuthModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};
