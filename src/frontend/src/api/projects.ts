import { api } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";

/** Progress is a discriminated union on `kind` (see build_project_progress). */
export type ProjectProgress =
  | {
      kind: "progress";
      current: number;
      max: number;
      percentage: number;
      label: string;
      message: string;
    }
  | { kind: "status"; label: string; message: string };

export interface ProjectListItem {
  id: number;
  name: string;
  query: string;
  step: string;
  step_label: string;
  is_finish: boolean;
  is_shared: boolean;
  can_delete: boolean;
  can_restart: boolean;
  can_open_project: boolean;
  project_url: string;
  progress: ProjectProgress;
  processed_documents: number;
  total_documents: number;
  best_dbcv: number;
  creation_date: string;
  range_begin_date: string;
  range_end_date: string;
  selected_indices: string[];
}

export type HistoricalSort = "more_documents_first" | "less_documents_first";

export function fetchRunningProjects(
  apiUrls: ApiUrls,
): Promise<{ projects: ProjectListItem[] }> {
  return api.get(apiUrls.runningProjects);
}

export function restartRunningProject(
  apiUrls: ApiUrls,
  projectId: number,
): Promise<{ detail: string }> {
  return api.post(`${apiUrls.runningProjects}${projectId}/restart/`);
}

export function deleteProject(
  apiUrls: ApiUrls,
  projectId: number,
): Promise<void> {
  return api.delete(`${apiUrls.projectDeleteBase}${projectId}/`);
}

export function fetchHistoricalProjects(
  apiUrls: ApiUrls,
  options: { search: string; sortType: HistoricalSort },
): Promise<{
  projects: ProjectListItem[];
  query_filter: string;
  sort_type: HistoricalSort;
}> {
  const params = new URLSearchParams();
  if (options.search) params.set("search", options.search);
  params.set("sort_type", options.sortType);
  return api.get(`${apiUrls.historicalProjects}?${params.toString()}`);
}

export function deleteAllFinishedProjects(
  apiUrls: ApiUrls,
): Promise<{ deleted_count: number }> {
  return api.delete(apiUrls.historicalDeleteAll);
}
