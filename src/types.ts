export enum OperationType {
  INCOME = 'income',
  EXPENSE = 'expense',
}

export interface Operation {
  id: string;
  balanceId: string;
  name: string;
  description: string;
  group: string;
  amount: number;
  type: OperationType;
  date: string;
  invoice?: string;
}

export interface Balance {
  id: string;
  name: string;
  initialAmount: number;
  position: number;
  operations?: Operation[];
}

export interface Association {
  id: string;
  name: string;
  password?: string;
  balances: Balance[];
  operations: Operation[];
}
