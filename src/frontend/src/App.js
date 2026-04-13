import { useEffect, useMemo } from "react";
import {
  BrowserRouter as Router,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import "./App.css";
import PublicLayout from "./components/public/layout";
import getContext from "./libs/context";
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

const PAGE_TITLES = {
  "/": "LiteRev Legal",
  "/search/": "LiteRev Legal | Search",
  "/running/": "LiteRev Legal | Running Projects",
  "/historicalpage/": "LiteRev Legal | Historical Search",
  "/project/": "LiteRev Legal | Project",
  "/rag/": "LiteRev Legal | RAG",
  "/contentdocument/": "LiteRev Legal | Document Content",
  "/contentdocument_highlighted/": "LiteRev Legal | Document Content",
  "/tableselect/": "LiteRev Legal | Results Table",
  "/team/": "LiteRev Legal | Team",
  "/product/": "LiteRev Legal | Product",
  "/company/": "LiteRev Legal | Company",
  "/blog/": "LiteRev Legal | Blog",
};

function normalizePath(pathname) {
  if (!pathname) {
    return "/";
  }

  return pathname.endsWith("/") ? pathname : `${pathname}/`;
}

function RouteDocumentTitle({ appName }) {
  const location = useLocation();

  useEffect(() => {
    const normalizedPath = normalizePath(location.pathname);
    if (normalizedPath.startsWith("/project/")) {
      document.title = PAGE_TITLES["/project/"];
      return;
    }
    if (normalizedPath.startsWith("/tableselect/")) {
      document.title = PAGE_TITLES["/tableselect/"];
      return;
    }
    if (normalizedPath.startsWith("/rag/")) {
      document.title = PAGE_TITLES["/rag/"];
      return;
    }
    if (normalizedPath.startsWith("/contentdocument/")) {
      document.title = PAGE_TITLES["/contentdocument/"];
      return;
    }
    if (normalizedPath.startsWith("/contentdocument_highlighted/")) {
      document.title = PAGE_TITLES["/contentdocument_highlighted/"];
      return;
    }
    document.title = PAGE_TITLES[normalizedPath] ?? appName;
  }, [appName, location.pathname]);

  return null;
}

function PublicRoutes({ context }) {
  return (
    <Routes>
      <Route path="/" element={<Home urls={context.urls} />} />
      <Route path="/search/*" element={<Search context={context} />} />
      <Route path="/running/*" element={<Running context={context} />} />
      <Route path="/project/:projectId/*" element={<Project context={context} />} />
      <Route path="/rag/:projectId/*" element={<RagPage context={context} />} />
      <Route path="/rag/:projectId/:ragId/*" element={<RagPage context={context} />} />
      <Route
        path="/contentdocument/:documentId/*"
        element={<ContentDocument context={context} />}
      />
      <Route
        path="/contentdocument_highlighted/:documentRagId/*"
        element={<HighlightedDocument context={context} />}
      />
      <Route
        path="/tableselect/*"
        element={<TableSelection context={context} />}
      />
      <Route
        path="/historicalpage/*"
        element={<HistoricalPage context={context} />}
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
