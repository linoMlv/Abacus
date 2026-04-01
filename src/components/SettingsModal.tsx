import React, { useState, useEffect, useCallback } from 'react';
import { Association } from '../types';
import { api } from '../api';
import { useUpdateAccount, useChangePassword } from '../hooks/useAbacusData';

interface ApiKeyItem {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  association: Association;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, association }) => {
  const [name, setName] = useState(association.name);
  const [email, setEmail] = useState(association.email || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // API Keys
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);

  const updateAccountMutation = useUpdateAccount();
  const changePasswordMutation = useChangePassword();

  const loadApiKeys = useCallback(async () => {
    try {
      const keys = await api.listApiKeys();
      setApiKeys(keys);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setName(association.name);
      setEmail(association.email || '');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setMessage('');
      setError('');
      setCreatedKey(null);
      setKeyCopied(false);
      setNewKeyName('');
      loadApiKeys();
    }
  }, [isOpen, association, loadApiKeys]);

  if (!isOpen) return null;

  const handleSaveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await updateAccountMutation.mutateAsync({ name, email });
      setMessage('Account updated successfully.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update account');
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 4) {
      setError('Password must be at least 4 characters.');
      return;
    }
    try {
      await changePasswordMutation.mutateAsync({ currentPassword, newPassword });
      setMessage('Password changed successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to change password');
    }
  };

  const handleCreateApiKey = async () => {
    if (!newKeyName.trim()) return;
    setError('');
    setMessage('');
    try {
      const result = await api.createApiKey(newKeyName.trim());
      setCreatedKey(result.key);
      setKeyCopied(false);
      setNewKeyName('');
      loadApiKeys();
    } catch {
      setError('Failed to create API key');
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    try {
      await api.revokeApiKey(keyId);
      loadApiKeys();
    } catch {
      setError('Failed to revoke API key');
    }
  };

  const handleCopyKey = () => {
    if (createdKey) {
      navigator.clipboard.writeText(createdKey);
      setKeyCopied(true);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-800">Settings</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-8">
          {/* Account Info */}
          <form onSubmit={handleSaveAccount} className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-700">Account Information</h3>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Association Name</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
            </div>
            <button type="submit" disabled={updateAccountMutation.isPending}
              className="px-5 py-2 bg-gray-800 text-white rounded-lg text-sm font-semibold hover:bg-gray-900 transition disabled:opacity-50">
              {updateAccountMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </form>

          <hr className="border-gray-100" />

          {/* Change Password */}
          <form onSubmit={handleChangePassword} className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-700">Change Password</h3>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Current Password</label>
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">New Password</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Confirm New Password</label>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
            </div>
            <button type="submit" disabled={changePasswordMutation.isPending}
              className="px-5 py-2 bg-gray-800 text-white rounded-lg text-sm font-semibold hover:bg-gray-900 transition disabled:opacity-50">
              {changePasswordMutation.isPending ? 'Updating...' : 'Change Password'}
            </button>
          </form>

          <hr className="border-gray-100" />

          {/* API Keys */}
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-700">API Keys</h3>
              <p className="text-xs text-gray-400 mt-1">Use API keys to connect AI agents or external tools via the MCP server.</p>
            </div>

            {/* Created key alert */}
            {createdKey && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 space-y-2">
                <p className="text-sm font-medium text-yellow-800">Save this key now — it won't be shown again.</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white px-3 py-2 rounded border border-yellow-200 font-mono break-all select-all">
                    {createdKey}
                  </code>
                  <button onClick={handleCopyKey}
                    className="shrink-0 px-3 py-2 text-xs font-medium bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200 transition">
                    {keyCopied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              </div>
            )}

            {/* Create new key */}
            <div className="flex gap-2">
              <input type="text" placeholder="Key name (e.g., Claude Agent)" value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-800 transition" />
              <button onClick={handleCreateApiKey} disabled={!newKeyName.trim()}
                className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm font-semibold hover:bg-gray-900 transition disabled:opacity-50">
                Create
              </button>
            </div>

            {/* Key list */}
            {apiKeys.length > 0 && (
              <div className="space-y-2">
                {apiKeys.map((key) => (
                  <div key={key.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div>
                      <p className="text-sm font-medium text-gray-700">{key.name}</p>
                      <p className="text-xs text-gray-400">
                        {key.key_prefix}... &middot; Created {new Date(key.created_at).toLocaleDateString('fr-FR')}
                        {key.last_used_at && ` &middot; Last used ${new Date(key.last_used_at).toLocaleDateString('fr-FR')}`}
                      </p>
                    </div>
                    <button onClick={() => handleRevokeKey(key.id)}
                      className="text-xs text-red-500 hover:text-red-700 font-medium transition">
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}
            {apiKeys.length === 0 && (
              <p className="text-sm text-gray-400">No API keys yet.</p>
            )}
          </div>

          {/* Messages */}
          {message && (
            <p className="text-green-600 text-sm text-center bg-green-50 p-2 rounded-lg">{message}</p>
          )}
          {error && (
            <p className="text-red-500 text-sm text-center bg-red-50 p-2 rounded-lg">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
