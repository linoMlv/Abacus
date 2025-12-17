import React from 'react';
import { format, parseISO } from 'date-fns';

import { Operation, Balance } from '../types';
import ExportButton from './ExportButton';
import ErrorBoundary from './ErrorBoundary';

interface HeaderProps {
  associationName: string;
  onLogout: () => void;
  dateRange: { start: Date; end: Date };
  setDateRange: (range: { start: Date; end: Date }) => void;
  operations: Operation[];
  balances: Balance[];
}

const Header: React.FC<HeaderProps> = ({
  associationName,
  onLogout,
  dateRange,
  setDateRange,
  operations,
  balances,
}) => {
  const handleDateChange = (field: 'start' | 'end', value: string) => {
    const newDate = parseISO(value);
    if (field === 'start' && newDate < dateRange.end) {
      setDateRange({ ...dateRange, start: newDate });
    }
    if (field === 'end' && newDate > dateRange.start) {
      setDateRange({ ...dateRange, end: newDate });
    }
  };

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center space-x-4">
            <img src="/abacus.svg" alt="Abacus" className="h-12" />
            <span className="hidden sm:block text-gray-400">|</span>
            <p className="hidden sm:block text-3xl font-medium text-gray-600">{associationName}</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <input
                type="date"
                value={format(dateRange.start, 'yyyy-MM-dd')}
                onChange={(e) => handleDateChange('start', e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-800"
              />
              <span className="text-gray-500">-</span>
              <input
                type="date"
                value={format(dateRange.end, 'yyyy-MM-dd')}
                onChange={(e) => handleDateChange('end', e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-800"
              />
            </div>
            <ErrorBoundary
              fallback={<span className="text-red-500 text-sm">Export Unavailable</span>}
            >
              <ExportButton
                operations={operations}
                balances={balances}
                dateRange={dateRange}
                associationName={associationName}
              />
            </ErrorBoundary>
            <button
              onClick={onLogout}
              className="text-sm font-medium text-gray-600 hover:text-gray-900 transition"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
