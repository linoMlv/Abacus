import React, { useState, useEffect } from 'react';
import { Balance } from '../../types';
import { useAddBalance, useUpdateBalance } from '../../hooks/useAbacusData';

interface BalanceFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  balanceToEdit?: Balance | null;
  associationId: string;
}

const BalanceFormModal: React.FC<BalanceFormModalProps> = ({
  isOpen,
  onClose,
  balanceToEdit,
  associationId,
}) => {
  const [name, setName] = useState('');
  const [initialAmount, setInitialAmount] = useState('');

  const addMutation = useAddBalance();
  const updateMutation = useUpdateBalance();
  const isSubmitting = addMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (balanceToEdit) {
      setName(balanceToEdit.name);
      setInitialAmount(balanceToEdit.initialAmount.toString());
    } else {
      setName('');
      setInitialAmount('');
    }
  }, [balanceToEdit, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !initialAmount) {
      return;
    }

    try {
      if (balanceToEdit) {
        await updateMutation.mutateAsync({
          ...balanceToEdit,
          name,
          initialAmount: parseFloat(initialAmount),
        });
      } else {
        await addMutation.mutateAsync({
          name,
          initialAmount: parseFloat(initialAmount),
          associationId,
        });
      }
      onClose();
      if (!balanceToEdit) {
        setName('');
        setInitialAmount('');
      }
    } catch (error) {
      console.error('Failed to save balance', error);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex justify-center items-center p-4 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
        <div className="flex justify-between items-center p-6 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-800">
            {balanceToEdit ? 'Edit Balance' : 'New Balance'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Balance Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              placeholder="e.g., Main Account"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Initial Amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-gray-400">€</span>
              <input
                type="number"
                step="0.01"
                value={initialAmount}
                onChange={(e) => setInitialAmount(e.target.value)}
                className="w-full pl-8 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
                placeholder="0.00"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2 gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-5 py-2.5 rounded-lg font-medium text-gray-600 hover:bg-gray-100 transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-gray-900 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-black transition shadow-lg shadow-gray-200 disabled:opacity-50 flex items-center"
            >
              {isSubmitting && (
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
              )}
              {balanceToEdit ? 'Save Changes' : 'Add Balance'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default BalanceFormModal;
