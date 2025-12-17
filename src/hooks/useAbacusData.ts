import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { Operation, Balance, OperationType } from '../types';

// Keys
export const keys = {
  me: ['me'],
  association: (id: string) => ['association', id],
};

// --- Queries ---

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api.getMe(),
    retry: false, // Don't retry on 401
  });
}

export function useAssociation(id: string | undefined) {
  return useQuery({
    queryKey: keys.association(id!),
    queryFn: () => api.getAssociation(id!),
    enabled: !!id,
  });
}

// --- Mutations ---

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, password }: { name: string; password: string }) =>
      api.login(name, password),
    onSuccess: (data) => {
      queryClient.setQueryData(keys.me, data);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      queryClient.setQueryData(keys.me, null);
      queryClient.removeQueries({ queryKey: ['association'] });
    },
  });
}

export function useAddOperation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (op: {
      name: string;
      description: string;
      group: string;
      amount: number;
      type: OperationType;
      date: string;
      balance_id: string;
      invoice?: string;
    }) => api.createOperation(op),
    onSuccess: (_, _variables) => {
      // Invalidate relevant association to re-fetch fresh data
      // (Finding the association ID is tricky without passing it, 
      // but usually we are in a context where we know it. 
      // For simplicity, we invalidate all associations or we rely on the component to refetch)
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}
export function useUpdateOperation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (op: Operation) => api.updateOperation(op),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}

export function useDeleteOperation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteOperation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}

export function useAddBalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      initialAmount,
      associationId,
    }: {
      name: string;
      initialAmount: number;
      associationId: string;
    }) => api.addBalance(name, initialAmount, associationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}

export function useUpdateBalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (balance: Balance) => api.updateBalance(balance),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}

export function useDeleteBalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteBalance(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association'] });
    },
  });
}
