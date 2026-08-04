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

async function requestJSON(url) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
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

export function fetchDocumentContent(apiUrls, documentId) {
  return requestJSON(`${apiUrls.documentContentBase}${documentId}/`);
}

export function fetchHighlightedDocumentContent(apiUrls, documentRagId) {
  return requestJSON(
    `${apiUrls.documentHighlightedBase}${documentRagId}/highlighted/`
  );
}

const documentContentApi = {
  fetchDocumentContent,
  fetchHighlightedDocumentContent,
};

export default documentContentApi;
