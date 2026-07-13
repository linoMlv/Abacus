import { useQuery } from '@tanstack/react-query';

import { accountingApi, type EcritureListItem } from '@/api/accounting';

/**
 * The analytic tags of an entry, in the words the association chose: category,
 * tiers, event. The reference lists come from the cache the journal filters
 * already populated, so this costs no extra request.
 */
export function OperationChips({
  associationId,
  entry,
}: {
  associationId: string;
  entry: EcritureListItem;
}) {
  const categories = useQuery({
    queryKey: ['categories', associationId],
    queryFn: () => accountingApi.listCategories(associationId),
  });
  const tiers = useQuery({
    queryKey: ['tiers', associationId],
    queryFn: () => accountingApi.listTiers(associationId),
  });
  const evenements = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });

  const categorie = categories.data?.find((c) => c.id === entry.categorie_id)?.libelle;
  const tiersNom = tiers.data?.find((t) => t.id === entry.tiers_id)?.nom;
  const evenement = evenements.data?.find((e) => e.id === entry.evenement_id);

  if (!categorie && !tiersNom && !evenement) return null;

  return (
    <span className="ml-2 inline-flex flex-wrap items-center gap-1 align-middle">
      {categorie && <Chip>{categorie}</Chip>}
      {tiersNom && <Chip>{tiersNom}</Chip>}
      {evenement && <Chip color={evenement.couleur}>{evenement.nom}</Chip>}
    </span>
  );
}

function Chip({ children, color }: { children: string; color?: string | null }) {
  return (
    <span
      className="inline-flex items-center rounded-full border border-hairline bg-subtle px-2 py-0.5 text-xs text-muted"
      style={color ? { borderColor: color, color } : undefined}
    >
      {children}
    </span>
  );
}
