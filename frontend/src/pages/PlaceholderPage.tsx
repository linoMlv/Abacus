import { useLocation } from 'react-router-dom';

import { ALL_NAV_ITEMS } from '@/lib/nav';

const DESCRIPTIONS: Record<string, string> = {
  saisie: 'Enregistrez recettes et dépenses ; l’écriture en partie double est générée pour vous.',
  journal:
    'Toutes les écritures de l’association, filtrables, avec saisie manuelle pour les experts.',
  comptes: 'Plan comptable, balance des comptes et grand livre par compte.',
  tiers: 'Fournisseurs, donateurs et financeurs de l’association.',
  banque: 'Import de relevés et rapprochement bancaire par lettrage.',
  recurrences: 'Dépenses et recettes récurrentes : loyers, abonnements, cotisations.',
  budget: 'Budget prévu et réalisé, par poste et par exercice.',
  rapports: 'Compte de résultat, bilan, annexe et exports PDF / Excel / FEC.',
  dons: 'Suivi des dons et reçus fiscaux Cerfa.',
  parametres: 'Association, exercices, régime de TVA, membres et rôles, journaux des accès.',
};

export function PlaceholderPage() {
  const { pathname } = useLocation();
  const segment = pathname.split('/').filter(Boolean).pop() ?? '';
  const item = ALL_NAV_ITEMS.find((i) => i.segment === segment);
  const Icon = item?.icon;
  const description = DESCRIPTIONS[segment] ?? 'Ce module arrive prochainement.';

  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-hairline bg-surface">
        {Icon && <Icon className="h-5 w-5 text-muted" aria-hidden />}
      </div>
      <h2 className="mt-5 text-lg font-semibold tracking-tight text-ink">
        {item?.label ?? 'Module'}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
      <p className="mt-6 inline-flex items-center rounded-full border border-hairline bg-surface px-3 py-1 text-xs font-medium text-faint">
        En préparation
      </p>
    </div>
  );
}
