import { MessagesSquare, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { isInvalidAnswer, type RagDocumentAnswer } from "@/api/rag";
import { SourceCard } from "@/components/rag/source-card";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

type SortKey = "date_desc" | "date_asc" | "confidence";

/**
 * The evidence rail: every valid per-decision answer, filterable by text,
 * procedure type and language, and sortable by date or confidence. This is the
 * "relevant papers" surface — the source decisions backing the verdict.
 */
export function SourceList({
  answers,
  loading,
  hasConfidence,
}: {
  answers: RagDocumentAnswer[];
  loading: boolean;
  hasConfidence: boolean;
}) {
  const [sort, setSort] = useState<SortKey>(
    hasConfidence ? "confidence" : "date_desc",
  );
  const [search, setSearch] = useState("");
  const [procedure, setProcedure] = useState("all");
  const [language, setLanguage] = useState("all");

  const valid = useMemo(
    () => answers.filter((a) => !isInvalidAnswer(a.answer)),
    [answers],
  );

  const procedureTypes = useMemo(() => {
    const set = new Set<string>();
    for (const a of valid) {
      if (a.document.procedure_type) set.add(a.document.procedure_type);
    }
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [valid]);

  const languages = useMemo(() => {
    const set = new Set<string>();
    for (const a of valid) {
      if (a.document.language) set.add(a.document.language);
    }
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [valid]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const filtered = valid.filter((a) => {
      if (procedure !== "all" && a.document.procedure_type !== procedure) {
        return false;
      }
      if (language !== "all" && a.document.language !== language) {
        return false;
      }
      if (needle) {
        const haystack = [
          a.answer,
          a.citation,
          a.document.procedure_type,
          a.document.decision_type,
          a.document.result,
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
    filtered.sort((a, b) => {
      if (sort === "confidence") {
        return (b.confidence_score ?? 0) - (a.confidence_score ?? 0);
      }
      const da = a.document.decision_date ?? "";
      const db = b.document.decision_date ?? "";
      return sort === "date_asc" ? da.localeCompare(db) : db.localeCompare(da);
    });
    return filtered;
  }, [valid, sort, search, procedure, language]);

  if (loading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (valid.length === 0) {
    return (
      <EmptyState
        icon={MessagesSquare}
        title="No cited decisions"
        description="No valid per-document answers were produced for this question."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-foreground">
          Cited decisions{" "}
          <span className="text-muted-foreground">
            ({visible.length}
            {visible.length !== valid.length ? ` / ${valid.length}` : ""})
          </span>
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter decisions…"
              className="h-9 w-44 pl-8"
              aria-label="Filter cited decisions"
            />
          </div>
          {procedureTypes.length > 1 && (
            <Select value={procedure} onValueChange={setProcedure}>
              <SelectTrigger className="h-9 w-44" aria-label="Procedure type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All procedure types</SelectItem>
                {procedureTypes.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {languages.length > 1 && (
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="h-9 w-32" aria-label="Language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All languages</SelectItem>
                {languages.map((lang) => (
                  <SelectItem key={lang} value={lang}>
                    {lang.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
            <SelectTrigger className="h-9 w-44" aria-label="Sort order">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date_desc">Newest first</SelectItem>
              <SelectItem value="date_asc">Oldest first</SelectItem>
              {hasConfidence && (
                <SelectItem value="confidence">Highest confidence</SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>
      </div>
      {visible.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No decisions match your filters.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {visible.map((answer, position) => (
            <SourceCard key={answer.id} answer={answer} index={position + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
