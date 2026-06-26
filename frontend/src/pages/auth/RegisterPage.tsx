import { useMutation } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { authApi } from '@/api/auth';
import { ApiError } from '@/api/client';
import { useAuth } from '@/auth/useAuth';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { AuthLayout } from './AuthLayout';

const MIN_PASSWORD = 8;

export function RegisterPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const register = useMutation({
    mutationFn: async () => {
      await authApi.register({ name, email, password });
      return authApi.login({ email, password });
    },
    onSuccess: () => {
      refresh();
      navigate('/', { replace: true });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setLocalError(`Le mot de passe doit contenir au moins ${MIN_PASSWORD} caractères.`);
      return;
    }
    setLocalError(null);
    register.mutate();
  };

  const error =
    localError ??
    (register.error instanceof ApiError
      ? register.error.message
      : register.isError
        ? 'Création du compte impossible.'
        : null);

  return (
    <AuthLayout
      title="Créer un compte"
      subtitle="Un compte personnel, autant d'associations que nécessaire."
      footer={
        <>
          Déjà inscrit ?{' '}
          <Link to="/login" className="font-medium text-accent hover:underline">
            Se connecter
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <div className="space-y-1.5">
          <Label htmlFor="name">Nom complet</Label>
          <Input
            id="name"
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Adresse e-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted">Au moins {MIN_PASSWORD} caractères.</p>
        </div>
        <Button type="submit" className="w-full" disabled={register.isPending}>
          {register.isPending ? 'Création…' : 'Créer mon compte'}
        </Button>
      </form>
    </AuthLayout>
  );
}
