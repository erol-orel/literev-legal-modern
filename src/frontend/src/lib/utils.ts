import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class lists so later utilities win over earlier ones. Used by
 * every UI primitive to let callers override styles through a `className` prop.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const numberFormatter = new Intl.NumberFormat("en-US");

/** Thousands-separated integer; nullish/NaN render as `0` rather than blank. */
export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "0";
  }
  return numberFormatter.format(value);
}

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

/**
 * Human-readable date. Backend dates arrive either as plain `YYYY-MM-DD` or as
 * full ISO timestamps; date-only strings are pinned to local midnight so they
 * never shift a day across time zones. Empty values render as an em dash and
 * unparseable ones fall back to the raw string.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = new Date(isDateOnly ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return dateFormatter.format(date);
}

/** Constrain a percentage to the [0, 100] range a progress bar can render. */
export function clampPercent(value: number): number {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.min(100, Math.max(0, value));
}
