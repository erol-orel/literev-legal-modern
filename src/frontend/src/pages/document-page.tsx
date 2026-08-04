import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FileText } from "lucide-react";
import { useParams } from "react-router-dom";

import { PageHeader } from "@/components/common/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppContext } from "@/hooks/use-app-context";
import {
  fetchDocumentContent,
  fetchHighlightedDocumentContent,
  type DocumentContent,
  type DocumentMeta,
  type DocumentPayload,
} from "@/api/documents";
import { ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

/** Full decision text for a corpus document. */
export function DocumentPage() {
  const { documentId = "" } = useParams();
  const { api: apiUrls } = useAppContext();

  const query = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => fetchDocumentContent(apiUrls, documentId),
    enabled: Boolean(documentId),
  });

  return <DocumentView query={query} highlighted={false} />;
}

/** Decision text with the passages a RAG answer cited highlighted inline. */
export function HighlightedDocumentPage() {
  const { documentRagId = "" } = useParams();
  const { api: apiUrls } = useAppContext();

  const query = useQuery({
    queryKey: ["document-highlighted", documentRagId],
    queryFn: () => fetchHighlightedDocumentContent(apiUrls, documentRagId),
    enabled: Boolean(documentRagId),
  });

  return <DocumentView query={query} highlighted />;
}

interface DocumentQuery {
  data: DocumentPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}

function DocumentView({
  query,
  highlighted,
}: {
  query: DocumentQuery;
  highlighted: boolean;
}) {
  const title = highlighted ? "Highlighted document" : "Document";

  if (query.isLoading) {
    return (
      <>
        <PageHeader title={title} />
        <Card>
          <CardContent className="space-y-3 py-6">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      </>
    );
  }

  if (query.isError || !query.data) {
    return (
      <>
        <PageHeader title={title} />
        <Alert variant="destructive">
          <AlertTitle>Could not load the document</AlertTitle>
          <AlertDescription>
            {query.error instanceof ApiError
              ? query.error.messages.join(" ")
              : "Please try again."}
          </AlertDescription>
        </Alert>
      </>
    );
  }

  const { document, content } = query.data;

  return (
    <>
      <PageHeader
        title={title}
        description={
          highlighted
            ? "Passages cited by the answer are highlighted below."
            : undefined
        }
      />
      <Card>
        <CardContent className="p-6">
          <DocumentMetadata document={document} />
          <Separator className="my-5" />
          <DocumentBody content={content} highlighted={highlighted} />
        </CardContent>
      </Card>
    </>
  );
}

function DocumentMetadata({ document }: { document: DocumentMeta }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {document.procedure_type && (
          <Badge variant="secondary">{document.procedure_type}</Badge>
        )}
        {document.language && (
          <Badge variant="outline" className="uppercase">
            {document.language}
          </Badge>
        )}
      </div>
      <p className="text-sm text-foreground">
        <span className="font-semibold">{document.decision_type || "—"}</span>
        {document.decision_date ? `, ${formatDate(document.decision_date)}` : ""}
        {"  "}
        <span className="text-muted-foreground">Result:</span>{" "}
        {document.result || "—"}
      </p>
      <p className="text-sm">
        <span className="font-semibold text-muted-foreground">Normes:</span>{" "}
        {document.standards_refs && document.standards_refs.length > 0 ? (
          document.standards_refs.map((ref, index) => (
            <span key={`${ref.token}-${index}`}>
              {index > 0 && (
                <span className="text-muted-foreground"> · </span>
              )}
              {ref.url ? (
                <a
                  href={ref.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-0.5 text-primary underline-offset-2 hover:underline"
                  title="Ouvrir le texte de loi sur Fedlex"
                >
                  {ref.label}
                  <ExternalLink className="size-3 shrink-0" />
                </a>
              ) : (
                <span className="text-foreground/90">{ref.label}</span>
              )}
            </span>
          ))
        ) : (
          <>{document.standards || "—"}</>
        )}
      </p>
    </div>
  );
}

function DocumentBody({
  content,
  highlighted,
}: {
  content: DocumentContent;
  highlighted: boolean;
}) {
  // All branches render trusted, server-rendered HTML/text from same-origin
  // Django. `legal-prose` styling lives in index.css so both themes read well.
  if (content.html_text) {
    return (
      <article
        className="legal-prose"
        dangerouslySetInnerHTML={{ __html: content.html_text }}
      />
    );
  }

  if (highlighted && content.highlighted_text) {
    return (
      <article
        className="legal-prose whitespace-pre-wrap break-words"
        dangerouslySetInnerHTML={{ __html: content.highlighted_text }}
      />
    );
  }

  if (content.raw_text) {
    return (
      <pre className="legal-prose whitespace-pre-wrap break-words font-sans">
        {content.raw_text}
      </pre>
    );
  }

  return (
    <EmptyState
      icon={FileText}
      title="No content available"
      description="This document has no readable text to display."
    />
  );
}
