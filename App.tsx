
import React, { useState, useEffect } from 'react';
import { Association } from './types';
import { api } from './api';
import LoginScreen from './components/LoginScreen';
import Dashboard from './components/Dashboard';
import ErrorBoundary from './components/ErrorBoundary';

const App: React.FC = () => {
  const [activeAssociation, setActiveAssociation] = useState<Association | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAssociation = async () => {
      try {
        const storedAssociationId = localStorage.getItem('abacus-active-association-id');
        if (storedAssociationId) {
          const association = await api.getAssociation(storedAssociationId);
          setActiveAssociation(association);
        }
      } catch (error) {
        console.error("Failed to load association", error);
        localStorage.removeItem('abacus-active-association-id');
      } finally {
        setLoading(false);
      }
    };
    loadAssociation();
  }, []);

  const handleLogin = (association: Association) => {
    localStorage.setItem('abacus-active-association-id', association.id);
    setActiveAssociation(association);
  };

  const handleLogout = () => {
    localStorage.removeItem('abacus-active-association-id');
    setActiveAssociation(null);
  };

  const updateAssociation = async (updatedAssociation: Association) => {
    setActiveAssociation(updatedAssociation);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-2xl font-semibold text-gray-700">Loading Abacus...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 font-sans">
      {activeAssociation ? (
        <ErrorBoundary>
          <Dashboard
            association={activeAssociation}
            onLogout={handleLogout}
            onUpdateAssociation={updateAssociation}
          />
        </ErrorBoundary>
      ) : (
        <LoginScreen onLogin={handleLogin} />
      )}
    </div>
  );
};

export default App;
