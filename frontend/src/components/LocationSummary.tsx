import { AlertTriangle, Crosshair, MapPin, X } from "lucide-react";

import { useLocationSummaryQuery } from "../api/queries";
import { formatTimestamp, warningLevelLabel, WARNING_LEVEL_COLOR } from "../lib/format";
import { flyTo } from "../lib/mapBus";
import { useAppStore } from "../store/appStore";
import { Spinner, StateNotice } from "./primitives";

export function LocationSummary() {
  const userLocation = useAppStore((state) => state.userLocation);
  const setUserLocation = useAppStore((state) => state.setUserLocation);
  const selection = useAppStore((state) => state.selection);
  const select = useAppStore((state) => state.select);
  const summaryQuery = useLocationSummaryQuery(userLocation);

  if (!userLocation) {
    return null;
  }

  const data = summaryQuery.data;
  const stations = data?.nearest_stations ?? [];
  const warnings = data?.warnings ?? [];

  return (
    <section className="rounded-md border border-primary/40 bg-primary/5 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
          <Crosshair aria-hidden className="size-3.5" /> Moja lokalizacja
        </h3>
        <button
          type="button"
          className="inline-flex size-6 items-center justify-center rounded text-muted-foreground hover:text-foreground"
          aria-label="Wyczyść lokalizację"
          onClick={() => setUserLocation(null)}
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>

      <p className="mb-2 text-[11px] text-muted-foreground">
        {userLocation.lat.toFixed(4)}, {userLocation.lon.toFixed(4)}
        {data ? ` · promień ${data.radius_km} km` : ""}
      </p>

      {summaryQuery.isLoading && <Spinner label="Szukanie najbliższych stacji..." />}
      {summaryQuery.isError && <StateNotice tone="error" title="Nie udało się pobrać danych lokalizacji." />}

      {data && (
        <>
          <h4 className="mb-1 text-[11px] font-semibold uppercase text-muted-foreground">
            Najbliższe stacje ({stations.length})
          </h4>
          {stations.length === 0 ? (
            <p className="mb-2 text-xs text-muted-foreground">
              {data.empty_state?.message ?? "Brak stacji w zasięgu."}
            </p>
          ) : (
            <ul className="mb-2 space-y-1">
              {stations.map((station) => (
                <li key={station.id}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-sm hover:bg-muted"
                    onClick={() => {
                      select({ kind: "station", id: station.id });
                      if (station.lon != null && station.lat != null) {
                        flyTo({ lng: station.lon, lat: station.lat, zoom: 9 });
                      }
                    }}
                  >
                    <MapPin aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate">{station.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {station.distance_km.toFixed(1)} km
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h4 className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase text-muted-foreground">
            <AlertTriangle aria-hidden className="size-3" /> Aktywne ostrzeżenia ({warnings.length})
          </h4>
          {warnings.length === 0 ? (
            <p className="text-xs text-muted-foreground">Brak aktywnych ostrzeżeń.</p>
          ) : (
            <ul className="space-y-1">
              {warnings.map((warning) => (
                <li key={warning.id}>
                  <button
                    type="button"
                    className={`flex w-full items-start gap-2 rounded px-1 py-1 text-left text-sm hover:bg-muted ${
                      selection?.kind === "warning" && selection.id === warning.id ? "bg-muted" : ""
                    }`}
                    onClick={() => select({ kind: "warning", id: warning.id })}
                  >
                    <span
                      className="mt-1 size-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: WARNING_LEVEL_COLOR[warning.level ?? 0] ?? "#9ca3af" }}
                      aria-hidden
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{warning.event}</span>
                      <span className="block text-[11px] text-muted-foreground">
                        Poziom {warningLevelLabel(warning.level)} · do {formatTimestamp(warning.valid_to)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {data.notes.length > 0 && (
            <p className="mt-2 text-[11px] text-muted-foreground">{data.notes[0]}</p>
          )}
        </>
      )}
    </section>
  );
}
