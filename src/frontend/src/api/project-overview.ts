import { api } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";
import type { ProjectProgress } from "@/api/projects";

export interface ProjectMeta {
  id: number;
  name: string;
  query: string;
  natural_language_query: string;
  step: string;
  step_label: string;
  is_running: boolean;
  is_finish: boolean;
  is_shared: boolean;
  can_delete: boolean;
  can_ask_top_docs: boolean;
  progress: ProjectProgress;
  processed_documents: number;
  total_documents: number;
  best_dbcv: number;
  creation_date: string;
  range_begin_date: string;
  range_end_date: string;
  selected_indices: string[];
}

export interface RepresentativeDocument {
  decision_type: string;
  document_id: string;
  procedure_type: string;
  result: string;
}

export interface ClusterSummaryItem {
  cluster_id: number;
  cluster_order: number;
  topic: string;
  topic_label: string;
  topic_color: string;
  summary_text: string;
  total_documents: number;
  representative_document: RepresentativeDocument | null;
}

export interface RefinementItem {
  id: number;
  name: string;
  owner_name: string;
  can_delete: boolean;
  filters: Record<string, unknown>;
  open_url: string;
}

export interface FilterOption {
  label: string;
  value: string;
  tooltip?: string;
}

export interface FilterTypeDefinition {
  input_kind: "select" | "datalist" | "text";
  label: string;
  value: string;
  placeholder?: string;
  options?: FilterOption[];
}

export interface ClusterPlot {
  div_plot: string;
  script_plot: string;
}

export interface ProjectOverview {
  project: ProjectMeta;
  cluster_summaries: ClusterSummaryItem[];
  refinements: RefinementItem[];
  filters: {
    refinement_limit: number;
    refinement_count: number;
    types: FilterTypeDefinition[];
  };
  no_clusters: boolean;
  plot: ClusterPlot | null;
}

/** Overview may instead return a redirect hint while still collecting docs. */
export interface OverviewRedirect {
  detail: string;
  redirect_url: string;
}

export type OverviewResponse = ProjectOverview | OverviewRedirect;

export function isOverviewRedirect(
  response: OverviewResponse,
): response is OverviewRedirect {
  return "redirect_url" in response;
}

/** Filters payload: { "filter-union": {...}, "filter-exclude": {...} }. */
export type ProjectFilters = Record<string, Record<string, string[]>>;

export function fetchProjectOverview(
  apiUrls: ApiUrls,
  projectId: string | number,
): Promise<OverviewResponse> {
  return api.get(`${apiUrls.projectApiBase}${projectId}/overview/`);
}

export function previewProjectFilters(
  apiUrls: ApiUrls,
  projectId: string | number,
  filters: ProjectFilters,
): Promise<{ can_continue: boolean; filters: ProjectFilters; number_documents: number }> {
  return api.post(`${apiUrls.projectApiBase}${projectId}/filters/preview/`, {
    filters,
  });
}

export function createProjectRefinement(
  apiUrls: ApiUrls,
  projectId: string | number,
  refinementName: string,
  filters: ProjectFilters,
): Promise<{
  detail: string;
  id: number;
  name: string;
  number_documents: number;
  refinement: RefinementItem;
  url: string;
}> {
  return api.post(`${apiUrls.projectApiBase}${projectId}/refinements/`, {
    refinement_name: refinementName,
    filters,
  });
}

export function deleteProjectRefinement(
  apiUrls: ApiUrls,
  projectId: string | number,
  refinementId: number,
): Promise<void> {
  return api.delete(
    `${apiUrls.projectApiBase}${projectId}/refinements/${refinementId}/`,
  );
}

export function generateProjectClusterSummary(
  apiUrls: ApiUrls,
  projectId: string | number,
  clusterId: number,
): Promise<{ cluster: ClusterSummaryItem; detail: string }> {
  return api.post(
    `${apiUrls.projectApiBase}${projectId}/clusters/${clusterId}/summary/`,
  );
}

export function askTopDocuments(
  apiUrls: ApiUrls,
  projectId: string | number,
): Promise<{ detail: string; urls: { rag: string } }> {
  return api.post(`${apiUrls.projectApiBase}${projectId}/ask-top-docs/`);
}
