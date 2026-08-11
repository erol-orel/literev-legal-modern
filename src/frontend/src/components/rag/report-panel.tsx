import { Check, Copy, Download, FileText } from "lucide-react";
import { useState } from "react";

import type { RagContext, RagDocumentAnswer } from "@/api/rag";
import { RagFactsTable } from "@/components/rag/facts-table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import { buildReportText } from "@/lib/citation";

/** Slugify the question into a safe download filename. */
function reportFilename(context: RagContext): string {
  const base =
    context.project.natural_language_query ||
    context.current?.query ||
    "literev-report";
  const slug = base
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${slug || "literev-report"}.txt`;
}

/**
 * The extractable report: the structured "éléments clés" and "articles de loi"
 * tables the pipeline produced, plus one-click copy and download of the full
 * report (question, summary, rule of law and every cited decision) so a jurist
 * can drop it straight into a memo.
 */
export function ReportPanel({
  context,
  answers,
}: {
  context: RagContext;
  answers: RagDocumentAnswer[];
}) {
  const { toast } = useToast();
  const { api: apiUrls } = useAppContext();
  const [copied, setCopied] = useState(false);
  const current = context.current;
  if (!current) return null;

  // Server-rendered Word memo (see `api-rag-report-docx`); session-cookie auth,
  // so a plain download link works.
  const docxUrl = `${apiUrls.ragReportBase}${context.project.id}/${current.id}/report.docx/`;

  const showKeyElements =
    current.has_section_ans &&
    Boolean(current.summary_text) &&
    current.key_elements.length > 0;
  const showLawArticles = current.law_articles.length > 0;

  const copyReport = async () => {
    try {
      await navigator.clipboard.writeText(buildReportText(context, answers));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
      toast({ variant: "success", title: "Report copied" });
    } catch {
      toast({
        variant: "destructive",
        title: "Copy failed",
        description: "Clipboard is unavailable in this browser.",
      });
    }
  };

  const downloadReport = () => {
    const blob = new Blob([buildReportText(context, answers)], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = reportFilename(context);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast({ variant: "success", title: "Report downloaded" });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">Report</CardTitle>
            <CardDescription>
              Extract the analysis for your memo.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={copyReport}>
              {copied ? (
                <Check className="size-3.5 text-success" />
              ) : (
                <Copy className="size-3.5" />
              )}
              Copy report
            </Button>
            <Button variant="outline" size="sm" onClick={downloadReport}>
              <Download className="size-3.5" /> Text
            </Button>
            <Button asChild variant="default" size="sm">
              <a href={docxUrl} download>
                <FileText className="size-3.5" /> Word
              </a>
            </Button>
          </div>
        </div>
      </CardHeader>
      {(showKeyElements || showLawArticles) && (
        <CardContent>
          {showKeyElements && showLawArticles ? (
            <Tabs defaultValue="key-elements">
              <TabsList>
                <TabsTrigger value="key-elements">Éléments clés</TabsTrigger>
                <TabsTrigger value="law-articles">Articles de loi</TabsTrigger>
              </TabsList>
              <TabsContent value="key-elements" className="pt-3">
                <RagFactsTable rows={current.key_elements} />
              </TabsContent>
              <TabsContent value="law-articles" className="pt-3">
                <RagFactsTable rows={current.law_articles} />
              </TabsContent>
            </Tabs>
          ) : showKeyElements ? (
            <RagFactsTable title="Éléments clés" rows={current.key_elements} />
          ) : (
            <RagFactsTable title="Articles de loi" rows={current.law_articles} />
          )}
        </CardContent>
      )}
    </Card>
  );
}
