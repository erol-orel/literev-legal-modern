import { useEffect, useMemo } from "react";
import {
  BrowserRouter as Router,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import "./App.css";
import RequireAuth from "./components/auth/require_auth";
import PublicLayout from "./components/public/layout";
import getContext from "./libs/context";
import { resolvePageTitle } from "./libs/routes";
import Blog from "./pages/blog/blog";
import Company from "./pages/company/company";
import ContentDocument from "./pages/contentdocument/contentdocument";
import HighlightedDocument from "./pages/hldocument/hldocument";
import HistoricalPage from "./pages/historicalpage/historicalpage";
import Home from "./pages/home/home";
import Product from "./pages/product/product";
import Project from "./pages/project/project";
import RagPage from "./pages/rag/rag";
import Running from "./pages/running/running";
import Search from "./pages/search/search";
import Team from "./pages/team/team";
import TableSelection from "./pages/tableselect/tableselect";

function RouteDocumentTitle({ appName }) {
  const location = useLocation();

  useEffect(() => {
    document.title = resolvePageTitle(location.pathname, appName);
  }, [appName, location.pathname]);

  return null;
}

function AuthenticatedRoute({ children, context }) {
  return <RequireAuth context={context}>{children}</RequireAuth>;
}

function HomeRoute({ context }) {
  if (context.user.isAuthenticated) {
    return <Navigate replace to={context.urls.search} />;
  }

  return <Home urls={context.urls} />;
}

function PublicRoutes({ context }) {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute context={context} />} />
      <Route
        path="/search/*"
        element={
          <AuthenticatedRoute context={context}>
            <Search context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/running/*"
        element={
          <AuthenticatedRoute context={context}>
            <Running context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/project/:projectId/*"
        element={
          <AuthenticatedRoute context={context}>
            <Project context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/rag/:projectId/*"
        element={
          <AuthenticatedRoute context={context}>
            <RagPage context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/rag/:projectId/:ragId/*"
        element={
          <AuthenticatedRoute context={context}>
            <RagPage context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/contentdocument/:documentId/*"
        element={
          <AuthenticatedRoute context={context}>
            <ContentDocument context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/contentdocument_highlighted/:documentRagId/*"
        element={
          <AuthenticatedRoute context={context}>
            <HighlightedDocument context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/tableselect/*"
        element={
          <AuthenticatedRoute context={context}>
            <TableSelection context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route
        path="/historicalpage/*"
        element={
          <AuthenticatedRoute context={context}>
            <HistoricalPage context={context} />
          </AuthenticatedRoute>
        }
      />
      <Route path="/team/*" element={<Team />} />
      <Route path="/product/*" element={<Product urls={context.urls} />} />
      <Route path="/company/*" element={<Company urls={context.urls} />} />
      <Route path="/blog/*" element={<Blog urls={context.urls} />} />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}

function App({ initialContext = null }) {
  const context = useMemo(() => getContext(initialContext), [initialContext]);

  return (
    <Router
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
    >
      <RouteDocumentTitle appName={context.appName} />
      <PublicLayout context={context}>
        <PublicRoutes context={context} />
      </PublicLayout>
    </Router>
  );
}

export default App;
