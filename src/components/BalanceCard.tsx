import React, { useMemo } from 'react';
import { Balance, Operation, OperationType } from '../types';

interface BalanceCardProps {
  balance: Balance;
  operations: Operation[];
  currentBalance: number;
  isSelected: boolean;
  onClick: () => void;
  onEdit: (balance: Balance) => void;
  onDelete: (balanceId: string) => void;
}

const BalanceCard: React.FC<BalanceCardProps> = ({
  balance,
  operations,
  currentBalance,
  isSelected,
  onClick,
  onEdit,
  onDelete,
}) => {
  const { totalIncome, totalExpenses } = useMemo(() => {
    const totalIncome = operations
      .filter((op) => op.type === OperationType.INCOME)
      .reduce((sum, op) => sum + op.amount, 0);

    const totalExpenses = operations
      .filter((op) => op.type === OperationType.EXPENSE)
      .reduce((sum, op) => sum + op.amount, 0);

    return { totalIncome, totalExpenses };
  }, [operations]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount);
  };

  const [openMenu, setOpenMenu] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = React.useState<{ top: number; left: number } | null>(
    null
  );

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const toggleMenu = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (openMenu) {
      setOpenMenu(false);
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPosition({
      top: rect.bottom,
      left: rect.right - 128,
    });
    setOpenMenu(true);
  };

  return (
    <div
      onClick={onClick}
      className={`relative p-6 rounded-xl border transition-all duration-200 cursor-pointer group ${
        isSelected
          ? 'bg-gray-800 text-white shadow-lg'
          : 'bg-white text-gray-800 shadow-md border-gray-200 hover:shadow-lg hover:border-gray-300'
      }`}
    >
      <div className="flex justify-between items-start">
        <p className={`text-lg font-semibold ${isSelected ? 'text-gray-300' : 'text-gray-600'}`}>
          {balance.name}
        </p>
        <button
          onClick={toggleMenu}
          className={`p-1 rounded-full hover:bg-gray-200 transition-colors ${isSelected ? 'text-gray-400 hover:bg-gray-700' : 'text-gray-400'}`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
          </svg>
        </button>
      </div>

      <p className="text-4xl font-bold mt-2 truncate">{formatCurrency(currentBalance)}</p>
      <div className="flex justify-between items-center mt-6">
        <div className="text-center">
          <p className={`text-sm ${isSelected ? 'text-gray-400' : 'text-gray-500'}`}>Income</p>
          <p
            className={`font-semibold text-green-500 ${isSelected ? 'text-green-400' : 'text-green-600'}`}
          >
            {formatCurrency(totalIncome)}
          </p>
        </div>
        <div className="text-center">
          <p className={`text-sm ${isSelected ? 'text-gray-400' : 'text-gray-500'}`}>Expenses</p>
          <p
            className={`font-semibold text-red-500 ${isSelected ? 'text-red-400' : 'text-red-600'}`}
          >
            {formatCurrency(totalExpenses)}
          </p>
        </div>
      </div>

      {openMenu && menuPosition && (
        <div
          ref={menuRef}
          className="fixed z-50 w-32 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
          style={{ top: menuPosition.top, left: menuPosition.left }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="py-1">
            <button
              onClick={() => {
                onEdit(balance);
                setOpenMenu(false);
              }}
              className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
            >
              Edit
            </button>
            <button
              onClick={() => {
                onDelete(balance.id);
                setOpenMenu(false);
              }}
              className="block w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-gray-100"
            >
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default BalanceCard;
