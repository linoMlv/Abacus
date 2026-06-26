import type { ReactNode } from 'react';

import { BrandWordmark } from '@/components/Brand';

/** Split auth scaffold: a quiet brand panel beside the form. */
export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-ink p-12 text-white lg:flex">
        <p className="text-sm font-semibold tracking-[0.2em] text-white/60">ABACUS</p>
        <div className="max-w-sm">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            La comptabilité de votre association, au carré.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-white/70">
            Saisie simple côté bénévole, partie double conforme en coulisses. Journal, grand livre
            et états légaux, sans la complexité.
          </p>
        </div>
        <p className="text-sm text-white/50">
          Conforme au plan comptable associatif (ANC 2018-06).
        </p>
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-accent/15 blur-3xl"
        />
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <BrandWordmark />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-muted">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
