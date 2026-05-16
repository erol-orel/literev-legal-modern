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

export function fetchRagContext(apiUrls, projectId, ragId = null) {
  const base = apiUrls.ragContextBase;
  const suffix = ragId ? `context/${ragId}/` : "context/";
  return requestJSON(`${base}${projectId}/${suffix}`, { method: "GET" });
}

export function deleteRagEntry(apiUrls, projectId, ragId) {
  return requestJSON(`${apiUrls.ragDeleteBase}${projectId}/${ragId}/`, {
    method: "DELETE",
  });
}

export function createRagEntry(apiUrls, projectId, payload) {
  return requestJSON(`${apiUrls.ragCreateBase}${projectId}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchRagStatus(apiUrls, projectId, ragId) {
  return requestJSON(`${apiUrls.ragStatusBase}${projectId}/${ragId}/`, {
    method: "GET",
  });
}

export function fetchRagDocuments(apiUrls, ragId) {
  const params = new URLSearchParams({ project_rag: String(ragId) });
  return requestJSON(`${apiUrls.ragDocumentsBase}?${params.toString()}`, {
    method: "GET",
  });
}

const ragApi = {
  fetchRagContext,
  deleteRagEntry,
  createRagEntry,
  fetchRagStatus,
  fetchRagDocuments,
};

export default ragApi;
