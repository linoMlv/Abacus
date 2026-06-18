import React from 'react';
import { Link } from 'react-router-dom';

const NotFoundPage: React.FC = () => {
  return (
    <main className="flex flex-grow flex-col items-center justify-center bg-gray-50 px-4 text-center">
      <img src="/abacus.svg" alt="Abacus" className="mb-6 h-16 w-auto" />
      <p className="text-6xl font-bold tracking-tight text-gray-900">404</p>
      <h1 className="mt-3 text-xl font-semibold text-gray-800">Page introuvable</h1>
      <p className="mt-2 max-w-sm text-gray-500">
        La page que vous cherchez n'existe pas ou a été déplacée.
      </p>
      <Link
        to="/"
        className="mt-8 rounded-lg bg-gray-900 px-6 py-2.5 font-medium text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
      >
        Retour à l'accueil
      </Link>
    </main>
  );
};

export default NotFoundPage;
