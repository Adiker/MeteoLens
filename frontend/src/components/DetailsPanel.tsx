import { Info, TerminalSquare } from "lucide-react";

import { useHealthQuery } from "../api/queries";

export function DetailsPanel() {
  const healthQuery = useHealthQuery();

  return (
    <aside className="absolute bottom-4 right-4 top-4 z-10 hidden w-[360px] rounded-lg border border-border bg-card/95 p-4 text-card-foreground shadow-lg backdrop-blur lg:block">
      <div className="mb-4 flex items-center gap-2">
        <Info aria-hidden className="size-4" />
        <h2 className="text-sm font-semibold">Panel szczegółów</h2>
      </div>

      <div className="space-y-4 text-sm">
        <section>
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Status backendu</h3>
          {healthQuery.isLoading && <p>Sprawdzanie...</p>}
          {healthQuery.isError && <p className="text-warning">Brak połączenia z backendem.</p>}
          {healthQuery.data && (
            <dl className="grid grid-cols-[110px_1fr] gap-2">
              <dt className="text-muted-foreground">Usługa</dt>
              <dd>{healthQuery.data.service}</dd>
              <dt className="text-muted-foreground">Wersja</dt>
              <dd>{healthQuery.data.version}</dd>
              <dt className="text-muted-foreground">Środowisko</dt>
              <dd>{healthQuery.data.environment}</dd>
            </dl>
          )}
        </section>

        <section className="rounded-md border border-border bg-background p-3">
          <div className="mb-2 flex items-center gap-2">
            <TerminalSquare aria-hidden className="size-4" />
            <h3 className="text-xs font-semibold uppercase text-muted-foreground">Tryb ekspercki</h3>
          </div>
          <p className="text-muted-foreground">
            Surowy JSON, timestamp pobrania, braki danych i metadane parsera pojawią się tutaj po
            integracji źródeł IMGW.
          </p>
        </section>
      </div>
    </aside>
  );
}

