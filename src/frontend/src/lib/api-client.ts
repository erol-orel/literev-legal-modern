/**
 * Thin fetch wrapper around the existing DRF endpoints. It keeps the exact
 * server contract the legacy app relied on — same-origin credentials, the
 * `X-CSRFToken` header from Django's `<meta name="csrf-token">`, JSON in and
 * out — while giving callers typed responses and a single `ApiError` to catch.
 */

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** Django puts the CSRF token in a meta tag on the server-rendered shell. */
function getCsrfToken(): string {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta?.getAttribute("content") ?? "";
}

/**
 * Flatten a DRF error body into user-facing strings. DRF returns errors in
 * several shapes: `{ detail: "..." }`, a bare array, or a field→messages map.
 */
function toErrorMessages(data: unknown): string[] {
  if (data == null) {
    return ["Request failed."];
  }

  if (typeof data === "object" && "detail" in data) {
    const { detail } = data as { detail: unknown };
    if (typeof detail === "string") {
      return [detail];
    }
  }

  if (Array.isArray(data)) {
    return data.map((value) => String(value));
  }

  if (typeof data === "object") {
    return Object.values(data as Record<string, unknown>).flatMap((value) =>
      Array.isArray(value)
        ? value.map((entry) => String(entry))
        : [String(value)],
    );
  }

  return [String(data)];
}

/** Error thrown for any non-2xx response; `messages` is always populated. */
export class ApiError extends Error {
  readonly status: number;
  readonly messages: string[];
  readonly data: unknown;

  constructor(status: number, messages: string[], data: unknown) {
    super(messages.join(" ") || `Request failed (${status}).`);
    this.name = "ApiError";
    this.status = status;
    this.messages = messages;
    this.data = data;
  }
}

async function parseBody(response: Response): Promise<unknown> {
  // 204 and empty bodies (e.g. DELETE) have nothing to parse.
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(
  method: HttpMethod,
  url: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };

  // Only unsafe methods need CSRF protection.
  if (method !== "GET") {
    headers["X-CSRFToken"] = getCsrfToken();
  }

  const init: RequestInit = {
    method,
    credentials: "same-origin",
    headers,
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const response = await fetch(url, init);
  const data = await parseBody(response);

  if (!response.ok) {
    throw new ApiError(response.status, toErrorMessages(data), data);
  }

  return data as T;
}

/** A binary response plus the server-suggested filename (for file exports). */
export interface DownloadResult {
  blob: Blob;
  filename: string | null;
}

async function download(url: string, body?: unknown): Promise<DownloadResult> {
  const headers: Record<string, string> = {
    Accept: "application/octet-stream, application/json",
    "X-CSRFToken": getCsrfToken(),
  };
  const init: RequestInit = { method: "POST", credentials: "same-origin", headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    const data = await parseBody(response);
    throw new ApiError(response.status, toErrorMessages(data), data);
  }

  return {
    blob: await response.blob(),
    filename: response.headers.get("Content-Disposition"),
  };
}

export const api = {
  get: <T>(url: string): Promise<T> => request<T>("GET", url),
  post: <T>(url: string, body?: unknown): Promise<T> =>
    request<T>("POST", url, body),
  put: <T>(url: string, body?: unknown): Promise<T> =>
    request<T>("PUT", url, body),
  patch: <T>(url: string, body?: unknown): Promise<T> =>
    request<T>("PATCH", url, body),
  delete: <T>(url: string): Promise<T> => request<T>("DELETE", url),
  download,
};
