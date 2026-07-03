import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import { accountingApi, type ImportReleveMapping } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

type AmountMode = 'montant' | 'debit_credit';
type Format = 'csv' | 'ofx';

interface Props {
  associationId: string;
  compteId: string;
  compteLibelle: string;
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

/** Sensible defaults for a typical French bank CSV (1-based column numbers in UI). */
const DEFAULTS = {
  delimiter: ';',
  decimalSep: ',',
  dateFormat: '%d/%m/%Y',
  hasHeader: true,
  dateCol: 1,
  libelleCol: 2,
  montantCol: 3,
  debitCol: 4,
  creditCol: 5,
};

export function ImportReleveDialog({
  associationId,
  compteId,
  compteLibelle,
  open,
  onClose,
  onImported,
}: Props) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<Format>('csv');
  const [amountMode, setAmountMode] = useState<AmountMode>('montant');
  const [delimiter, setDelimiter] = useState(DEFAULTS.delimiter);
  const [decimalSep, setDecimalSep] = useState(DEFAULTS.decimalSep);
  const [dateFormat, setDateFormat] = useState(DEFAULTS.dateFormat);
  const [hasHeader, setHasHeader] = useState(DEFAULTS.hasHeader);
  const [dateCol, setDateCol] = useState(DEFAULTS.dateCol);
  const [libelleCol, setLibelleCol] = useState(DEFAULTS.libelleCol);
  const [montantCol, setMontantCol] = useState(DEFAULTS.montantCol);
  const [debitCol, setDebitCol] = useState(DEFAULTS.debitCol);
  const [creditCol, setCreditCol] = useState(DEFAULTS.creditCol);
  const [localError, setLocalError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (format === 'ofx') {
        return accountingApi.importerReleveOfx(associationId, compteId, file as File);
      }
      // Columns are 1-based in the UI, 0-based in the API.
      const mapping: ImportReleveMapping = {
        date_col: dateCol - 1,
        libelle_col: libelleCol - 1,
        date_format: dateFormat,
        decimal_sep: decimalSep,
        delimiter: delimiter === 'tab' ? '\t' : delimiter,
        has_header: hasHeader,
        ...(amountMode === 'montant'
          ? { montant_col: montantCol - 1 }
          : { debit_col: debitCol - 1, credit_col: creditCol - 1 }),
      };
      return accountingApi.importerReleve(associationId, compteId, mapping, file as File);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['banque', associationId] });
      onImported();
      reset();
      onClose();
    },
  });

  function reset() {
    setFile(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (!file) {
      setLocalError('Sélectionnez un fichier.');
      return;
    }
    mutation.mutate();
  }

  const error = localError ?? apiErrorMessage(mutation, 'Import impossible.');

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Importer un relevé</DialogTitle>
        <DialogDescription>Relevé du compte « {compteLibelle} ».</DialogDescription>

        <form onSubmit={onSubmit} className="mt-4 space-y-5">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wide text-faint">Format</span>
            <div className="mt-1.5 flex gap-2">
              {(['csv', 'ofx'] as Format[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFormat(f)}
                  aria-pressed={format === f}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                    format === f
                      ? 'border-accent bg-accent-soft text-accent'
                      : 'border-hairline text-muted hover:bg-hover'
                  }`}
                >
                  {f === 'csv' ? 'CSV' : 'OFX'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label htmlFor="releve-file">Fichier {format.toUpperCase()}</Label>
            <Input
              id="releve-file"
              ref={fileRef}
              type="file"
              accept={format === 'ofx' ? '.ofx,.qfx,application/x-ofx' : '.csv,text/csv,text/plain'}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1.5"
            />
            {format === 'ofx' && (
              <p className="mt-1 text-xs text-faint">
                Format bancaire standard : dates, montants et libellés sont lus automatiquement. Les
                opérations déjà importées sont ignorées.
              </p>
            )}
          </div>

          {format === 'csv' && (
            <>
              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold uppercase tracking-wide text-faint">
                  Format
                </legend>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="delimiter">Séparateur</Label>
                    <Select
                      id="delimiter"
                      value={delimiter}
                      onChange={(e) => setDelimiter(e.target.value)}
                      className="mt-1.5"
                    >
                      <option value=";">Point-virgule ( ; )</option>
                      <option value=",">Virgule ( , )</option>
                      <option value="tab">Tabulation</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="decimal">Décimale</Label>
                    <Select
                      id="decimal"
                      value={decimalSep}
                      onChange={(e) => setDecimalSep(e.target.value)}
                      className="mt-1.5"
                    >
                      <option value=",">Virgule ( 12,50 )</option>
                      <option value=".">Point ( 12.50 )</option>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label htmlFor="dateformat">Format de date</Label>
                  <Input
                    id="dateformat"
                    value={dateFormat}
                    onChange={(e) => setDateFormat(e.target.value)}
                    className="mt-1.5"
                  />
                  <p className="mt-1 text-xs text-faint">
                    Ex. <code>%d/%m/%Y</code> pour 31/12/2026, <code>%Y-%m-%d</code> pour
                    2026-12-31.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm text-ink-soft">
                  <input
                    type="checkbox"
                    checked={hasHeader}
                    onChange={(e) => setHasHeader(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  La première ligne est un en-tête
                </label>
              </fieldset>

              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold uppercase tracking-wide text-faint">
                  Colonnes (n° à partir de 1)
                </legend>
                <div className="grid grid-cols-2 gap-3">
                  <NumberField label="Date" value={dateCol} onChange={setDateCol} />
                  <NumberField label="Libellé" value={libelleCol} onChange={setLibelleCol} />
                </div>
                <div className="flex gap-4 text-sm text-ink-soft">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="amount-mode"
                      checked={amountMode === 'montant'}
                      onChange={() => setAmountMode('montant')}
                      className="h-4 w-4 accent-accent"
                    />
                    Montant unique (signé)
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="amount-mode"
                      checked={amountMode === 'debit_credit'}
                      onChange={() => setAmountMode('debit_credit')}
                      className="h-4 w-4 accent-accent"
                    />
                    Débit / Crédit séparés
                  </label>
                </div>
                {amountMode === 'montant' ? (
                  <NumberField label="Montant" value={montantCol} onChange={setMontantCol} />
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <NumberField label="Débit" value={debitCol} onChange={setDebitCol} />
                    <NumberField label="Crédit" value={creditCol} onChange={setCreditCol} />
                  </div>
                )}
              </fieldset>
            </>
          )}

          {error && <Alert>{error}</Alert>}

          <div className="flex gap-2">
            <Button type="button" variant="ghost" className="flex-1" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" variant="accent" className="flex-1" disabled={mutation.isPending}>
              {mutation.isPending ? 'Import…' : 'Importer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <Input
        type="number"
        min={1}
        value={value}
        onChange={(e) => onChange(Math.max(1, Number(e.target.value) || 1))}
        className="mt-1.5"
      />
    </div>
  );
}
