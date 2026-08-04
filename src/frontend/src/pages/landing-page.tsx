import { ArrowRight, Layers, MessagesSquare, Search } from "lucide-react";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/hooks/use-app-context";

const FEATURES = [
  {
    icon: Search,
    title: "Search with intent",
    body: "Turn a plain-language question into a precise Boolean query over French judicial decisions.",
  },
  {
    icon: Layers,
    title: "Cluster & explore",
    body: "Automatically group decisions by topic and navigate the landscape of a legal question.",
  },
  {
    icon: MessagesSquare,
    title: "Ask & cite",
    body: "Interrogate the selected corpus and get answers with citations and confidence scores.",
  },
];

export function LandingPage() {
  const { urls } = useAppContext();

  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Logo onDark={false} />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button asChild variant="ghost">
            <a href={urls.login}>Sign in</a>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6">
        <section className="py-20 text-center sm:py-28">
          <p className="mb-4 text-sm font-medium uppercase tracking-widest text-primary">
            Legal research, reimagined
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Search, cluster and question French legal decisions — in one place.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            LiteRev Legal helps lawyers move from a question to a well-founded
            answer: retrieve relevant case law, understand the terrain, and get
            cited answers you can trust.
          </p>
          <div className="mt-9 flex items-center justify-center gap-3">
            <Button asChild size="lg">
              <a href={urls.login}>
                Get started <ArrowRight className="size-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="grid gap-6 pb-24 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border bg-card p-6 shadow-sm"
            >
              <div className="mb-4 flex size-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <feature.icon className="size-5" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                {feature.title}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">{feature.body}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
