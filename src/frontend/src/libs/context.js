const DEFAULT_CONTEXT = {
  appName: "LiteRev Legal",
  urls: {
    home: "/",
    search: "/search/",
    team: "/team/",
    product: "/product/",
    company: "/company/",
    blog: "/blog/",
    login: "/accounts/login/",
    logout: "/accounts/logout/",
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
