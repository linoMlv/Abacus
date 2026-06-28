import { useMutation } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { authApi } from '@/api/auth';
import { apiErrorMessage } from '@/api/client';
import { useAuth } from '@/auth/useAuth';
import { BrandWordmark } from '@/components/Brand';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function CreateAssociationPage() {
  const { session, refresh } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');

  const hasAssociations = (session?.associations.length ?? 0) > 0;

  const create = useMutation({
    mutationFn: () => authApi.createAssociation({ name, email }),
    onSuccess: (assoc) => {
      refresh();
      // Onboarding: declare the starting balances of the seeded accounts.
      navigate(`/asso/${assoc.id}/bienvenue`, { replace: true });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  const error = apiErrorMessage(create, 'Création impossible.');

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <header className="flex h-16 items-center px-6 lg:px-8">
        <BrandWordmark />
      </header>
      <div className="flex flex-1 items-center justify-center px-6 pb-16">
        <Card className="w-full max-w-md">
          <CardHeader>
            <h1 className="text-xl font-semibold tracking-tight text-ink">
              {hasAssociations ? 'Nouvelle association' : 'Bienvenue sur Abacus'}
            </h1>
            <p className="text-sm text-muted">
              Créez l'association dont vous tiendrez la comptabilité. Son plan comptable et son
              premier exercice sont préparés automatiquement.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              {error && <Alert>{error}</Alert>}
              <div className="space-y-1.5">
                <Label htmlFor="assoc-name">Nom de l'association</Label>
                <Input
                  id="assoc-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="assoc-email">E-mail de contact</Label>
                <Input
                  id="assoc-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="flex gap-3 pt-1">
                {hasAssociations && (
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1"
                    onClick={() => navigate(-1)}
                  >
                    Annuler
                  </Button>
                )}
                <Button type="submit" className="flex-1" disabled={create.isPending}>
                  {create.isPending ? 'Création…' : "Créer l'association"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
