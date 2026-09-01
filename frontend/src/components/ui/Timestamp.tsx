import React from 'react';

export interface TimestampProps {
  isoString?: string | null;
  format?: 'time' | 'date' | 'full';
}

export const Timestamp: React.FC<TimestampProps> = ({ isoString, format = 'time' }) => {
  if (!isoString) return <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>—</span>;

  let formatted = isoString;
  try {
    const dt = new Date(isoString);
    if (format === 'time') {
      formatted = dt.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false }) + ' IST';
    } else if (format === 'date') {
      formatted = dt.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
    } else {
      formatted = `${dt.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short' })} ${dt.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })} IST`;
    }
  } catch {
    formatted = isoString;
  }

  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
      {formatted}
    </span>
  );
};
