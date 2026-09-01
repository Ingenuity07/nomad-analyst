import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Table, TableColumn } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { MonitorRule, MonitorRuleType } from '../storage';

export interface CustomMonitorManagerProps {
  rules: MonitorRule[];
  onAddRule: (rule: Omit<MonitorRule, 'id' | 'createdAt' | 'updatedAt'>) => void;
  onToggleRule: (id: string) => void;
  onDeleteRule: (id: string) => void;
  availableWatchedSymbols?: string[];
}

export const CustomMonitorManager: React.FC<CustomMonitorManagerProps> = ({
  rules,
  onAddRule,
  onToggleRule,
  onDeleteRule,
  availableWatchedSymbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK'],
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [ruleType, setRuleType] = useState<MonitorRuleType>('PRICE_ABOVE');
  const [symbol, setSymbol] = useState(availableWatchedSymbols[0] || 'RELIANCE');
  const [threshold, setThreshold] = useState<string>('3000');
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (e?: React.SyntheticEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    setFormError(null);

    const isPriceRule = ruleType === 'PRICE_ABOVE' || ruleType === 'PRICE_BELOW';
    const isOppRule = ruleType === 'OPPORTUNITY_SCORE_ABOVE';

    if (isPriceRule || isOppRule) {
      const num = Number(threshold);
      if (isNaN(num) || num <= 0) {
        setFormError('Please enter a valid numeric threshold greater than 0.');
        return;
      }
    }

    onAddRule({
      type: ruleType,
      symbol: isPriceRule ? symbol.trim().toUpperCase() : undefined,
      threshold: isPriceRule || isOppRule ? Number(threshold) : undefined,
      enabled: true,
      baselineEstablished: true,
    });

    setIsModalOpen(false);
    setThreshold('3000');
  };

  const formatRuleCondition = (rule: MonitorRule) => {
    switch (rule.type) {
      case 'PRICE_ABOVE':
        return `Price > ₹${rule.threshold}`;
      case 'PRICE_BELOW':
        return `Price < ₹${rule.threshold}`;
      case 'NEW_ACTIVE_BUY':
        return 'New Active BUY Strategy Signal';
      case 'OPPORTUNITY_SCORE_ABOVE':
        return `Opportunity Score >= ${rule.threshold}/100`;
      case 'REGIME_SHIFT_TO_BEARISH':
        return 'Market Regime Transition to BEARISH';
      default:
        return rule.type;
    }
  };

  const columns: TableColumn<MonitorRule>[] = [
    {
      key: 'target',
      header: 'Target / Scope',
      render: (r) => (
        <span style={{ fontWeight: 'var(--weight-bold)', fontFamily: 'var(--font-mono)', color: 'var(--brand-primary)' }}>
          {r.symbol || 'MARKET-WIDE'}
        </span>
      ),
    },
    {
      key: 'condition',
      header: 'Trigger Condition',
      render: (r) => formatRuleCondition(r),
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <Badge variant={r.enabled ? 'positive' : 'neutral'} size="sm">
          {r.enabled ? 'ACTIVE' : 'PAUSED'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div style={{ display: 'flex', gap: 'var(--space-1-5)' }}>
          <Button
            data-testid={`toggle-rule-${r.id}`}
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onToggleRule(r.id);
            }}
          >
            {r.enabled ? '⏸ Pause' : '▶ Resume'}
          </Button>
          <Button
            data-testid={`delete-rule-${r.id}`}
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onDeleteRule(r.id);
            }}
          >
            🗑️ Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card
      header="Configured Monitor Rules"
      action={
        <Button
          data-testid="add-monitor-rule-btn"
          type="button"
          variant="primary"
          size="sm"
          onClick={() => setIsModalOpen(true)}
        >
          + Add Monitor Rule
        </Button>
      }
      data-testid="custom-monitor-manager"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        <Table
          columns={columns}
          data={rules}
          keyExtractor={(r) => r.id}
          emptyMessage="No monitor rules configured. Add a rule to begin live event tracking."
        />
      </div>

      {/* Add Rule Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add Custom Monitor Rule"
      >
        <form
          data-testid="add-monitor-rule-form"
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
        >
          {/* Rule Type Selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontWeight: 'var(--weight-medium)' }}>
              Condition Type:
            </label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as MonitorRuleType)}
              style={{
                padding: 'var(--space-2)',
                backgroundColor: 'var(--bg-surface-sunken)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--text-primary)',
                fontSize: 'var(--text-xs)',
              }}
            >
              <option value="PRICE_ABOVE">Stock Price Crosses Above (₹)</option>
              <option value="PRICE_BELOW">Stock Price Crosses Below (₹)</option>
              <option value="NEW_ACTIVE_BUY">New Active BUY Recommendation</option>
              <option value="OPPORTUNITY_SCORE_ABOVE">High Opportunity Score (Above Threshold)</option>
              <option value="REGIME_SHIFT_TO_BEARISH">Market Regime Shifts to BEARISH</option>
            </select>
          </div>

          {/* Symbol Selector for Price Rules */}
          {(ruleType === 'PRICE_ABOVE' || ruleType === 'PRICE_BELOW') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <label style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontWeight: 'var(--weight-medium)' }}>
                Target Symbol:
              </label>
              <Input
                placeholder="e.g. RELIANCE, TCS, INFY"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              />
            </div>
          )}

          {/* Threshold Input for Price / Opportunity Rules */}
          {(ruleType === 'PRICE_ABOVE' || ruleType === 'PRICE_BELOW' || ruleType === 'OPPORTUNITY_SCORE_ABOVE') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <label style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontWeight: 'var(--weight-medium)' }}>
                {ruleType === 'OPPORTUNITY_SCORE_ABOVE' ? 'Minimum Opportunity Score (1-100):' : 'Price Threshold (₹):'}
              </label>
              <Input
                data-testid="rule-threshold-input"
                placeholder={ruleType === 'OPPORTUNITY_SCORE_ABOVE' ? '80' : '3000'}
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
              />
            </div>
          )}

          {formError && (
            <div style={{ color: 'var(--negative)', fontSize: 'var(--text-xs)' }}>
              {formError}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button
              data-testid="save-monitor-rule-btn"
              type="button"
              variant="primary"
              size="sm"
              onClick={() => handleSubmit()}
            >
              Save Monitor
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
};
