import getCSRFToken from "./csrf";

function toErrorMessages(data) {
  if (!data) {
    return ["Request failed."];
  }

  if (typeof data.detail === "string") {
    return [data.detail];
  }

  if (Array.isArray(data)) {
    return data.map((value) => String(value));
  }

  if (typeof data === "object") {
    return Object.values(data).flatMap((value) => {
      if (Array.isArray(value)) {
        return value.map((entry) => String(entry));
      }
      return [String(value)];
    });
  }

  return [String(data)];
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
      ...(options.headers ?? {}),
    },
  });

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    const error = new Error(toErrorMessages(data).join(" "));
    error.messages = toErrorMessages(data);
    error.response = data;
    throw error;
  }

  return data;
}

function buildProjectUrl(apiUrls, projectId, suffix = "") {
  return `${apiUrls.projectApiBase}${projectId}/${suffix}`;
}

export function fetchProjectOverview(apiUrls, projectId) {
  return requestJSON(buildProjectUrl(apiUrls, projectId, "overview/"), {
    method: "GET",
  });
}

export function previewProjectFilters(apiUrls, projectId, filters) {
  return requestJSON(buildProjectUrl(apiUrls, projectId, "filters/preview/"), {
    body: JSON.stringify({ filters }),
    method: "POST",
  });
}

export function createProjectRefinement(
  apiUrls,
  projectId,
  refinementName,
  filters
) {
  return requestJSON(buildProjectUrl(apiUrls, projectId, "refinements/"), {
    body: JSON.stringify({
      filters,
      refinement_name: refinementName,
    }),
    method: "POST",
  });
}

export function deleteProjectRefinement(apiUrls, projectId, refinementId) {
  return requestJSON(
    buildProjectUrl(apiUrls, projectId, `refinements/${refinementId}/`),
    {
      method: "DELETE",
    }
  );
}

export function generateProjectClusterSummary(apiUrls, projectId, clusterId) {
  return requestJSON(
    buildProjectUrl(apiUrls, projectId, `clusters/${clusterId}/summary/`),
    {
      method: "POST",
    }
  );
}

export function askTopDocuments(apiUrls, projectId) {
  return requestJSON(buildProjectUrl(apiUrls, projectId, "ask-top-docs/"), {
    method: "POST",
  });
}

const projectOverviewApi = {
  askTopDocuments,
  createProjectRefinement,
  deleteProjectRefinement,
  fetchProjectOverview,
  generateProjectClusterSummary,
  previewProjectFilters,
};

export default projectOverviewApi;
