import React, { useState, useRef, useEffect } from 'react';
import { format, parseISO } from 'date-fns';

import { Operation, Balance } from '../types';
import ExportButton from './ExportButton';
import ErrorBoundary from './ErrorBoundary';

interface HeaderProps {
  associationName: string;
  onLogout: () => void;
  onOpenSettings: () => void;
  dateRange: { start: Date; end: Date };
  setDateRange: (range: { start: Date; end: Date }) => void;
  operations: Operation[];
  balances: Balance[];
}

const Header: React.FC<HeaderProps> = ({
  associationName,
  onLogout,
  onOpenSettings,
  dateRange,
  setDateRange,
  operations,
  balances,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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
              resetKey={operations.length}
            >
              {operations.length > 0 ? (
                <ExportButton
                  operations={operations}
                  balances={balances}
                  dateRange={dateRange}
                  associationName={associationName}
                />
              ) : (
                <span className="text-gray-400 text-sm">Loading...</span>
              )}
            </ErrorBoundary>

            {/* Profile dropdown */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center justify-center w-9 h-9 rounded-full bg-gray-800 text-white text-sm font-semibold hover:bg-gray-900 transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-800"
                title={associationName}
              >
                {associationName.charAt(0).toUpperCase()}
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-800 truncate">{associationName}</p>
                  </div>
                  <button
                    onClick={() => { setDropdownOpen(false); onOpenSettings(); }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition flex items-center space-x-2"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>Settings</span>
                  </button>
                  <button
                    onClick={() => { setDropdownOpen(false); onLogout(); }}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition flex items-center space-x-2"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
