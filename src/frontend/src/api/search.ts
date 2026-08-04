import { api } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";

/** Payload accepted by the validate / preview / projects endpoints. */
export interface SearchPayload {
  project_name: string;
  selected_indices: string[];
  natural_language_query: string;
  query: string;
  range_begin_date: string;
  range_end_date: string;
}

/** Normalized payload echoed back by preview/validate. */
export interface SearchPreview extends SearchPayload {
  total_documents: number;
  can_continue: boolean;
  can_cluster: boolean;
  clustering_min_documents: number;
}

export interface CreatedProject {
  id: number;
  name: string;
  total_documents: number;
  detail: string;
  urls: { running: string; project: string };
}

export function convertToBooleanQuery(
  apiUrls: ApiUrls,
  naturalLanguageQuery: string,
): Promise<{ query: string }> {
  return api.post(apiUrls.searchConvertQuery, {
    natural_language_query: naturalLanguageQuery,
  });
}

export function previewSearch(
  apiUrls: ApiUrls,
  payload: SearchPayload,
): Promise<SearchPreview> {
  return api.post(apiUrls.searchPreview, payload);
}

export function createSearchProject(
  apiUrls: ApiUrls,
  payload: SearchPayload,
): Promise<CreatedProject> {
  return api.post(apiUrls.searchProjects, payload);
}
