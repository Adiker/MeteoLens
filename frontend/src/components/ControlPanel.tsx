import { AlertTriangle, Layers, RefreshCw, X } from "lucide-react";

import {
  API_BASE_URL,
  warningEventsExportUrl,
  type WarningChangeKind,
} from "../api/client";
import {
  useMapLayersQuery,
  useSourcesQuery,
  useWarningEventsQuery,
  useWarningsQuery,
} from "../api/queries";
import { useActiveAt } from "../hooks/useActiveAt";
import {
  cacheStatusLabel,
  formatTimestamp,
  warningChangeKindLabel,
  warningLevelLabel,
  WARNING_LEVEL_COLOR,
} from "../lib/format";
import { LAYERS, STATION_LAYERS, WARNING_LAYERS, type WarningType } from "../lib/layers";
import { cn } from "../lib/utils";
import { activeLayerKeys, useAppStore } from "../store/appStore";
import { LocationSummary } from "./LocationSummary";
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
  const activeWarningKeys = WARNING_LAYERS.filter((l) => activeLayers[l.key]).map((l) => l.key);
  const mapQuery = useMapLayersQuery([...activeStationKeys, ...activeWarningKeys]);

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
              {layer.kind === "warning" && counts && (
                <span className="block text-xs text-muted-foreground">
                  {counts.features} poligonów · {counts.missing} bez geometrii
                </span>
              )}
              {layer.kind === "warning" && !counts && (
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
          <option value="-1">{warningLevelLabel(-1)}</option>
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
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Województwo (TERYT)</span>
        <input
          type="text"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          placeholder="np. 12"
          value={filters.province}
          onChange={(event) => setFilter("province", event.target.value)}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Powiat (TERYT)</span>
        <input
          type="text"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          placeholder="np. 1205"
          value={filters.county}
          onChange={(event) => setFilter("county", event.target.value)}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Zlewnia</span>
        <input
          type="text"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          placeholder="np. Z_P_WP_1856"
          value={filters.basin}
          onChange={(event) => setFilter("basin", event.target.value)}
        />
      </label>
    </div>
  );
}

function ActiveWarningsList() {
  const activeLayers = useAppStore((state) => state.activeLayers);
  const filters = useAppStore((state) => state.filters);
  const selection = useAppStore((state) => state.selection);
  const select = useAppStore((state) => state.select);

  const activeWarningLayers = WARNING_LAYERS.filter((l) => activeLayers[l.key]);
  const type: WarningType | undefined =
    activeWarningLayers.length === 1 ? activeWarningLayers[0].warningType : undefined;
  // Ticks each minute so the "active" window advances while the panel stays open.
  const activeAt = useActiveAt();

  const warningsQuery = useWarningsQuery({
    type,
    level: filters.warningLevel ?? undefined,
    phenomenon: filters.phenomenon.trim() || undefined,
    province: filters.province.trim() || undefined,
    county: filters.county.trim() || undefined,
    basin: filters.basin.trim() || undefined,
    active_at: activeAt,
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
        <StateNotice tone="error" title="Nie udało się pobrać ostrzeżeń.">
          Brak połączenia z backendem ({API_BASE_URL}).
        </StateNotice>
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

const WARNING_CHANGE_KINDS: WarningChangeKind[] = [
  "first_observed",
  "created",
  "appeared_in_source",
  "updated",
  "extended",
  "escalated",
  "downgraded",
  "expired",
  "removed_from_source",
  "reappeared",
  "cancelled",
  "correction",
  "duplicate_conflict",
];

function HistoryFilters() {
  const filters = useAppStore((state) => state.warningHistoryFilters);
  const setFilter = useAppStore((state) => state.setWarningHistoryFilter);
  return (
    <div className="grid grid-cols-2 gap-2 rounded-md border border-border bg-background p-2">
      <label className="text-xs">
        <span className="mb-1 block text-muted-foreground">Rodzaj</span>
        <select
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.warningType}
          onChange={(event) =>
            setFilter("warningType", event.target.value as "" | "meteo" | "hydro")
          }
        >
          <option value="">Wszystkie</option>
          <option value="meteo">Meteorologiczne</option>
          <option value="hydro">Hydrologiczne</option>
        </select>
      </label>
      <label className="text-xs">
        <span className="mb-1 block text-muted-foreground">Zmiana</span>
        <select
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.changeKind}
          onChange={(event) => setFilter("changeKind", event.target.value)}
        >
          <option value="">Wszystkie</option>
          {WARNING_CHANGE_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {warningChangeKindLabel(kind)}
            </option>
          ))}
        </select>
      </label>
      <label className="col-span-2 text-xs">
        <span className="mb-1 block text-muted-foreground">Biuro</span>
        <input
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.office}
          placeholder="np. Kraków"
          onChange={(event) => setFilter("office", event.target.value)}
        />
      </label>
      <label className="col-span-2 text-xs">
        <span className="mb-1 block text-muted-foreground">Kod obszaru</span>
        <input
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.area}
          placeholder="TERYT lub kod zlewni"
          onChange={(event) => setFilter("area", event.target.value)}
        />
      </label>
      <label className="text-xs">
        <span className="mb-1 block text-muted-foreground">Od</span>
        <input
          type="date"
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.from}
          onChange={(event) => setFilter("from", event.target.value)}
        />
      </label>
      <label className="text-xs">
        <span className="mb-1 block text-muted-foreground">Do</span>
        <input
          type="date"
          className="w-full rounded border border-border bg-background px-2 py-1.5"
          value={filters.to}
          onChange={(event) => setFilter("to", event.target.value)}
        />
      </label>
    </div>
  );
}

