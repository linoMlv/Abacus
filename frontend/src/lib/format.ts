/**
 * Locale-aware formatting for the French associative accounting context.
 * Amounts come from the API as decimal strings (e.g. "150.00"); parse defensively
 * and render with fr-FR grouping and the EUR symbol.
 */

const EUR = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DECIMAL = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function toNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === 'string' ? Number(value) : value;
  return Number.isFinite(n) ? n : 0;
}

/** "1 234,56 €" — for amounts shown with their currency. */
export function formatEUR(value: number | string | null | undefined): string {
  return EUR.format(toNumber(value));
}

/** "1 234,56" — for amounts in débit/crédit columns where € sits in the header. */
export function formatAmount(value: number | string | null | undefined): string {
  return DECIMAL.format(toNumber(value));
}

const DATE = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

/** "27/06/2026" from an ISO date/datetime string or Date. */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '';
  const d = typeof value === 'string' ? new Date(value) : value;
  return Number.isNaN(d.getTime()) ? '' : DATE.format(d);
}

/** Today as an ISO `yyyy-mm-dd` string — the value date/datetime inputs expect.
 * Built from the *local* calendar day (not `toISOString`, which is UTC and can
 * be off by one either side of midnight for a French user). */
export function today(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** "3 Ko" / "1.2 Mo" — a human file size from a byte count. */
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} Ko`;
  return `${(n / (1024 * 1024)).toFixed(1)} Mo`;
}

/**
 * Integer cents from a euro amount — compare money without binary-float drift.
 * Accepts a number or a (possibly empty/invalid) input string, which coerces to 0.
 */
export function cents(value: number | string): number {
  return Math.round((Number(value) || 0) * 100);
}
