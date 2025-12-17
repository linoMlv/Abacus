import React, { useState, useMemo, useEffect } from 'react';
import { Association, Balance, Operation, OperationType } from '../types';
import { startOfMonth, endOfMonth } from 'date-fns';
import { useDeleteBalance, useDeleteOperation, useUpdateBalance } from '../hooks/useAbacusData';

// Components
import Header from './Header';
import BalanceCard from './BalanceCard';
import OperationsChart from './OperationsChart';
import OperationsTable from './OperationsTable';
import ErrorBoundary from './ErrorBoundary';
import ConfirmationModal from './ConfirmationModal';
import OperationFormModal from './dashboard/OperationFormModal';
import BalanceFormModal from './dashboard/BalanceFormModal';

interface DashboardProps {
  association: Association;
  onLogout: () => void;
  // onUpdateAssociation is no longer needed as React Query handles data updates
  onUpdateAssociation?: (association: Association) => void;
}

const Dashboard: React.FC<DashboardProps> = ({ association, onLogout }) => {
  const today = new Date();

  // --- Local State ---
  const [dateRange, setDateRange] = useState<{ start: Date; end: Date }>(() => {
    const stored = localStorage.getItem('abacus-date-range');
    if (stored) {
      try {
        const { start, end } = JSON.parse(stored);
        return { start: new Date(start), end: new Date(end) };
      } catch (e) {
        console.error('Failed to parse date range', e);
      }
    }
    return { start: startOfMonth(today), end: endOfMonth(today) };
  });

  useEffect(() => {
    localStorage.setItem('abacus-date-range', JSON.stringify(dateRange));
  }, [dateRange]);

  const [selectedBalanceId, setSelectedBalanceId] = useState<string | null>(null);

  // Auto-select first balance
  useEffect(() => {
    if (!selectedBalanceId && association.balances.length > 0) {
      const sortedBalances = [...association.balances].sort((a, b) => a.position - b.position);
      setSelectedBalanceId(sortedBalances[0].id);
    } else if (selectedBalanceId && !association.balances.find((b) => b.id === selectedBalanceId)) {
      // If selected balance was deleted
      setSelectedBalanceId(association.balances.length > 0 ? association.balances[0].id : null);
    }
  }, [association.balances, selectedBalanceId]);

  // Modals State
  const [isOpModalOpen, setIsOpModalOpen] = useState(false);
  const [opToEdit, setOpToEdit] = useState<Operation | null>(null);

  const [isBalanceModalOpen, setIsBalanceModalOpen] = useState(false);
  const [balanceToEdit, setBalanceToEdit] = useState<Balance | null>(null);

  const [isDeleteBalanceModalOpen, setIsDeleteBalanceModalOpen] = useState(false);
  const [balanceToDeleteId, setBalanceToDeleteId] = useState<string | null>(null);

  // --- Mutations ---
  const deleteOperationMutation = useDeleteOperation();
  const deleteBalanceMutation = useDeleteBalance();
  const updateBalanceMutation = useUpdateBalance();

  // --- Computed Data ---
  const filteredOperations = useMemo(() => {
    return (association.operations || []).filter((op) => {
      const opDate = new Date(op.date);
      return opDate >= dateRange.start && opDate <= dateRange.end;
    });
  }, [association.operations, dateRange]);

  const selectedBalance = useMemo(() => {
    return (association.balances || []).find((b) => b.id === selectedBalanceId) ?? null;
  }, [association.balances, selectedBalanceId]);

  const operationsUntilEndOfPeriod = useMemo(() => {
    return (association.operations || []).filter((op) => {
      const opDate = new Date(op.date);
      return opDate <= dateRange.end;
    });
  }, [association.operations, dateRange.end]);

  const operationsForSelectedBalance = useMemo(() => {
    return filteredOperations.filter((op) => op.balanceId === selectedBalanceId);
  }, [filteredOperations, selectedBalanceId]);

  const incomesForSelectedBalance = operationsForSelectedBalance.filter(
    (op) => op.type === OperationType.INCOME
  );
  const expensesForSelectedBalance = operationsForSelectedBalance.filter(
    (op) => op.type === OperationType.EXPENSE
  );

  const existingGroups = useMemo(() => {
    const groups = new Set((association.operations || []).map((op) => op.group));
    return Array.from(groups).sort();
  }, [association.operations]);

  // --- Handlers ---

  // Scroll Logic
  const scrollContainerRef = React.useRef<HTMLDivElement>(null);
  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = 320;
      const newScrollLeft =
        scrollContainerRef.current.scrollLeft +
        (direction === 'right' ? scrollAmount : -scrollAmount);
      scrollContainerRef.current.scrollTo({ left: newScrollLeft, behavior: 'smooth' });
    }
  };

  // Operation Handlers
  const handleEditOperation = (operation: Operation) => {
    setOpToEdit(operation);
    setIsOpModalOpen(true);
  };

  const handleDeleteOperation = async (operationId: string) => {
    if (confirm('Are you sure you want to delete this operation?')) {
      deleteOperationMutation.mutate(operationId);
    }
  };

  const handleCloseOpModal = () => {
    setIsOpModalOpen(false);
    setOpToEdit(null);
  };

  // Balance Handlers
  const handleEditBalance = (balance: Balance) => {
    setBalanceToEdit(balance);
    setIsBalanceModalOpen(true);
  };

  const handleDeleteBalance = (balanceId: string) => {
    setBalanceToDeleteId(balanceId);
    setIsDeleteBalanceModalOpen(true);
  };

  const confirmDeleteBalance = () => {
    if (balanceToDeleteId) {
      deleteBalanceMutation.mutate(balanceToDeleteId);
      setIsDeleteBalanceModalOpen(false);
      setBalanceToDeleteId(null);
    }
  };

  const handleCloseBalanceModal = () => {
    setIsBalanceModalOpen(false);
    setBalanceToEdit(null);
  };

  // Drag & Drop Handlers (Optimistic update handled here for UX, then mutation)
  const [draggedBalanceIndex, setDraggedBalanceIndex] = useState<number | null>(null);

  const handleDragStart = (index: number) => setDraggedBalanceIndex(index);
  const handleDragOver = (e: React.DragEvent) => e.preventDefault();

  const handleDrop = async (dropIndex: number) => {
    if (draggedBalanceIndex === null || draggedBalanceIndex === dropIndex) return;

    // Calculate new positions locally to visualize immediately
    const sortedBalances = [...association.balances].sort((a, b) => a.position - b.position);
    const [draggedBalance] = sortedBalances.splice(draggedBalanceIndex, 1);
    sortedBalances.splice(dropIndex, 0, draggedBalance);

    // Update all affected balances
    const updates = sortedBalances.map((b, index) => ({ ...b, position: index }));

    // Ideally we would update local state via a specialized hook or optimistic update in React Query
    // For now, we fire requests.
    try {
      await Promise.all(updates.map((b) => updateBalanceMutation.mutateAsync(b)));
    } catch (err) {
      console.error('Failed to reorder', err);
    }
    setDraggedBalanceIndex(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      <Header
        associationName={association.name}
        onLogout={onLogout}
        dateRange={dateRange}
        setDateRange={setDateRange}
        operations={association.operations}
        balances={association.balances}
      />

      <main className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-8">
        {/* Actions Row */}
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-800">Balances</h2>
          <div className="flex space-x-3">
            <button
              onClick={() => {
                setBalanceToEdit(null);
                setIsBalanceModalOpen(true);
              }}
              className="bg-white text-gray-700 border border-gray-200 px-4 py-2 rounded-lg font-semibold hover:bg-gray-50 hover:border-gray-300 transition flex items-center space-x-2 shadow-sm"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-gray-500"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>Add Balance</span>
            </button>
            <button
              onClick={() => {
                setOpToEdit(null);
                setIsOpModalOpen(true);
              }}
              className="bg-gray-900 text-white px-4 py-2 rounded-lg font-semibold hover:bg-black transition flex items-center space-x-2 shadow-lg shadow-gray-200"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>Add Operation</span>
            </button>
          </div>
        </div>

        {/* Balances Carousel */}
        <div className="relative group">
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 -ml-4 z-10 bg-white rounded-full p-2 shadow-lg border border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
          >
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
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>

          <div
            ref={scrollContainerRef}
            className="flex space-x-6 overflow-x-auto pb-4 pt-1 px-1 scrollbar-hide snap-x"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {association.balances
              .sort((a, b) => a.position - b.position)
              .map((balance, index) => {
                const balanceOpsUntilEnd = operationsUntilEndOfPeriod.filter(
                  (op) => op.balanceId === balance.id
                );
                const totalIncome = balanceOpsUntilEnd
                  .filter((op) => op.type === OperationType.INCOME)
                  .reduce((sum, op) => sum + op.amount, 0);
                const totalExpenses = balanceOpsUntilEnd
                  .filter((op) => op.type === OperationType.EXPENSE)
                  .reduce((sum, op) => sum + op.amount, 0);
                const currentBalance = balance.initialAmount + totalIncome - totalExpenses;

                return (
                  <div
                    key={balance.id}
                    className="snap-center flex-shrink-0 w-80 transform transition-transform"
                    draggable
                    onDragStart={() => handleDragStart(index)}
                    onDragOver={handleDragOver}
                    onDrop={() => handleDrop(index)}
                  >
                    <BalanceCard
                      balance={balance}
                      operations={filteredOperations.filter((op) => op.balanceId === balance.id)}
                      currentBalance={currentBalance}
                      isSelected={selectedBalanceId === balance.id}
                      onClick={() => setSelectedBalanceId(balance.id)}
                      onEdit={handleEditBalance}
                      onDelete={handleDeleteBalance}
                    />
                  </div>
                );
              })}
          </div>

          <button
            onClick={() => scroll('right')}
            className="absolute right-0 top-1/2 -translate-y-1/2 -mr-4 z-10 bg-white rounded-full p-2 shadow-lg border border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Chart Section */}
          <div className="lg:col-span-3 bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-bold text-gray-800 mb-6">Financial Overview</h3>
            <ErrorBoundary>
              <OperationsChart
                balances={association.balances}
                allOperations={association.operations}
                dateRange={dateRange}
              />
            </ErrorBoundary>
          </div>

          {/* Operations Tables */}
          {selectedBalance && (
            <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 h-full">
                <OperationsTable
                  title="Income"
                  operations={incomesForSelectedBalance}
                  onEdit={handleEditOperation}
                  onDelete={handleDeleteOperation}
                />
              </div>
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 h-full">
                <OperationsTable
                  title="Expenses"
                  operations={expensesForSelectedBalance}
                  onEdit={handleEditOperation}
                  onDelete={handleDeleteOperation}
                />
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Modals */}
      <OperationFormModal
        isOpen={isOpModalOpen}
        onClose={handleCloseOpModal}
        operationToEdit={opToEdit}
        balances={association.balances}
        existingGroups={existingGroups}
      />

      <BalanceFormModal
        isOpen={isBalanceModalOpen}
        onClose={handleCloseBalanceModal}
        balanceToEdit={balanceToEdit}
        associationId={association.id}
      />

      <ConfirmationModal
        isOpen={isDeleteBalanceModalOpen}
        onClose={() => setIsDeleteBalanceModalOpen(false)}
        onConfirm={confirmDeleteBalance}
        title="Delete Balance"
        message="Are you sure you want to delete this balance? All operations linked to it will be permanently lost."
        confirmText="Delete Balance"
        isDanger={true}
      />
    </div>
  );
};

export default Dashboard;
