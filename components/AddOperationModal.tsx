
import React, { useState, useEffect, useRef } from 'react';
import { Balance, Operation, OperationType } from '../types';

interface AddOperationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAddOperation: (operation: Omit<Operation, 'id'>) => void;
    onUpdateOperation?: (operation: Operation) => void;
    operationToEdit?: Operation | null;
    balances: Balance[];
    existingGroups: string[];
}

const AddOperationModal: React.FC<AddOperationModalProps> = ({ isOpen, onClose, onAddOperation, onUpdateOperation, operationToEdit, balances, existingGroups }) => {
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
    }, [balances, operationToEdit, isOpen]);

    useEffect(() => {
        if (isOpen) {
            setFilteredGroups(existingGroups);
        }
    }, [isOpen, existingGroups]);

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
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handleGroupChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        setGroup(value);
        setFilteredGroups(existingGroups.filter(g => g.toLowerCase().includes(value.toLowerCase())));
        setIsGroupDropdownOpen(true);
    };

    const handleGroupSelect = (selectedGroup: string) => {
        setGroup(selectedGroup);
        setIsGroupDropdownOpen(false);
    };

    const resetFormFields = () => {
        setName('');
        setDescription('');
        setGroup('');
        setAmount('');
        setType(OperationType.EXPENSE);
        setDate(new Date().toISOString().split('T')[0]);
        if (balances.length > 0) setBalanceId(balances[0].id);
        setInvoice('');
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !amount || !balanceId || !group) {
            alert('Please fill all required fields.');
            return;
        }

        const operationData = {
            balanceId,
            name,
            description,
            group,
            amount: parseFloat(amount),
            type,
            date: new Date(date).toISOString(),
            invoice
        };

        if (operationToEdit && onUpdateOperation) {
            onUpdateOperation({
                ...operationData,
                id: operationToEdit.id
            });
        } else {
            onAddOperation(operationData);
        }
        resetForm();
    };

    const resetForm = () => {
        resetFormFields();
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[95vh] overflow-scroll">
                <div className="flex justify-between items-center p-6 border-b border-gray-200">
                    <h2 className="text-xl font-bold text-gray-800">{operationToEdit ? 'Edit Operation' : 'Add New Operation'}</h2>
                    <button onClick={resetForm} className="text-gray-400 hover:text-gray-600">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <button type="button" onClick={() => setType(OperationType.EXPENSE)} className={`w-full py-3 rounded-lg font-semibold transition ${type === OperationType.EXPENSE ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-700'}`}>
                            Expense
                        </button>
                        <button type="button" onClick={() => setType(OperationType.INCOME)} className={`w-full py-3 rounded-lg font-semibold transition ${type === OperationType.INCOME ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-700'}`}>
                            Income
                        </button>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Balance</label>
                        <select value={balanceId} onChange={(e) => setBalanceId(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition">
                            {balances.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Title</label>
                        <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
                    </div>

                    <div className="relative">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Group</label>
                        <input
                            ref={groupInputRef}
                            type="text"
                            placeholder="Select or type a group..."
                            value={group}
                            onChange={handleGroupChange}
                            onFocus={() => setIsGroupDropdownOpen(true)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-gray-800"
                            required
                        />
                        {isGroupDropdownOpen && (
                            <ul
                                ref={groupDropdownRef}
                                className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
                            >
                                {filteredGroups.length > 0 ? (
                                    filteredGroups.map((g) => (
                                        <li
                                            key={g}
                                            onClick={() => handleGroupSelect(g)}
                                            className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm text-gray-700"
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
                            <label className="text-sm font-medium text-gray-700">Amount (€)</label>
                            <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
                        </div>
                        <div>
                            <label className="text-sm font-medium text-gray-700">Date</label>
                            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
                        </div>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Description</label>
                        <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"></textarea>
                    </div>

                    {type === OperationType.EXPENSE && (
                        <div>
                            <label className="text-sm font-medium text-gray-700">Invoice URL</label>
                            <input type="url" placeholder="https://..." value={invoice} onChange={e => setInvoice(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
                        </div>
                    )}

                    <div className="flex justify-end pt-4">
                        <button type="button" onClick={onClose} className="mr-3 px-6 py-2 rounded-lg font-semibold text-gray-600 hover:bg-gray-100 transition">
                            Cancel
                        </button>
                        <button type="submit" className="bg-gray-800 text-white px-6 py-2 rounded-lg font-semibold hover:bg-gray-900 transition">
                            {operationToEdit ? 'Save Changes' : 'Add Operation'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default AddOperationModal;
