const DEFAULT_CONTEXT = {
  appName: "LiteRev Legal",
  urls: {
    home: "/",
    search: "/search/",
    running: "/running/",
    historicalpage: "/historicalpage/",
    projectBase: "/project/",
    contentdocumentBase: "/contentdocument/",
    contentdocumentHighlightedBase: "/contentdocument_highlighted/",
    tableselectBase: "/tableselect/",
    ragBase: "/rag/",
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

function normalizeContext(context = {}) {
  return {
    ...DEFAULT_CONTEXT,
    ...context,
    urls: {
      ...DEFAULT_CONTEXT.urls,
      ...(context?.urls ?? {}),
    },
    api: {
      ...DEFAULT_CONTEXT.api,
      ...(context?.api ?? {}),
    },
    search: {
      ...DEFAULT_CONTEXT.search,
      ...(context?.search ?? {}),
    },
    user: {
      ...DEFAULT_CONTEXT.user,
      ...(context?.user ?? {}),
    },
  };
}

export function getContext(initialContext = null) {
  if (initialContext) {
    return normalizeContext(initialContext);
  }

  const contextElement = document.getElementById("context-data");
  if (!contextElement?.textContent) {
    return normalizeContext();
  }

  try {
    return normalizeContext(JSON.parse(contextElement.textContent));
  } catch {
    return normalizeContext();
  }
}

export default getContext;
