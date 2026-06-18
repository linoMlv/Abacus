import React from 'react';

interface SessionExpiredModalProps {
  onConfirm: () => void;
}

/**
 * Shown when the session can no longer be refreshed. Informs the user and
 * returns them to the login screen.
 */
const SessionExpiredModal: React.FC<SessionExpiredModalProps> = ({ onConfirm }) => {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
    >
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="session-expired-title" className="text-lg font-semibold text-gray-900">
          Session expirée
        </h2>
        <p className="mt-2 text-sm text-gray-600">
          Votre session a expiré pour des raisons de sécurité. Veuillez vous reconnecter pour
          continuer.
        </p>
        <button
          type="button"
          onClick={onConfirm}
          autoFocus
          className="mt-6 w-full rounded-lg bg-gray-900 px-4 py-2.5 font-medium text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          Se reconnecter
        </button>
      </div>
    </div>
  );
};

export default SessionExpiredModal;
