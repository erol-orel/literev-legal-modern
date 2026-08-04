import type { ProjectFilters } from "@/api/project-overview";

export type Mode = "filter-union" | "filter-exclude";

export interface AppliedFilter {
  mode: Mode;
  field: string;
  fieldLabel: string;
  value: string;
  /** Union group index; ignored for excluded filters. */
  group: number;
}

/**
 * Build the backend filter payload from the applied filters.
 *
 * Each union group becomes its own `filter-union-<n>` key: the backend
 * OR-combines separate union keys while AND-combining fields within one
 * group (see `select_functions.apply_filters`). Excluded filters share a
 * single `filter-exclude` bucket.
 */
export function buildFiltersPayload(filters: AppliedFilter[]): ProjectFilters {
  const payload: ProjectFilters = {};
  for (const filter of filters) {
    const key =
      filter.mode === "filter-union"
        ? `filter-union-${filter.group}`
        : "filter-exclude";
    const bucket = (payload[key] ??= {});
    (bucket[filter.field] ??= []).push(filter.value);
  }
  return payload;
}
