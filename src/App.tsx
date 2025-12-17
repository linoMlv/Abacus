import React from 'react';
import { useMe, useLogout } from './hooks/useAbacusData';
import LoginScreen from './components/LoginScreen';
import Dashboard from './components/Dashboard';
import ErrorBoundary from './components/ErrorBoundary';
import { useQueryClient } from '@tanstack/react-query';

const App: React.FC = () => {
  const { data: activeAssociation, isLoading } = useMe();
  const logoutMutation = useLogout();
  const queryClient = useQueryClient();

  const handleLoginSuccess = () => {
    // When login succeeds, we invalidate 'me' query to fetch user data
    queryClient.invalidateQueries({ queryKey: ['me'] });
  };

  const handleLogout = () => {
    logoutMutation.mutate();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <svg
            className="animate-spin h-10 w-10 text-gray-800"
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
          <div className="text-xl font-medium text-gray-600">Loading Abacus...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 font-sans">
      {activeAssociation ? (
        <ErrorBoundary>
          <Dashboard association={activeAssociation} onLogout={handleLogout} />
        </ErrorBoundary>
      ) : (
        <LoginScreen onLogin={handleLoginSuccess} />
      )}
    </div>
  );
};

export default App;
