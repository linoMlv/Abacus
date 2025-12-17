import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Balance, Operation, OperationType } from '../../types';
import { useAddOperation, useUpdateOperation } from '../../hooks/useAbacusData';

interface OperationFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  operationToEdit?: Operation | null;
  balances: Balance[];
  existingGroups: string[];
}

const OperationFormModal: React.FC<OperationFormModalProps> = ({
  isOpen,
  onClose,
  operationToEdit,
  balances,
  existingGroups,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [group, setGroup] = useState('');
  const [isGroupDropdownOpen, setIsGroupDropdownOpen] = useState(false);
  const [filteredGroups, setFilteredGroups] = useState<string[]>([]);
  const groupInputRef = useRef<HTMLInputElement>(null);
  const groupDropdownRef = useRef<HTMLUListElement>(null);
  const [amount, setAmount] = useState('');
  const [type, setType] = useState<OperationType>(OperationType.EXPENSE);
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [balanceId, setBalanceId] = useState<string>('');
  const [invoice, setInvoice] = useState<string>('');

  const addMutation = useAddOperation();
  const updateMutation = useUpdateOperation();

  const isSubmitting = addMutation.isPending || updateMutation.isPending;

  const resetFormFields = useCallback(() => {
    setName('');
    setDescription('');
    setGroup('');
    setAmount('');
    setType(OperationType.EXPENSE);
    setDate(new Date().toISOString().split('T')[0]);
    if (balances.length > 0) setBalanceId(balances[0].id);
    setInvoice('');
  }, [balances]);

  useEffect(() => {
    if (operationToEdit) {
      setName(operationToEdit.name);
      setDescription(operationToEdit.description);
      setGroup(operationToEdit.group);
      setAmount(operationToEdit.amount.toString());
      setType(operationToEdit.type);
      setDate(new Date(operationToEdit.date).toISOString().split('T')[0]);
      setBalanceId(operationToEdit.balanceId);
      setInvoice(operationToEdit.invoice || '');
    } else if (balances.length > 0) {
      setBalanceId(balances[0].id);
      resetFormFields();
    }
  }, [balances, operationToEdit, isOpen, resetFormFields]);

  useEffect(() => {
    if (isOpen) {
      setFilteredGroups(existingGroups);
    }
  }, [isOpen, existingGroups]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        groupDropdownRef.current &&
        !groupDropdownRef.current.contains(event.target as Node) &&
        groupInputRef.current &&
        !groupInputRef.current.contains(event.target as Node)
      ) {
        setIsGroupDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleGroupChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setGroup(value);
    setFilteredGroups(existingGroups.filter((g) => g.toLowerCase().includes(value.toLowerCase())));
    setIsGroupDropdownOpen(true);
  };

  const handleGroupSelect = (selectedGroup: string) => {
    setGroup(selectedGroup);
    setIsGroupDropdownOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !amount || !balanceId || !group) {
      return; // Add proper validation UI later
    }

    const operationData = {
      name,
      description,
      group,
      amount: parseFloat(amount),
      type,
      date: new Date(date).toISOString(),
      balance_id: balanceId,
      invoice,
    };

    try {
      if (operationToEdit) {
        await updateMutation.mutateAsync({
          ...operationData,
          id: operationToEdit.id,
          balanceId: balanceId, // Ensure consistency
        });
      } else {
        await addMutation.mutateAsync(operationData);
      }
      onClose();
      resetFormFields();
    } catch (error) {
      console.error('Failed to save operation', error);
      // Handle error UI here (e.g. toast)
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex justify-center items-center p-4 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[95vh] overflow-y-auto">
        <div className="flex justify-between items-center p-6 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-800">
            {operationToEdit ? 'Edit Operation' : 'New Operation'}
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
          {/* Type Selector */}
          <div className="flex bg-gray-100 p-1 rounded-lg">
            <button
              type="button"
              onClick={() => setType(OperationType.EXPENSE)}
              className={`flex-1 py-2 rounded-md text-sm font-semibold transition ${type === OperationType.EXPENSE ? 'bg-white text-red-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Expense
            </button>
            <button
              type="button"
              onClick={() => setType(OperationType.INCOME)}
              className={`flex-1 py-2 rounded-md text-sm font-semibold transition ${type === OperationType.INCOME ? 'bg-white text-green-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Income
            </button>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Balance
            </label>
            <select
              value={balanceId}
              onChange={(e) => setBalanceId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition bg-white"
            >
              {balances.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Title
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              placeholder="e.g. Printer Paper"
            />
          </div>

          <div className="relative">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Group
            </label>
            <input
              ref={groupInputRef}
              type="text"
              placeholder="Category..."
              value={group}
              onChange={handleGroupChange}
              onFocus={() => setIsGroupDropdownOpen(true)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
            />
            {isGroupDropdownOpen && (
              <ul
                ref={groupDropdownRef}
                className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-auto py-1"
              >
                {filteredGroups.length > 0 ? (
                  filteredGroups.map((g) => (
                    <li
                      key={g}
                      onClick={() => handleGroupSelect(g)}
                      className="px-4 py-2 hover:bg-gray-50 cursor-pointer text-sm text-gray-700"
                    >
                      {g}
                    </li>
                  ))
                ) : (
                  <li className="px-4 py-2 text-sm text-gray-500 italic">
                    Type to create "{group}"
                  </li>
                )}
              </ul>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Amount
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-gray-400">€</span>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full pl-8 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Date
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition resize-none"
            ></textarea>
          </div>

          {type === OperationType.EXPENSE && (
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Invoice URL
              </label>
              <input
                type="url"
                placeholder="https://..."
                value={invoice}
                onChange={(e) => setInvoice(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              />
            </div>
          )}

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
              {operationToEdit ? 'Save Changes' : 'Add Operation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default OperationFormModal;
