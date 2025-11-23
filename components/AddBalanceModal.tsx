import React, { useState } from 'react';
import { Balance } from '../types';

interface AddBalanceModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAddBalance: (balance: Omit<Balance, 'id'>) => void;
    onUpdateBalance?: (balance: Balance) => void;
    balanceToEdit?: Balance | null;
}

const AddBalanceModal: React.FC<AddBalanceModalProps> = ({ isOpen, onClose, onAddBalance, onUpdateBalance, balanceToEdit }) => {
    const [name, setName] = useState('');
    const [initialAmount, setInitialAmount] = useState('');

    React.useEffect(() => {
        if (balanceToEdit) {
            setName(balanceToEdit.name);
            setInitialAmount(balanceToEdit.initialAmount.toString());
        } else {
            setName('');
            setInitialAmount('');
        }
    }, [balanceToEdit, isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !initialAmount) {
            alert('Please fill all required fields.');
            return;
        }

        if (balanceToEdit && onUpdateBalance) {
            onUpdateBalance({
                ...balanceToEdit,
                name,
                initialAmount: parseFloat(initialAmount),
            });
        } else {
            onAddBalance({
                name,
                initialAmount: parseFloat(initialAmount),
            });
        }
        resetForm();
    };

    const resetForm = () => {
        setName('');
        setInitialAmount('');
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
                <div className="flex justify-between items-center p-6 border-b border-gray-200">
                    <h2 className="text-xl font-bold text-gray-800">{balanceToEdit ? 'Edit Balance' : 'Add New Balance'}</h2>
                    <button onClick={resetForm} className="text-gray-400 hover:text-gray-600">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="text-sm font-medium text-gray-700">Balance Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
                            placeholder="e.g., Main Account, Savings"
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Initial Amount (€)</label>
                        <input
                            type="number"
                            step="0.01"
                            value={initialAmount}
                            onChange={e => setInitialAmount(e.target.value)}
                            className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
                            placeholder="0.00"
                        />
                    </div>

                    <div className="flex justify-end pt-4">
                        <button type="submit" className="bg-gray-800 text-white px-6 py-2 rounded-lg font-semibold hover:bg-gray-900 transition">
                            {balanceToEdit ? 'Save Changes' : 'Add Balance'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default AddBalanceModal;
