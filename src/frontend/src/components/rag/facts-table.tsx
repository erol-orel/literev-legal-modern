import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import type { RagKeyElement } from "@/api/rag";
import { Button } from "@/components/ui/button";

/** Prettify an arbitrary payload key into a header ("law_article" → "Law article"). */
function prettyColumn(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function formatCell(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value == null) return "";
  return String(value);
}

/**
 * Renders the RAG "éléments clés" / "articles de loi" tables. Rows are arbitrary
 * column maps (columns taken from the first row) with an optional `references`
 * list linking into the source documents and an `article_url` (Fedlex) linking
 * the `article` cell.
 */
export function RagFactsTable({
  title,
  rows,
}: {
  title?: string;
  rows: RagKeyElement[];
}) {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]).filter((col) => col !== "article_url");

  return (
    <div className="space-y-2">
      {title && (
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </p>
      )}
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {col === "references" ? "Références" : prettyColumn(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-t align-top">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-foreground/90">
                    {col === "references" ? (
                      <div className="flex flex-wrap gap-1">
                        {(row.references ?? []).map((ref) => (
                          <Button
                            key={`${ref.id}-${ref.procedure_type}`}
                            asChild
                            variant="secondary"
                            size="sm"
                            className="h-6 px-2 text-xs"
                          >
                            <Link to={`/contentdocument/${ref.id}/`}>
                              {ref.procedure_type}
                            </Link>
                          </Button>
                        ))}
                      </div>
                    ) : col === "article" &&
                      typeof row.article_url === "string" ? (
                      <a
                        href={row.article_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-medium text-primary underline-offset-2 hover:underline"
                        title="Ouvrir le texte de loi sur Fedlex"
                      >
                        {formatCell(row[col])}
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : (
                      formatCell(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
