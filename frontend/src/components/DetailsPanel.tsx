import { BarChart3, Download, ExternalLink, ListTree, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  stationObservationsCsvUrl,
  stationObservationsJsonUrl,
  type SourceMetadata,
  type WarningEvent,
  type WarningHistoryVersion,
  type WarningRecord,
  type WarningSnapshotMetadata,
} from "../api/client";
import {
  useObservationsQuery,
  useStationQuery,
  useWarningHistoryQuery,
  useWarningQuery,
} from "../api/queries";
import {
  formatDelay,
  formatTimestamp,
  formatValue,
  metricLabel,
  warningChangeKindLabel,
  warningLevelLabel,
} from "../lib/format";
import { cn } from "../lib/utils";
import { useAppStore } from "../store/appStore";
import { StationChart } from "./StationChart";
import { Field, Spinner, StateNotice } from "./primitives";

function apiErrorNotice(error: unknown): ReactNode {
  if (error instanceof ApiError) {
    if (error.code === "cache_empty") {
      return (
        <StateNotice tone="warning" title="Brak danych w cache">
          Odśwież źródła IMGW w backendzie, aby zobaczyć szczegóły.
        </StateNotice>
      );
    }
    if (error.code === "not_found" || error.status === 404) {
      return <StateNotice tone="info" title="Nie znaleziono obiektu" />;
    }
    // Other failures (e.g. cache_invalid 503) must surface, not be hidden as "empty".
    return <StateNotice tone="error" title={error.message} />;
  }
  return <StateNotice tone="error" title="Wystąpił błąd podczas pobierania danych." />;
}

function SourceFooter({ source, expert }: { source: SourceMetadata; expert: boolean }) {
  return (
    <section className="space-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
      <p>{source.attribution}</p>
      <p>{source.processed_notice}</p>
      <p>Pobrano: {formatTimestamp(source.retrieved_at)}</p>
      {expert && (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          <ExternalLink aria-hidden className="size-3" /> {source.url}
        </a>
      )}
    </section>
  );
}

function RawSection({ raw }: { raw: Record<string, unknown> }) {
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <ListTree aria-hidden className="size-3.5" /> Surowe dane źródła
      </h3>
      <pre className="max-h-64 overflow-auto rounded-md border border-border bg-background p-2 text-[11px] leading-relaxed">
        {JSON.stringify(raw, null, 2)}
      </pre>
    </section>
  );
}

function MissingFields({ fields }: { fields: string[] }) {
  if (fields.length === 0) {
    return null;
  }
  return (
    <p className="text-xs text-muted-foreground">
      Braki danych: <span className="text-foreground">{fields.join(", ")}</span>
    </p>
  );
}

function seriesOriginLabel(origin?: "live_refresh" | "archive_import" | "mixed") {
  if (origin === "archive_import") {
    return "Seria z importu archiwalnego IMGW-PIB";
  }
  if (origin === "mixed") {
    return "Seria mieszana: live refresh + import archiwalny";
  }
  return "Seria z odświeżeń live IMGW-PIB";
}

const HYDRO_HISTORY_METRICS = [
  { key: "water_level", label: "Stan wody" },
  { key: "flow", label: "Przepływ" },
  { key: "water_temperature", label: "Temperatura wody" },
] as const;

