import { useMutation, useQuery } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { authApi } from '@/api/auth';
import { apiErrorMessage } from '@/api/client';
import { useAuth } from '@/auth/useAuth';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ROLE_LABELS } from '@/lib/roles';
import { cn } from '@/lib/utils';

import { AuthLayout } from './AuthLayout';

const MIN_PASSWORD = 8;

export function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const { session, refresh } = useAuth();
  const navigate = useNavigate();

  const preview = useQuery({
    queryKey: ['invitation-preview', token],
    queryFn: () => authApi.invitationPreview(token),
    enabled: !!token,
    retry: false,
  });

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const data = preview.data;
  const goToAssociation = () => {
    refresh();
    if (data) navigate(`/asso/${data.association_id}/synthese`, { replace: true });
  };

  // Logged in as the invited account: one click joins.
  const join = useMutation({
    mutationFn: () => authApi.acceptInvitation({ token }),
    onSuccess: goToAssociation,
  });
  // Not logged in, existing account: sign in then accept (the cookie carries over).
  const loginAndJoin = useMutation({
    mutationFn: async () => {
      await authApi.login({ email: data!.email, password });
      return authApi.acceptInvitation({ token });
    },
    onSuccess: goToAssociation,
  });
  // Not logged in, new account: accept creates it with the invitation e-mail.
  const registerAndJoin = useMutation({
    mutationFn: () => authApi.acceptInvitation({ token, name, password }),
    onSuccess: goToAssociation,
  });
  // Wrong account: sign out, then this page falls back to the sign-in / sign-up flow.
  const signOut = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => refresh(),
  });

  const layout = (children: React.ReactNode, subtitle: string) => (
    <AuthLayout title="Invitation" subtitle={subtitle}>
      {children}
    </AuthLayout>
  );

  if (!token) {
    return layout(<Alert>Lien d’invitation incomplet.</Alert>, 'Rejoindre une association.');
  }
  if (preview.isLoading) {
    return layout(<p className="text-sm text-muted">Chargement…</p>, 'Rejoindre une association.');
  }
  if (preview.isError || !data) {
    return layout(
      <div className="space-y-4">
        <Alert>Cette invitation est invalide ou a expiré.</Alert>
        <Link to="/login" className="text-sm font-medium text-accent hover:underline">
          Aller à la connexion
        </Link>
      </div>,
      'Rejoindre une association.'
    );
  }

  const context = (
    <div className="rounded-lg border border-hairline bg-hover px-4 py-3">
      <p className="text-sm text-ink">
        Vous êtes invité·e à rejoindre <strong>{data.association_name}</strong>
      </p>
      <p className="mt-0.5 text-xs text-muted">
        en tant que {ROLE_LABELS[data.role]} · {data.email}
      </p>
    </div>
  );

  // --- Already signed in --------------------------------------------------- //
  if (session) {
    const sameAccount = session.user.email === data.email;
    return layout(
      <div className="space-y-4">
        {context}
        {sameAccount ? (
          <>
            {join.isError && <Alert>{apiErrorMessage(join, 'Impossible de rejoindre.')}</Alert>}
            <Button className="w-full" onClick={() => join.mutate()} disabled={join.isPending}>
              {join.isPending ? 'Ajout…' : `Rejoindre ${data.association_name}`}
            </Button>
          </>
        ) : (
          <>
            <Alert>
              Vous êtes connecté·e en tant que <strong>{session.user.email}</strong>, mais cette
              invitation est destinée à <strong>{data.email}</strong>.
            </Alert>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => signOut.mutate()}
              disabled={signOut.isPending}
            >
              Se déconnecter pour continuer
            </Button>
          </>
        )}
      </div>,
      `Rejoindre ${data.association_name}.`
    );
  }

  // --- Not signed in: sign in or create the invited account ---------------- //
  const onLogin = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    loginAndJoin.mutate();
  };
  const onRegister = (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setLocalError(`Le mot de passe doit contenir au moins ${MIN_PASSWORD} caractères.`);
      return;
    }
    setLocalError(null);
    registerAndJoin.mutate();
  };

  const error =
    localError ??
    apiErrorMessage(mode === 'login' ? loginAndJoin : registerAndJoin, 'Une erreur est survenue.');

  return layout(
    <div className="space-y-5">
      {context}

      <div
        className="inline-flex w-full rounded-lg border border-hairline bg-surface p-0.5"
        role="tablist"
        aria-label="Méthode"
      >
        {(['login', 'register'] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => {
              setMode(m);
              setLocalError(null);
            }}
            className={cn(
              'flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              mode === m ? 'bg-accent text-white' : 'text-muted hover:text-ink'
            )}
          >
            {m === 'login' ? 'J’ai un compte' : 'Créer un compte'}
          </button>
        ))}
      </div>

      {error && <Alert>{error}</Alert>}

      {mode === 'login' ? (
        <form onSubmit={onLogin} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="email">Adresse e-mail</Label>
            <Input id="email" type="email" value={data.email} readOnly disabled />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Mot de passe</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={loginAndJoin.isPending}>
            {loginAndJoin.isPending ? 'Connexion…' : 'Se connecter et rejoindre'}
          </Button>
        </form>
      ) : (
        <form onSubmit={onRegister} className="space-y-4" noValidate>
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
            <Input id="email" type="email" value={data.email} readOnly disabled />
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
          <Button type="submit" className="w-full" disabled={registerAndJoin.isPending}>
            {registerAndJoin.isPending ? 'Création…' : 'Créer mon compte et rejoindre'}
          </Button>
        </form>
      )}
    </div>,
    `Rejoindre ${data.association_name}.`
  );
}
