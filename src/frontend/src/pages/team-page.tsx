import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/hooks/use-app-context";

import coFoundersImg from "@/assets/team/co_founders.jpeg";
import azizaImg from "@/assets/team/aziza.jpeg";
import erolImg from "@/assets/team/erol.jpeg";
import oliviaImg from "@/assets/team/olivia.jpeg";
import ivanImg from "@/assets/team/ivan.jpeg";
import sandroImg from "@/assets/team/sandro.jpeg";
import everImg from "@/assets/team/ever.jpeg";
import miaImg from "@/assets/team/mia.png";
import ugLogo from "@/assets/partners/ug.png";
import tgnLogo from "@/assets/partners/tgn.png";
import oslLogo from "@/assets/partners/osl.png";
import hugLogo from "@/assets/partners/hug2.png";

interface Member {
  name: string;
  role: string;
  photo: string;
}

const TEAM: Member[] = [
  { name: "Aziza Merzouki", role: "Co-founder & CEO", photo: azizaImg },
  { name: "Erol Orel", role: "Co-founder & CPO", photo: erolImg },
  { name: "Olivia Keiser", role: "Chairman", photo: oliviaImg },
  { name: "Ivan Osagawara", role: "Lead Developer", photo: ivanImg },
  { name: "Sandro Loch", role: "DevOps Engineer", photo: sandroImg },
  { name: "John Ever Vino Duran", role: "Full-Stack Developer", photo: everImg },
  { name: "Mia Müller", role: "Head of Marketing", photo: miaImg },
];

const PARTNERS = [
  { name: "University of Geneva", href: "https://unige.ch/", logo: ugLogo },
  {
    name: "The Graph Network",
    href: "https://thegraphnetwork.org/",
    logo: tgnLogo,
  },
  {
    name: "Open Science Labs",
    href: "https://www.opensciencelabs.org/",
    logo: oslLogo,
  },
  { name: "Hôpitaux Universitaires de Genève", href: "https://www.hug.ch/", logo: hugLogo },
];

export function TeamPage() {
  const { urls } = useAppContext();

  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Logo onDark={false} />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button asChild variant="ghost">
            <Link to="/">
              <ArrowLeft className="size-4" /> Home
            </Link>
          </Button>
          <Button asChild variant="ghost">
            <a href={urls.login}>Sign in</a>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6">
        <section className="py-16 text-center sm:py-20">
          <p className="mb-4 text-sm font-medium uppercase tracking-widest text-primary">
            Smarter research. Better insights.
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Meet the team
          </h1>
        </section>

        {/* Co-founders */}
        <section className="mx-auto mb-16 flex max-w-xl flex-col items-center text-center">
          <img
            src={coFoundersImg}
            alt="LiteRev co-founders"
            loading="lazy"
            className="w-full max-w-md rounded-3xl border shadow-sm"
          />
          <h2 className="mt-5 text-lg font-semibold text-foreground">
            Co-Founders
          </h2>
          <p className="text-sm text-muted-foreground">CEO, CPO, and Chairman</p>
        </section>

        {/* Team members */}
        <section className="mb-20 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {TEAM.map((member) => (
            <figure key={member.name} className="flex flex-col items-center text-center">
              <img
                src={member.photo}
                alt={member.name}
                loading="lazy"
                className="size-40 rounded-3xl border object-cover shadow-sm"
              />
              <figcaption className="mt-4">
                <p className="text-base font-semibold text-foreground">
                  {member.name}
                </p>
                <p className="text-sm text-muted-foreground">{member.role}</p>
              </figcaption>
            </figure>
          ))}
        </section>

        {/* Partners */}
        <section className="pb-24">
          <h2 className="mb-8 text-center text-2xl font-semibold text-foreground">
            With the participation of
          </h2>
          <div className="mx-auto grid max-w-4xl grid-cols-2 items-center gap-8 sm:grid-cols-4">
            {PARTNERS.map((partner) => (
              <a
                key={partner.name}
                href={partner.href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center rounded-2xl border bg-card p-6 shadow-sm transition-colors hover:bg-accent"
                title={partner.name}
              >
                <img
                  src={partner.logo}
                  alt={partner.name}
                  loading="lazy"
                  className="max-h-16 w-full object-contain"
                />
              </a>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
