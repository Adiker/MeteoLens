import { AlertTriangle, Layers, RefreshCw, X } from "lucide-react";

import { useMapLayersQuery, useSourcesQuery, useWarningsQuery } from "../api/queries";
import {
  cacheStatusLabel,
  formatTimestamp,
  warningLevelLabel,
  WARNING_LEVEL_COLOR,
} from "../lib/format";
import { LAYERS, STATION_LAYERS, WARNING_LAYERS, type WarningType } from "../lib/layers";
import { cn } from "../lib/utils";
import { activeLayerKeys, useAppStore } from "../store/appStore";
import { Spinner, StateNotice } from "./primitives";

const CACHE_DOT: Record<string, string> = {
  fresh: "bg-meteo",
  stale: "bg-warning",
  empty: "bg-muted-foreground",
  error: "bg-warning",
  invalid: "bg-warning",
};

function LayerToggles() {
  const activeLayers = useAppStore((state) => state.activeLayers);
  const toggleLayer = useAppStore((state) => state.toggleLayer);
  const activeStationKeys = STATION_LAYERS.filter((l) => activeLayers[l.key]).map((l) => l.key);
  const mapQuery = useMapLayersQuery(activeStationKeys);

  const countsByKey = new Map<string, { features: number; missing: number }>();
  for (const layer of mapQuery.data?.layers ?? []) {
    countsByKey.set(layer.key, {
      features: layer.geojson.features.length,
      missing: layer.missing_geometry.length,
    });
  }

  return (
    <div className="space-y-1.5">
      {LAYERS.map((layer) => {
        const counts = countsByKey.get(layer.key);
        return (
          <label
            key={layer.key}
            className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-border bg-background px-3 py-2"
          >
            <span
              className="size-3 shrink-0 rounded-full"
              style={{ backgroundColor: layer.color }}
              aria-hidden
            />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2 text-sm font-medium">
                {layer.title}
                <kbd className="rounded border border-border px-1 text-[10px] text-muted-foreground">
                  {layer.hotkey}
                </kbd>
              </span>
              {layer.kind === "station" && counts && (
                <span className="block text-xs text-muted-foreground">
                  {counts.features} na mapie
                  {counts.missing > 0 && ` · ${counts.missing} bez współrzędnych`}
                </span>
              )}
              {layer.kind === "warning" && (
                <span className="block text-xs text-muted-foreground">
                  Brak geometrii — lista poniżej
                </span>
              )}
            </span>
            <input
              type="checkbox"
              className="size-4"
              checked={Boolean(activeLayers[layer.key])}
              onChange={() => toggleLayer(layer.key)}
              aria-label={`Warstwa ${layer.title}`}
            />
          </label>
        );
      })}
    </div>
  );
}

function Filters() {
  const filters = useAppStore((state) => state.filters);
  const setFilter = useAppStore((state) => state.setFilter);
  return (
    <div className="space-y-2">
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Poziom ostrzeżenia</span>
        <select
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          value={filters.warningLevel ?? ""}
          onChange={(event) =>
            setFilter("warningLevel", event.target.value ? Number(event.target.value) : null)
          }
        >
          <option value="">Wszystkie</option>
          <option value="1">{warningLevelLabel(1)}</option>
          <option value="2">{warningLevelLabel(2)}</option>
          <option value="3">{warningLevelLabel(3)}</option>
        </select>
      </label>
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Zjawisko</span>
        <input
          type="text"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          placeholder="np. burze, upał"
          value={filters.phenomenon}
          onChange={(event) => setFilter("phenomenon", event.target.value)}
        />
      </label>
    </div>
  );
}

