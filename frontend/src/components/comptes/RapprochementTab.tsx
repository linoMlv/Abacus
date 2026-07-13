import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Check, TriangleAlert } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { accountingApi, type RapprochementCompte } from '@/api/accounting';
import { Alert } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';

/**
 * Books vs. bank, account by account (C25).
 *
 * The question a treasurer actually asks is "est-ce que mes comptes collent avec
 * ma banque ?". So each card states the booked balance, what the bank reported and
 * nobody has booked yet, and the balance the bank should therefore show — with the
 * status carried by an icon and a word, never by colour alone.
 */
export function RapprochementTab() {
  const { associationId } = useParams() as { associationId: string };

  const query = useQuery({
    queryKey: ['rapprochement', associationId],
    queryFn: () => accountingApi.getRapprochement(associationId),
  });
  const comptes = query.data ?? [];

  if (query.isError) return <Alert>Impossible de charger l’état de rapprochement.</Alert>;
  if (query.isLoading) return <Card className="p-6 text-sm text-muted">Chargement…</Card>;
  if (comptes.length === 0) {
    return (
      <Card className="p-6 text-sm text-muted">
        Aucun compte de trésorerie. Créez-en un depuis la Synthèse pour suivre vos soldes.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Comparez vos écritures avec ce que votre banque a réellement enregistré. Un écart s’explique
        par les lignes de relevé pas encore rapprochées.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {comptes.map((compte) => (
          <RapprochementCard key={compte.compte_id} compte={compte} />
        ))}
      </div>
    </div>
  );
}

function RapprochementCard({ compte }: { compte: RapprochementCompte }) {
  const enAttente = compte.nb_non_rapprochees > 0;

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{compte.libelle}</h3>
          <p className="font-mono text-xs tabular-nums text-faint">{compte.numero}</p>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
            enAttente ? 'bg-depense-soft text-depense' : 'bg-recette-soft text-recette'
          }`}
        >
          {enAttente ? (
            <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <Check className="h-3.5 w-3.5" aria-hidden />
          )}
          {enAttente ? `${compte.nb_non_rapprochees} à rapprocher` : 'Rapproché'}
        </span>
      </div>

      <dl className="space-y-1.5 text-sm">
        <Row label="Solde dans vos comptes" value={formatEUR(compte.solde_comptable)} />
        <Row
          label="Mouvements non rapprochés"
          value={formatEUR(compte.montant_non_rapproche)}
          muted={!enAttente}
        />
        <Row
          label="Solde attendu en banque"
          value={formatEUR(compte.solde_bancaire_estime)}
          strong
        />
      </dl>

      <div className="flex items-center justify-between border-t border-hairline pt-3 text-xs text-muted">
        <span>
          {compte.dernier_import
            ? `Dernier relevé importé le ${formatDate(compte.dernier_import)}`
            : 'Aucun relevé importé'}
        </span>
        <Link
          to="../banque"
          className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
        >
          Rapprocher
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
    </Card>
  );
}

function Row({
  label,
  value,
  strong,
  muted,
}: {
  label: string;
  value: string;
  strong?: boolean;
  muted?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className={muted ? 'text-faint' : 'text-muted'}>{label}</dt>
      <dd
        className={`font-mono tabular-nums ${
          strong ? 'text-base font-semibold text-ink' : muted ? 'text-faint' : 'text-ink-soft'
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
