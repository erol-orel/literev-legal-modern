import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { Spinner } from "@/components/ui/spinner";
import { useAppContext } from "@/hooks/use-app-context";

/**
 * Route-level code splitting: each page is its own async chunk so the initial
 * load ships only the shell + the landing/search entry point. React Router
 * treats trailing slashes as optional, matching Django's slash-terminated URLs.
 * Pages use named exports, so we map them onto the default export `lazy` wants.
 */
const LandingPage = lazy(() =>
  import("@/pages/landing-page").then((m) => ({ default: m.LandingPage })),
);
const SearchPage = lazy(() =>
  import("@/pages/search-page").then((m) => ({ default: m.SearchPage })),
);
const RunningPage = lazy(() =>
  import("@/pages/running-page").then((m) => ({ default: m.RunningPage })),
);
const HistoryPage = lazy(() =>
  import("@/pages/history-page").then((m) => ({ default: m.HistoryPage })),
);
const ProjectPage = lazy(() =>
  import("@/pages/project-page").then((m) => ({ default: m.ProjectPage })),
);
const TableSelectPage = lazy(() =>
  import("@/pages/tableselect-page").then((m) => ({
    default: m.TableSelectPage,
  })),
);
const DocumentPage = lazy(() =>
  import("@/pages/document-page").then((m) => ({ default: m.DocumentPage })),
);
const HighlightedDocumentPage = lazy(() =>
  import("@/pages/document-page").then((m) => ({
    default: m.HighlightedDocumentPage,
  })),
);
const RagPage = lazy(() =>
  import("@/pages/rag-page").then((m) => ({ default: m.RagPage })),
);
const TeamPage = lazy(() =>
  import("@/pages/team-page").then((m) => ({ default: m.TeamPage })),
);

/** Centered fallback while a route chunk is fetched. */
function RouteFallback() {
  return (
    <div
      className="flex min-h-[40vh] items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <Spinner className="size-6 text-muted-foreground" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/**
 * Client-side routes. Paths mirror the Django URL structure so the app works
 * whichever server route rendered the shell.
 */
export function App() {
  const { user } = useAppContext();

  return (
    <Suspense fallback={<RouteFallback />}>
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
          <Route path="/tableselect/*" element={<TableSelectPage />} />
          <Route
            path="/contentdocument/:documentId"
            element={<DocumentPage />}
          />
          <Route
            path="/contentdocument_highlighted/:documentRagId"
            element={<HighlightedDocumentPage />}
          />
          <Route path="/rag/:projectId" element={<RagPage />} />
          <Route path="/rag/:projectId/:ragId" element={<RagPage />} />
        </Route>

        {/* Public marketing routes */}
        <Route path="/team" element={<TeamPage />} />
        <Route path="/product" element={<LandingPage />} />
        <Route path="/company" element={<LandingPage />} />
        <Route path="/blog" element={<LandingPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
