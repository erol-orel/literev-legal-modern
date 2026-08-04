/**
 * Django-injected bootstrap context. The server renders a
 * `<script id="context-data" type="application/json">…</script>` block into the
 * shell; this module reads it once, fills in defaults for anything the server
 * omits, and hands the app a fully-typed, stable object.
 *
 * Keeping the defaults here means the SPA still runs (dev server, tests, or a
 * shell that predates a given key) without every consumer guarding for
 * `undefined`.
 */

/** Client-side navigation targets. Paths mirror Django's slash-terminated URLs. */
export interface UrlMap {
  home: string;
  search: string;
  running: string;
  historicalpage: string;
  rag: string;
  projectBase: string;
  ragBase: string;
  tableselectBase: string;
  contentdocumentBase: string;
  contentdocumentHighlightedBase: string;
  team: string;
  product: string;
  company: string;
  blog: string;
  login: string;
  logout: string;
}

/** DRF endpoint bases. `*Base` values are prefixes callers append ids/paths to. */
export interface ApiUrls {
  searchConvertQuery: string;
  searchValidate: string;
  searchPreview: string;
  searchProjects: string;
  runningProjects: string;
  historicalProjects: string;
  historicalDeleteAll: string;
  projectApiBase: string;
  projectDeleteBase: string;
  documentContentBase: string;
  documentHighlightedBase: string;
  tableSelectionBase: string;
  ragContextBase: string;
  ragDeleteBase: string;
  ragStatusBase: string;
  ragCreateBase: string;
  ragDocumentsBase: string;
}

/** A selectable legal source (Cour de cassation chamber, etc.). */
export interface Source {
  value: string;
  label: string;
}

export interface SearchConfig {
  clusteringMinDocuments: number;
  sources: Source[];
}

export interface User {
  email: string;
  isAuthenticated: boolean;
}

export interface AppContext {
  appName: string;
  appVersion: string;
  urls: UrlMap;
  api: ApiUrls;
  search: SearchConfig;
  user: User;
}

const DEFAULT_CONTEXT: AppContext = {
  appName: "LiteRev Legal",
  appVersion: "",
  urls: {
    home: "/",
    search: "/search/",
    running: "/running/",
    historicalpage: "/historicalpage/",
    rag: "/rag/",
    projectBase: "/project/",
    ragBase: "/rag/",
    tableselectBase: "/tableselect/",
    contentdocumentBase: "/contentdocument/",
    contentdocumentHighlightedBase: "/contentdocument_highlighted/",
    team: "/team/",
    product: "/product/",
    company: "/company/",
    blog: "/blog/",
    login: "/accounts/login/",
    logout: "/accounts/logout/",
  },
  api: {
    searchConvertQuery: "/api/project/search/convert-query/",
    searchValidate: "/api/project/search/validate/",
    searchPreview: "/api/project/search/preview/",
    searchProjects: "/api/project/search/projects/",
    runningProjects: "/api/project/running/",
    historicalProjects: "/api/project/historical/",
    historicalDeleteAll: "/api/project/historical/delete-all/",
    projectApiBase: "/api/project/projects/",
    projectDeleteBase: "/api/project/projects/",
    documentContentBase: "/api/project/documents/",
    documentHighlightedBase: "/api/project/documents/rag/",
    tableSelectionBase: "/api/project/tableselect/",
    ragContextBase: "/api/project/rag/",
    ragDeleteBase: "/api/project/rag/",
    ragStatusBase: "/api/project-rags-by-project/",
    ragCreateBase: "/api/project-rags-by-project/",
    ragDocumentsBase: "/api/project-documents-rag/",
  },
  search: {
    clusteringMinDocuments: 0,
    sources: [],
  },
  user: {
    email: "",
    isAuthenticated: false,
  },
};

/** A partial context (e.g. what the server injects, or a test override). */
type PartialContext = {
  [K in keyof AppContext]?: Partial<AppContext[K]>;
};

/** Deep-merge a partial over the defaults, one nested level per top-level key. */
function normalizeContext(partial: PartialContext | null | undefined): AppContext {
  const source = partial ?? {};
  return {
    ...DEFAULT_CONTEXT,
    ...source,
    urls: { ...DEFAULT_CONTEXT.urls, ...source.urls },
    api: { ...DEFAULT_CONTEXT.api, ...source.api },
    search: { ...DEFAULT_CONTEXT.search, ...source.search },
    user: { ...DEFAULT_CONTEXT.user, ...source.user },
  };
}

function readFromDom(): AppContext {
  const element = document.getElementById("context-data");
  if (!element?.textContent) {
    return normalizeContext(null);
  }
  try {
    return normalizeContext(JSON.parse(element.textContent) as PartialContext);
  } catch {
    return normalizeContext(null);
  }
}

let cached: AppContext | null = null;
let testOverride: AppContext | null = null;

/**
 * The resolved bootstrap context. Read once from the DOM and memoized, so every
 * `useAppContext()` call across the tree sees the same object.
 */
export function getAppContext(): AppContext {
  if (testOverride) {
    return testOverride;
  }
  if (!cached) {
    cached = readFromDom();
  }
  return cached;
}

/**
 * Test hook: install a partial context (merged over defaults) or pass `null` to
 * clear the override and the DOM cache. Not used by production code.
 */
export function __setAppContextForTests(
  partial: PartialContext | null,
): void {
  cached = null;
  testOverride = partial ? normalizeContext(partial) : null;
}