function StationDetails({ id, expert }: { id: string; expert: boolean }) {
  const stationQuery = useStationQuery(id);
  const [selectedMetric, setSelectedMetric] = useState<string | undefined>(
    id.startsWith("hydro:") ? "water_level" : undefined,
  );
  const observationsQuery = useObservationsQuery(id, selectedMetric);
  const [tab, setTab] = useState<"data" | "chart">("data");

  useEffect(() => {
    setSelectedMetric(id.startsWith("hydro:") ? "water_level" : undefined);
  }, [id]);

  if (stationQuery.isLoading) {
    return <Spinner label="Ładowanie stacji..." />;
  }
  if (stationQuery.isError) {
    return apiErrorNotice(stationQuery.error);
  }
  if (!stationQuery.data) {
    return null;
  }

  const { station, latest_observed_at, data_delay_seconds } = stationQuery.data;
  const currentObservations = station.observations;
  const chartObservations = observationsQuery.data?.observations ?? currentObservations;
  const seriesOrigin = observationsQuery.data?.series_origin ?? "live_refresh";
  const archiveMetadata = chartObservations.find(
    (observation) => observation.origin === "archive_import",
  );
  const hasCoords = station.lat != null && station.lon != null;

  const tabClass = (active: boolean) =>
    cn(
      "flex items-center gap-1.5 border-b-2 px-2 pb-1.5 text-sm",
      active ? "border-primary text-foreground" : "border-transparent text-muted-foreground",
    );

  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase text-muted-foreground">Stacja {station.station_type}</p>
        <h2 className="text-lg font-semibold leading-tight">{station.name}</h2>
      </header>

      <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-sm">
        <Field label="ID źródła">{station.source_id}</Field>
        <Field label="Współrzędne">
          {hasCoords ? `${station.lat?.toFixed(4)}, ${station.lon?.toFixed(4)}` : "brak"}
        </Field>
        {station.coordinate_source && (
          <Field label="Źródło współrz.">{station.coordinate_source}</Field>
        )}
        {station.region && <Field label="Region">{station.region}</Field>}
        {station.watercourse && <Field label="Ciek">{station.watercourse}</Field>}
        <Field label="Pomiar">{formatTimestamp(latest_observed_at)}</Field>
        <Field label="Opóźnienie">{formatDelay(data_delay_seconds)}</Field>
      </dl>

      <MissingFields fields={station.missing_fields} />

      {observationsQuery.data?.series_kind === "history" && (
        <p className="text-xs text-muted-foreground">{seriesOriginLabel(seriesOrigin)}</p>
      )}

      <div className="flex gap-3 border-b border-border">
        <button type="button" className={tabClass(tab === "data")} onClick={() => setTab("data")}>
          <ListTree aria-hidden className="size-3.5" /> Pomiary
        </button>
        <button type="button" className={tabClass(tab === "chart")} onClick={() => setTab("chart")}>
          <BarChart3 aria-hidden className="size-3.5" /> Wykres
        </button>
      </div>

      {tab === "data" ? (
        <ul className="divide-y divide-border rounded-md border border-border">
          {currentObservations.map((obs) => (
            <li
              key={`${obs.metric}:${obs.observed_at ?? "snapshot"}:${obs.origin ?? "live"}`}
              className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
            >
              <span>
                <span className="block">{metricLabel(obs.metric)}</span>
                {expert && (
                  <span className="block text-[11px] text-muted-foreground">
                    {obs.raw_field}
                    {obs.origin === "archive_import" ? " · import archiwalny" : ""}
                  </span>
                )}
              </span>
              <span className={cn("font-medium", obs.value === null && "text-muted-foreground")}>
                {formatValue(obs.value, obs.unit)}
              </span>
            </li>
          ))}
          {currentObservations.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">Brak pomiarów.</li>
          )}
        </ul>
      ) : (
        <div className="space-y-3">
          {station.station_type === "hydro" && (
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Metryka wykresu</span>
              <select
                aria-label="Metryka wykresu"
                value={selectedMetric}
                onChange={(event) => setSelectedMetric(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              >
                {HYDRO_HISTORY_METRICS.map((metric) => (
                  <option key={metric.key} value={metric.key}>
                    {metric.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <StationChart
            observations={chartObservations}
            seriesKind={observationsQuery.data?.series_kind ?? "snapshot"}
          />
          {expert && archiveMetadata && (
            <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 break-all text-[11px] text-muted-foreground">
              <dt>Rodzaj archiwum</dt>
              <dd>{archiveMetadata.archive_kind ?? "—"}</dd>
              <dt>Jakość</dt>
              <dd>{archiveMetadata.quality_status ?? "—"}</dd>
              <dt>Rozdzielczość</dt>
              <dd>{archiveMetadata.temporal_resolution ?? "—"}</dd>
              <dt>Plik źródłowy</dt>
              <dd>{archiveMetadata.import_source_url ?? "—"}</dd>
              <dt>SHA-256</dt>
              <dd>{archiveMetadata.source_file_sha256 ?? "—"}</dd>
              <dt>Last-Modified</dt>
              <dd>{archiveMetadata.source_file_last_modified ?? "—"}</dd>
              <dt>Czas importu</dt>
              <dd>{archiveMetadata.retrieved_at ?? "—"}</dd>
            </dl>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href={stationObservationsCsvUrl(station.id, selectedMetric)}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:border-primary"
        >
          <Download aria-hidden className="size-3.5" /> CSV
        </a>
        <a
          href={stationObservationsJsonUrl(station.id, selectedMetric)}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:border-primary"
        >
          <Download aria-hidden className="size-3.5" /> JSON
        </a>
      </div>

      {expert && <RawSection raw={station.raw} />}
      <SourceFooter source={station.source} expert={expert} />
    </div>
  );
}

const APPROXIMATE_MAPPING_PRECISIONS = new Set(["refined", "coarse", "coastal"]);

function approximateMappingPrecisions(
  resolvedAreas: Array<Record<string, unknown>> | undefined,
): string[] {
  if (!resolvedAreas?.length) {
    return [];
  }
  const labels = new Set<string>();
  for (const area of resolvedAreas) {
    const precision = area.mapping_precision;
    if (typeof precision === "string" && APPROXIMATE_MAPPING_PRECISIONS.has(precision)) {
      labels.add(precision);
    }
  }
  return [...labels].sort();
}

function WarningGeometryNotice({
  geometryStatus,
  resolvedAreas,
}: {
  geometryStatus: string;
  resolvedAreas?: Array<Record<string, unknown>>;
}) {
  const approximations = approximateMappingPrecisions(resolvedAreas);
  const approximationNote =
    approximations.length > 0
      ? ` Część zlewni hydro ma precyzję mapowania ${approximations.join("/")} — to przybliżenie obszaru prognostycznego IMGW, nie oficjalny poligon ostrzeżenia.`
      : "";

  if (geometryStatus === "resolved") {
    return (
      <StateNotice tone={approximations.length ? "warning" : "info"} title="Geometria obszaru dostępna">
        Obszar ostrzeżenia został dopasowany do zatwierdzonych granic administracyjnych
        lub zlewni.
        {approximationNote}
      </StateNotice>
    );
  }
  if (geometryStatus === "partial") {
    return (
      <StateNotice tone="warning" title="Częściowa geometria obszaru">
        Część obszarów ostrzeżenia została dopasowana do zatwierdzonej geometrii, a część
        pozostaje nierozwiązana ({geometryStatus}).
        {approximationNote}
      </StateNotice>
    );
  }
  if (geometryStatus === "geometry_not_found") {
    return (
      <StateNotice tone="warning" title="Brak dopasowania geometrii">
        Zatwierdzony zbiór geometrii jest dostępny, ale kody obszarów tego ostrzeżenia nie
        zostały dopasowane ({geometryStatus}).
      </StateNotice>
    );
  }
  return (
    <StateNotice tone="info" title="Brak geometrii obszaru">
      Dokładne dopasowanie przestrzenne ostrzeżeń będzie możliwe po dodaniu zbiorów
      TERYT/zlewni ({geometryStatus}).
    </StateNotice>
  );
}

function WarningDetails({ id, expert }: { id: string; expert: boolean }) {
  const warningQuery = useWarningQuery(id);
  const historyQuery = useWarningHistoryQuery(
    warningQuery.data?.warning.history_id ?? null,
  );

  if (warningQuery.isLoading) {
    return <Spinner label="Ładowanie ostrzeżenia..." />;
  }
  if (warningQuery.isError) {
    return apiErrorNotice(warningQuery.error);
  }
  if (!warningQuery.data) {
    return null;
  }

  const { warning, geometry_status } = warningQuery.data;

  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase text-muted-foreground">
          Ostrzeżenie {warning.warning_type}
        </p>
        <h2 className="text-lg font-semibold leading-tight">{warning.event}</h2>
      </header>

      <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-sm">
        <Field label="Poziom">{warningLevelLabel(warning.level)}</Field>
        <Field label="Prawdopodob.">
          {warning.probability != null ? `${warning.probability}%` : "—"}
        </Field>
        <Field label="Od">{formatTimestamp(warning.valid_from)}</Field>
        <Field label="Do">{formatTimestamp(warning.valid_to)}</Field>
        <Field label="Publikacja">{formatTimestamp(warning.published_at)}</Field>
        {warning.office && <Field label="Biuro">{warning.office}</Field>}
        <Field label="Obszary">
          {warning.areas.length
            ? warning.areas.map((area) => area.label ?? area.code).join(", ")
            : "—"}
        </Field>
      </dl>

      {warning.content && <p className="text-sm">{warning.content}</p>}
      {warning.comment && <p className="text-xs text-muted-foreground">{warning.comment}</p>}

      <WarningGeometryNotice
        geometryStatus={geometry_status}
        resolvedAreas={warning.resolved_areas}
      />

      <MissingFields fields={warning.missing_fields} />
      {!warning.history_available && (
        <p className="text-xs text-muted-foreground">
          {warningQuery.data.alerting_disclaimer}
        </p>
      )}
      {warning.history_available && warning.history_id && (
        <WarningHistoryTimeline
          events={historyQuery.data?.history.events ?? []}
          versions={historyQuery.data?.history.versions ?? []}
          snapshots={historyQuery.data?.history.snapshots ?? []}
          historyStartedAt={warning.history_started_at ?? null}
          disclaimer={
            historyQuery.data?.alerting_disclaimer ??
            warningQuery.data.alerting_disclaimer
          }
          loading={historyQuery.isLoading}
          error={historyQuery.isError}
          expert={expert}
        />
      )}
      {expert && <RawSection raw={warning.raw} />}
      <SourceFooter source={warning.source} expert={expert} />
    </div>
  );
}

function WarningHistoryTimeline({
  events,
  versions,
  snapshots,
  historyStartedAt,
  disclaimer,
  loading,
  error,
  expert,
}: {
  events: WarningEvent[];
  versions: WarningHistoryVersion[];
  snapshots: WarningSnapshotMetadata[];
  historyStartedAt: string | null;
  disclaimer?: string;
  loading: boolean;
  error: boolean;
  expert: boolean;
}) {
  const byId = new Map(versions.map((version) => [version.version_id, version.warning]));
  if (loading) {
    return <Spinner label="Ładowanie osi zmian..." />;
  }
  if (error) {
    return (
      <StateNotice tone="error" title="Nie udało się pobrać osi zmian.">
        Bieżące ostrzeżenie pozostaje dostępne. {disclaimer}
      </StateNotice>
    );
  }
  return (
    <section className="space-y-3 border-t border-border pt-3">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <ListTree aria-hidden className="size-3.5" /> Oś zmian
      </h3>
      <p className="text-xs text-muted-foreground">
        Historia lokalna od {formatTimestamp(historyStartedAt)}. {disclaimer}
      </p>
      {events.length === 0 && (
        <StateNotice tone="info" title="Brak zmian po pierwszej obserwacji" />
      )}
      <ol className="relative ml-2 space-y-4 border-l border-border pl-4">
        {events.map((event) => {
          const before = event.from_version_id ? byId.get(event.from_version_id) : undefined;
          const after = event.to_version_id ? byId.get(event.to_version_id) : undefined;
          const visibleChangedFields = event.changed_fields.filter(
            (field) => expert || field !== "raw",
          );
          return (
            <li key={event.event_id} className="relative">
              <span
                className={cn(
                  "absolute -left-[21px] top-1 size-2.5 rounded-full border border-card",
                  event.confidence === "ambiguous" ? "bg-warning" : "bg-primary",
                )}
                aria-hidden
              />
              <p className="text-sm font-medium">
                {event.change_kinds.map(warningChangeKindLabel).join(" · ")}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatTimestamp(event.detected_at)} · {event.classification_basis}
                {event.confidence === "ambiguous" && " · niepotwierdzone przez źródło"}
                {event.snapshot?.completeness === "partial" && " · snapshot częściowy"}
              </p>
              {visibleChangedFields.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs">
                  {visibleChangedFields.map((field) => (
                    <li key={field}>
                      <span className="text-muted-foreground">{field}:</span>{" "}
                      {field === "raw"
                        ? "zmieniono — pełne wersje w metadanych zdarzenia"
                        : `${_warningFieldValue(before, field)} → ${_warningFieldValue(after, field)}`}
                    </li>
                  ))}
                </ul>
              )}
              {expert && (
                <details className="mt-1 text-xs">
                  <summary className="cursor-pointer text-primary">Metadane zdarzenia</summary>
                  <pre className="mt-1 max-h-48 overflow-auto rounded border border-border bg-background p-2 text-[10px]">
                    {JSON.stringify(event, null, 2)}
                  </pre>
                </details>
              )}
            </li>
          );
        })}
      </ol>
      {expert && (
        <details className="text-xs">
          <summary className="cursor-pointer text-primary">
            Surowe wersje i metadane snapshotów
          </summary>
          <pre className="mt-1 max-h-72 overflow-auto rounded border border-border bg-background p-2 text-[10px]">
            {JSON.stringify({ versions, snapshots }, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}

function _warningFieldValue(warning: WarningRecord | undefined, field: string): string {
  if (!warning) {
    return "—";
  }
  const value = warning[field as keyof WarningRecord];
  if (value === null || value === undefined) {
    return "—";
  }
  if (field === "valid_from" || field === "valid_to" || field === "published_at") {
    return formatTimestamp(String(value));
  }
  if (field === "level") {
    return warningLevelLabel(value as number);
  }
  if (Array.isArray(value)) {
    return value
      .map((item) =>
        typeof item === "object" && item && "code" in item
          ? String(item.code)
          : String(item),
      )
      .join(", ");
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function WarningHistoryDetails({ id, expert }: { id: string; expert: boolean }) {
  const historyQuery = useWarningHistoryQuery(id);
  if (historyQuery.isLoading) {
    return <Spinner label="Ładowanie historii ostrzeżenia..." />;
  }
  if (historyQuery.isError) {
    return apiErrorNotice(historyQuery.error);
  }
  if (!historyQuery.data) {
    return null;
  }
  const { history } = historyQuery.data;
  const current = history.current_version_id
    ? history.versions.find((version) => version.version_id === history.current_version_id)
    : undefined;
  if (history.current_version_id && !current) {
    return (
      <StateNotice tone="error" title="Historia ma niespójne dane">
        Wskazana bieżąca wersja nie występuje w zachowanej osi czasu.
      </StateNotice>
    );
  }
  if (!current) {
    return (
      <div className="space-y-4">
        <header>
          <p className="text-xs uppercase text-muted-foreground">Historia ostrzeżenia</p>
          <h2 className="text-lg font-semibold leading-tight">Konflikt danych źródłowych</h2>
        </header>
        <StateNotice tone="warning" title="Historia nie ma reprezentatywnej wersji">
          Źródło zwróciło różne rekordy o tej samej tożsamości. MeteoLens nie wybiera
          arbitralnie żadnego z nich.
        </StateNotice>
        <WarningHistoryTimeline
          events={history.events}
          versions={history.versions}
          snapshots={history.snapshots}
          historyStartedAt={history.history_started_at}
          disclaimer={historyQuery.data.alerting_disclaimer}
          loading={false}
          error={false}
          expert={expert}
        />
      </div>
    );
  }
  const warning = current.warning;
  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase text-muted-foreground">
          Historia ostrzeżenia {warning.warning_type}
        </p>
        <h2 className="text-lg font-semibold leading-tight">{warning.event}</h2>
        <p className="text-xs text-muted-foreground">
          Stan: {history.status} · tożsamość: {history.identity_status}
        </p>
      </header>
      <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-sm">
        <Field label="Poziom">{warningLevelLabel(warning.level)}</Field>
        <Field label="Od">{formatTimestamp(warning.valid_from)}</Field>
        <Field label="Do">{formatTimestamp(warning.valid_to)}</Field>
        <Field label="Publikacja">{formatTimestamp(warning.published_at)}</Field>
        {warning.office && <Field label="Biuro">{warning.office}</Field>}
        <Field label="Obszary">
          {warning.areas.map((area) => area.label ?? area.code).join(", ") || "—"}
        </Field>
      </dl>
      {history.identity_status === "ambiguous" && (
        <StateNotice tone="warning" title="Niejednoznaczna tożsamość">
          MeteoLens nie łączy tego rekordu heurystycznie z innymi ostrzeżeniami.
        </StateNotice>
      )}
      <WarningHistoryTimeline
        events={history.events}
        versions={history.versions}
        snapshots={history.snapshots}
        historyStartedAt={history.history_started_at}
        disclaimer={historyQuery.data.alerting_disclaimer}
        loading={false}
        error={false}
        expert={expert}
      />
      {expert && <RawSection raw={current.raw} />}
      <SourceFooter source={current.source} expert={expert} />
    </div>
  );
}

export function DetailsPanel() {
  const selection = useAppStore((state) => state.selection);
  const clearSelection = useAppStore((state) => state.clearSelection);
  const mode = useAppStore((state) => state.mode);
  const expert = mode === "expert";

  if (!selection) {
    return null;
  }

  return (
    <aside
      className={cn(
        "absolute z-20 overflow-y-auto border-border bg-card text-card-foreground shadow-xl",
        // Mobile: bottom sheet. Desktop: right side panel.
        "inset-x-0 bottom-0 max-h-[70vh] rounded-t-xl border-t p-4",
        "lg:inset-y-4 lg:left-auto lg:right-4 lg:max-h-none lg:w-[380px] lg:rounded-lg lg:border",
      )}
      aria-label="Panel szczegółów"
      role="dialog"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-muted-foreground">
          Szczegóły {selection.kind === "station" ? "stacji" : "ostrzeżenia"}
        </span>
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground"
          aria-label="Zamknij panel szczegółów"
          onClick={clearSelection}
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>

      {selection.kind === "station" ? (
        <StationDetails id={selection.id} expert={expert} />
      ) : selection.kind === "warning-history" ? (
        <WarningHistoryDetails id={selection.id} expert={expert} />
      ) : (
        <WarningDetails id={selection.id} expert={expert} />
      )}
    </aside>
  );
}