function WarningsList() {
  const activeLayers = useAppStore((state) => state.activeLayers);
  const filters = useAppStore((state) => state.filters);
  const selection = useAppStore((state) => state.selection);
  const select = useAppStore((state) => state.select);

  const activeWarningLayers = WARNING_LAYERS.filter((l) => activeLayers[l.key]);
  const type: WarningType | undefined =
    activeWarningLayers.length === 1 ? activeWarningLayers[0].warningType : undefined;

  const warningsQuery = useWarningsQuery({
    type,
    level: filters.warningLevel ?? undefined,
    phenomenon: filters.phenomenon.trim() || undefined,
  });

  if (activeWarningLayers.length === 0) {
    return null;
  }

  const warnings = warningsQuery.data?.warnings ?? [];
  const empty = warningsQuery.data?.empty_state;

  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <AlertTriangle aria-hidden className="size-3.5" /> Aktywne ostrzeżenia ({warnings.length})
      </h3>
      {warningsQuery.isLoading && <Spinner label="Ładowanie ostrzeżeń..." />}
      {warningsQuery.isError && (
        <StateNotice tone="error" title="Nie udało się pobrać ostrzeżeń." />
      )}
      {!warningsQuery.isLoading && !warningsQuery.isError && warnings.length === 0 && (
        <StateNotice tone="info" title="Brak aktywnych ostrzeżeń">
          {empty?.message}
        </StateNotice>
      )}
      <ul className="space-y-1.5">
        {warnings.map((warning) => (
          <li key={warning.id}>
            <button
              type="button"
              onClick={() => select({ kind: "warning", id: warning.id })}
              className={cn(
                "flex w-full items-start gap-2 rounded-md border border-border bg-background px-3 py-2 text-left text-sm hover:border-primary",
                selection?.kind === "warning" && selection.id === warning.id && "border-primary",
              )}
            >
              <span
                className="mt-0.5 size-3 shrink-0 rounded-full"
                style={{ backgroundColor: WARNING_LEVEL_COLOR[warning.level ?? 0] ?? "#9ca3af" }}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{warning.event}</span>
                <span className="block text-xs text-muted-foreground">
                  Poziom {warningLevelLabel(warning.level)} · do {formatTimestamp(warning.valid_to)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SourceStatus() {
  const sourcesQuery = useSourcesQuery();
  const sources = sourcesQuery.data?.sources ?? [];

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">Status źródeł</h3>
        <button
          type="button"
          className="inline-flex size-7 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground"
          aria-label="Odśwież status źródeł"
          onClick={() => void sourcesQuery.refetch()}
        >
          <RefreshCw aria-hidden className={cn("size-3.5", sourcesQuery.isFetching && "animate-spin")} />
        </button>
      </div>
      {sourcesQuery.isLoading && <Spinner label="Sprawdzanie źródeł..." />}
      {sourcesQuery.isError && <StateNotice tone="error" title="Backend nie odpowiada." />}
      <ul className="space-y-1 text-xs">
        {sources.map((source) => (
          <li key={source.key} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <span className={cn("size-2 rounded-full", CACHE_DOT[source.cache_status] ?? "bg-muted-foreground")} />
              {source.title}
            </span>
            <span className="text-muted-foreground">{cacheStatusLabel(source.cache_status)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ControlPanel() {
  const open = useAppStore((state) => state.controlPanelOpen);
  const setOpen = useAppStore((state) => state.setControlPanelOpen);
  const activeLayers = useAppStore((state) => state.activeLayers);
  const activeStationKeys = STATION_LAYERS.filter((l) => activeLayers[l.key]).map((l) => l.key);
  const mapQuery = useMapLayersQuery(activeStationKeys);
  const emptyState = mapQuery.data?.empty_state;
  const noActiveLayers = activeLayerKeys(activeLayers).length === 0;

  return (
    <aside
      className={cn(
        "absolute left-0 top-0 z-20 flex h-full w-[min(360px,100vw)] flex-col gap-4 overflow-y-auto border-r border-border bg-card/95 p-3 text-card-foreground shadow-lg backdrop-blur transition-transform lg:left-4 lg:top-4 lg:h-auto lg:max-h-[calc(100%-2rem)] lg:rounded-lg lg:border",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        !open && "lg:hidden",
      )}
      aria-label="Panel warstw i filtrów"
    >
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Layers aria-hidden className="size-4" /> Warstwy i filtry
        </h2>
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground lg:hidden"
          aria-label="Zamknij panel"
          onClick={() => setOpen(false)}
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>

      <LayerToggles />

      {noActiveLayers && (
        <StateNotice tone="info" title="Brak aktywnych warstw">
          Włącz warstwę, aby zobaczyć dane na mapie.
        </StateNotice>
      )}
      {emptyState && (
        <StateNotice tone="warning" title="Brak danych w cache">
          {emptyState.message}
        </StateNotice>
      )}
      {mapQuery.isError && (
        <StateNotice tone="error" title="Nie udało się pobrać warstw mapy.">
          Sprawdź, czy backend jest dostępny.
        </StateNotice>
      )}

      <Filters />
      <WarningsList />
      <SourceStatus />
    </aside>
  );
}
