import React, { useState, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StockIntradayContextItem } from '@/lib/api/types';

interface IntradayStockContextTableProps {
  stocks: StockIntradayContextItem[];
  isLoading?: boolean;
}

type SortField = 'symbol' | 'last_price' | 'change_pct' | 'distance_from_vwap' | 'relative_strength_vs_market' | 'volume' | 'context_score';

export const IntradayStockContextTable: React.FC<IntradayStockContextTableProps> = ({
  stocks = [],
  isLoading,
}) => {
  const [search, setSearch] = useState('');
  const [selectedSector, setSelectedSector] = useState('ALL');
  const [sortField, setSortField] = useState<SortField>('change_pct');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Extract unique sectors
  const sectors = useMemo(() => {
    const set = new Set<string>();
    stocks.forEach((s) => {
      if (s.sector && s.sector !== 'Unknown') set.add(s.sector);
    });
    return Array.from(set).sort();
  }, [stocks]);

  // Filter & Sort
  const filteredStocks = useMemo(() => {
    return stocks.filter((s) => {
      const matchSearch =
        s.symbol.toLowerCase().includes(search.toLowerCase()) ||
        (s.company_name && s.company_name.toLowerCase().includes(search.toLowerCase()));
      const matchSector = selectedSector === 'ALL' || s.sector === selectedSector;
      return matchSearch && matchSector;
    });
  }, [stocks, search, selectedSector]);

  const sortedStocks = useMemo(() => {
    return [...filteredStocks].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      if (aVal === null || aVal === undefined) aVal = sortOrder === 'asc' ? Infinity : -Infinity;
      if (bVal === null || bVal === undefined) bVal = sortOrder === 'asc' ? Infinity : -Infinity;

      if (typeof aVal === 'string') {
        return sortOrder === 'asc'
          ? (aVal as string).localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal as string);
      }

      return sortOrder === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
  }, [filteredStocks, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const getVolBadge = (volState: string) => {
    switch (volState) {
      case 'CONFIRMED_UP':
        return <Badge variant="positive">Confirmed ↑</Badge>;
      case 'WEAK_UP':
        return <Badge variant="warning">Weak ↑</Badge>;
      case 'CONFIRMED_DOWN':
        return <Badge variant="negative">Confirmed ↓</Badge>;
      case 'WEAK_DOWN':
        return <Badge variant="warning">Weak ↓</Badge>;
      default:
        return <Badge variant="neutral">Neutral</Badge>;
    }
  };

  const getOrbBadge = (orb: string) => {
    switch (orb) {
      case 'ABOVE_ORB':
        return <span style={{ color: 'var(--positive)', fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-xs)' }}>Above ORB</span>;
      case 'BELOW_ORB':
        return <span style={{ color: 'var(--negative)', fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-xs)' }}>Below ORB</span>;
      default:
        return <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>Inside ORB</span>;
    }
  };

  return (
    <Card style={{ padding: 'var(--space-4)' }}>
      {/* Table Toolbar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            NIFTY 50 Intraday Stock Context ({sortedStocks.length} constituents)
          </span>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <input
            type="text"
            placeholder="Search symbol..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: 'var(--space-2) var(--space-3)',
              backgroundColor: 'var(--card-bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-xs)',
              width: '160px',
            }}
          />

          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            style={{
              padding: 'var(--space-2) var(--space-3)',
              backgroundColor: 'var(--card-bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-xs)',
            }}
          >
            <option value="ALL">All Sectors</option>
            {sectors.map((sec) => (
              <option key={sec} value={sec}>
                {sec}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-xs)', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              <th onClick={() => handleSort('symbol')} style={{ padding: 'var(--space-2)', cursor: 'pointer' }}>
                Stock {sortField === 'symbol' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th style={{ padding: 'var(--space-2)' }}>Sector</th>
              <th onClick={() => handleSort('last_price')} style={{ padding: 'var(--space-2)', textAlign: 'right', cursor: 'pointer' }}>
                Price {sortField === 'last_price' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th onClick={() => handleSort('change_pct')} style={{ padding: 'var(--space-2)', textAlign: 'right', cursor: 'pointer' }}>
                Change % {sortField === 'change_pct' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th style={{ padding: 'var(--space-2)', textAlign: 'right' }}>VWAP</th>
              <th onClick={() => handleSort('distance_from_vwap')} style={{ padding: 'var(--space-2)', textAlign: 'right', cursor: 'pointer' }}>
                Vs VWAP {sortField === 'distance_from_vwap' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th style={{ padding: 'var(--space-2)', textAlign: 'right' }}>5m %</th>
              <th style={{ padding: 'var(--space-2)', textAlign: 'right' }}>15m %</th>
              <th onClick={() => handleSort('relative_strength_vs_market')} style={{ padding: 'var(--space-2)', textAlign: 'right', cursor: 'pointer' }}>
                RS NIFTY {sortField === 'relative_strength_vs_market' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th style={{ padding: 'var(--space-2)' }}>Volume State</th>
              <th style={{ padding: 'var(--space-2)' }}>ORB State</th>
              <th onClick={() => handleSort('context_score')} style={{ padding: 'var(--space-2)', textAlign: 'right', cursor: 'pointer' }}>
                Context Score {sortField === 'context_score' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && sortedStocks.length === 0 ? (
              <tr>
                <td colSpan={12} style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--text-muted)' }}>
                  Loading real-time intraday context...
                </td>
              </tr>
            ) : sortedStocks.length === 0 ? (
              <tr>
                <td colSpan={12} style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--text-muted)' }}>
                  No constituents match the current filter.
                </td>
              </tr>
            ) : (
              sortedStocks.map((stock) => {
                const isPos = stock.change_pct >= 0;
                const vwapDist = stock.distance_from_vwap;
                const rs = stock.relative_strength_vs_market;

                return (
                  <tr
                    key={stock.symbol}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      transition: 'background-color 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--card-bg-elevated)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: 'var(--space-2)', fontWeight: 'var(--weight-semibold)' }}>
                      {stock.symbol}
                    </td>
                    <td style={{ padding: 'var(--space-2)', color: 'var(--text-secondary)' }}>
                      {stock.sector}
                    </td>
                    <td style={{ padding: 'var(--space-2)', textAlign: 'right', fontWeight: 'var(--weight-semibold)' }}>
                      ₹{stock.last_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td
                      style={{
                        padding: 'var(--space-2)',
                        textAlign: 'right',
                        fontWeight: 'var(--weight-bold)',
                        color: isPos ? 'var(--positive)' : 'var(--negative)',
                      }}
                    >
                      {isPos ? '+' : ''}{stock.change_pct.toFixed(2)}%
                    </td>
                    <td style={{ padding: 'var(--space-2)', textAlign: 'right', color: 'var(--text-muted)' }}>
                      {stock.vwap ? `₹${stock.vwap.toFixed(2)}` : '—'}
                    </td>
                    <td
                      style={{
                        padding: 'var(--space-2)',
                        textAlign: 'right',
                        color: vwapDist !== null && vwapDist >= 0 ? 'var(--positive)' : 'var(--negative)',
                      }}
                    >
                      {vwapDist !== null ? `${vwapDist >= 0 ? '+' : ''}${vwapDist.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ padding: 'var(--space-2)', textAlign: 'right', color: 'var(--text-secondary)' }}>
                      {stock.momentum_5m !== null ? `${stock.momentum_5m >= 0 ? '+' : ''}${stock.momentum_5m.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ padding: 'var(--space-2)', textAlign: 'right', color: 'var(--text-secondary)' }}>
                      {stock.momentum_15m !== null ? `${stock.momentum_15m >= 0 ? '+' : ''}${stock.momentum_15m.toFixed(2)}%` : '—'}
                    </td>
                    <td
                      style={{
                        padding: 'var(--space-2)',
                        textAlign: 'right',
                        fontWeight: 'var(--weight-medium)',
                        color: rs !== null && rs >= 0 ? 'var(--positive)' : 'var(--negative)',
                      }}
                    >
                      {rs !== null ? `${rs >= 0 ? '+' : ''}${rs.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ padding: 'var(--space-2)' }}>
                      {getVolBadge(stock.volume_confirmation)}
                    </td>
                    <td style={{ padding: 'var(--space-2)' }}>
                      {getOrbBadge(stock.opening_range_state)}
                    </td>
                    <td style={{ padding: 'var(--space-2)', textAlign: 'right', fontWeight: 'var(--weight-bold)' }}>
                      <span style={{ color: stock.context_score >= 70 ? 'var(--positive)' : stock.context_score <= 40 ? 'var(--negative)' : 'var(--text-primary)' }}>
                        {stock.context_score.toFixed(0)}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
