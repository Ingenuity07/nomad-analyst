import React, { useState, useEffect } from 'react';

export const ISTClock: React.FC = () => {
  const [timeStr, setTimeStr] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const istTime = now.toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setTimeStr(`${istTime} IST`);
    };

    updateTime();
    const intervalId = setInterval(updateTime, 1000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1-5)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
      <span style={{ color: 'var(--text-muted)' }}>🕒</span>
      <span>{timeStr || '--:--:-- IST'}</span>
    </div>
  );
};
