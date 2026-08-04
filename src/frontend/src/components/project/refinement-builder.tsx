import { useMutation } from "@tanstack/react-query";
import { Plus, Wand2, X } from "lucide-react";
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
  type ProjectFilters,
} from "@/api/project-overview";
import { ApiError } from "@/lib/api-client";
import { formatNumber } from "@/lib/utils";

type Mode = "filter-union" | "filter-exclude";

interface AppliedFilter {
  mode: Mode;
  field: string;
  fieldLabel: string;
  value: string;
}

function buildFiltersPayload(filters: AppliedFilter[]): ProjectFilters {
  const payload: ProjectFilters = {};
  for (const filter of filters) {
    const bucket = (payload[filter.mode] ??= {});
    (bucket[filter.field] ??= []).push(filter.value);
  }
  return payload;
}

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
  const [previewCount, setPreviewCount] = useState<number | null>(null);

  const atLimit = count >= limit;

  const activeType = useMemo(
    () => filterTypes.find((type) => type.value === field),
    [filterTypes, field],
  );

  const resetPreview = () => setPreviewCount(null);

  const addFilter = () => {
    if (!activeType || !value.trim()) return;
    setApplied((prev) => [
      ...prev,
      { mode, field, fieldLabel: activeType.label, value: value.trim() },
    ]);
    setValue("");
    resetPreview();
  };

  const removeFilter = (index: number) => {
    setApplied((prev) => prev.filter((_, i) => i !== index));
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
            <Plus className="size-4" /> Add filter
          </Button>
        </div>

        {applied.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {applied.map((filter, index) => (
              <Badge
                key={`${filter.field}-${filter.value}-${index}`}
                variant={filter.mode === "filter-exclude" ? "destructive" : "default"}
                className="gap-1"
              >
                {filter.mode === "filter-exclude" ? "−" : "+"} {filter.fieldLabel}:{" "}
                {filter.value}
                <button
                  type="button"
                  onClick={() => removeFilter(index)}
                  aria-label={`Remove ${filter.fieldLabel} ${filter.value}`}
                  className="ml-0.5 rounded-full hover:text-foreground"
                >
                  <X className="size-3" />
                </button>
              </Badge>
            ))}
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
            disabled={create.isPending || atLimit || !name.trim()}
          >
            {create.isPending && <Spinner className="size-4" />}
            Create
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
