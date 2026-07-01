import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";

import type { StationFeature } from "../api/client";
import { useMapLayersQuery } from "../api/queries";
import { CAPTURE_PNG_EVENT, FLY_TO_EVENT, type FlyToDetail } from "../lib/mapBus";
import { LAYERS, STATION_LAYERS, STATION_TYPE_COLOR, WARNING_LAYERS } from "../lib/layers";
import { decodePermalink } from "../lib/permalink";
import { useAppStore } from "../store/appStore";

const STATIONS_SOURCE = "stations";
const STATIONS_LAYER = "stations-circles";
const SELECTED_LAYER = "stations-selected";
const WARNINGS_SOURCE = "warnings";
const WARNINGS_FILL_LAYER = "warnings-fill";
const WARNINGS_OUTLINE_LAYER = "warnings-outline";

function collection(features: StationFeature[]): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features } as unknown as GeoJSON.FeatureCollection;
}

function selectedFilter(id: string): maplibregl.FilterSpecification {
  return ["==", ["get", "id"], id];
}

const PNG_ATTRIBUTION =
  "Źródło danych: IMGW-PIB. Dane przetworzone przez MeteoLens. © OpenStreetMap";

function downloadCanvasPng(map: maplibregl.Map) {
  try {
    const mapCanvas = map.getCanvas();
    // The MapLibre/MeteoLens attribution is DOM outside the WebGL canvas, so draw
    // it onto a composite before export — every export must carry attribution.
    const footerHeight = 28;
    const out = document.createElement("canvas");
    out.width = mapCanvas.width;
    out.height = mapCanvas.height + footerHeight;
    const ctx = out.getContext("2d");
    if (!ctx) {
      throw new Error("2d context unavailable");
    }
    ctx.drawImage(mapCanvas, 0, 0);
    ctx.fillStyle = "#0b1f2a";
    ctx.fillRect(0, mapCanvas.height, out.width, footerHeight);
    ctx.fillStyle = "#ffffff";
    ctx.font = "13px sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(PNG_ATTRIBUTION, 10, mapCanvas.height + footerHeight / 2);

    const link = document.createElement("a");
    link.href = out.toDataURL("image/png");
    link.download = "meteolens-mapa.png";
    link.click();
  } catch {
    window.alert("Eksport PNG nie powiódł się w tej przeglądarce.");
  }
}

