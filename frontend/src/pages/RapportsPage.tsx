import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Download, FileSpreadsheet, FileText, Wallet } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi, EXERCICE_STATUT_LABELS, TYPE_TRESORERIE_LABELS } from '@/api/accounting';
import { budgetApi } from '@/api/budget';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { usePermissions } from '@/hooks/usePermissions';
import { useRegimeTva } from '@/hooks/useRegimeTva';
import { triggerDownload } from '@/lib/download';
import { formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

/** A single downloadable document (server-generated, named by the server). */
function DownloadRow({ icon, label, url }: { icon: React.ReactNode; label: string; url: string }) {
  return (
    <button
      type="button"
      onClick={() => triggerDownload(url)}
      className="flex w-full items-center gap-3 rounded-lg border border-hairline px-3.5 py-2.5 text-left text-sm transition-colors hover:border-accent/40 hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <span className="shrink-0 text-faint">{icon}</span>
      <span className="min-w-0 flex-1 truncate font-medium text-ink">{label}</span>
      <Download className="h-4 w-4 shrink-0 text-faint" aria-hidden />
    </button>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink-soft">{title}</h3>
        <p className="text-xs text-muted">{description}</p>
      </div>
      {children}
    </section>
  );
}

const PDF = <FileText className="h-4 w-4" aria-hidden />;
const XLSX = <FileSpreadsheet className="h-4 w-4" aria-hidden />;

export function RapportsPage() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const regimeTva = useRegimeTva();
  const canExportFec = has(PERMISSIONS.REPORT_EXPORT_FEC);
  const canBudget = has(PERMISSIONS.BUDGET_MANAGE);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const period = { date_from: dateFrom || undefined, date_to: dateTo || undefined };

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const evenementsQuery = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });
  const exercicesQuery = useQuery({
    queryKey: ['exercices', associationId],
    queryFn: () => accountingApi.listExercices(associationId),
    enabled: canExportFec,
  });
  const etatTvaQuery = useQuery({
    queryKey: ['etat-tva', associationId, period],
    queryFn: () => accountingApi.getEtatTva(associationId, period),
    enabled: regimeTva,
  });
  const comptes = tresorerieQuery.data ?? [];
  const evenements = evenementsQuery.data ?? [];
  const exercices = exercicesQuery.data ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Rapports</h2>
          <p className="mt-1 text-sm text-muted">
            Tous les exports comptables au même endroit (PDF et Excel).
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <CalendarRange className="h-4 w-4 text-faint" aria-hidden />
          <Input
            type="date"
            aria-label="Date de début"
            className="w-40"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <span className="text-xs text-muted">au</span>
          <Input
            type="date"
            aria-label="Date de fin"
            className="w-40"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </div>
      <p className="-mt-4 text-xs text-faint">
        Sans dates, la période par défaut est l’exercice ouvert.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="Journal & grand livre"
          description="Toutes les écritures de la période, par pièce ou par compte."
        >
          <div className="space-y-2">
            <DownloadRow
              icon={PDF}
              label="Journal (PDF)"
              url={accountingApi.journalPdfUrl(associationId, period)}
            />
            <DownloadRow
              icon={XLSX}
              label="Journal (Excel)"
              url={accountingApi.journalXlsxUrl(associationId, period)}
            />
            <DownloadRow
              icon={PDF}
              label="Grand livre (PDF)"
              url={accountingApi.grandLivrePdfUrl(associationId, period)}
            />
            <DownloadRow
              icon={XLSX}
              label="Grand livre (Excel)"
              url={accountingApi.grandLivreXlsxUrl(associationId, period)}
            />
          </div>
        </Section>

        <Section
          title="États comptables"
          description="Documents de synthèse ANC pour l’AG et le conseil."
        >
          <div className="space-y-2">
            <DownloadRow
              icon={PDF}
              label="Compte de résultat (PDF)"
              url={accountingApi.compteResultatPdfUrl(associationId, period)}
            />
            <DownloadRow
              icon={PDF}
              label="Bilan (PDF)"
              url={accountingApi.bilanPdfUrl(associationId, period)}
            />
            <DownloadRow
              icon={PDF}
              label="Annexe (PDF)"
              url={accountingApi.annexePdfUrl(associationId, period)}
            />
          </div>
        </Section>

        {regimeTva && (
          <Section title="TVA" description="Position de TVA sur la période (écritures validées).">
            {etatTvaQuery.isError ? (
              <Card className="p-4 text-sm text-muted">État de TVA indisponible.</Card>
            ) : (
              <Card className="divide-y divide-hairline p-0 text-sm">
                <div className="flex items-center justify-between px-4 py-2.5">
                  <span className="text-ink-soft">TVA collectée</span>
                  <span className="tabular-nums text-ink">
                    {formatEUR(etatTvaQuery.data?.collectee ?? 0)}
                  </span>
                </div>
                <div className="flex items-center justify-between px-4 py-2.5">
                  <span className="text-ink-soft">TVA déductible</span>
                  <span className="tabular-nums text-ink">
                    {formatEUR(etatTvaQuery.data?.deductible ?? 0)}
                  </span>
                </div>
                <div className="flex items-center justify-between bg-hover px-4 py-2.5 font-semibold">
                  <span className="text-ink">À décaisser</span>
                  <span className="tabular-nums text-ink">
                    {formatEUR(etatTvaQuery.data?.a_decaisser ?? 0)}
                  </span>
                </div>
              </Card>
            )}
          </Section>
        )}

        <Section
          title="Relevés de trésorerie"
          description="Un relevé façon bancaire par compte (mouvements + solde)."
        >
          {tresorerieQuery.isError ? (
            <Card className="p-4 text-sm text-muted">Comptes indisponibles.</Card>
          ) : comptes.length === 0 ? (
            <Card className="p-4 text-sm text-muted">Aucun compte de trésorerie.</Card>
          ) : (
            <div className="space-y-2">
              {comptes.map((compte) => (
                <DownloadRow
                  key={compte.id}
                  icon={<Wallet className="h-4 w-4" aria-hidden />}
                  label={`${compte.libelle} — ${TYPE_TRESORERIE_LABELS[compte.type_tresorerie]}`}
                  url={accountingApi.relevePdfUrl(associationId, compte.id, period)}
                />
              ))}
            </div>
          )}
        </Section>

        <Section
          title="Bilans d’événements"
          description="Le réalisé d’une action (recettes, dépenses, budget)."
        >
          {evenementsQuery.isError ? (
            <Card className="p-4 text-sm text-muted">Événements indisponibles.</Card>
          ) : evenements.length === 0 ? (
            <Card className="p-4 text-sm text-muted">Aucun événement.</Card>
          ) : (
            <div className="space-y-2">
              {evenements.map((evenement) => (
                <DownloadRow
                  key={evenement.id}
                  icon={<CalendarRange className="h-4 w-4" aria-hidden />}
                  label={`Bilan « ${evenement.nom} » (PDF)`}
                  url={accountingApi.evenementBilanPdfUrl(associationId, evenement.id)}
                />
              ))}
            </div>
          )}
        </Section>

        {canBudget && (
          <Section
            title="Budget"
            description="Le prévu vs réalisé par catégorie (exercice ouvert)."
          >
            <div className="space-y-2">
              <DownloadRow
                icon={PDF}
                label="Budget (PDF)"
                url={budgetApi.budgetPdfUrl(associationId)}
              />
              <DownloadRow
                icon={XLSX}
                label="Budget (Excel)"
                url={budgetApi.budgetXlsxUrl(associationId)}
              />
            </div>
          </Section>
        )}

        {canExportFec && (
          <Section
            title="FEC"
            description="Fichier des Écritures Comptables (une par exercice) pour l’administration."
          >
            {exercices.length === 0 ? (
              <Card className="p-4 text-sm text-muted">Aucun exercice.</Card>
            ) : (
              <div className="space-y-2">
                {exercices.map((exercice) => (
                  <DownloadRow
                    key={exercice.id}
                    icon={PDF}
                    label={`FEC ${exercice.libelle} — ${EXERCICE_STATUT_LABELS[exercice.statut]}`}
                    url={accountingApi.fecUrl(associationId, exercice.id)}
                  />
                ))}
              </div>
            )}
          </Section>
        )}
      </div>
    </div>
  );
}
