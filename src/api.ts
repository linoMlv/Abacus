import { Association, Operation, OperationType, Balance } from './types';

const API_URL = '/api';

interface BackendOperation {
  id: string;
  name: string;
  description: string;
  group: string;
  amount: number;
  type: OperationType;
  date: string;
  balance_id: string;
  invoice?: string;
}

interface BackendBalance {
  id: string;
  name: string;
  initialAmount: number;
  position: number;
  operations: BackendOperation[];
}

interface BackendAssociation {
  id: string;
  name: string;
  balances: BackendBalance[];
  operations: BackendOperation[];
}

const mapAssociationData = (data: BackendAssociation): Association => {
  const mappedOperations: Operation[] = data.operations.map((op) => ({
    ...op,
    balanceId: op.balance_id,
  }));

  const mappedBalances: Balance[] = data.balances.map((balance) => ({
    ...balance,
    operations: balance.operations.map((op) => ({
      ...op,
      balanceId: op.balance_id,
    })),
  }));

  return {
    ...data,
    operations: mappedOperations,
    balances: mappedBalances,
  };
};

/**
 * Generic fetch wrapper to handle credentials and common headers.
 */
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // Tells the browser to send cookies with the request
  };

  const response = await fetch(url, config);

  if (response.status === 401) {
    // Optional: Redirect to login or dispatch an event if 401 occurs
    // window.location.href = '/';
    // We let the caller handle the error, but this is a good place for global hooks
  }

  return response;
}

export const api = {
  async signup(
    name: string,
    password: string,
    balances: { name: string; amount: string }[]
  ): Promise<Association> {
    const response = await fetchWithAuth(`${API_URL}/signup`, {
      method: 'POST',
      body: JSON.stringify({ name, password, balances }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Signup failed');
    }
    const data: BackendAssociation = await response.json();
    return mapAssociationData(data);
  },

  async login(name: string, password: string): Promise<Association> {
    const response = await fetchWithAuth(`${API_URL}/login`, {
      method: 'POST',
      body: JSON.stringify({ name, password }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    const data = await response.json();
    // No need to store token in localStorage, cookie is set by server
    return mapAssociationData(data.association);
  },

  async getMe(): Promise<Association | null> {
    const response = await fetchWithAuth(`${API_URL}/me`);
    if (!response.ok) {
      return null;
    }
    const data: BackendAssociation = await response.json();
    return mapAssociationData(data);
  },

  async logout(): Promise<void> {
    await fetchWithAuth(`${API_URL}/logout`, {
      method: 'POST',
    });
    // Can optionally clear local client state here if needed
  },

  async getAssociation(id: string): Promise<Association> {
    const response = await fetchWithAuth(`${API_URL}/associations/${id}`);

    if (!response.ok) {
      throw new Error('Failed to fetch association');
    }
    const data: BackendAssociation = await response.json();
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
    const response = await fetchWithAuth(`${API_URL}/operations`, {
      method: 'POST',
      body: JSON.stringify(operation),
    });
    if (!response.ok) {
      throw new Error('Failed to create operation');
    }
    const data: BackendOperation = await response.json();
    return {
      ...data,
      balanceId: data.balance_id,
    };
  },

  async updateOperation(operation: Operation): Promise<Operation> {
    const response = await fetchWithAuth(`${API_URL}/operations/${operation.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: operation.name,
        description: operation.description,
        group: operation.group,
        amount: operation.amount,
        type: operation.type,
        date: operation.date,
        balance_id: operation.balanceId,
        invoice: operation.invoice,
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to update operation');
    }
    const data: BackendOperation = await response.json();
    return {
      ...data,
      balanceId: data.balance_id,
    };
  },

  async deleteOperation(id: string): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/operations/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete operation');
    }
  },

  async addBalance(name: string, initialAmount: number, associationId: string): Promise<Balance> {
    const response = await fetchWithAuth(`${API_URL}/balances_add`, {
      method: 'POST',
      body: JSON.stringify({ name, initialAmount, association_id: associationId }),
    });
    if (!response.ok) {
      throw new Error('Failed to add balance');
    }
    const data: BackendBalance = await response.json();
    return {
      ...data,
      operations: (data.operations || []).map((op) => ({
        ...op,
        balanceId: op.balance_id,
      })),
    };
  },

  async updateBalance(balance: Balance): Promise<Balance> {
    const response = await fetchWithAuth(`${API_URL}/balances/${balance.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: balance.name,
        initialAmount: balance.initialAmount,
        position: balance.position,
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to update balance');
    }
    const data: BackendBalance = await response.json();
    return {
      ...data,
      operations: (data.operations || []).map((op) => ({
        ...op,
        balanceId: op.balance_id,
      })),
    };
  },

  async deleteBalance(balanceId: string): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/balances/${balanceId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete balance');
    }
  },
};