export function MapShell() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);

  const activeLayers = useAppStore((state) => state.activeLayers);
  const selection = useAppStore((state) => state.selection);

  const activeMapLayerKeys = LAYERS.filter((layer) => activeLayers[layer.key]).map((layer) => layer.key);
  const mapQuery = useMapLayersQuery(activeMapLayerKeys);

  const stationFeatures = useMemo(
    () =>
      (mapQuery.data?.layers ?? [])
        .filter((layer) => STATION_LAYERS.some((stationLayer) => stationLayer.key === layer.key))
        .flatMap((layer) => layer.geojson.features),
    [mapQuery.data],
  );
  const warningFeatures = useMemo(
    () =>
      (mapQuery.data?.layers ?? [])
        .filter((layer) => WARNING_LAYERS.some((warningLayer) => warningLayer.key === layer.key))
        .flatMap((layer) => layer.geojson.features),
    [mapQuery.data],
  );
  const featuresRef = useRef(stationFeatures);
  const warningFeaturesRef = useRef(warningFeatures);
  const selectionRef = useRef(selection);

  // --- Map lifecycle (mount once) -----------------------------------------
  useEffect(() => {
    if (!containerRef.current) {
      return undefined;
    }
    const { mapView, select, setMapView } = useAppStore.getState();
    // Child effects run before the parent's usePermalink hydration, so read the
    // permalink directly here to honour a shared center/zoom on first load.
    const initialView = decodePermalink(window.location.search).mapView ?? mapView;
    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [initialView.lng, initialView.lat],
      zoom: initialView.zoom,
      minZoom: 4,
      maxZoom: 14,
      attributionControl: false,
      preserveDrawingBuffer: true, // required for PNG canvas export
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    map.on("load", () => {
      map.addSource(STATIONS_SOURCE, { type: "geojson", data: collection(featuresRef.current) });
      map.addLayer({
        id: STATIONS_LAYER,
        type: "circle",
        source: STATIONS_SOURCE,
        paint: {
          "circle-radius": 5,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-color": [
            "match",
            ["get", "station_type"],
            "synop",
            STATION_TYPE_COLOR.synop,
            "hydro",
            STATION_TYPE_COLOR.hydro,
            "meteo",
            STATION_TYPE_COLOR.meteo,
            "#6b7280",
          ],
        },
      });
      map.addLayer({
        id: SELECTED_LAYER,
        type: "circle",
        source: STATIONS_SOURCE,
        filter: selectedFilter(
          selectionRef.current?.kind === "station" ? selectionRef.current.id : "__none__",
        ),
        paint: {
          "circle-radius": 9,
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-width": 3,
          "circle-stroke-color": "#0e7490",
        },
      });

      map.on("click", STATIONS_LAYER, (event) => {
        const id = event.features?.[0]?.properties?.id;
        if (typeof id === "string") {
          select({ kind: "station", id });
        }
      });
      map.on("mouseenter", STATIONS_LAYER, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", STATIONS_LAYER, () => {
        map.getCanvas().style.cursor = "";
      });

      map.addSource(WARNINGS_SOURCE, {
        type: "geojson",
        data: { type: "FeatureCollection", features: warningFeaturesRef.current },
      });
      map.addLayer({
        id: WARNINGS_FILL_LAYER,
        type: "fill",
        source: WARNINGS_SOURCE,
        paint: {
          "fill-color": [
            "match",
            ["get", "level"],
            1,
            "rgba(250, 204, 21, 0.25)",
            2,
            "rgba(249, 115, 22, 0.28)",
            3,
            "rgba(220, 38, 38, 0.32)",
            "rgba(124, 58, 237, 0.25)",
          ],
        },
      });
      map.addLayer({
        id: WARNINGS_OUTLINE_LAYER,
        type: "line",
        source: WARNINGS_SOURCE,
        paint: {
          "line-color": "#7c3aed",
          "line-width": 1.5,
        },
      });

      map.on("click", WARNINGS_FILL_LAYER, (event) => {
        const warningId = event.features?.[0]?.properties?.warning_id;
        if (typeof warningId === "string") {
          select({ kind: "warning", id: warningId });
        }
      });
      map.on("mouseenter", WARNINGS_FILL_LAYER, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", WARNINGS_FILL_LAYER, () => {
        map.getCanvas().style.cursor = "";
      });

      loadedRef.current = true;
    });

    map.on("moveend", () => {
      const center = map.getCenter();
      setMapView({ lng: center.lng, lat: center.lat, zoom: map.getZoom() });
    });

    const onFlyTo = (event: Event) => {
      const detail = (event as CustomEvent<FlyToDetail>).detail;
      map.flyTo({ center: [detail.lng, detail.lat], zoom: detail.zoom ?? map.getZoom() });
    };
    const onCapture = () => downloadCanvasPng(map);
    window.addEventListener(FLY_TO_EVENT, onFlyTo);
    window.addEventListener(CAPTURE_PNG_EVENT, onCapture);

    return () => {
      window.removeEventListener(FLY_TO_EVENT, onFlyTo);
      window.removeEventListener(CAPTURE_PNG_EVENT, onCapture);
      loadedRef.current = false;
      mapRef.current = null;
      map.remove();
    };
  }, []);

  // --- Push station features into the map source --------------------------
  useEffect(() => {
    featuresRef.current = stationFeatures;
    const map = mapRef.current;
    if (!map || !loadedRef.current) {
      return;
    }
    const source = map.getSource(STATIONS_SOURCE) as maplibregl.GeoJSONSource | undefined;
    source?.setData(collection(stationFeatures));
  }, [stationFeatures]);

  useEffect(() => {
    warningFeaturesRef.current = warningFeatures;
    const map = mapRef.current;
    if (!map || !loadedRef.current) {
      return;
    }
    const source = map.getSource(WARNINGS_SOURCE) as maplibregl.GeoJSONSource | undefined;
    source?.setData({ type: "FeatureCollection", features: warningFeatures });
    const visibility = warningFeatures.length > 0 ? "visible" : "none";
    if (map.getLayer(WARNINGS_FILL_LAYER)) {
      map.setLayoutProperty(WARNINGS_FILL_LAYER, "visibility", visibility);
      map.setLayoutProperty(WARNINGS_OUTLINE_LAYER, "visibility", visibility);
    }
  }, [warningFeatures]);

  // --- Reflect selection as a highlight ring ------------------------------
  useEffect(() => {
    selectionRef.current = selection;
    const map = mapRef.current;
    if (!map || !loadedRef.current || !map.getLayer(SELECTED_LAYER)) {
      return;
    }
    const id = selection?.kind === "station" ? selection.id : "__none__";
    map.setFilter(SELECTED_LAYER, selectedFilter(id));
  }, [selection]);

  return (
    <div className="h-full w-full bg-muted">
      <div ref={containerRef} className="h-full w-full" aria-label="Mapa MeteoLens" />
    </div>
  );
}
