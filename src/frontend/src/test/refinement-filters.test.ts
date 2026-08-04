import { describe, expect, it } from "vitest";

import {
  buildFiltersPayload,
  type AppliedFilter,
} from "@/components/project/refinement-filters";

/**
 * The backend (`select_functions.apply_filters`) treats every key containing
 * "filter-union" as a separate OR-group: groups are OR-combined, fields within
 * a group are AND-combined, and values within a field are OR-combined.
 * "filter-exclude" is a single OR bucket. These tests lock that encoding.
 */
describe("buildFiltersPayload", () => {
  const f = (
    over: Partial<AppliedFilter> & Pick<AppliedFilter, "field" | "value">,
  ): AppliedFilter => ({
    mode: "filter-union",
    fieldLabel: over.field,
    group: 0,
    ...over,
  });

  it("returns an empty payload for no filters", () => {
    expect(buildFiltersPayload([])).toEqual({});
  });

  it("AND-combines fields within a single union group", () => {
    const payload = buildFiltersPayload([
      f({ field: "Topic", value: "asylum", group: 0 }),
      f({ field: "Result", value: "rejected", group: 0 }),
    ]);
    expect(payload).toEqual({
      "filter-union-0": { Topic: ["asylum"], Result: ["rejected"] },
    });
  });

  it("OR-combines values of the same field within a group", () => {
    const payload = buildFiltersPayload([
      f({ field: "Topic", value: "asylum", group: 0 }),
      f({ field: "Topic", value: "deportation", group: 0 }),
    ]);
    expect(payload).toEqual({
      "filter-union-0": { Topic: ["asylum", "deportation"] },
    });
  });

  it("emits a distinct filter-union key per OR group", () => {
    const payload = buildFiltersPayload([
      f({ field: "Topic", value: "asylum", group: 0 }),
      f({ field: "Result", value: "granted", group: 1 }),
    ]);
    expect(payload).toEqual({
      "filter-union-0": { Topic: ["asylum"] },
      "filter-union-1": { Result: ["granted"] },
    });
  });

  it("collapses all excluded filters into one filter-exclude bucket", () => {
    const payload = buildFiltersPayload([
      f({ mode: "filter-exclude", field: "Keyword", value: "draft", group: 0 }),
      f({ mode: "filter-exclude", field: "Keyword", value: "interim", group: 1 }),
    ]);
    expect(payload).toEqual({
      "filter-exclude": { Keyword: ["draft", "interim"] },
    });
  });

  it("combines multiple union groups with an exclude bucket", () => {
    const payload = buildFiltersPayload([
      f({ field: "Topic", value: "asylum", group: 0 }),
      f({ field: "Norm", value: "art3", group: 0 }),
      f({ field: "Result", value: "granted", group: 1 }),
      f({ mode: "filter-exclude", field: "Keyword", value: "draft", group: 0 }),
    ]);
    expect(payload).toEqual({
      "filter-union-0": { Topic: ["asylum"], Norm: ["art3"] },
      "filter-union-1": { Result: ["granted"] },
      "filter-exclude": { Keyword: ["draft"] },
    });
  });
});
