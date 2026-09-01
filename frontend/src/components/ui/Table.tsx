import React from 'react';

export interface TableColumn<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  isNumeric?: boolean;
  width?: string;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage = 'No data records found',
}: TableProps<T>) {
  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead>
          <tr style={{ backgroundColor: 'var(--bg-surface-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 'var(--weight-medium)',
                  color: 'var(--text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  textAlign: col.align || (col.isNumeric ? 'right' : 'left'),
                  width: col.width,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  padding: 'var(--space-8)',
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                  fontSize: 'var(--text-sm)',
                }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr
                key={keyExtractor(item)}
                onClick={() => onRowClick && onRowClick(item)}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  if (onRowClick) e.currentTarget.style.backgroundColor = 'var(--bg-surface-elevated)';
                }}
                onMouseLeave={(e) => {
                  if (onRowClick) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {columns.map((col) => {
                  const val = (item as any)[col.key];
                  return (
                    <td
                      key={col.key}
                      style={{
                        padding: 'var(--space-2) var(--space-3)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--text-primary)',
                        textAlign: col.align || (col.isNumeric ? 'right' : 'left'),
                        fontFamily: col.isNumeric ? 'var(--font-mono)' : 'var(--font-sans)',
                        fontVariantNumeric: col.isNumeric ? 'tabular-nums' : undefined,
                      }}
                    >
                      {col.render ? col.render(item) : val !== undefined && val !== null ? String(val) : '—'}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
