import React from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  tag?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/market', label: 'Market Overview', icon: '📊' },
  { to: '/intraday', label: 'Intraday Scanner', icon: '⚡' },
  { to: '/delivery', label: 'Opportunities', icon: '🎯' },
  { to: '/stocks', label: 'Stocks & Research', icon: '📈' },
  { to: '/fundamentals', label: 'Fundamentals', icon: '🏛️' },
  { to: '/recommendations', label: 'Recommendations', icon: '💡' },
  { to: '/research', label: 'AI Intelligence', icon: '🤖' },
  { to: '/backtests', label: 'Backtesting Lab', icon: '🧪' },
  { to: '/watchlist', label: 'Watchlists', icon: '⭐' },
  { to: '/design-system', label: 'Design System', icon: '🎨', tag: 'DEV' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside
      style={{
        width: '240px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: 'var(--space-4)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
        }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--brand-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            fontWeight: 'var(--weight-bold)',
            fontSize: 'var(--text-sm)',
          }}
        >
          N
        </div>
        <div>
          <div style={{ fontWeight: 'var(--weight-bold)', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
            NOMAD ANALYST
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            EQUITY TERMINAL v1.0
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ flex: 1, padding: 'var(--space-2) var(--space-2)', overflowY: 'auto' }}>
        <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', textTransform: 'uppercase', padding: 'var(--space-2) var(--space-3)', letterSpacing: '0.05em' }}>
          Workspaces
        </div>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 'var(--text-sm)',
              fontWeight: isActive ? 'var(--weight-semibold)' : 'var(--weight-regular)',
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              backgroundColor: isActive ? 'var(--bg-surface-elevated)' : 'transparent',
              borderLeft: isActive ? '3px solid var(--brand-primary)' : '3px solid transparent',
              marginBottom: '2px',
              transition: 'all var(--transition-fast)',
            })}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2-5)' }}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </div>
            {item.tag && (
              <span style={{ fontSize: 'var(--text-2xs)', padding: '1px 4px', borderRadius: 'var(--radius-xs)', backgroundColor: 'var(--brand-subtle)', color: 'var(--brand-primary)', border: '1px solid var(--brand-border)' }}>
                {item.tag}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Environment / System Footer */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          borderTop: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-surface-subtle)',
          fontSize: 'var(--text-2xs)',
          color: 'var(--text-muted)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>NSE • CASH & EQ</span>
        <span style={{ color: 'var(--positive)', fontFamily: 'var(--font-mono)' }}>● ONLINE</span>
      </div>
    </aside>
  );
};
