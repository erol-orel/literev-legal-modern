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

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
    },
    credentials: "same-origin",
    body: JSON.stringify(payload),
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

export function convertToBooleanQuery(apiUrls, naturalLanguageQuery) {
  return postJSON(apiUrls.searchConvertQuery, {
    natural_language_query: naturalLanguageQuery,
  });
}

export function validateSearch(apiUrls, payload) {
  return postJSON(apiUrls.searchValidate, payload);
}

export function previewSearch(apiUrls, payload) {
  return postJSON(apiUrls.searchPreview, payload);
}

export function createSearchProject(apiUrls, payload) {
  return postJSON(apiUrls.searchProjects, payload);
}

const searchApi = {
  convertToBooleanQuery,
  createSearchProject,
  previewSearch,
  validateSearch,
};

export default searchApi;