function WarningHistoryList() {
  const commonFilters = useAppStore((state) => state.filters);
  const historyFilters = useAppStore((state) => state.warningHistoryFilters);
  const selection = useAppStore((state) => state.selection);
  const select = useAppStore((state) => state.select);
  const params = {
    type: historyFilters.warningType || undefined,
    level: commonFilters.warningLevel ?? undefined,
    phenomenon: commonFilters.phenomenon.trim() || undefined,
    office: historyFilters.office.trim() || undefined,
    area: historyFilters.area.trim() || undefined,
    change_kind: (historyFilters.changeKind || undefined) as WarningChangeKind | undefined,
    from: historyFilters.from ? `${historyFilters.from}T00:00:00Z` : undefined,
    to: historyFilters.to ? `${historyFilters.to}T23:59:59Z` : undefined,
  };
  const query = useWarningEventsQuery(params);
  const events = query.data?.pages.flatMap((page) => page.events) ?? [];
  const firstPage = query.data?.pages[0];

  return (
    <section className="space-y-2">
      <HistoryFilters />
      <StateNotice tone="info" title="Historia lokalna">
        Rejestr zmian rozpoczyna się
        {firstPage?.history_started_at
          ? ` ${formatTimestamp(firstPage.history_started_at)}`
          : " po pierwszym poprawnym odświeżeniu"}
        .{" "}
        {firstPage?.alerting_disclaimer ??
          "MeteoLens nie jest urzędowym systemem ostrzegania."}
      </StateNotice>
      <div className="flex gap-2 text-xs">
        <a
          className="rounded border border-border bg-background px-2 py-1 hover:border-primary"
          href={warningEventsExportUrl("csv", params)}
        >
          Eksport CSV
        </a>
        <a
          className="rounded border border-border bg-background px-2 py-1 hover:border-primary"
          href={warningEventsExportUrl("json", params)}
        >
          Eksport JSON
        </a>
      </div>
      {query.isLoading && <Spinner label="Ładowanie historii..." />}
      {query.isError && (
        <StateNotice tone="error" title="Nie udało się pobrać historii.">
          Backend nie udostępnił feedu zmian.
        </StateNotice>
      )}
      {!query.isLoading && !query.isError && events.length === 0 && (
        <StateNotice tone="info" title="Brak zapisanych zmian">
          Historia zostanie wypełniona przez poprawne odświeżenia źródeł.
        </StateNotice>
      )}
      <ul className="space-y-1.5">
        {events.map((event) => (
          <li key={event.event_id}>
            <button
              type="button"
              onClick={() => select({ kind: "warning-history", id: event.history_id })}
              className={cn(
                "w-full rounded-md border border-border bg-background px-3 py-2 text-left text-sm hover:border-primary",
                selection?.kind === "warning-history" &&
                  selection.id === event.history_id &&
                  "border-primary",
              )}
            >
              <span className="block font-medium">
                {event.change_kinds.map(warningChangeKindLabel).join(" · ")}
              </span>
              <span className="block truncate">{event.warning?.event ?? "Ostrzeżenie"}</span>
              <span className="block text-xs text-muted-foreground">
                {formatTimestamp(event.detected_at)}
                {event.confidence === "ambiguous" && " · niepotwierdzone"}
                {event.snapshot?.completeness === "partial" && " · snapshot częściowy"}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {query.hasNextPage && (
        <button
          type="button"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm hover:border-primary"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {query.isFetchingNextPage ? "Ładowanie..." : "Pokaż starsze"}
        </button>
      )}
    </section>
  );
}

function WarningsBrowser() {
  const view = useAppStore((state) => state.warningPanelView);
  const setView = useAppStore((state) => state.setWarningPanelView);
  return (
    <section className="space-y-3">
      <div className="grid grid-cols-2 rounded-md border border-border bg-background p-1">
        <button
          type="button"
          className={cn("rounded px-2 py-1.5 text-sm", view === "active" && "bg-muted")}
          onClick={() => setView("active")}
        >
          Aktywne
        </button>
        <button
          type="button"
          className={cn("rounded px-2 py-1.5 text-sm", view === "history" && "bg-muted")}
          onClick={() => setView("history")}
        >
          Historia
        </button>
      </div>
      {view === "active" ? <ActiveWarningsList /> : <WarningHistoryList />}
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
      {sourcesQuery.isError && (
        <StateNotice tone="error" title="Backend nie odpowiada.">
          Nie udało się połączyć z {API_BASE_URL}. Sprawdź, czy backend MeteoLens działa pod tym
          adresem (ten port może zajmować inna aplikacja).
        </StateNotice>
      )}
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
        // `open` only drives the mobile drawer; the panel is always visible at lg.
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
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

      <LocationSummary />
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
          Brak połączenia z backendem ({API_BASE_URL}).
        </StateNotice>
      )}

      <Filters />
      <WarningsBrowser />
      <SourceStatus />
    </aside>
  );
}
