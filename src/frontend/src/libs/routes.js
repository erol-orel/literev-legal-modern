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


export function normalizePath(pathname) {
  if (!pathname) {
    return "/";
  }

  return pathname.endsWith("/") ? pathname : `${pathname}/`;
}

export function resolvePageTitle(pathname, appName) {
  const normalizedPath = normalizePath(pathname);

  if (normalizedPath.startsWith("/project/")) {
    return PAGE_TITLES["/project/"];
  }
  if (normalizedPath.startsWith("/tableselect/")) {
    return PAGE_TITLES["/tableselect/"];
  }
  if (normalizedPath.startsWith("/rag/")) {
    return PAGE_TITLES["/rag/"];
  }
  if (normalizedPath.startsWith("/contentdocument/")) {
    return PAGE_TITLES["/contentdocument/"];
  }
  if (normalizedPath.startsWith("/contentdocument_highlighted/")) {
    return PAGE_TITLES["/contentdocument_highlighted/"];
  }

  return PAGE_TITLES[normalizedPath] ?? appName;
}


export function buildLoginRedirect(urls, pathname, search = "", hash = "") {
  const loginUrl = urls?.login || "/accounts/login/";
  const nextPath = `${pathname || "/"}${search || ""}${hash || ""}`;
  const separator = loginUrl.includes("?") ? "&" : "?";

  return `${loginUrl}${separator}next=${encodeURIComponent(nextPath)}`;
}

export const PUBLIC_NAVIGATION_ITEMS = [
  { label: "Product", to: "product" },
  { label: "Company", to: "company" },
  { label: "Blog", to: "blog" },
  { label: "Team", to: "team" },
  { label: "Search", to: "search" },
];

export const AUTHENTICATED_NAVIGATION_ITEMS = [
  { label: "Running", to: "running" },
  { label: "History", to: "historicalpage" },
];
