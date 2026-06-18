import React, { useState } from 'react';
import { Association } from '../types';
import { api } from '../api';

interface LoginScreenProps {
  onLogin: (association: Association) => void;
}

const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin }) => {
  const [isLoginView, setIsLoginView] = useState(true);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const [associationName, setAssociationName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [initialBalances, setInitialBalances] = useState<{ name: string; amount: string }[]>([
    { name: '', amount: '' },
  ]);
  const [error, setError] = useState('');

  const handleAddBalance = () => {
    setInitialBalances([...initialBalances, { name: '', amount: '' }]);
  };

  const handleRemoveBalance = (index: number) => {
    setInitialBalances(initialBalances.filter((_, i) => i !== index));
  };

  const handleBalanceChange = (index: number, field: 'name' | 'amount', value: string) => {
    const newBalances = [...initialBalances];
    newBalances[index][field] = value;
    setInitialBalances(newBalances);
  };

  const handleForgotPassword = async () => {
    setError('');
    if (!forgotEmail.trim()) {
      setError('Please enter your email address.');
      return;
    }
    try {
      await api.forgotPassword(forgotEmail.trim());
      setForgotSent(true);
    } catch {
      setError('Failed to send reset email.');
    }
  };

  const validateSignup = () => {
    if (!associationName.trim() || !email.trim() || !password.trim()) {
      setError('Association name, email, and password are required.');
      return false;
    }
    if (
      initialBalances.some((b) => !b.name.trim() || !b.amount.trim() || isNaN(parseFloat(b.amount)))
    ) {
      setError('All balance fields must be filled correctly.');
      return false;
    }
    return true;
  };

  const handleSignup = async () => {
    setError('');
    if (!validateSignup()) return;

    try {
      const newAssociation = await api.signup(
        associationName.trim(),
        email.trim(),
        password,
        initialBalances.map((b) => ({ name: b.name.trim(), amount: b.amount }))
      );
      onLogin(newAssociation);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Signup failed');
      }
    }
  };

  const handleLogin = async () => {
    setError('');
    if (!associationName.trim() || !password.trim()) {
      setError('Please enter association name and password.');
      return;
    }

    try {
      const association = await api.login(associationName.trim(), password);
      onLogin(association);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Login failed');
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoginView) {
      handleLogin();
    } else {
      handleSignup();
    }
  };

  if (showForgotPassword) {
    return (
      <div className="flex items-center justify-center flex-grow bg-gray-50 px-4">
        <div className="w-full max-w-md">
          <img src="/abacus.svg" alt="Abacus Logo" className="h-20 w-auto mx-auto mb-6" />
          <p className="text-center text-gray-500 mb-8">Password Recovery</p>
          <div className="bg-white p-8 rounded-xl shadow-md border border-gray-200">
            {forgotSent ? (
              <div className="text-center space-y-4">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-12 w-12 mx-auto text-green-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="text-gray-600">
                  If an account with this email exists, a reset link has been sent.
                </p>
                <button
                  onClick={() => {
                    setShowForgotPassword(false);
                    setForgotSent(false);
                    setForgotEmail('');
                  }}
                  className="text-sm font-semibold text-gray-700 hover:underline"
                >
                  Back to login
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                <h2 className="text-2xl font-semibold text-center">Reset Password</h2>
                <p className="text-sm text-gray-500 text-center">
                  Enter the email address associated with your account.
                </p>
                <input
                  type="email"
                  placeholder="Email"
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
                />
                {error && <p className="text-red-500 text-sm text-center">{error}</p>}
                <button
                  onClick={handleForgotPassword}
                  className="w-full bg-gray-800 text-white py-3 rounded-lg font-semibold hover:bg-gray-900 transition"
                >
                  Send Reset Link
                </button>
                <p className="text-center">
                  <button
                    onClick={() => {
                      setShowForgotPassword(false);
                      setError('');
                    }}
                    className="text-sm font-semibold text-gray-700 hover:underline"
                  >
                    Back to login
                  </button>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center bg-gray-50 px-4">
      {' '}
      {/* min-h-screen */}
      <div className="w-full max-w-md">
        <img src="/abacus.svg" alt="Abacus Logo" className="h-20 w-auto mx-auto mb-6" />
        <p className="text-center text-gray-500 mb-8">
          Simplified accounting for your association.
        </p>
        <div className="bg-white p-8 rounded-xl shadow-md border border-gray-200">
          <h2 className="text-2xl font-semibold text-center mb-6">
            {isLoginView ? 'Login' : 'Create Account'}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-6">
            <input
              type="text"
              placeholder="Association Name"
              value={associationName}
              onChange={(e) => setAssociationName(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
            />
            {!isLoginView && (
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              />
            )}
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
            />

            {!isLoginView && (
              <div>
                <h3 className="text-lg font-medium mb-3">Initial Balances</h3>
                <div className="space-y-4 max-h-48 overflow-y-auto pr-2">
                  {initialBalances.map((balance, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <input
                        type="text"
                        placeholder="Balance Name (e.g., Main Account)"
                        value={balance.name}
                        onChange={(e) => handleBalanceChange(index, 'name', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Amount (€)"
                        value={balance.amount}
                        onChange={(e) => handleBalanceChange(index, 'amount', e.target.value)}
                        className="w-40 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      />
                      {initialBalances.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveBalance(index)}
                          className="p-2 text-gray-400 hover:text-red-500 transition"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={handleAddBalance}
                  className="mt-3 text-sm font-semibold text-gray-700 hover:text-gray-900"
                >
                  + Add another balance
                </button>
              </div>
            )}

            {error && <p className="text-red-500 text-sm text-center">{error}</p>}

            <button
              type="submit"
              className="w-full bg-gray-800 text-white py-3 rounded-lg font-semibold hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-800 transition"
            >
              {isLoginView ? 'Login' : 'Sign Up'}
            </button>
          </form>

          {isLoginView && (
            <p className="text-center text-sm text-gray-400 mt-4">
              <button
                onClick={() => {
                  setShowForgotPassword(true);
                  setError('');
                }}
                className="hover:text-gray-600 hover:underline transition"
              >
                Forgot your password?
              </button>
            </p>
          )}

          <p className="text-center text-sm text-gray-500 mt-4">
            {isLoginView ? "Don't have an account?" : 'Already have an account?'}
            <button
              onClick={() => {
                setIsLoginView(!isLoginView);
                setError('');
              }}
              className="font-semibold text-gray-700 hover:underline ml-1"
            >
              {isLoginView ? 'Sign Up' : 'Login'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
