import { Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  mapGeoJsonUrl,
  mapStateJsonUrl,
  stationCsvUrl,
  stationJsonUrl,
  warningsGeoJsonUrl,
} from "../api/client";
import { WARNING_LAYERS, type WarningType } from "../lib/layers";
import { captureMapPng } from "../lib/mapBus";
import { activeLayerKeys, useAppStore } from "../store/appStore";
import { iconButtonClass } from "./primitives";

export function ExportMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const selection = useAppStore((state) => state.selection);
  // Select the stable object, then derive — a selector returning a fresh array
  // each call would break Zustand's snapshot caching.
  const activeLayers = activeLayerKeys(useAppStore((state) => state.activeLayers));
  const mapView = useAppStore((state) => state.mapView);
  const filters = useAppStore((state) => state.filters);
  const mode = useAppStore((state) => state.mode);
  const theme = useAppStore((state) => state.theme);
  const timeline = useAppStore((state) => state.timeline);
  const stationId = selection?.kind === "station" ? selection.id : null;
  const activeWarningTypes = WARNING_LAYERS.filter((layer) =>
    activeLayers.includes(layer.key),
  ).map((layer) => layer.warningType)
    .filter((value): value is WarningType => Boolean(value));
  const warningTypeFilter =
    activeWarningTypes.length === 1 ? activeWarningTypes[0] : undefined;
  const warningExportUrl = warningsGeoJsonUrl({
    type: warningTypeFilter,
    level: filters.warningLevel,
    phenomenon: filters.phenomenon,
    province: filters.province,
    county: filters.county,
    basin: filters.basin,
  });
  const stateExportUrl = mapStateJsonUrl({
    layers: activeLayers,
    mapView,
    mode,
    theme,
    selection,
    filters,
    timelineLayer: timeline.activeLayerKey,
    timelineFrameIndex: timeline.frameIndex,
  });

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const itemClass =
    "block w-full px-3 py-2 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className={iconButtonClass}
        aria-label="Eksport danych"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Download aria-hidden className="size-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-60 overflow-hidden rounded-md border border-border bg-card text-card-foreground shadow-lg"
        >
          <p className="px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">Eksport</p>
          {stationId ? (
            <>
              <a className={itemClass} role="menuitem" href={stationCsvUrl(stationId)} download>
                Stacja — CSV
              </a>
              <a className={itemClass} role="menuitem" href={stationJsonUrl(stationId)} download>
                Stacja — JSON
              </a>
            </>
          ) : (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              Wybierz stację, aby wyeksportować jej dane.
            </p>
          )}
          <div className="border-t border-border" />
          {activeLayers.length > 0 ? (
            <>
              <a className={itemClass} role="menuitem" href={mapGeoJsonUrl(activeLayers)} download>
                Widoczna mapa — GeoJSON
              </a>
              <a className={itemClass} role="menuitem" href={stateExportUrl} download>
                Stan mapy — JSON
              </a>
            </>
          ) : (
            <>
              {/* An empty `layers` param means "all layers" to the backend, so
                  we disable these exports rather than silently exporting hidden data. */}
              <button type="button" role="menuitem" className={itemClass} disabled>
                Widoczna mapa — GeoJSON
              </button>
              <button type="button" role="menuitem" className={itemClass} disabled>
                Stan mapy — JSON
              </button>
            </>
          )}
          {activeWarningTypes.length > 0 ? (
            <a className={itemClass} role="menuitem" href={warningExportUrl} download>
              Ostrzeżenia — GeoJSON
            </a>
          ) : (
            <button type="button" role="menuitem" className={itemClass} disabled>
              Ostrzeżenia — GeoJSON
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              captureMapPng();
              setOpen(false);
            }}
          >
            Bieżąca mapa — PNG
          </button>
          <p className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
            Każdy eksport zawiera atrybucję IMGW-PIB i notę o przetworzeniu danych.
          </p>
        </div>
      )}
    </div>
  );
}
