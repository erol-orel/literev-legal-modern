import { useMutation } from "@tanstack/react-query";
import { Layers, Plus, Wand2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  createProjectRefinement,
  previewProjectFilters,
  type FilterTypeDefinition,
} from "@/api/project-overview";
import { ApiError } from "@/lib/api-client";
import { formatNumber } from "@/lib/utils";
import {
  buildFiltersPayload,
  type AppliedFilter,
  type Mode,
} from "@/components/project/refinement-filters";

export function RefinementBuilder({
  projectId,
  filterTypes,
  limit,
  count,
}: {
  projectId: string;
  filterTypes: FilterTypeDefinition[];
  limit: number;
  count: number;
}) {
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [applied, setApplied] = useState<AppliedFilter[]>([]);
  const [field, setField] = useState(filterTypes[0]?.value ?? "");
  const [mode, setMode] = useState<Mode>("filter-union");
  const [value, setValue] = useState("");
  const [currentGroup, setCurrentGroup] = useState(0);
  const [previewCount, setPreviewCount] = useState<number | null>(null);

  const atLimit = count >= limit;

  const activeType = useMemo(
    () => filterTypes.find((type) => type.value === field),
    [filterTypes, field],
  );

  /** Union filters grouped for display, renumbered contiguously. */
  const unionGroups = useMemo(() => {
    const ids = [
      ...new Set(
        applied.filter((f) => f.mode === "filter-union").map((f) => f.group),
      ),
    ].sort((a, b) => a - b);
    return ids.map((id) => ({
      id,
      filters: applied.filter(
        (f) => f.mode === "filter-union" && f.group === id,
      ),
    }));
  }, [applied]);

  const excludeFilters = useMemo(
    () => applied.filter((f) => f.mode === "filter-exclude"),
    [applied],
  );

  const currentGroupHasFilters = applied.some(
    (f) => f.mode === "filter-union" && f.group === currentGroup,
  );

  const resetPreview = () => setPreviewCount(null);

  const addFilter = () => {
    if (!activeType || !value.trim()) return;
    setApplied((prev) => [
      ...prev,
      {
        mode,
        field,
        fieldLabel: activeType.label,
        value: value.trim(),
        group: currentGroup,
      },
    ]);
    setValue("");
    resetPreview();
  };

  const startNewGroup = () => {
    if (!currentGroupHasFilters) return;
    setCurrentGroup((g) => g + 1);
    setMode("filter-union");
    resetPreview();
  };

  const removeFilter = (target: AppliedFilter) => {
    setApplied((prev) => prev.filter((f) => f !== target));
    resetPreview();
  };

  const notifyError = (error: unknown) =>
    toast({
      variant: "destructive",
      title: "Refinement failed",
      description:
        error instanceof ApiError ? error.messages.join(" ") : "Unexpected error.",
    });

  const preview = useMutation({
    mutationFn: () =>
      previewProjectFilters(apiUrls, projectId, buildFiltersPayload(applied)),
    onSuccess: (data) => setPreviewCount(data.number_documents),
    onError: notifyError,
  });

  const create = useMutation({
    mutationFn: () =>
      createProjectRefinement(
        apiUrls,
        projectId,
        name.trim(),
        buildFiltersPayload(applied),
      ),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: "Refinement created",
        description: `${formatNumber(data.number_documents)} documents.`,
      });
      navigate(data.url);
    },
    onError: notifyError,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Wand2 className="size-4 text-primary" /> New refinement
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="refinement-name">Name</Label>
          <Input
            id="refinement-name"
            placeholder="e.g. Rejected appeals only"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">
            Add a filter
          </Label>
          <Select
            value={field}
            onValueChange={(next) => {
              setField(next);
              setValue("");
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Field" />
            </SelectTrigger>
            <SelectContent>
              {filterTypes.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={mode} onValueChange={(next) => setMode(next as Mode)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="filter-union">Include</SelectItem>
              <SelectItem value="filter-exclude">Exclude</SelectItem>
            </SelectContent>
          </Select>

          {activeType?.options && activeType.options.length > 0 ? (
            <Select value={value} onValueChange={setValue}>
              <SelectTrigger>
                <SelectValue placeholder="Value" />
              </SelectTrigger>
              <SelectContent>
                {activeType.options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              placeholder={activeType?.placeholder ?? "Value"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addFilter();
                }
              }}
            />
          )}

          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={addFilter}
            disabled={!value.trim()}
          >
            <Plus className="size-4" />{" "}
            {mode === "filter-exclude" ? "Exclude" : "Add to group"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={startNewGroup}
            disabled={!currentGroupHasFilters}
            title="Start a new OR group: documents matching this group OR the previous ones"
          >
            <Layers className="size-4" /> New OR group
          </Button>
        </div>

        {(unionGroups.length > 0 || excludeFilters.length > 0) && (
          <div className="space-y-3">
            {unionGroups.map((group, index) => (
              <div key={group.id}>
                {index > 0 && (
                  <div className="flex items-center gap-2 py-1 text-xs font-semibold uppercase text-muted-foreground">
                    <span className="h-px flex-1 bg-border" /> or{" "}
                    <span className="h-px flex-1 bg-border" />
                  </div>
                )}
                <div
                  className={`flex flex-wrap items-center gap-1.5 rounded-lg border p-2 ${
                    group.id === currentGroup
                      ? "border-primary/50 bg-primary/5"
                      : "bg-muted/20"
                  }`}
                >
                  {group.filters.map((filter, fIndex) => (
                    <span
                      key={`${filter.field}-${filter.value}-${fIndex}`}
                      className="flex items-center gap-1.5"
                    >
                      {fIndex > 0 && (
                        <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                          and
                        </span>
                      )}
                      <Badge variant="default" className="gap-1">
                        {filter.fieldLabel}: {filter.value}
                        <button
                          type="button"
                          onClick={() => removeFilter(filter)}
                          aria-label={`Remove ${filter.fieldLabel} ${filter.value}`}
                          className="ml-0.5 rounded-full hover:text-foreground"
                        >
                          <X className="size-3" />
                        </button>
                      </Badge>
                    </span>
                  ))}
                </div>
              </div>
            ))}

            {excludeFilters.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                  and not
                </span>
                {excludeFilters.map((filter, index) => (
                  <Badge
                    key={`${filter.field}-${filter.value}-${index}`}
                    variant="destructive"
                    className="gap-1"
                  >
                    {filter.fieldLabel}: {filter.value}
                    <button
                      type="button"
                      onClick={() => removeFilter(filter)}
                      aria-label={`Remove ${filter.fieldLabel} ${filter.value}`}
                      className="ml-0.5 rounded-full hover:text-foreground"
                    >
                      <X className="size-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {previewCount !== null && (
          <p className="text-sm text-muted-foreground">
            Matches:{" "}
            <span className="font-semibold text-foreground">
              {formatNumber(previewCount)}
            </span>{" "}
            documents
          </p>
        )}

        {atLimit && (
          <p className="text-xs text-warning">
            Refinement limit reached ({count}/{limit}).
          </p>
        )}

        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => preview.mutate()}
            disabled={preview.isPending || applied.length === 0}
          >
            {preview.isPending && <Spinner className="size-4" />}
            Preview
          </Button>
          <Button
            className="flex-1"
            onClick={() => create.mutate()}
            disabled={create.isPending || atLimit || !name.trim() || applied.length === 0}
          >
            {create.isPending && <Spinner className="size-4" />}
            Create
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
