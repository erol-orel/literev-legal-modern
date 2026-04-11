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
import Home from "./pages/home/home";
import Product from "./pages/product/product";
import Team from "./pages/team/team";

const PAGE_TITLES = {
  "/": "LiteRev Legal",
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
    document.title = PAGE_TITLES[normalizedPath] ?? appName;
  }, [appName, location.pathname]);

  return null;
}

function PublicRoutes({ context }) {
  return (
    <Routes>
      <Route path="/" element={<Home urls={context.urls} />} />
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
