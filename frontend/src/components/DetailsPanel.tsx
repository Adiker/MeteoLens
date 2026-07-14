import { BarChart3, Download, ExternalLink, ListTree, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { ApiError, stationCsvUrl, stationJsonUrl, type SourceMetadata } from "../api/client";
import {
  useObservationsQuery,
  useStationQuery,
  useWarningQuery,
} from "../api/queries";
import {
  formatDelay,
  formatTimestamp,
  formatValue,
  metricLabel,
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

function StationDetails({ id, expert }: { id: string; expert: boolean }) {
  const stationQuery = useStationQuery(id);
  const observationsQuery = useObservationsQuery(id);
  const [tab, setTab] = useState<"data" | "chart">("data");

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
        <StationChart
          observations={chartObservations}
          seriesKind={observationsQuery.data?.series_kind ?? "snapshot"}
        />
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href={stationCsvUrl(station.id)}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:border-primary"
        >
          <Download aria-hidden className="size-3.5" /> CSV
        </a>
        <a
          href={stationJsonUrl(station.id)}
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

function WarningDetails({ id, expert }: { id: string; expert: boolean }) {
  const warningQuery = useWarningQuery(id);

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

      {geometry_status === "resolved" ? (
        <StateNotice tone="info" title="Geometria obszaru dostępna">
          Obszar ostrzeżenia został dopasowany do zatwierdzonych granic administracyjnych.
        </StateNotice>
      ) : geometry_status === "partial" ? (
        <StateNotice tone="warning" title="Częściowa geometria obszaru">
          Część obszarów ostrzeżenia została dopasowana do zatwierdzonej geometrii, a część
          pozostaje nierozwiązana ({geometry_status}).
        </StateNotice>
      ) : (
        <StateNotice tone="info" title="Brak geometrii obszaru">
          Dokładne dopasowanie przestrzenne ostrzeżeń będzie możliwe po dodaniu zbiorów
          TERYT/zlewni ({geometry_status}).
        </StateNotice>
      )}

      <MissingFields fields={warning.missing_fields} />
      {expert && <RawSection raw={warning.raw} />}
      <SourceFooter source={warning.source} expert={expert} />
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
      ) : (
        <WarningDetails id={selection.id} expert={expert} />
      )}
    </aside>
  );
}
