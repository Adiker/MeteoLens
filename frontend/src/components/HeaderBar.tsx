import { Download, Moon, Search, SunMedium } from "lucide-react";

export function HeaderBar() {
  return (
    <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-card px-4">
      <div>
        <h1 className="text-base font-semibold">MeteoLens</h1>
        <p className="text-xs text-muted-foreground">Panel pogodowo-hydrologiczny IMGW-PIB</p>
      </div>

      <div className="hidden min-w-0 flex-1 justify-center md:flex">
        <label className="flex w-full max-w-lg items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
          <Search aria-hidden className="size-4 text-muted-foreground" />
          <input
            className="min-w-0 flex-1 bg-transparent outline-none"
            disabled
            placeholder="Szukaj lokalizacji lub stacji"
            type="search"
          />
        </label>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="inline-flex size-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground"
          disabled
          type="button"
          aria-label="Eksport"
        >
          <Download aria-hidden className="size-4" />
        </button>
        <button
          className="inline-flex size-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground"
          disabled
          type="button"
          aria-label="Tryb jasny"
        >
          <SunMedium aria-hidden className="size-4" />
        </button>
        <button
          className="inline-flex size-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground"
          disabled
          type="button"
          aria-label="Tryb ciemny"
        >
          <Moon aria-hidden className="size-4" />
        </button>
      </div>
    </header>
  );
}

