import { api, type DownloadResult } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";

/** A reviewer's verdict on a document within an iteration. */
export type Verdict = "yes" | "maybe" | "no";

/** One document row in the triage table. */
export interface TableSelectionRow {
  id: number;
  /** true → yes, false → no, null → undecided (maybe). */
  is_check: boolean | null;
  /** false marks a neighbour document pulled in by the last iteration. */
  is_initial: boolean;
  procedure_type: string;
  content_url: string;
  decision_type: string;
  decision_date: string | null;
  result: string;
  standards: string;
  /** Server-rendered HTML excerpt (trusted, same-origin Django). */
  sample_document: string;
  es_score?: number;
  topic?: string;
  color?: string;
  hdbscan_score?: number;
}

export interface TableSelectionIteration {
  id: number;
  name: string;
  is_active: boolean;
  is_parent: boolean;
  is_root: boolean;
}

export interface SortOption {
  value: string;
  label: string;
}

export interface TableSelectionTable {
  rows: TableSelectionRow[];
  sort_by: string;
  sort_options: SortOption[];
  current_page: number;
  total_pages: number;
  has_es_scores: boolean;
  has_hdbscan_scores: boolean;
}

export interface TableSelectionProject {
  name: string;
  creation_date: string;
  query: string;
  range_begin_date: string;
  range_end_date: string;
  processed_documents: number;
  can_iterate: boolean;
}

export interface TableSelectionFilters {
  union_sets_html?: string;
  excluded_set_html?: string;
}

export interface TableSelectionState {
  /** When set and different from the current path, the client should redirect. */
  canonical_url?: string;
  /** True while the backend is (re)computing results for a new filter/iteration. */
  processing_filters?: boolean;
  project: TableSelectionProject;
  counts: { initial?: number; neighbour?: number; chosen?: number };
  filters?: TableSelectionFilters;
  current_iteration_id: number | null;
  iterations: TableSelectionIteration[];
  table: TableSelectionTable;
  urls: { back_to_filter: string };
}

/** The three disjoint id buckets the selection endpoints expect. */
export interface SelectionPayload {
  selected_documents: number[];
  deselected_documents: number[];
  maybe_documents: number[];
}

/** Most iteration mutations answer with the canonical URL to navigate to. */
export interface UrlResponse {
  url: string;
  detail?: string;
}

function baseUrl(
  apiUrls: ApiUrls,
  projectId: string | number,
  refinementId: string | number,
): string {
  return `${apiUrls.tableSelectionBase}${projectId}/${refinementId}/`;
}

function selectionBody(iterationId: number | null, selection: SelectionPayload) {
  return {
    iteration_id: iterationId,
    selected_documents: selection.selected_documents,
    deselected_documents: selection.deselected_documents,
    maybe_documents: selection.maybe_documents,
  };
}

export function fetchTableSelectionState(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId?: number | null;
    page?: number;
    orderBy?: string;
  },
): Promise<TableSelectionState> {
  const params = new URLSearchParams();
  if (args.iterationId) params.set("iteration_id", String(args.iterationId));
  params.set("page", String(args.page ?? 1));
  params.set("order_by", args.orderBy ?? "es_score");
  return api.get(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}state/?${params.toString()}`,
  );
}

export function updateTableSelection(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number | null;
    selection: SelectionPayload;
  },
): Promise<{ detail?: string }> {
  return api.put(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}selection/`,
    selectionBody(args.iterationId, args.selection),
  );
}

export function activateTableSelectionIteration(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number;
    orderBy?: string;
  },
): Promise<UrlResponse> {
  return api.post(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}iterations/${args.iterationId}/activate/`,
    { order_by: args.orderBy ?? "es_score" },
  );
}

export function deleteTableSelectionIteration(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number;
    orderBy?: string;
  },
): Promise<UrlResponse> {
  const params = new URLSearchParams({ order_by: args.orderBy ?? "es_score" });
  return api.delete(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}iterations/${args.iterationId}/?${params.toString()}`,
  );
}

export function iterateTableSelection(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number | null;
    selection: SelectionPayload;
  },
): Promise<UrlResponse> {
  return api.post(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}iterate/`,
    selectionBody(args.iterationId, args.selection),
  );
}

export function resetTableSelection(
  apiUrls: ApiUrls,
  args: { projectId: string | number; refinementId: string | number },
): Promise<UrlResponse> {
  return api.post(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}reset/`,
  );
}

export function setAllTableSelection(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number | null;
    mode: Verdict;
  },
): Promise<{ detail?: string }> {
  return api.post(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}check-all/`,
    { iteration_id: args.iterationId, mode: args.mode },
  );
}

export function exportTableSelection(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number | null;
    selection: SelectionPayload;
  },
): Promise<DownloadResult> {
  return api.download(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}export/`,
    selectionBody(args.iterationId, args.selection),
  );
}

export function askSelectedTableDocuments(
  apiUrls: ApiUrls,
  args: {
    projectId: string | number;
    refinementId: string | number;
    iterationId: number | null;
    selection: SelectionPayload;
  },
): Promise<UrlResponse> {
  return api.post(
    `${baseUrl(apiUrls, args.projectId, args.refinementId)}ask-selected/`,
    selectionBody(args.iterationId, args.selection),
  );
}

/** Map a row's stored verdict flag to the tri-state control value. */
export function verdictFromRow(row: TableSelectionRow): Verdict {
  if (row.is_check === true) return "yes";
  if (row.is_check === false) return "no";
  return "maybe";
}

/** Split a verdict map into the three id buckets the API expects. */
export function selectionPayloadFrom(
  verdicts: Record<number, Verdict>,
): SelectionPayload {
  const payload: SelectionPayload = {
    selected_documents: [],
    deselected_documents: [],
    maybe_documents: [],
  };
  for (const [id, verdict] of Object.entries(verdicts)) {
    const numericId = Number(id);
    if (verdict === "yes") payload.selected_documents.push(numericId);
    else if (verdict === "no") payload.deselected_documents.push(numericId);
    else payload.maybe_documents.push(numericId);
  }
  return payload;
}

/** Pull a download filename out of a Content-Disposition header. */
export function filenameFromDisposition(disposition: string | null): string {
  const fallback = "selected_documents_literev.csv";
  if (!disposition) return fallback;
  const match = disposition.match(/filename=([^;]+)/i);
  return match ? match[1].replaceAll('"', "").trim() : fallback;
}
