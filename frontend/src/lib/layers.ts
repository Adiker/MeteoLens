export type LayerKey =
  | "synop_stations"
  | "hydro_stations"
  | "meteo_stations"
  | "warnings_meteo"
  | "warnings_hydro";

export type StationType = "synop" | "hydro" | "meteo";
export type WarningType = "meteo" | "hydro";

export interface LayerConfig {
  key: LayerKey;
  title: string;
  kind: "station" | "warning";
  /** Station type for station layers. */
  stationType?: StationType;
  /** Warning type for warning layers. */
  warningType?: WarningType;
  /** Concrete colour used both for map markers (WebGL, CSS vars unavailable) and legend swatches. */
  color: string;
  /** Number key (1-5) that toggles the layer via keyboard. */
  hotkey: string;
}

/**
 * Layer registry. Mirrors the backend `MAP_LAYER_DEFINITIONS` keys so the
 * frontend can drive `/api/v1/map/layers` and `/api/v1/warnings` directly.
 */
export const LAYERS: LayerConfig[] = [
  {
    key: "synop_stations",
    title: "Stacje synoptyczne",
    kind: "station",
    stationType: "synop",
    color: "#d97706",
    hotkey: "1",
  },
  {
    key: "hydro_stations",
    title: "Stacje hydrologiczne",
    kind: "station",
    stationType: "hydro",
    color: "#2563eb",
    hotkey: "2",
  },
  {
    key: "meteo_stations",
    title: "Stacje meteorologiczne",
    kind: "station",
    stationType: "meteo",
    color: "#059669",
    hotkey: "3",
  },
  {
    key: "warnings_meteo",
    title: "Ostrzeżenia meteorologiczne",
    kind: "warning",
    warningType: "meteo",
    color: "#dc2626",
    hotkey: "4",
  },
  {
    key: "warnings_hydro",
    title: "Ostrzeżenia hydrologiczne",
    kind: "warning",
    warningType: "hydro",
    color: "#7c3aed",
    hotkey: "5",
  },
];

export const LAYER_BY_KEY: Record<LayerKey, LayerConfig> = Object.fromEntries(
  LAYERS.map((layer) => [layer.key, layer]),
) as Record<LayerKey, LayerConfig>;

export const STATION_LAYERS = LAYERS.filter((layer) => layer.kind === "station");
export const WARNING_LAYERS = LAYERS.filter((layer) => layer.kind === "warning");

export const STATION_TYPE_COLOR: Record<StationType, string> = {
  synop: LAYER_BY_KEY.synop_stations.color,
  hydro: LAYER_BY_KEY.hydro_stations.color,
  meteo: LAYER_BY_KEY.meteo_stations.color,
};

export const DEFAULT_ACTIVE_LAYERS: LayerKey[] = [
  "synop_stations",
  "hydro_stations",
  "meteo_stations",
  "warnings_meteo",
  "warnings_hydro",
];
