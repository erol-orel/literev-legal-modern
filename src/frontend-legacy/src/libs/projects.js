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

export function fetchRunningProjects(apiUrls) {
  return requestJSON(apiUrls.runningProjects);
}

export function restartRunningProject(apiUrls, projectId) {
  return requestJSON(`${apiUrls.runningProjects}${projectId}/restart/`, {
    method: "POST",
  });
}

export function deleteProject(apiUrls, projectId) {
  return requestJSON(`${apiUrls.projectDeleteBase}${projectId}/`, {
    method: "DELETE",
  });
}

export function fetchHistoricalProjects(
  apiUrls,
  { search = "", sortType = "more_documents_first" } = {}
) {
  const params = new URLSearchParams();
  if (search) {
    params.set("search", search);
  }
  params.set("sort_type", sortType);

  return requestJSON(`${apiUrls.historicalProjects}?${params.toString()}`);
}

export function deleteAllFinishedProjects(apiUrls) {
  return requestJSON(apiUrls.historicalDeleteAll, {
    method: "DELETE",
  });
}

const projectsApi = {
  deleteAllFinishedProjects,
  deleteProject,
  fetchHistoricalProjects,
  fetchRunningProjects,
  restartRunningProject,
};

export default projectsApi;
