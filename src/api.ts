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
  const mappedBalances: Balance[] = data.balances.map((balance) => ({
    ...balance,
    initialAmount: parseFloat(String(balance.initialAmount)),
    operations: [],
  }));

  return {
    ...data,
    operations: [],
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
    cache: 'no-store', // Prevent aggressive browser caching of API responses
  };

  const response = await fetch(url, config);

  // Note: 401 handling is done per-caller (e.g. getMe returns null).
  // Do NOT redirect globally here — it causes an infinite reload loop
  // on the login page since /api/me always returns 401 when unauthenticated.

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

  async getOperationsByDate(start: string, end: string): Promise<Operation[]> {
    const params = new URLSearchParams();
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    const response = await fetchWithAuth(`${API_URL}/operations?${params.toString()}`);
    if (!response.ok) {
      throw new Error('Failed to fetch operations by date');
    }
    const data: BackendOperation[] = await response.json();
    return data.map((op) => ({ ...op, balanceId: op.balance_id, amount: parseFloat(String(op.amount)) }));
  },

  async getAllOperationsUntilDate(end: string): Promise<Operation[]> {
    const response = await fetchWithAuth(`${API_URL}/operations?end_date=${end}`);
    if (!response.ok) {
      throw new Error('Failed to fetch all operations until date');
    }
    const data: BackendOperation[] = await response.json();
    return data.map((op) => ({ ...op, balanceId: op.balance_id, amount: parseFloat(String(op.amount)) }));
  },

  async getOperationsByBalance(balanceId: string, skip: number, limit: number): Promise<Operation[]> {
    const response = await fetchWithAuth(`${API_URL}/balances/${balanceId}/operations?skip=${skip}&limit=${limit}`);
    if (!response.ok) {
      throw new Error('Failed to fetch operations for balance');
    }
    const data: BackendOperation[] = await response.json();
    return data.map((op) => ({ ...op, balanceId: op.balance_id, amount: parseFloat(String(op.amount)) }));
  },

  async reorderBalances(balances: { id: string; position: number }[]): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/balances/reorder`, {
      method: 'PUT',
      body: JSON.stringify({ balances }),
    });
    if (!response.ok) {
      throw new Error('Failed to reorder balances');
    }
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
      operations: [],
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
      operations: [],
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
