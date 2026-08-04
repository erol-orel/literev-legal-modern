import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { useAppContext } from "@/hooks/use-app-context";
import { LandingPage } from "@/pages/landing-page";
import { PlaceholderPage } from "@/pages/placeholder-page";
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
        <Route
          path="/running"
          element={
            <PlaceholderPage
              title="Running projects"
              description="Track collection, clustering and RAG jobs in progress."
            />
          }
        />
        <Route
          path="/historicalpage"
          element={
            <PlaceholderPage
              title="Project history"
              description="Browse and revisit completed analyses."
            />
          }
        />
        <Route
          path="/project/:projectId"
          element={
            <PlaceholderPage
              title="Project overview"
              description="Clusters, refinements and top-document questions."
            />
          }
        />
        <Route
          path="/tableselect/*"
          element={<PlaceholderPage title="Document selection" />}
        />
        <Route
          path="/contentdocument/:documentId"
          element={<PlaceholderPage title="Document" />}
        />
        <Route
          path="/contentdocument_highlighted/:documentRagId"
          element={<PlaceholderPage title="Document" />}
        />
        <Route
          path="/rag/:projectId"
          element={
            <PlaceholderPage
              title="Ask the corpus"
              description="Question your selected decisions with cited answers."
            />
          }
        />
        <Route
          path="/rag/:projectId/:ragId"
          element={<PlaceholderPage title="Ask the corpus" />}
        />
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
