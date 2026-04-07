import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import BalanceCard from '../components/BalanceCard';
import { Balance, Operation, OperationType } from '../types';

describe('BalanceCard', () => {
  const mockBalance: Balance = {
    id: '1',
    name: 'Test Balance',
    initialAmount: 1000,
    position: 0,
  };

  const mockOperations: Operation[] = [
    {
      id: 'op1',
      balanceId: '1',
      name: 'Salary',
      description: 'Monthly salary',
      group: 'Income',
      amount: 2000,
      type: OperationType.INCOME,
      date: '2025-01-01',
    },
  ];

  it('displays end balance computed from startBalance + operations', () => {
    // startBalance = 3000, income = 2000 => endBalance = 5000
    render(
      <BalanceCard
        balance={mockBalance}
        operations={mockOperations}
        startBalance={3000}
        isSelected={false}
        onClick={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    // endBalance = 3000 + 2000 = 5000
    expect(screen.getByText(/5\s?000/)).toBeInTheDocument();
  });

  it('displays start balance, income and expenses based on passed operations', () => {
    render(
      <BalanceCard
        balance={mockBalance}
        operations={mockOperations}
        startBalance={3000}
        isSelected={false}
        onClick={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    // Start balance should be 3000
    expect(screen.getByText(/3\s?000/)).toBeInTheDocument();
    // Income should be 2000
    expect(screen.getByText(/2\s?000/)).toBeInTheDocument();
  });
});
