
import React, { useState, useMemo, useEffect } from 'react';
import { Association, Balance, Operation, OperationType } from '../types';
import { api } from '../api';
import Header from './Header';
import BalanceCard from './BalanceCard';
import OperationsChart from './OperationsChart';
import OperationsTable from './OperationsTable';
import AddOperationModal from './AddOperationModal';
import AddBalanceModal from './AddBalanceModal';
import { format, subDays, startOfMonth, endOfMonth } from 'date-fns';
import ErrorBoundary from './ErrorBoundary';
import ConfirmationModal from './ConfirmationModal';

interface DashboardProps {
    association: Association;
    onLogout: () => void;
    onUpdateAssociation: (association: Association) => void;
}

const Dashboard: React.FC<DashboardProps> = ({ association, onLogout, onUpdateAssociation }) => {
    const today = new Date();
    const [dateRange, setDateRange] = useState<{ start: Date, end: Date }>({ start: startOfMonth(today), end: endOfMonth(today) });
    const [selectedBalanceId, setSelectedBalanceId] = useState<string | null>(null);

    useEffect(() => {
        if (!selectedBalanceId && association.balances.length > 0) {
            const sortedBalances = [...association.balances].sort((a, b) => a.position - b.position);
            setSelectedBalanceId(sortedBalances[0].id);
        }
    }, [association.balances, selectedBalanceId]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isAddBalanceModalOpen, setIsAddBalanceModalOpen] = useState(false);

    const [balanceToEdit, setBalanceToEdit] = useState<Balance | null>(null);
    const [draggedBalanceIndex, setDraggedBalanceIndex] = useState<number | null>(null);

    const [operationToEdit, setOperationToEdit] = useState<Operation | null>(null);
    const [isDeleteBalanceModalOpen, setIsDeleteBalanceModalOpen] = useState(false);
    const [balanceToDeleteId, setBalanceToDeleteId] = useState<string | null>(null);
    const scrollContainerRef = React.useRef<HTMLDivElement>(null);

    const scroll = (direction: 'left' | 'right') => {
        if (scrollContainerRef.current) {
            const scrollAmount = 320;
            const newScrollLeft = scrollContainerRef.current.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);
            scrollContainerRef.current.scrollTo({
                left: newScrollLeft,
                behavior: 'smooth'
            });
        }
    };

    const filteredOperations = useMemo(() => {
        return association.operations.filter(op => {
            const opDate = new Date(op.date);
            return opDate >= dateRange.start && opDate <= dateRange.end;
        });
    }, [association.operations, dateRange]);

    const selectedBalance = useMemo(() => {
        return association.balances.find(b => b.id === selectedBalanceId) ?? null;
    }, [association.balances, selectedBalanceId]);

    const operationsForSelectedBalance = useMemo(() => {
        return filteredOperations.filter(op => op.balanceId === selectedBalanceId);
    }, [filteredOperations, selectedBalanceId]);

    const incomesForSelectedBalance = operationsForSelectedBalance.filter(op => op.type === OperationType.INCOME);
    const expensesForSelectedBalance = operationsForSelectedBalance.filter(op => op.type === OperationType.EXPENSE);

    const existingGroups = useMemo(() => {
        const groups = new Set(association.operations.map(op => op.group));
        return Array.from(groups).sort();
    }, [association.operations]);

    const handleAddOperation = async (newOperationData: Omit<Operation, 'id'>) => {
        try {
            const newOperation = await api.createOperation({
                ...newOperationData,
                balance_id: newOperationData.balanceId,
                date: newOperationData.date,
            });

            const updatedAssociation = {
                ...association,
                operations: [...association.operations, newOperation]
            };
            onUpdateAssociation(updatedAssociation);
            setIsModalOpen(false);
        } catch (error) {
            console.error("Failed to add operation", error);
            alert("Failed to add operation");
        }
    };

    const handleUpdateOperation = async (updatedOperation: Operation) => {
        try {
            const result = await api.updateOperation({
                ...updatedOperation,
                balanceId: updatedOperation.balanceId,
            });

            const updatedAssociation = {
                ...association,
                operations: association.operations.map(op => op.id === result.id ? result : op)
            };
            onUpdateAssociation(updatedAssociation);
            setIsModalOpen(false);
            setOperationToEdit(null);
        } catch (error) {
            console.error("Failed to update operation", error);
            alert("Failed to update operation");
        }
    };

    const handleDeleteOperation = async (operationId: string) => {
        try {
            await api.deleteOperation(operationId);
            const updatedAssociation = {
                ...association,
                operations: association.operations.filter(op => op.id !== operationId)
            };
            onUpdateAssociation(updatedAssociation);
        } catch (error) {
            console.error("Failed to delete operation", error);
            alert("Failed to delete operation");
        }
    };

    const handleEditOperation = (operation: Operation) => {
        setOperationToEdit(operation);
        setIsModalOpen(true);
    };

    const handleCloseModal = () => {
        setIsModalOpen(false);
        setOperationToEdit(null);
    };

    const handleAddBalance = async (newBalanceData: Omit<Balance, 'id'>) => {
        try {
            const newBalance = await api.addBalance(newBalanceData.name, newBalanceData.initialAmount, association.id);
            const updatedAssociation = {
                ...association,
                balances: [...association.balances, newBalance]
            };
            onUpdateAssociation(updatedAssociation);
            setIsAddBalanceModalOpen(false);
            setSelectedBalanceId(newBalance.id);
        } catch (error) {
            console.error("Failed to add balance", error);
            alert("Failed to add balance");
        }
    };

    const handleEditBalance = (balance: Balance) => {
        setBalanceToEdit(balance);
        setIsAddBalanceModalOpen(true);
    };

    const handleDeleteBalance = (balanceId: string) => {
        setBalanceToDeleteId(balanceId);
        setIsDeleteBalanceModalOpen(true);
    };

    const confirmDeleteBalance = async () => {
        if (!balanceToDeleteId) return;

        try {
            await api.deleteBalance(balanceToDeleteId);
            const updatedAssociation = {
                ...association,
                balances: association.balances.filter(b => b.id !== balanceToDeleteId)
            };
            onUpdateAssociation(updatedAssociation);
            if (selectedBalanceId === balanceToDeleteId) {
                setSelectedBalanceId(updatedAssociation.balances[0]?.id ?? null);
            }
        } catch (error) {
            console.error("Failed to delete balance", error);
            alert("Failed to delete balance");
        } finally {
            setIsDeleteBalanceModalOpen(false);
            setBalanceToDeleteId(null);
        }
    };

    const handleUpdateBalance = async (updatedBalance: Balance) => {
        try {
            const result = await api.updateBalance(updatedBalance);
            const updatedAssociation = {
                ...association,
                balances: association.balances.map(b => b.id === result.id ? result : b)
            };
            onUpdateAssociation(updatedAssociation);
            setIsAddBalanceModalOpen(false);
            setBalanceToEdit(null);
        } catch (error) {
            console.error("Failed to update balance", error);
            alert("Failed to update balance");
        }
    };

    const handleDragStart = (index: number) => {
        setDraggedBalanceIndex(index);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handleDrop = async (dropIndex: number) => {
        if (draggedBalanceIndex === null || draggedBalanceIndex === dropIndex) return;

        const newBalances = [...association.balances];
        const [draggedBalance] = newBalances.splice(draggedBalanceIndex, 1);
        newBalances.splice(dropIndex, 0, draggedBalance);

        const updatedBalances = newBalances.map((b, index) => ({
            ...b,
            position: index
        }));

        onUpdateAssociation({
            ...association,
            balances: updatedBalances
        });

        try {
            await Promise.all(updatedBalances.map(b => api.updateBalance(b)));
        } catch (error) {
            console.error("Failed to update balance positions", error);
            alert("Failed to save new order");
        }
        setDraggedBalanceIndex(null);
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* ... Header ... */}
            <Header
                associationName={association.name}
                onLogout={onLogout}
                dateRange={dateRange}
                setDateRange={setDateRange}
                operations={association.operations}
                balances={association.balances}
            />
            <main className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold text-gray-800">Balances</h2>
                    <div className="flex space-x-3">
                        <button
                            onClick={() => {
                                setBalanceToEdit(null);
                                setIsAddBalanceModalOpen(true);
                            }}
                            className="bg-white text-gray-800 border border-gray-300 px-4 py-2 rounded-lg font-semibold hover:bg-gray-50 transition flex items-center space-x-2"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
                            </svg>
                            <span>Add Balance</span>
                        </button>
                        <button
                            onClick={() => setIsModalOpen(true)}
                            className="bg-gray-800 text-white px-4 py-2 rounded-lg font-semibold hover:bg-gray-900 transition flex items-center space-x-2"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" /></svg>
                            <span>Add Operation</span>
                        </button>
                    </div>
                </div>

                <div className="relative group">
                    <button
                        onClick={() => scroll('left')}
                        className="absolute left-0 top-1/2 -translate-y-1/2 -ml-4 z-10 bg-white rounded-full p-2 shadow-lg border border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
                        aria-label="Scroll left"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                    </button>

                    <div
                        ref={scrollContainerRef}
                        className="p-2 flex space-x-6 pb-6 overflow-x-auto snap-x snap-mandatory scrollbar-none"
                        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                    >
                        {association.balances
                            .sort((a, b) => (a.position - b.position))
                            .map((balance, index) => (
                                <div
                                    key={balance.id}
                                    className="snap-start flex-shrink-0 w-80"
                                    draggable
                                    onDragStart={() => handleDragStart(index)}
                                    onDragOver={handleDragOver}
                                    onDrop={() => handleDrop(index)}
                                >
                                    <BalanceCard
                                        balance={balance}
                                        operations={filteredOperations.filter(op => op.balanceId === balance.id)}
                                        isSelected={selectedBalanceId === balance.id}
                                        onClick={() => setSelectedBalanceId(balance.id)}
                                        onEdit={handleEditBalance}
                                        onDelete={handleDeleteBalance}
                                    />
                                </div>
                            ))}
                    </div>

                    <button
                        onClick={() => scroll('right')}
                        className="absolute right-0 top-1/2 -translate-y-1/2 -mr-4 z-10 bg-white rounded-full p-2 shadow-lg border border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
                        aria-label="Scroll right"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
                    <div className="lg:col-span-3 bg-white p-6 rounded-xl shadow-md border border-gray-200">
                        <h3 className="text-xl font-semibold mb-4 text-gray-800">Balances Variation</h3>
                        <ErrorBoundary>
                            <OperationsChart
                                key={association.operations.length}
                                balances={association.balances}
                                allOperations={association.operations}
                                dateRange={dateRange}
                            />
                        </ErrorBoundary>
                    </div>

                    {selectedBalance && (
                        <>
                            <div className="lg:col-span-3 bg-white p-6 rounded-xl shadow-md border border-gray-200">
                                <h3 className="text-xl font-semibold mb-4 text-gray-800">
                                    Operations for <span className="text-gray-900 font-bold">{selectedBalance.name}</span>
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <ErrorBoundary>
                                        <OperationsTable
                                            title="Income"
                                            operations={incomesForSelectedBalance}
                                            onEdit={handleEditOperation}
                                            onDelete={handleDeleteOperation}
                                        />
                                    </ErrorBoundary>
                                    <ErrorBoundary>
                                        <OperationsTable
                                            title="Expenses"
                                            operations={expensesForSelectedBalance}
                                            onEdit={handleEditOperation}
                                            onDelete={handleDeleteOperation}
                                        />
                                    </ErrorBoundary>
                                </div>
                            </div>
                        </>
                    )}
                </div>

            </main>
            <ConfirmationModal
                isOpen={isDeleteBalanceModalOpen}
                onClose={() => {
                    setIsDeleteBalanceModalOpen(false);
                    setBalanceToDeleteId(null);
                }}
                onConfirm={confirmDeleteBalance}
                title="Delete Balance"
                message="Are you sure you want to delete this balance? All associated operations will be lost. This action cannot be undone."
                confirmText="Delete"
                isDanger={true}
            />
            <AddOperationModal
                isOpen={isModalOpen}
                onClose={handleCloseModal}
                onAddOperation={handleAddOperation}
                onUpdateOperation={handleUpdateOperation}
                operationToEdit={operationToEdit}
                balances={association.balances}
                existingGroups={existingGroups}
            />
            <AddBalanceModal
                isOpen={isAddBalanceModalOpen}
                onClose={() => {
                    setIsAddBalanceModalOpen(false);
                    setBalanceToEdit(null);
                }}
                onAddBalance={handleAddBalance}
                onUpdateBalance={handleUpdateBalance}
                balanceToEdit={balanceToEdit}
            />
        </div>
    );
};

export default Dashboard;
