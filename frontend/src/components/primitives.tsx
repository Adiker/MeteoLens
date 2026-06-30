import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import type { CacheSourceState } from "../api/client";
import { cacheStatusLabel } from "../lib/format";
import { cn } from "../lib/utils";

export const iconButtonClass =
  "inline-flex size-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60";

export function Spinner({ label }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 aria-hidden className="size-4 animate-spin" />
      {label ?? "Ładowanie..."}
    </p>
  );
}

type Tone = "info" | "warning" | "error";

const TONE_CLASS: Record<Tone, string> = {
  info: "border-border bg-background text-muted-foreground",
  warning: "border-warning/40 bg-warning/10 text-foreground",
  error: "border-warning/60 bg-warning/15 text-foreground",
};

export function StateNotice({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className={cn("rounded-md border px-3 py-2 text-sm", TONE_CLASS[tone])} role="status">
      {title && <p className="font-medium">{title}</p>}
      {children && <p className="text-xs text-muted-foreground">{children}</p>}
    </div>
  );
}

const CACHE_DOT: Record<string, string> = {
  fresh: "bg-meteo",
  stale: "bg-warning",
  empty: "bg-muted-foreground",
  error: "bg-warning",
  invalid: "bg-warning",
};

/** Compact freshness chips for the per-source cache status array. */
export function CacheBadges({ cache }: { cache: CacheSourceState[] }) {
  if (!cache.length) {
    return null;
  }
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Status cache źródeł">
      {cache.map((entry) => (
        <li
          key={entry.source_key}
          className="inline-flex items-center gap-1.5 rounded border border-border bg-background px-2 py-0.5 text-[11px]"
          title={
            entry.status.age_seconds != null
              ? `Wiek danych: ${Math.round(entry.status.age_seconds / 60)} min`
              : undefined
          }
        >
          <span className={cn("size-2 rounded-full", CACHE_DOT[entry.status.status] ?? "bg-muted-foreground")} />
          <span className="font-medium">{entry.source_key}</span>
          <span className="text-muted-foreground">{cacheStatusLabel(entry.status.status)}</span>
        </li>
      ))}
    </ul>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </>
  );
}
