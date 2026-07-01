import type { CompteTresorerie } from '@/api/accounting';

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-depense">{message}</p>;
}

/** The named treasury accounts as <option>s (with a placeholder when empty). */
export function CompteOptions({ comptes }: { comptes: CompteTresorerie[] }) {
  return (
    <>
      {comptes.length === 0 && <option value="">—</option>}
      {comptes.map((c) => (
        <option key={c.id} value={c.id}>
          {c.libelle}
        </option>
      ))}
    </>
  );
}
