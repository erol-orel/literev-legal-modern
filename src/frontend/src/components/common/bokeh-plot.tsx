import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import type { ClusterPlot } from "@/api/project-overview";

const BOKEH_SRC = "/static/js/bokeh.min.js";

let bokehLoader: Promise<void> | null = null;

function loadBokeh(): Promise<void> {
  if (bokehLoader) return bokehLoader;
  bokehLoader = new Promise<void>((resolve, reject) => {
    if (document.querySelector(`script[src="${BOKEH_SRC}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = BOKEH_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Bokeh"));
    document.body.appendChild(script);
  });
  return bokehLoader;
}

/** Strip the outer <script> wrapper so the body can be re-injected live. */
function extractScriptBody(scriptHtml: string): string {
  const match = scriptHtml.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
  return match ? match[1] : scriptHtml;
}

/**
 * Renders the server-produced Bokeh cluster scatter. The overview endpoint
 * returns pre-rendered `div_plot` + `script_plot` HTML (not raw coordinates),
 * so this preserves the existing behaviour while theming the container.
 *
 * NOTE: exposing raw ClusterElement coordinates from the backend would let us
 * replace this with a fully native, themeable, interactive React scatter.
 */
export function BokehPlot({ plot }: { plot: ClusterPlot | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    if (!plot?.div_plot || !plot?.script_plot) {
      setState("error");
      return;
    }

    let cancelled = false;
    setState("loading");

    loadBokeh()
      .then(() => {
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = plot.div_plot;
        const script = document.createElement("script");
        script.type = "text/javascript";
        script.text = extractScriptBody(plot.script_plot);
        containerRef.current.appendChild(script);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [plot]);

  if (state === "error") {
    return (
      <Alert variant="warning">
        <AlertTitle>Cluster plot unavailable</AlertTitle>
        <AlertDescription>
          The cluster plot could not be rendered right now.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="relative min-h-[24rem] w-full overflow-x-auto rounded-lg border bg-card p-2">
      {state === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Rendering cluster map…
        </div>
      )}
      <div ref={containerRef} className="bk-root mx-auto" />
    </div>
  );
}
