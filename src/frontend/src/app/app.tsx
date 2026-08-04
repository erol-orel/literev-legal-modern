import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { useAppContext } from "@/hooks/use-app-context";
import { HistoryPage } from "@/pages/history-page";
import { LandingPage } from "@/pages/landing-page";
import { PlaceholderPage } from "@/pages/placeholder-page";
import { ProjectPage } from "@/pages/project-page";
import { RagPage } from "@/pages/rag-page";
import { RunningPage } from "@/pages/running-page";
import { SearchPage } from "@/pages/search-page";

/**
 * Client-side routes. Paths mirror the Django URL structure so the app works
 * whichever server route rendered the shell. React Router v6 treats trailing
 * slashes as optional, matching Django's slash-terminated URLs.
 */
export function App() {
  const { user } = useAppContext();

  return (
    <Routes>
      <Route
        path="/"
        element={
          user.isAuthenticated ? (
            <Navigate to="/search/" replace />
          ) : (
            <LandingPage />
          )
        }
      />

      {/* Authenticated application shell */}
      <Route element={<AppShell />}>
        <Route path="/search" element={<SearchPage />} />
        <Route path="/running" element={<RunningPage />} />
        <Route path="/historicalpage" element={<HistoryPage />} />
        <Route path="/project/:projectId" element={<ProjectPage />} />
        <Route
          path="/tableselect/*"
          element={
            <PlaceholderPage
              title="Document selection"
              description="Triage documents across iterations before asking questions."
            />
          }
        />
        <Route
          path="/contentdocument/:documentId"
          element={<PlaceholderPage title="Document" />}
        />
        <Route
          path="/contentdocument_highlighted/:documentRagId"
          element={<PlaceholderPage title="Document" />}
        />
        <Route path="/rag/:projectId" element={<RagPage />} />
        <Route path="/rag/:projectId/:ragId" element={<RagPage />} />
      </Route>

      {/* Public marketing routes */}
      <Route path="/team" element={<LandingPage />} />
      <Route path="/product" element={<LandingPage />} />
      <Route path="/company" element={<LandingPage />} />
      <Route path="/blog" element={<LandingPage />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
