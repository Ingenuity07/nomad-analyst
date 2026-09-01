import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PageContainer } from '@/components/layout/PageContainer';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export const StocksPageShell: React.FC = () => {
  const navigate = useNavigate();

  return (
    <PageContainer
      title="Stocks & Research Directory"
      subtitle="Search and analyze audited balance sheets, technical indicator trees, and interactive charts"
    >
      <Card header="Stock Directory Workspace (FE-5 Target)">
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6 }}>
          Type any NSE symbol in the top header search bar or select a quick demonstration profile below:
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
          <Button variant="secondary" onClick={() => navigate('/stocks/RELIANCE')}>
            Open RELIANCE Terminal →
          </Button>
          <Button variant="outline" onClick={() => navigate('/stocks/TCS')}>
            Open TCS Terminal →
          </Button>
          <Button variant="outline" onClick={() => navigate('/stocks/INFY')}>
            Open INFY Terminal →
          </Button>
        </div>
      </Card>
    </PageContainer>
  );
};
