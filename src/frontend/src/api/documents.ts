import { api } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";

/** Metadata header shown above every document body. */
export interface DocumentMeta {
  procedure_type: string;
  decision_type: string;
  decision_date: string | null;
  result: string;
  standards: string;
}

/**
 * Document body. The backend supplies one of these, in priority order:
 * pre-rendered `html_text`, RAG-cited `highlighted_text` (highlighted view
 * only), or plain `raw_text`. All HTML is trusted, same-origin Django output.
 */
export interface DocumentContent {
  html_text?: string;
  highlighted_text?: string;
  raw_text?: string;
}

export interface DocumentPayload {
  document: DocumentMeta;
  content: DocumentContent;
}

export function fetchDocumentContent(
  apiUrls: ApiUrls,
  documentId: string | number,
): Promise<DocumentPayload> {
  return api.get(`${apiUrls.documentContentBase}${documentId}/`);
}

export function fetchHighlightedDocumentContent(
  apiUrls: ApiUrls,
  documentRagId: string | number,
): Promise<DocumentPayload> {
  return api.get(
    `${apiUrls.documentHighlightedBase}${documentRagId}/highlighted/`,
  );
}
