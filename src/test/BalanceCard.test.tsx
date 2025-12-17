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

    it('displays the passed currentBalance prop regardless of operations', () => {
        // We pass a currentBalance that is DIFFERENT from what (initial + operations) would yield
        // initial (1000) + income (2000) would be 3000.
        // But we pass 5000 to simulate that there are other operations outside this period.
        const passedBalance = 5000;

        render(
            <BalanceCard
                balance={mockBalance}
                operations={mockOperations}
                currentBalance={passedBalance}
                isSelected={false}
                onClick={vi.fn()}
                onEdit={vi.fn()}
                onDelete={vi.fn()}
            />
        );

        // The display should show the formatted currency of the passed balance
        // 5000 EUR -> "5 000,00 €" or similar depending on locale, but checking for the number 5000 is safe if we look for text content
        // We can just check that it does NOT display 3000 (the calculated one)
        expect(screen.getByText(/5\s?000/)).toBeInTheDocument();
    });

    it('displays income and expenses based on passed operations', () => {
        render(
            <BalanceCard
                balance={mockBalance}
                operations={mockOperations}
                currentBalance={5000}
                isSelected={false}
                onClick={vi.fn()}
                onEdit={vi.fn()}
                onDelete={vi.fn()}
            />
        );

        // Income should be 2000
        expect(screen.getByText(/2\s?000/)).toBeInTheDocument();
    });
});
