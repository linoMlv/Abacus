import { type ComponentType, Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { useAuth } from '@/auth/useAuth';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth } from '@/components/RequireAuth';
import { ALL_NAV_ITEMS } from '@/lib/nav';
import { PlaceholderPage } from '@/pages/PlaceholderPage';
import { AcceptInvitationPage } from '@/pages/auth/AcceptInvitationPage';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';

// Business pages are code-split: each loads on first navigation, so the initial
// bundle stays small. The auth pages and shell above stay eager for first paint.
const lazyPage = <T extends string>(factory: () => Promise<Record<T, ComponentType>>, name: T) =>
  lazy(() => factory().then((m) => ({ default: m[name] })));

const CreateAssociationPage = lazyPage(
  () => import('@/pages/CreateAssociationPage'),
  'CreateAssociationPage'
);
const OnboardingSoldesPage = lazyPage(
  () => import('@/pages/OnboardingSoldesPage'),
  'OnboardingSoldesPage'
);
const SynthesePage = lazyPage(() => import('@/pages/SynthesePage'), 'SynthesePage');
const SaisiePage = lazyPage(() => import('@/pages/SaisiePage'), 'SaisiePage');
const JournalPage = lazyPage(() => import('@/pages/JournalPage'), 'JournalPage');
const ComptesPage = lazyPage(() => import('@/pages/ComptesPage'), 'ComptesPage');
const BanquePage = lazyPage(() => import('@/pages/BanquePage'), 'BanquePage');
const RecurrencesPage = lazyPage(() => import('@/pages/RecurrencesPage'), 'RecurrencesPage');
const BudgetPage = lazyPage(() => import('@/pages/BudgetPage'), 'BudgetPage');
const RapportsPage = lazyPage(() => import('@/pages/RapportsPage'), 'RapportsPage');
const DonsPage = lazyPage(() => import('@/pages/DonsPage'), 'DonsPage');
const ParametresPage = lazyPage(() => import('@/pages/ParametresPage'), 'ParametresPage');

/** Send a signed-in user to their first association, or to onboarding. */
function HomeRedirect() {
  const { session } = useAuth();
  const first = session?.associations[0];
  return <Navigate to={first ? `/asso/${first.id}/synthese` : '/associations/nouvelle'} replace />;
}

function PageFallback() {
  return (
    <div className="p-6 text-sm text-muted" role="status" aria-live="polite">
      Chargement…
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/invitation" element={<AcceptInvitationPage />} />

          <Route element={<RequireAuth />}>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/associations/nouvelle" element={<CreateAssociationPage />} />
            <Route path="/asso/:associationId/bienvenue" element={<OnboardingSoldesPage />} />

            <Route path="/asso/:associationId" element={<AppShell />}>
              <Route index element={<Navigate to="synthese" replace />} />
              <Route path="synthese" element={<SynthesePage />} />
              <Route path="saisie" element={<SaisiePage />} />
              <Route path="journal" element={<JournalPage />} />
              <Route path="comptes" element={<ComptesPage />} />
              <Route path="banque" element={<BanquePage />} />
              <Route path="recurrences" element={<RecurrencesPage />} />
              <Route path="budget" element={<BudgetPage />} />
              <Route path="rapports" element={<RapportsPage />} />
              <Route path="dons" element={<DonsPage />} />
              <Route path="parametres" element={<ParametresPage />} />
              {ALL_NAV_ITEMS.filter(
                (item) =>
                  ![
                    'synthese',
                    'saisie',
                    'journal',
                    'comptes',
                    'banque',
                    'recurrences',
                    'budget',
                    'rapports',
                    'dons',
                    'parametres',
                  ].includes(item.segment)
              ).map((item) => (
                <Route key={item.segment} path={item.segment} element={<PlaceholderPage />} />
              ))}
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  );
}
