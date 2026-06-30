import { Layers, RefreshCw } from "lucide-react";

import { useSourcesQuery } from "../api/queries";

export function ControlPanel() {
  const sourcesQuery = useSourcesQuery();
  const sources = sourcesQuery.data?.sources ?? [];

  return (
    <aside className="absolute left-4 top-4 z-10 w-[min(360px,calc(100vw-2rem))] rounded-lg border border-border bg-card/95 p-3 text-card-foreground shadow-lg backdrop-blur">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Layers aria-hidden className="size-4" />
          <h2 className="text-sm font-semibold">Warstwy danych</h2>
        </div>
        <button
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground"
          type="button"
          aria-label="Odśwież status źródeł"
          onClick={() => void sourcesQuery.refetch()}
        >
          <RefreshCw aria-hidden className="size-4" />
        </button>
      </div>

      {sourcesQuery.isLoading && <p className="text-sm text-muted-foreground">Ładowanie statusu źródeł...</p>}
      {sourcesQuery.isError && (
        <p className="text-sm text-warning">Backend nie odpowiada albo endpoint źródeł jest niedostępny.</p>
      )}
      {!sourcesQuery.isLoading && !sourcesQuery.isError && (
        <div className="space-y-2">
          {sources.map((source) => (
            <label
              className="flex min-h-12 items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2"
              key={source.key}
            >
              <span>
                <span className="block text-sm font-medium">{source.title}</span>
                <span className="block text-xs text-muted-foreground">
                  Parser: {source.parser_status} · Cache: {source.cache_status}
                </span>
              </span>
              <input aria-label={`Warstwa ${source.title}`} disabled type="checkbox" />
            </label>
          ))}
        </div>
      )}
    </aside>
  );
}

