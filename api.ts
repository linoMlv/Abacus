import { Association, Operation, OperationType, Balance } from './types';

const API_URL = '/api';

const mapAssociationData = (data: any): Association => {
    const mappedOperations = data.operations.map((op: any) => ({
        ...op,
        balanceId: op.balance_id || op.balanceId
    }));

    const mappedBalances = data.balances.map((balance: any) => ({
        ...balance,
        operations: balance.operations.map((op: any) => ({
            ...op,
            balanceId: op.balance_id || op.balanceId
        }))
    }));

    return {
        ...data,
        operations: mappedOperations,
        balances: mappedBalances
    };
};

export const api = {
    async signup(name: string, password: string, balances: { name: string; amount: string }[]): Promise<Association> {
        const response = await fetch(`${API_URL}/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, password, balances }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Signup failed');
        }
        const data = await response.json();
        return mapAssociationData(data);
    },

    async login(name: string, password: string): Promise<Association> {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, password }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        const data = await response.json();
        localStorage.setItem('abacus_token', data.access_token);
        return mapAssociationData(data.association);
    },

    async getAssociation(id: string): Promise<Association> {
        const token = localStorage.getItem('abacus_token');
        const headers: HeadersInit = {
            'Authorization': `Bearer ${token}`
        };

        const response = await fetch(`${API_URL}/associations/${id}`, {
            headers
        });

        if (!response.ok) {
            throw new Error('Failed to fetch association');
        }
        const data = await response.json();
        return mapAssociationData(data);
    },

    async createOperation(operation: {
        name: string;
        description: string;
        group: string;
        amount: number;
        type: OperationType;
        date: string;
        balance_id: string;
        invoice?: string;
    }): Promise<Operation> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/operations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(operation),
        });
        if (!response.ok) {
            throw new Error('Failed to create operation');
        }
        const data = await response.json();
        return {
            ...data,
            balanceId: data.balance_id,
        };
    },

    async updateOperation(operation: Operation): Promise<Operation> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/operations/${operation.id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                name: operation.name,
                description: operation.description,
                group: operation.group,
                amount: operation.amount,
                type: operation.type,
                date: operation.date,
                balance_id: operation.balanceId,
                invoice: operation.invoice
            }),
        });
        if (!response.ok) {
            throw new Error('Failed to update operation');
        }
        const data = await response.json();
        return {
            ...data,
            balanceId: data.balance_id,
        };
    },

    async deleteOperation(id: string): Promise<void> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/operations/${id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (!response.ok) {
            throw new Error('Failed to delete operation');
        }
    },

    async addBalance(name: string, initialAmount: number, associationId: string): Promise<any> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/balances_add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ name, initialAmount, association_id: associationId }),
        });
        if (!response.ok) {
            throw new Error('Failed to add balance');
        }
        return response.json();
    },

    async updateBalance(balance: Balance): Promise<Balance> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/balances/${balance.id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                name: balance.name,
                initialAmount: balance.initialAmount,
                position: balance.position,
            }),
        });
        if (!response.ok) {
            throw new Error('Failed to update balance');
        }
        return response.json();
    },

    async deleteBalance(balanceId: string): Promise<void> {
        const token = localStorage.getItem('abacus_token');
        const response = await fetch(`${API_URL}/balances/${balanceId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (!response.ok) {
            throw new Error('Failed to delete balance');
        }
    }
};
