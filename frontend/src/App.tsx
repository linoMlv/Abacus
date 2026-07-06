import { Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { useAuth } from '@/auth/useAuth';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth } from '@/components/RequireAuth';
import { ALL_NAV_ITEMS } from '@/lib/nav';
import { BanquePage } from '@/pages/BanquePage';
import { BudgetPage } from '@/pages/BudgetPage';
import { CreateAssociationPage } from '@/pages/CreateAssociationPage';
import { DonsPage } from '@/pages/DonsPage';
import { JournalPage } from '@/pages/JournalPage';
import { OnboardingSoldesPage } from '@/pages/OnboardingSoldesPage';
import { ParametresPage } from '@/pages/ParametresPage';
import { PlaceholderPage } from '@/pages/PlaceholderPage';
import { RapportsPage } from '@/pages/RapportsPage';
import { RecurrencesPage } from '@/pages/RecurrencesPage';
import { SaisiePage } from '@/pages/SaisiePage';
import { SynthesePage } from '@/pages/SynthesePage';
import { AcceptInvitationPage } from '@/pages/auth/AcceptInvitationPage';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';

/** Send a signed-in user to their first association, or to onboarding. */
function HomeRedirect() {
  const { session } = useAuth();
  const first = session?.associations[0];
  return <Navigate to={first ? `/asso/${first.id}/synthese` : '/associations/nouvelle'} replace />;
}

export default function App() {
  return (
    <AuthProvider>
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
    </AuthProvider>
  );
}
