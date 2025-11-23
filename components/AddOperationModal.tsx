
import React, { useState, useEffect } from 'react';
import { Balance, Operation, OperationType } from '../types';

interface AddOperationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAddOperation: (operation: Omit<Operation, 'id'>) => void;
    onUpdateOperation?: (operation: Operation) => void;
    operationToEdit?: Operation | null;
    balances: Balance[];
}

const AddOperationModal: React.FC<AddOperationModalProps> = ({ isOpen, onClose, onAddOperation, onUpdateOperation, operationToEdit, balances }) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [group, setGroup] = useState('');
    const [amount, setAmount] = useState('');
    const [type, setType] = useState<OperationType>(OperationType.EXPENSE);
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [balanceId, setBalanceId] = useState<string>('');
    const [invoice, setInvoice] = useState<File | null>(null);

    useEffect(() => {
        if (operationToEdit) {
            setName(operationToEdit.name);
            setDescription(operationToEdit.description);
            setGroup(operationToEdit.group);
            setAmount(operationToEdit.amount.toString());
            setType(operationToEdit.type);
            setDate(new Date(operationToEdit.date).toISOString().split('T')[0]);
            setBalanceId(operationToEdit.balanceId);
        } else if (balances.length > 0) {
            setBalanceId(balances[0].id);
            resetFormFields();
        }
    }, [balances, operationToEdit, isOpen]);

    const resetFormFields = () => {
        setName('');
        setDescription('');
        setGroup('');
        setAmount('');
        setType(OperationType.EXPENSE);
        setDate(new Date().toISOString().split('T')[0]);
        if (balances.length > 0) setBalanceId(balances[0].id);
        setInvoice(null);
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
            invoice: invoice ? invoice.name : (operationToEdit?.invoice)
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
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
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

                    <div>
                        <label className="text-sm font-medium text-gray-700">Group</label>
                        <input type="text" placeholder="e.g., Donations, Office Supplies" value={group} onChange={e => setGroup(e.target.value)} className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
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
                            <label className="text-sm font-medium text-gray-700">Invoice</label>
                            <input type="file" onChange={e => setInvoice(e.target.files ? e.target.files[0] : null)} className="w-full mt-1 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200" />
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
