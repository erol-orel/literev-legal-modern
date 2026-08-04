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

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": getCSRFToken(),
      ...(options.headers ?? {}),
    },
  });

  return response;
}

async function requestJSON(url, options = {}) {
  const response = await request(url, options);

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

async function requestBlob(url, options = {}) {
  const response = await request(url, options);

  if (!response.ok) {
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    const error = new Error(toErrorMessages(data).join(" "));
    error.messages = toErrorMessages(data);
    error.response = data;
    throw error;
  }

  const blob = await response.blob();
  return {
    blob,
    filename: response.headers.get("Content-Disposition"),
  };
}

function buildBaseUrl(apiUrls, projectId, refinementId) {
  return `${apiUrls.tableSelectionBase}${projectId}/${refinementId}/`;
}

function buildSelectionBody(iterationId, selection) {
  return JSON.stringify({
    iteration_id: iterationId,
    selected_documents: selection.selected_documents,
    deselected_documents: selection.deselected_documents,
    maybe_documents: selection.maybe_documents,
  });
}

export function fetchTableSelectionState(
  apiUrls,
  { projectId, refinementId, iterationId = null, page = 1, orderBy = "es_score" }
) {
  const params = new URLSearchParams();
  if (iterationId) {
    params.set("iteration_id", String(iterationId));
  }
  params.set("page", String(page));
  params.set("order_by", orderBy);

  return requestJSON(
    `${buildBaseUrl(apiUrls, projectId, refinementId)}state/?${params.toString()}`,
    {
      method: "GET",
    }
  );
}

export function updateTableSelection(apiUrls, { projectId, refinementId, iterationId, selection }) {
  return requestJSON(`${buildBaseUrl(apiUrls, projectId, refinementId)}selection/`, {
    body: buildSelectionBody(iterationId, selection),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PUT",
  });
}

export function activateTableSelectionIteration(
  apiUrls,
  { projectId, refinementId, iterationId, orderBy = "es_score" }
) {
  return requestJSON(
    `${buildBaseUrl(apiUrls, projectId, refinementId)}iterations/${iterationId}/activate/`,
    {
      body: JSON.stringify({ order_by: orderBy }),
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
    }
  );
}

export function deleteTableSelectionIteration(
  apiUrls,
  { projectId, refinementId, iterationId, orderBy = "es_score" }
) {
  const params = new URLSearchParams({ order_by: orderBy });
  return requestJSON(
    `${buildBaseUrl(
      apiUrls,
      projectId,
      refinementId
    )}iterations/${iterationId}/?${params.toString()}`,
    {
      method: "DELETE",
    }
  );
}

export function iterateTableSelection(
  apiUrls,
  { projectId, refinementId, iterationId, selection }
) {
  return requestJSON(`${buildBaseUrl(apiUrls, projectId, refinementId)}iterate/`, {
    body: buildSelectionBody(iterationId, selection),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function resetTableSelection(apiUrls, { projectId, refinementId }) {
  return requestJSON(`${buildBaseUrl(apiUrls, projectId, refinementId)}reset/`, {
    method: "POST",
  });
}

export function setAllTableSelection(apiUrls, { projectId, refinementId, iterationId, mode }) {
  return requestJSON(`${buildBaseUrl(apiUrls, projectId, refinementId)}check-all/`, {
    body: JSON.stringify({ iteration_id: iterationId, mode }),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function exportTableSelection(apiUrls, { projectId, refinementId, iterationId, selection }) {
  return requestBlob(`${buildBaseUrl(apiUrls, projectId, refinementId)}export/`, {
    body: buildSelectionBody(iterationId, selection),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function askSelectedTableDocuments(
  apiUrls,
  { projectId, refinementId, iterationId, selection }
) {
  return requestJSON(
    `${buildBaseUrl(apiUrls, projectId, refinementId)}ask-selected/`,
    {
      body: buildSelectionBody(iterationId, selection),
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
    }
  );
}

const tableSelectionApi = {
  activateTableSelectionIteration,
  askSelectedTableDocuments,
  deleteTableSelectionIteration,
  exportTableSelection,
  fetchTableSelectionState,
  iterateTableSelection,
  resetTableSelection,
  setAllTableSelection,
  updateTableSelection,
};

export default tableSelectionApi;
